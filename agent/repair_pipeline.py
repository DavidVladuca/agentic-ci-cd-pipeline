from dataclasses import dataclass
from pathlib import Path
import time

from agent.diff_tracker import DiffTracker
from agent.docker_runner import DockerRunner
from agent.error_extractor import ErrorExtractor
from agent.file_rewriter import FileRewriter
from agent.llm_client import LLMClient
from agent.project_sandbox import ProjectSandbox
from agent.repair_task import RepairTask
from agent.run_metrics import RunMetrics
from agent.source_context import SourceContextBuilder
from agent.project_analyzer import ProjectAnalyzer
from agent.file_selector import FileSelector


@dataclass
class RepairRunResult:
    task_name: str
    task_dir: str
    difficulty: str
    category: str
    description: str
    expected_error_type: str | None
    baseline_status: str
    baseline_error_type: str | None
    final_status: str
    solved: bool
    total_seconds: float
    repair_attempts: int
    final_error_type: str | None
    summary_file: str
    log_file: str
    artifact_dir: str
    final_patch_file: str | None
    changed_files: list[str]
    patch_files: list[str]


# run one full repair loop for one task
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
        self.diff_tracker = DiffTracker(self.project_root)

    def run_task(self, task_dir):
        repair_task = RepairTask.load(task_dir)
        return self.run_repair_task(repair_task)

    def run_repair_task(self, repair_task):
        metrics = RunMetrics(
            task_prompt=repair_task.prompt,
            max_attempts=self.max_attempts
        )

        self.logger.info("[REPAIR] Loaded repair task: %s", repair_task.name)
        self.logger.info("[REPAIR] Task difficulty: %s", repair_task.metadata.difficulty)
        self.logger.info("[REPAIR] Task category: %s", repair_task.metadata.category)
        self.logger.info("[REPAIR] Expected baseline error type: %s", repair_task.metadata.expected_error_type)

        task_artifact_dir = self.diff_tracker.prepare_task_dir(repair_task.name)
        self.logger.info("[REPAIR] Task artifact dir: %s", task_artifact_dir)

        all_changed_files = []
        all_patch_files = []
        final_patch_file = None

        sandbox = ProjectSandbox(self.project_root)
        sandbox_root = sandbox.prepare_task(repair_task)

        initial_snapshot = self.diff_tracker.snapshot_production_files(sandbox_root)

        self.logger.info("[REPAIR] Sandbox root: %s", sandbox_root)

        if repair_task.hidden_tests_dir is None:
            self.logger.info("[REPAIR] No hidden tests directory provided.")
        else:
            self.logger.info("[REPAIR] Hidden tests injected from: %s", repair_task.hidden_tests_dir)

        runner = DockerRunner(
            sandbox_root=sandbox_root,
            image_name=self.docker_image,
            timeout_seconds=self.timeout_seconds
        )

        llm = LLMClient(model=self.model)
        source_context_builder = SourceContextBuilder()
        project_analyzer = ProjectAnalyzer()
        file_selector = FileSelector(max_context_chars=source_context_builder.max_chars)
        file_rewriter = FileRewriter(sandbox_root)

        self.logger.info("[REPAIR] Running baseline Maven/JUnit tests inside Docker...")
        baseline_result = runner.run_tests()

        if baseline_result.success:
            baseline_status = "BASELINE_UNEXPECTED_SUCCESS"
            baseline_error_type = None

            self.logger.error("[REPAIR] Baseline unexpectedly passed.")
            self.logger.error("[REPAIR] This repair task is invalid because hidden tests did not expose a failure.")

            metrics.add_attempt(
                attempt=0,
                status=baseline_status,
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
                final_status=baseline_status,
                baseline_status=baseline_status,
                baseline_error_type=baseline_error_type,
                artifact_dir=str(task_artifact_dir),
                final_patch_file=final_patch_file,
                changed_files=all_changed_files,
                patch_files=all_patch_files
            )

        baseline_error_summary = ErrorExtractor.extract_errors(
            raw_output=baseline_result.combined_output,
            timed_out=baseline_result.timed_out
        )

        baseline_error_type = ErrorExtractor.classify_error(
            error_summary=baseline_error_summary,
            timed_out=baseline_result.timed_out
        )

        baseline_status = "BASELINE_FAILURE_DETECTED"

        self.logger.info("[REPAIR] Baseline failure detected.")
        self.logger.info("[REPAIR] Baseline error type: %s", baseline_error_type)
        self.logger.error("[REPAIR] Baseline failure:")
        self.logger.error(baseline_error_summary)

        if repair_task.metadata.expected_error_type and repair_task.metadata.expected_error_type != baseline_error_type:
            self.logger.error(
                "[REPAIR] Baseline error type mismatch. Expected %s but got %s",
                repair_task.metadata.expected_error_type,
                baseline_error_type
            )

        metrics.add_attempt(
            attempt=0,
            status=baseline_status,
            llm_seconds=0.0,
            workspace_seconds=0.0,
            maven_seconds=baseline_result.duration_seconds,
            attempt_seconds=baseline_result.duration_seconds,
            exit_code=baseline_result.exit_code,
            error_type=baseline_error_type,
            error_summary=baseline_error_summary
        )

        if baseline_error_type in {"DEPENDENCY_RESOLUTION_ERROR", "DOCKER_ERROR", "SANDBOX_ERROR", "TIMEOUT"}:
            self.logger.error("[REPAIR] Baseline failed because of infrastructure, not project code. Stopping before LLM repair.")

            return self.finish_run(
                repair_task=repair_task,
                metrics=metrics,
                final_status=f"FAILED_BASELINE_{baseline_error_type}",
                baseline_status=baseline_status,
                baseline_error_type=baseline_error_type,
                artifact_dir=str(task_artifact_dir),
                final_patch_file=final_patch_file,
                changed_files=all_changed_files,
                patch_files=all_patch_files
            )

        last_error_summary = baseline_error_summary
        seen_errors = set()  # to see if we are stuck in a loop with the same repair failure

        for attempt in range(1, self.max_attempts + 1):
            attempt_start = time.perf_counter()

            llm_seconds = 0.0
            workspace_seconds = 0.0
            maven_seconds = 0.0
            attempt_changed_files = []
            attempt_patch_file = None
            attempt_artifact_dir = None

            self.logger.info("")
            self.logger.info("[REPAIR] Repair attempt %s/%s", attempt, self.max_attempts)

            try:
                project_analysis = project_analyzer.analyze(sandbox_root)

                file_selection = file_selector.select(
                    analysis=project_analysis,
                    task_prompt=repair_task.prompt,
                    error_summary=last_error_summary
                )

                self.logger.info(
                    "[REPAIR] Selected %s context files, estimated context size: %s characters",
                    len(file_selection.selected_paths),
                    file_selection.estimated_chars
                )

                for selected_path in file_selection.selected_paths:
                    reasons = file_selection.reasons_by_path.get(selected_path, [])
                    reason_text = "; ".join(reasons) if reasons else "no reason recorded"

                    self.logger.info(
                        "[REPAIR] Context file selected: %s | %s",
                        selected_path,
                        reason_text
                    )

                source_context = source_context_builder.build(
                    sandbox_root=sandbox_root,
                    selected_paths=file_selection.selected_paths
                )

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

                before_snapshot = self.diff_tracker.snapshot_production_files(sandbox_root)

                self.logger.info("[REPAIR] Applying LLM file edits...")
                workspace_start = time.perf_counter()

                written_paths = file_rewriter.apply_files(repair_json["files"])

                workspace_seconds = time.perf_counter() - workspace_start
                self.logger.info("[TIMING] File rewrite took %.3f seconds", workspace_seconds)
                self.logger.info("[REPAIR] Written files: %s", ", ".join(written_paths))

                artifact_info = self.diff_tracker.write_attempt_artifacts(
                    task_name=repair_task.name,
                    attempt=attempt,
                    sandbox_root=sandbox_root,
                    before_snapshot=before_snapshot,
                    changed_files=written_paths
                )

                attempt_changed_files = artifact_info["changed_files"]
                attempt_patch_file = artifact_info["patch_file"]
                attempt_artifact_dir = artifact_info["artifact_dir"]

                all_patch_files.append(attempt_patch_file)

                for changed_file in attempt_changed_files:
                    if changed_file not in all_changed_files:
                        all_changed_files.append(changed_file)

                self.logger.info("[REPAIR] Attempt artifacts: %s", attempt_artifact_dir)
                self.logger.info("[REPAIR] Patch file: %s", attempt_patch_file)

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
                        error_summary=error_summary,
                        changed_files=attempt_changed_files,
                        patch_file=attempt_patch_file,
                        artifact_dir=attempt_artifact_dir
                    )

                    return self.finish_run(
                        repair_task=repair_task,
                        metrics=metrics,
                        final_status="FAILED_REPEATED_LLM_FAILURE",
                        baseline_status=baseline_status,
                        baseline_error_type=baseline_error_type,
                        artifact_dir=str(task_artifact_dir),
                        final_patch_file=final_patch_file,
                        changed_files=all_changed_files,
                        patch_files=all_patch_files
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
                    error_summary=error_summary,
                    changed_files=attempt_changed_files,
                    patch_file=attempt_patch_file,
                    artifact_dir=attempt_artifact_dir
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

                final_artifact_info = self.diff_tracker.write_final_repair_artifacts(
                    task_name=repair_task.name,
                    sandbox_root=sandbox_root,
                    initial_snapshot=initial_snapshot
                )

                final_patch_file = final_artifact_info["final_patch_file"]
                all_changed_files = final_artifact_info["changed_files"]

                self.logger.info("[REPAIR] Final repair patch: %s", final_patch_file)

                metrics.add_attempt(
                    attempt=attempt,
                    status="REPAIR_SUCCESS",
                    llm_seconds=llm_seconds,
                    workspace_seconds=workspace_seconds,
                    maven_seconds=maven_seconds,
                    attempt_seconds=attempt_seconds,
                    exit_code=result.exit_code,
                    error_type=None,
                    error_summary=None,
                    changed_files=attempt_changed_files,
                    patch_file=attempt_patch_file,
                    artifact_dir=attempt_artifact_dir
                )

                return self.finish_run(
                    repair_task=repair_task,
                    metrics=metrics,
                    final_status="REPAIR_SUCCESS",
                    baseline_status=baseline_status,
                    baseline_error_type=baseline_error_type,
                    artifact_dir=str(task_artifact_dir),
                    final_patch_file=final_patch_file,
                    changed_files=all_changed_files,
                    patch_files=all_patch_files
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
                    error_summary=error_summary,
                    changed_files=attempt_changed_files,
                    patch_file=attempt_patch_file,
                    artifact_dir=attempt_artifact_dir
                )

                return self.finish_run(
                    repair_task=repair_task,
                    metrics=metrics,
                    final_status="FAILED_REPEATED_MAVEN_ERROR",
                    baseline_status=baseline_status,
                    baseline_error_type=baseline_error_type,
                    artifact_dir=str(task_artifact_dir),
                    final_patch_file=final_patch_file,
                    changed_files=all_changed_files,
                    patch_files=all_patch_files
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
                error_summary=error_summary,
                changed_files=attempt_changed_files,
                patch_file=attempt_patch_file,
                artifact_dir=attempt_artifact_dir
            )

        self.logger.error("")
        self.logger.error("[REPAIR] FAILED after %s repair attempts.", self.max_attempts)

        return self.finish_run(
            repair_task=repair_task,
            metrics=metrics,
            final_status="FAILED_MAX_ATTEMPTS",
            baseline_status=baseline_status,
            baseline_error_type=baseline_error_type,
            artifact_dir=str(task_artifact_dir),
            final_patch_file=final_patch_file,
            changed_files=all_changed_files,
            patch_files=all_patch_files
        )

    def finish_run(
        self,
        repair_task,
        metrics,
        final_status,
        baseline_status,
        baseline_error_type,
        artifact_dir,
        final_patch_file,
        changed_files,
        patch_files
    ):
        metrics.set_artifacts(
            artifact_dir=artifact_dir,
            final_patch_file=final_patch_file,
            changed_files=changed_files,
            patch_files=patch_files
        )

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
            difficulty=repair_task.metadata.difficulty,
            category=repair_task.metadata.category,
            description=repair_task.metadata.description,
            expected_error_type=repair_task.metadata.expected_error_type,
            baseline_status=baseline_status,
            baseline_error_type=baseline_error_type,
            final_status=final_status,
            solved=final_status == "REPAIR_SUCCESS",
            total_seconds=metrics.total_seconds,
            repair_attempts=repair_attempts,
            final_error_type=last_attempt.get("error_type"),
            summary_file=str(summary_file),
            log_file=str(self.log_file),
            artifact_dir=artifact_dir,
            final_patch_file=final_patch_file,
            changed_files=changed_files,
            patch_files=patch_files
        )