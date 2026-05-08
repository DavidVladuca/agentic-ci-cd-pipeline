from pathlib import Path
import time

from agent.docker_runner import DockerRunner
from agent.error_extractor import ErrorExtractor
from agent.file_rewriter import FileRewriter
from agent.llm_client import LLMClient
from agent.logger_config import setup_logger
from agent.project_sandbox import ProjectSandbox
from agent.repair_cli import parse_repair_cli_args
from agent.repair_task import RepairTask
from agent.run_metrics import RunMetrics
from agent.source_context import SourceContextBuilder


# This is the V2 repair-task controller
# RepairTask → ProjectSandbox → DockerRunner → ErrorExtractor → SourceContextBuilder → LLMClient → FileRewriter → RunMetrics
# At this stage : it loads a broken project, injects hidden tests, and tries to repair the code with an LLM
def main(argv=None):
    args = parse_repair_cli_args(argv)

    # __file__ = path of current file (repair_controller.py), resolve() = absolute path
    project_root = Path(__file__).resolve().parents[1]

    # if path is wrong, kill it imediatly
    if not (project_root / "pom.xml").exists():
        raise RuntimeError(f"Could not find pom.xml at project root: {project_root}")

    # setup logger
    logger, log_file = setup_logger(project_root)

    logger.info("[REPAIR] Starting Phase 7 LLM repair loop")
    logger.info("[REPAIR] Project root: %s", project_root)
    logger.info("[REPAIR] Task dir: %s", args.task_dir)
    logger.info("[REPAIR] Model: %s", args.model)
    logger.info("[REPAIR] Max attempts: %s", args.max_attempts)
    logger.info("[REPAIR] Docker image: %s", args.docker_image)
    logger.info("[REPAIR] Docker/Maven timeout: %s seconds", args.timeout)
    logger.info("[REPAIR] Log file: %s", log_file)

    repair_task = RepairTask.load(args.task_dir)

    metrics = RunMetrics(
        task_prompt=repair_task.prompt,
        max_attempts=args.max_attempts
    )

    logger.info("[REPAIR] Loaded repair task: %s", repair_task.name)

    sandbox = ProjectSandbox(project_root)
    sandbox_root = sandbox.prepare_task(repair_task)

    logger.info("[REPAIR] Sandbox root: %s", sandbox_root)
    logger.info("[REPAIR] Hidden tests injected from: %s", repair_task.hidden_tests_dir)

    runner = DockerRunner(
        sandbox_root=sandbox_root,
        image_name=args.docker_image,
        timeout_seconds=args.timeout
    )

    llm = LLMClient(model=args.model)
    source_context_builder = SourceContextBuilder()
    file_rewriter = FileRewriter(sandbox_root)

    logger.info("[REPAIR] Running baseline Maven/JUnit tests inside Docker...")
    baseline_result = runner.run_tests()

    baseline_error_summary = None
    baseline_error_type = None

    if baseline_result.success:
        logger.error("[REPAIR] Baseline unexpectedly passed.")
        logger.error("[REPAIR] This repair task is invalid because hidden tests did not expose a failure.")

        metrics.add_attempt(
            attempt=0,
            status="BASELINE_UNEXPECTED_SUCCESS",
            llm_seconds=0.0,
            workspace_seconds=0.0,
            maven_seconds=baseline_result.duration_seconds,
            attempt_seconds=baseline_result.duration_seconds,
            exit_code=baseline_result.exit_code,
            error_type=None,
            error_summary=None
        )

        finish_run(
            metrics=metrics,
            project_root=project_root,
            log_file=log_file,
            logger=logger,
            final_status="BASELINE_UNEXPECTED_SUCCESS"
        )
        return

    baseline_error_summary = ErrorExtractor.extract_errors(
        raw_output=baseline_result.combined_output,
        timed_out=baseline_result.timed_out
    )

    baseline_error_type = ErrorExtractor.classify_error(
        error_summary=baseline_error_summary,
        timed_out=baseline_result.timed_out
    )

    logger.info("[REPAIR] Baseline failure detected.")
    logger.info("[REPAIR] Baseline error type: %s", baseline_error_type)
    logger.error("[REPAIR] Baseline failure:")
    logger.error(baseline_error_summary)

    metrics.add_attempt(
        attempt=0,
        status="BASELINE_FAILURE_DETECTED",
        llm_seconds=0.0,
        workspace_seconds=0.0,
        maven_seconds=baseline_result.duration_seconds,
        attempt_seconds=baseline_result.duration_seconds,
        exit_code=baseline_result.exit_code,
        error_type=baseline_error_type,
        error_summary=baseline_error_summary
    )

    last_error_summary = baseline_error_summary
    seen_errors = set()  # to see if we are stuck in a loop with the same repair failure

    for attempt in range(1, args.max_attempts + 1):
        attempt_start = time.perf_counter()

        llm_seconds = 0.0
        workspace_seconds = 0.0
        maven_seconds = 0.0

        logger.info("")
        logger.info("[REPAIR] Repair attempt %s/%s", attempt, args.max_attempts)

        try:
            source_context = source_context_builder.build(sandbox_root)
            logger.info("[REPAIR] Source context length: %s characters", len(source_context))

            logger.info("[REPAIR] Calling LLM for repair file edits...")
            llm_start = time.perf_counter()

            repair_json = llm.generate_repair_files(
                task_prompt=repair_task.prompt,
                source_context=source_context,
                previous_error=last_error_summary
            )

            llm_seconds = time.perf_counter() - llm_start
            logger.info("[TIMING] LLM repair generation took %.3f seconds", llm_seconds)

            logger.info("[REPAIR] Applying LLM file edits...")
            workspace_start = time.perf_counter()

            written_paths = file_rewriter.apply_files(repair_json["files"])

            workspace_seconds = time.perf_counter() - workspace_start
            logger.info("[TIMING] File rewrite took %.3f seconds", workspace_seconds)
            logger.info("[REPAIR] Written files: %s", ", ".join(written_paths))

        # this is for catching errors before Docker/Maven runs!!!
        except RuntimeError as e:
            llm_seconds = time.perf_counter() - attempt_start

            error_summary = f"LLM generation failed before Docker/Maven could run:\n{e}"
            error_type = ErrorExtractor.classify_error(error_summary)
            normalized_error = ErrorExtractor.fingerprint_error(error_summary, error_type)

            logger.error("[REPAIR] LLM/WRITE FAILURE")
            logger.error(error_summary)
            logger.info("[REPAIR] Error type: %s", error_type)

            attempt_seconds = time.perf_counter() - attempt_start

            # got same error again, we are stuck
            if normalized_error in seen_errors:
                logger.error("[REPAIR] Repeated LLM/write failure detected. Stopping.")

                metrics.add_attempt(
                    attempt=attempt,
                    status="REPEATED_LLM_FAILURE",
                    llm_seconds=llm_seconds,
                    workspace_seconds=workspace_seconds,
                    maven_seconds=maven_seconds,
                    attempt_seconds=attempt_seconds,
                    exit_code=None,
                    error_type=error_type,
                    error_summary=error_summary
                )

                finish_run(
                    metrics=metrics,
                    project_root=project_root,
                    log_file=log_file,
                    logger=logger,
                    final_status="FAILED_REPEATED_LLM_FAILURE"
                )
                return

            seen_errors.add(normalized_error)
            last_error_summary = error_summary

            metrics.add_attempt(
                attempt=attempt,
                status="LLM_FAILURE",
                llm_seconds=llm_seconds,
                workspace_seconds=workspace_seconds,
                maven_seconds=maven_seconds,
                attempt_seconds=attempt_seconds,
                exit_code=None,
                error_type=error_type,
                error_summary=error_summary
            )

            continue

        logger.info("[REPAIR] Running Maven/JUnit tests inside Docker after repair...")
        result = runner.run_tests()

        maven_seconds = result.duration_seconds
        logger.info("[TIMING] Docker/Maven run took %.3f seconds", maven_seconds)
        logger.info("[REPAIR] Docker/Maven exit code: %s", result.exit_code)

        attempt_seconds = time.perf_counter() - attempt_start

        if result.success:
            logger.info("[REPAIR] REPAIR SUCCESS")
            logger.info("[REPAIR] Passed on repair attempt %s/%s", attempt, args.max_attempts)
            logger.info("[TIMING] Attempt took %.3f seconds", attempt_seconds)

            metrics.add_attempt(
                attempt=attempt,
                status="REPAIR_SUCCESS",
                llm_seconds=llm_seconds,
                workspace_seconds=workspace_seconds,
                maven_seconds=maven_seconds,
                attempt_seconds=attempt_seconds,
                exit_code=result.exit_code,
                error_type=None,
                error_summary=None
            )

            finish_run(
                metrics=metrics,
                project_root=project_root,
                log_file=log_file,
                logger=logger,
                final_status="REPAIR_SUCCESS"
            )
            return

        error_summary = ErrorExtractor.extract_errors(
            raw_output=result.combined_output,
            timed_out=result.timed_out
        )

        error_type = ErrorExtractor.classify_error(
            error_summary=error_summary,
            timed_out=result.timed_out
        )

        logger.error("[REPAIR] Repair attempt failed.")
        logger.error("[REPAIR] Extracted Docker/Maven failure:")
        logger.error(error_summary)
        logger.info("[REPAIR] Error type: %s", error_type)
        logger.info("[TIMING] Attempt took %.3f seconds", attempt_seconds)

        normalized_error = ErrorExtractor.fingerprint_error(error_summary, error_type)

        # got same error again, we are stuck
        if normalized_error in seen_errors:
            logger.error("[REPAIR] Repeated Docker/Maven error detected. Stopping.")

            metrics.add_attempt(
                attempt=attempt,
                status="REPEATED_MAVEN_ERROR",
                llm_seconds=llm_seconds,
                workspace_seconds=workspace_seconds,
                maven_seconds=maven_seconds,
                attempt_seconds=attempt_seconds,
                exit_code=result.exit_code,
                error_type=error_type,
                error_summary=error_summary
            )

            finish_run(
                metrics=metrics,
                project_root=project_root,
                log_file=log_file,
                logger=logger,
                final_status="FAILED_REPEATED_MAVEN_ERROR"
            )
            return

        seen_errors.add(normalized_error)
        last_error_summary = error_summary

        metrics.add_attempt(
            attempt=attempt,
            status="REPAIR_FAILURE",
            llm_seconds=llm_seconds,
            workspace_seconds=workspace_seconds,
            maven_seconds=maven_seconds,
            attempt_seconds=attempt_seconds,
            exit_code=result.exit_code,
            error_type=error_type,
            error_summary=error_summary
        )

    logger.error("")
    logger.error("[REPAIR] FAILED after %s repair attempts.", args.max_attempts)

    finish_run(
        metrics=metrics,
        project_root=project_root,
        log_file=log_file,
        logger=logger,
        final_status="FAILED_MAX_ATTEMPTS"
    )


# helper to finish the run (write summary + log final info)
def finish_run(metrics, project_root, log_file, logger, final_status):
    metrics.finish(final_status)
    summary_file = metrics.write_summary(project_root, log_file)

    logger.info("[REPAIR] Final status: %s", final_status)
    logger.info("[TIMING] Total run took %.3f seconds", metrics.total_seconds)
    logger.info("[REPAIR] Run summary written to: %s", summary_file)


if __name__ == "__main__":
    main()