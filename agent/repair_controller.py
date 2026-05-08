from pathlib import Path
import time

from agent.docker_runner import DockerRunner
from agent.error_extractor import ErrorExtractor
from agent.logger_config import setup_logger
from agent.project_sandbox import ProjectSandbox
from agent.repair_cli import parse_repair_cli_args
from agent.repair_task import RepairTask
from agent.run_metrics import RunMetrics


# This is the V2 repair-task controller
# RepairTask → ProjectSandbox → DockerRunner → ErrorExtractor → Logger → RunMetrics
# At this stage : it loads a broken project, injects hidden tests, and verifies the baseline failure
def main(argv=None):
    args = parse_repair_cli_args(argv)

    # __file__ = path of current file (repair_controller.py), resolve() = absolute path
    project_root = Path(__file__).resolve().parents[1]

    # if path is wrong, kill it imediatly
    if not (project_root / "pom.xml").exists():
        raise RuntimeError(f"Could not find pom.xml at project root: {project_root}")

    # setup logger
    logger, log_file = setup_logger(project_root)

    logger.info("[REPAIR] Starting Phase 6 repair-task baseline run")
    logger.info("[REPAIR] Project root: %s", project_root)
    logger.info("[REPAIR] Task dir: %s", args.task_dir)
    logger.info("[REPAIR] Docker image: %s", args.docker_image)
    logger.info("[REPAIR] Docker/Maven timeout: %s seconds", args.timeout)
    logger.info("[REPAIR] Log file: %s", log_file)

    repair_task = RepairTask.load(args.task_dir)

    metrics = RunMetrics(
        task_prompt=repair_task.prompt,
        max_attempts=1
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

    attempt_start = time.perf_counter()

    logger.info("[REPAIR] Running baseline Maven/JUnit tests inside Docker...")
    result = runner.run_tests()

    attempt_seconds = time.perf_counter() - attempt_start

    logger.info("[TIMING] Docker/Maven run took %.3f seconds", result.duration_seconds)
    logger.info("[REPAIR] Docker/Maven exit code: %s", result.exit_code)

    # hidden tests pass in broken state -> invalid repair task
    if result.success:
        logger.error("[REPAIR] Baseline unexpectedly passed.")
        logger.error("[REPAIR] This repair task is invalid because hidden tests did not expose a failure.")

        metrics.add_attempt(
            attempt=1,
            status="BASELINE_UNEXPECTED_SUCCESS",
            llm_seconds=0.0,
            workspace_seconds=0.0,
            maven_seconds=result.duration_seconds,
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
            final_status="BASELINE_UNEXPECTED_SUCCESS"
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

    logger.info("[REPAIR] Baseline failure detected.")
    logger.info("[REPAIR] Error type: %s", error_type)
    logger.error("[REPAIR] Extracted failure:")
    logger.error(error_summary)

    metrics.add_attempt(
        attempt=1,
        status="BASELINE_FAILURE_DETECTED",
        llm_seconds=0.0,
        workspace_seconds=0.0,
        maven_seconds=result.duration_seconds,
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
        final_status="BASELINE_FAILURE_DETECTED"
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