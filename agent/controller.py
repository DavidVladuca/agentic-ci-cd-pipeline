from pathlib import Path
import time

from agent.llm_client import LLMClient
from agent.workspace import WorkspaceManager
from agent.docker_runner import DockerRunner
from agent.error_extractor import ErrorExtractor
from agent.logger_config import setup_logger
from agent.run_metrics import RunMetrics
from agent.sandbox_manager import SandboxManager

# This is the controller
# LLMClient → SandboxManager → WorkspaceManager → DockerRunner → ErrorExtractor → Logger → RunMetrics
# At this stage : it runs a retry feedback loop with logging, metrics and Docker sandboxing
def main():
    # __file__ = path of current file (controller.py),  resolve() = absolute path
    project_root = Path(__file__).resolve().parents[1]

    # if path is wrong, kill it imediatly
    if not (project_root / "pom.xml").exists():
        raise RuntimeError(f"Could not find pom.xml at project root: {project_root}")

    # setup logger 
    logger, log_file = setup_logger(project_root)

    task_prompt = """
        Create a Java class App with a static method add(int a, int b) that returns the sum.
        Create a JUnit 5 test class AppTest that verifies the add method.
        """.strip()

    max_attempts = 5
    last_error_summary = None
    seen_errors = set()  # to see if we are stuck in a loop with the same error

    metrics = RunMetrics(
        task_prompt=task_prompt,
        max_attempts=max_attempts
    )

    logger.info("[CONTROLLER] Starting Phase 4 Docker sandboxing run")
    logger.info("[CONTROLLER] Project root: %s", project_root)
    logger.info("[CONTROLLER] Max attempts: %s", max_attempts)
    logger.info("[CONTROLLER] Log file: %s", log_file)

    llm = LLMClient(model="agent-coder")
    sandbox = SandboxManager(project_root)
    sandbox_root = sandbox.prepare()
    workspace = WorkspaceManager(sandbox_root)
    runner = DockerRunner(sandbox_root, image_name="agent-pipeline-java", timeout_seconds=30)

    logger.info("[CONTROLLER] Sandbox root: %s", sandbox_root)
    logger.info("[CONTROLLER] Docker image: agent-pipeline-java")

    for attempt in range(1, max_attempts + 1):
        attempt_start = time.perf_counter()

        llm_seconds = 0.0
        workspace_seconds = 0.0
        maven_seconds = 0.0

        logger.info("")
        logger.info("[CONTROLLER] Attempt %s/%s", attempt, max_attempts)

        try:
            if last_error_summary is None:
                logger.info("[CONTROLLER] Calling LLM for initial generation...")
            else:
                logger.info("[CONTROLLER] Calling LLM with previous Maven error feedback...")

            llm_start = time.perf_counter()

            generated = llm.generate_code(
                task_prompt=task_prompt,
                previous_error=last_error_summary
            )
            
            # THESE ARE JUST FOR TESTING !!!
            # test when it breaks main
            # if attempt == 1:
            #     generated["main_class"] = generated["main_class"].replace("return a + b;", "return a + ;")
            # test when it breaks tests
            # if attempt == 1:
            #     generated["test_class"] = generated["test_class"].replace("assertEquals(5, App.add(2, 3));", "assertEquals(6, App.add(2, 3));")
            # test when everytime is wrong
            # generated["main_class"] = generated["main_class"].replace("return a + b;", "return a + ;")

            llm_seconds = time.perf_counter() - llm_start
            logger.info("[TIMING] LLM generation took %.3f seconds", llm_seconds)

        # this is for catching errors before Docker/Maven runs!!!
        except RuntimeError as e:
            llm_seconds = time.perf_counter() - attempt_start

            error_summary = f"LLM generation failed before Docker/Maven could run:\n{e}"
            normalized_error = ErrorExtractor.fingerprint_error(error_summary, error_type)
            error_type = ErrorExtractor.classify_error(error_summary)

            logger.error("[CONTROLLER] LLM FAILURE")
            logger.error(error_summary)
            logger.info("[CONTROLLER] Error type: %s", error_type)

            attempt_seconds = time.perf_counter() - attempt_start

            # got same error again, we are stuck
            if normalized_error in seen_errors:
                logger.error("[CONTROLLER] Repeated LLM failure detected. Stopping.")

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

        logger.info("[CONTROLLER] Writing generated Java files into sandbox...")
        workspace_start = time.perf_counter()

        workspace.write_java_files(
            main_class=generated["main_class"],
            test_class=generated["test_class"]
        )

        workspace_seconds = time.perf_counter() - workspace_start
        logger.info("[TIMING] Workspace write took %.3f seconds", workspace_seconds)

        logger.info("[CONTROLLER] Running Maven tests inside Docker...")
        result = runner.run_tests()

        maven_seconds = result.duration_seconds
        logger.info("[TIMING] Docker/Maven run took %.3f seconds", maven_seconds)
        logger.info("[CONTROLLER] Docker/Maven exit code: %s", result.exit_code)

        attempt_seconds = time.perf_counter() - attempt_start

        if result.success:
            logger.info("[CONTROLLER] BUILD SUCCESS")
            logger.info("[CONTROLLER] Passed on attempt %s/%s", attempt, max_attempts)
            logger.info("[TIMING] Attempt took %.3f seconds", attempt_seconds)

            metrics.add_attempt(
                attempt=attempt,
                status="SUCCESS",
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
                final_status="SUCCESS"
            )
            return

        logger.error("[CONTROLLER] BUILD FAILURE")

        error_summary = ErrorExtractor.extract_errors(
            raw_output=result.combined_output,
            timed_out=result.timed_out
        )

        error_type = ErrorExtractor.classify_error(
            error_summary=error_summary,
            timed_out=result.timed_out
        )

        logger.error("[CONTROLLER] Extracted Docker/Maven failure:")
        logger.error(error_summary)
        logger.info("[CONTROLLER] Error type: %s", error_type)
        logger.info("[TIMING] Attempt took %.3f seconds", attempt_seconds)

        normalized_error = ErrorExtractor.fingerprint_error(error_summary, error_type)

        # got same error again, we are stuck
        if normalized_error in seen_errors:
            logger.error("[CONTROLLER] Repeated Docker/Maven error detected. Stopping.")

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
            status="MAVEN_FAILURE",
            llm_seconds=llm_seconds,
            workspace_seconds=workspace_seconds,
            maven_seconds=maven_seconds,
            attempt_seconds=attempt_seconds,
            exit_code=result.exit_code,
            error_type=error_type,
            error_summary=error_summary
        )

    logger.error("")
    logger.error("[CONTROLLER] FAILED after %s attempts.", max_attempts)

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

    logger.info("[CONTROLLER] Final status: %s", final_status)
    logger.info("[TIMING] Total run took %.3f seconds", metrics.total_seconds)
    logger.info("[CONTROLLER] Run summary written to: %s", summary_file)


if __name__ == "__main__":
    main()