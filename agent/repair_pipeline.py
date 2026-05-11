from dataclasses import dataclass
from pathlib import Path
import time

from agent.diff_tracker import DiffTracker, NO_CHANGE_SENTINEL
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
from agent.repair_strategy import RepairStrategy



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


class RepairPipeline:
    """Runs one full LLM-guided repair loop for a single Java Maven task, including sandboxing, baseline testing, and iterative patch attempts."""
    def __init__(
        self,
        project_root,
        logger,
        log_file,
        model,
        max_attempts,
        docker_image,
        timeout_seconds,
        prepare_dependencies=False,
        maven_repo_host_dir=None,
        dependency_timeout_seconds=180
    ):
        self.project_root = Path(project_root)
        self.logger = logger
        self.log_file = log_file
        self.model = model
        self.max_attempts = max_attempts
        self.docker_image = docker_image
        self.timeout_seconds = timeout_seconds
        self.prepare_dependencies = prepare_dependencies
        self.maven_repo_host_dir = Path(maven_repo_host_dir).resolve() if maven_repo_host_dir else None
        self.dependency_timeout_seconds = dependency_timeout_seconds
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
        sandbox_result = sandbox.prepare_task(repair_task)

        sandbox_root = sandbox_result.sandbox_root
        hidden_test_paths = sandbox_result.hidden_test_paths

        initial_snapshot = self.diff_tracker.snapshot_production_files(sandbox_root)

        self.logger.info("[REPAIR] Sandbox root: %s", sandbox_root)
        self.logger.info("[REPAIR] Hidden test files tracked: %s", len(hidden_test_paths))

        if repair_task.hidden_tests_dir is None:
            self.logger.info("[REPAIR] No hidden tests directory provided.")
        else:
            self.logger.info("[REPAIR] Hidden tests injected from: %s", repair_task.hidden_tests_dir)

        maven_repo_host_dir = self.maven_repo_host_dir

        if self.prepare_dependencies:
            if maven_repo_host_dir is None:
                maven_repo_host_dir = (
                    self.project_root
                    / ".sandbox"
                    / "maven_repos"
                    / repair_task.name
                )

            self.logger.info("[REPAIR] Preparing Maven dependencies with network enabled...")
            self.logger.info("[REPAIR] Maven dependency cache: %s", maven_repo_host_dir)

            prefetch_runner = DockerRunner(
                sandbox_root=sandbox_root,
                image_name=self.docker_image,
                timeout_seconds=self.dependency_timeout_seconds,
                maven_repo_host_dir=maven_repo_host_dir,
                offline=False,
                network_enabled=True
            )

            prefetch_result = prefetch_runner.run_dependency_prefetch()

            self.logger.info("[REPAIR] Dependency prefetch exit code: %s", prefetch_result.exit_code)
            self.logger.info("[TIMING] Dependency prefetch took %.3f seconds", prefetch_result.duration_seconds)

            if not prefetch_result.success:
                error_summary = ErrorExtractor.extract_errors(
                    raw_output=prefetch_result.combined_output,
                    timed_out=prefetch_result.timed_out,
                    timeout_seconds=self.dependency_timeout_seconds
                )

                error_type = ErrorExtractor.classify_error(
                    error_summary=error_summary,
                    timed_out=prefetch_result.timed_out
                )

                self.logger.error("[REPAIR] Dependency prefetch failed.")
                self.logger.error(error_summary)
                self.logger.info("[REPAIR] Error type: %s", error_type)

                metrics.add_attempt(
                    attempt=0,
                    status="DEPENDENCY_PREFETCH_FAILED",
                    llm_seconds=0.0,
                    workspace_seconds=0.0,
                    maven_seconds=prefetch_result.duration_seconds,
                    attempt_seconds=prefetch_result.duration_seconds,
                    exit_code=prefetch_result.exit_code,
                    error_type=error_type,
                    error_summary=error_summary
                )

                return self.finish_run(
                    repair_task=repair_task,
                    metrics=metrics,
                    final_status="FAILED_DEPENDENCY_PREFETCH",
                    baseline_status="DEPENDENCY_PREFETCH_FAILED",
                    baseline_error_type=error_type,
                    artifact_dir=str(task_artifact_dir),
                    final_patch_file=final_patch_file,
                    changed_files=all_changed_files,
                    patch_files=all_patch_files
                )

        runner = DockerRunner(
            sandbox_root=sandbox_root,
            image_name=self.docker_image,
            timeout_seconds=self.timeout_seconds,
            maven_repo_host_dir=maven_repo_host_dir,
            offline=True,
            network_enabled=False
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
            timed_out=baseline_result.timed_out,
            timeout_seconds=self.timeout_seconds
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

        if RepairStrategy.is_infrastructure_error(baseline_error_type):
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
        last_patch_feedback = None
        last_meaningful_patch_feedback = None
        strategy_note = None
        expand_context_next_attempt = False
        expanded_error_fingerprints = set()
        seen_error_counts = {}
        consecutive_no_change_count = 0

        last_compiling_snapshot = None

        if RepairStrategy.error_type_means_project_compiled(baseline_error_type):
            last_compiling_snapshot = self.diff_tracker.snapshot_production_files(sandbox_root)
            self.logger.info("[REPAIR] Baseline produced a compiling source state. Snapshot saved.")
        else:
            self.logger.info("[REPAIR] Baseline did not produce a known compiling source state.")

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
                project_analysis = project_analyzer.analyze(
                    sandbox_root=sandbox_root,
                    hidden_test_paths=hidden_test_paths
                )

                if expand_context_next_attempt:
                    self.logger.info("[REPAIR] Expanded context mode enabled for this attempt.")

                    source_context = source_context_builder.build(
                        sandbox_root=sandbox_root,
                        selected_paths=None,
                        hidden_test_paths=hidden_test_paths
                    )

                    expand_context_next_attempt = False

                else:
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
                        selected_paths=file_selection.selected_paths,
                        hidden_test_paths=hidden_test_paths
                    )

                self.logger.info("[REPAIR] Source context length: %s characters", len(source_context))

                self.logger.info("[REPAIR] Calling LLM for repair file edits...")
                llm_start = time.perf_counter()

                repair_json = llm.generate_repair_files(
                    task_prompt=repair_task.prompt,
                    source_context=source_context,
                    previous_error=last_error_summary,
                    previous_patch=last_patch_feedback,
                    strategy_note=strategy_note
                )

                llm_seconds = time.perf_counter() - llm_start
                self.logger.info("[TIMING] LLM repair generation took %.3f seconds", llm_seconds)

                strategy_note = None

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

                attempt_patch_text = self.diff_tracker.read_patch_file(attempt_patch_file)

                if attempt_patch_text and attempt_patch_text.strip() == NO_CHANGE_SENTINEL:
                    consecutive_no_change_count += 1

                    error_summary = (
                        "The previous repair output made zero textual changes to the source files. "
                        "The generated content was identical to the current broken code, so running Maven again "
                        "would only repeat the same failure. The next repair must make a real source change."
                    )

                    error_type = "LLM_ERROR"

                    no_change_note = (
                        "CRITICAL: Your previous repair made ZERO source-code changes. "
                        "The existing code is known to be wrong. "
                        "Do not submit the same implementation again. "
                        "Use the Maven/JUnit failure output as concrete behavioral evidence. "
                        "Identify which rule is still violated and change the implementation so the actual result changes."
                    )

                    strategy_note = no_change_note

                    last_error_summary = (
                        last_error_summary + "\n\n" + error_summary
                        if last_error_summary
                        else error_summary
                    )

                    # Keep the last real diff. Do not feed the sentinel as the previous patch.
                    last_patch_feedback = last_meaningful_patch_feedback

                    # A no-change output means the model is stuck. Give it broader context next.
                    expand_context_next_attempt = True

                    attempt_seconds = time.perf_counter() - attempt_start

                    self.logger.error("[REPAIR] No-change repair patch detected. Skipping Maven run.")
                    self.logger.error(error_summary)

                    metrics.add_attempt(
                        attempt=attempt,
                        status="NO_CHANGE_PATCH",
                        llm_seconds=llm_seconds,
                        workspace_seconds=workspace_seconds,
                        maven_seconds=0.0,
                        attempt_seconds=attempt_seconds,
                        exit_code=None,
                        error_type=error_type,
                        error_summary=error_summary,
                        changed_files=attempt_changed_files,
                        patch_file=attempt_patch_file,
                        artifact_dir=attempt_artifact_dir
                    )

                    if consecutive_no_change_count >= 3:
                        self.logger.error("[REPAIR] Model stagnated: repeated no-change repair outputs.")

                        return self.finish_run(
                            repair_task=repair_task,
                            metrics=metrics,
                            final_status="FAILED_MODEL_STAGNATION",
                            baseline_status=baseline_status,
                            baseline_error_type=baseline_error_type,
                            artifact_dir=str(task_artifact_dir),
                            final_patch_file=final_patch_file,
                            changed_files=all_changed_files,
                            patch_files=all_patch_files
                        )

                    continue

                # This was a real textual patch. Preserve it for future feedback.
                last_meaningful_patch_feedback = attempt_patch_text
                consecutive_no_change_count = 0

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

                previous_count = seen_error_counts.get(normalized_error, 0)
                seen_error_counts[normalized_error] = previous_count + 1

                last_error_summary = error_summary

                # Preserve the last real diff if one exists. Do not erase useful feedback.
                last_patch_feedback = last_meaningful_patch_feedback

                strategy_note = (
                    "The previous model output was rejected before Maven could run. "
                    "Return a complete valid Java source file. "
                    "The content string must include the full file from imports through the final closing brace. "
                    "Do not truncate the file. "
                    "Do not output partial classes. "
                    "Do not output partial methods. "
                    "Do not use placeholders. "
                    "Do not use comments instead of implementation. "
                    "Make the smallest correct repair."
                )

                attempt_status = "LLM_FAILURE"

                if previous_count > 0:
                    self.logger.error(
                        "[REPAIR] Repeated LLM/write failure detected. "
                        "Feeding the validation failure back to the model instead of stopping early."
                    )

                    attempt_status = "REPEATED_LLM_FAILURE"

                    if normalized_error not in expanded_error_fingerprints:
                        expanded_error_fingerprints.add(normalized_error)
                        expand_context_next_attempt = True

                metrics.add_attempt(
                    attempt=attempt,
                    status=attempt_status,
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

                if attempt == self.max_attempts:
                    return self.finish_run(
                        repair_task=repair_task,
                        metrics=metrics,
                        final_status="FAILED_REPEATED_LLM_FAILURE" if previous_count > 0 else "FAILED_LLM_FAILURE",
                        baseline_status=baseline_status,
                        baseline_error_type=baseline_error_type,
                        artifact_dir=str(task_artifact_dir),
                        final_patch_file=final_patch_file,
                        changed_files=all_changed_files,
                        patch_files=all_patch_files
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
                timed_out=result.timed_out,
                timeout_seconds=self.timeout_seconds
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

            previous_count = seen_error_counts.get(normalized_error, 0)
            seen_error_counts[normalized_error] = previous_count + 1

            attempt_patch_text = self.diff_tracker.read_patch_file(attempt_patch_file)

            if attempt_patch_text and attempt_patch_text.strip() != NO_CHANGE_SENTINEL:
                last_meaningful_patch_feedback = attempt_patch_text
                consecutive_no_change_count = 0

            decision = RepairStrategy.decide_after_maven_failure(
                error_type=error_type,
                repeated_count=previous_count,
                context_already_expanded=normalized_error in expanded_error_fingerprints,
                has_last_compiling_snapshot=last_compiling_snapshot is not None
            )

            if decision.should_rollback:
                self.logger.error("[REPAIR] Repair regression detected. Rolling back to last compiling source snapshot.")

                self.diff_tracker.restore_production_snapshot(
                    sandbox_root=sandbox_root,
                    snapshot=last_compiling_snapshot
                )

                self.logger.info("[REPAIR] Rollback complete.")

            elif RepairStrategy.error_type_means_project_compiled(error_type):
                last_compiling_snapshot = self.diff_tracker.snapshot_production_files(sandbox_root)
                self.logger.info("[REPAIR] Failed attempt still compiled. Updated last compiling snapshot.")

            last_error_summary = error_summary

            if attempt_patch_text and attempt_patch_text.strip() != NO_CHANGE_SENTINEL:
                last_patch_feedback = attempt_patch_text
            else:
                last_patch_feedback = last_meaningful_patch_feedback

            strategy_note = decision.strategy_note

            if previous_count > 0:
                assertion_feedback_note = (
                    "The latest Maven/JUnit output contains concrete failing test names and expected/actual values. "
                    "Treat those as executable examples of the required behavior. "
                    "For every failing assertion, identify what exact output or boolean result the current code still produces, "
                    "and make the next patch change that behavior. "
                    "Do not submit a patch that would produce the same actual value shown in the failure output again. "
                    "If the expected value contains punctuation, delimiters, quotes, empty values, signs, or boundary values "
                    "that the actual value lacks, preserve those values explicitly. "
                    "If a failing test name says a case should be allowed but the actual result is false, the current logic is too restrictive. "
                    "If a failing test name says a case should be rejected but the actual result is true, the current logic is too permissive."
                )

                strategy_note = (
                    assertion_feedback_note + " " + strategy_note
                    if strategy_note
                    else assertion_feedback_note
                )

            if decision.should_expand_context:
                self.logger.error("[REPAIR] Repeated Maven error detected. Will retry once with expanded context.")

                expanded_error_fingerprints.add(normalized_error)
                expand_context_next_attempt = True

                metrics.add_attempt(
                    attempt=attempt,
                    status="REPAIR_FAILURE_EXPAND_CONTEXT",
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

                continue

            if decision.should_stop:
                self.logger.error("[REPAIR] Repeated Docker/Maven error detected after expanded context. Stopping.")

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