from dataclasses import dataclass
from pathlib import Path
import time

from agent.docker_runner import DockerRunner
from agent.error_extractor import ErrorExtractor
from agent.file_rewriter import FileRewriter
from agent.llm_client import LLMClient
from agent.project_sandbox import ProjectSandbox
from agent.repair_task import RepairTask
from agent.run_metrics import RunMetrics
from agent.source_context import SourceContextBuilder


@dataclass
class RepairRunResult:
    task_name: str
    task_dir: str
    final_status: str
    solved: bool
    total_seconds: float
    repair_attempts: int
    final_error_type: str | None
    summary_file: str
    log_file: str


# run one full rapair loop for one task
class RepairPipeline:
    def __init__(
        self,
        project_root,
        logger,
        log_file,
        model,
        max_attempts,
        docker_image,
        timeout_seconds
    ):
        self.project_root = Path(project_root)
        self.logger = logger
        self.log_file = log_file
        self.model = model
        self.max_attempts = max_attempts
        self.docker_image = docker_image
        self.timeout_seconds = timeout_seconds

    def run_task(self, task_dir):
        repair_task = RepairTask.load(task_dir)

        metrics = RunMetrics(
            task_prompt=repair_task.prompt,
            max_attempts=self.max_attempts
        )

        self.logger.info("[REPAIR] Loaded repair task: %s", repair_task.name)

        sandbox = ProjectSandbox(self.project_root)
        sandbox_root = sandbox.prepare_task(repair_task)

        self.logger.info("[REPAIR] Sandbox root: %s", sandbox_root)
        self.logger.info("[REPAIR] Hidden tests injected from: %s", repair_task.hidden_tests_dir)

        runner = DockerRunner(
            sandbox_root=sandbox_root,
            image_name=self.docker_image,
            timeout_seconds=self.timeout_seconds
        )

        llm = LLMClient(model=self.model)
        source_context_builder = SourceContextBuilder()
        file_rewriter = FileRewriter(sandbox_root)

        self.logger.info("[REPAIR] Running baseline Maven/JUnit tests inside Docker...")
        baseline_result = runner.run_tests()

        if baseline_result.success:
            self.logger.error("[REPAIR] Baseline unexpectedly passed.")
            self.logger.error("[REPAIR] This repair task is invalid because hidden tests did not expose a failure.")

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

            return self.finish_run(
                repair_task=repair_task,
                metrics=metrics,
                final_status="BASELINE_UNEXPECTED_SUCCESS"
            )

        baseline_error_summary = ErrorExtractor.extract_errors(
            raw_output=baseline_result.combined_output,
            timed_out=baseline_result.timed_out
        )

        baseline_error_type = ErrorExtractor.classify_error(
            error_summary=baseline_error_summary,
            timed_out=baseline_result.timed_out
        )

        self.logger.info("[REPAIR] Baseline failure detected.")
        self.logger.info("[REPAIR] Baseline error type: %s", baseline_error_type)
        self.logger.error("[REPAIR] Baseline failure:")
        self.logger.error(baseline_error_summary)

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

        for attempt in range(1, self.max_attempts + 1):
            attempt_start = time.perf_counter()

            llm_seconds = 0.0
            workspace_seconds = 0.0
            maven_seconds = 0.0

            self.logger.info("")
            self.logger.info("[REPAIR] Repair attempt %s/%s", attempt, self.max_attempts)

            try:
                source_context = source_context_builder.build(sandbox_root)
                self.logger.info("[REPAIR] Source context length: %s characters", len(source_context))

                self.logger.info("[REPAIR] Calling LLM for repair file edits...")
                llm_start = time.perf_counter()

                repair_json = llm.generate_repair_files(
                    task_prompt=repair_task.prompt,
                    source_context=source_context,
                    previous_error=last_error_summary
                )

                llm_seconds = time.perf_counter() - llm_start
                self.logger.info("[TIMING] LLM repair generation took %.3f seconds", llm_seconds)

                self.logger.info("[REPAIR] Applying LLM file edits...")
                workspace_start = time.perf_counter()

                written_paths = file_rewriter.apply_files(repair_json["files"])

                workspace_seconds = time.perf_counter() - workspace_start
                self.logger.info("[TIMING] File rewrite took %.3f seconds", workspace_seconds)
                self.logger.info("[REPAIR] Written files: %s", ", ".join(written_paths))

            # this is for catching errors before Docker/Maven runs!!!
            except RuntimeError as e:
                llm_seconds = time.perf_counter() - attempt_start

                error_summary = f"LLM generation failed before Docker/Maven could run:\n{e}"
                error_type = ErrorExtractor.classify_error(error_summary)
                normalized_error = ErrorExtractor.fingerprint_error(error_summary, error_type)

                self.logger.error("[REPAIR] LLM/WRITE FAILURE")
                self.logger.error(error_summary)
                self.logger.info("[REPAIR] Error type: %s", error_type)

                attempt_seconds = time.perf_counter() - attempt_start

                # got same error again, we are stuck
                if normalized_error in seen_errors:
                    self.logger.error("[REPAIR] Repeated LLM/write failure detected. Stopping.")

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

                    return self.finish_run(
                        repair_task=repair_task,
                        metrics=metrics,
                        final_status="FAILED_REPEATED_LLM_FAILURE"
                    )

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

            self.logger.info("[REPAIR] Running Maven/JUnit tests inside Docker after repair...")
            result = runner.run_tests()

            maven_seconds = result.duration_seconds
            self.logger.info("[TIMING] Docker/Maven run took %.3f seconds", maven_seconds)
            self.logger.info("[REPAIR] Docker/Maven exit code: %s", result.exit_code)

            attempt_seconds = time.perf_counter() - attempt_start

            if result.success:
                self.logger.info("[REPAIR] REPAIR SUCCESS")
                self.logger.info("[REPAIR] Passed on repair attempt %s/%s", attempt, self.max_attempts)
                self.logger.info("[TIMING] Attempt took %.3f seconds", attempt_seconds)

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

                return self.finish_run(
                    repair_task=repair_task,
                    metrics=metrics,
                    final_status="REPAIR_SUCCESS"
                )

            error_summary = ErrorExtractor.extract_errors(
                raw_output=result.combined_output,
                timed_out=result.timed_out
            )

            error_type = ErrorExtractor.classify_error(
                error_summary=error_summary,
                timed_out=result.timed_out
            )

            self.logger.error("[REPAIR] Repair attempt failed.")
            self.logger.error("[REPAIR] Extracted Docker/Maven failure:")
            self.logger.error(error_summary)
            self.logger.info("[REPAIR] Error type: %s", error_type)
            self.logger.info("[TIMING] Attempt took %.3f seconds", attempt_seconds)

            normalized_error = ErrorExtractor.fingerprint_error(error_summary, error_type)

            # got same error again, we are stuck
            if normalized_error in seen_errors:
                self.logger.error("[REPAIR] Repeated Docker/Maven error detected. Stopping.")

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

                return self.finish_run(
                    repair_task=repair_task,
                    metrics=metrics,
                    final_status="FAILED_REPEATED_MAVEN_ERROR"
                )

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

        self.logger.error("")
        self.logger.error("[REPAIR] FAILED after %s repair attempts.", self.max_attempts)

        return self.finish_run(
            repair_task=repair_task,
            metrics=metrics,
            final_status="FAILED_MAX_ATTEMPTS"
        )

    def finish_run(self, repair_task, metrics, final_status):
        metrics.finish(final_status)
        summary_file = metrics.write_summary(self.project_root, self.log_file)

        self.logger.info("[REPAIR] Final status: %s", final_status)
        self.logger.info("[TIMING] Total run took %.3f seconds", metrics.total_seconds)
        self.logger.info("[REPAIR] Run summary written to: %s", summary_file)

        last_attempt = metrics.attempts[-1] if metrics.attempts else {}

        repair_attempts = 0
        for attempt in metrics.attempts:
            if attempt["attempt"] > 0:
                repair_attempts += 1

        return RepairRunResult(
            task_name=repair_task.name,
            task_dir=str(repair_task.task_dir),
            final_status=final_status,
            solved=final_status == "REPAIR_SUCCESS",
            total_seconds=metrics.total_seconds,
            repair_attempts=repair_attempts,
            final_error_type=last_attempt.get("error_type"),
            summary_file=str(summary_file),
            log_file=str(self.log_file)
        )