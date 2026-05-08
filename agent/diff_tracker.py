from pathlib import Path
from datetime import datetime
import difflib


# tracks before/after source changes and writes patch artifacts
class DiffTracker:
    def __init__(self, project_root, run_id=None):
        self.project_root = Path(project_root)

        if run_id is None:
            run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")

        self.run_id = run_id
        self.run_artifacts_dir = self.project_root / "artifacts" / "runs" / self.run_id
        self.run_artifacts_dir.mkdir(parents=True, exist_ok=True)

    def prepare_task_dir(self, task_name):
        task_dir = self.run_artifacts_dir / task_name
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    # snapshot all Java files before LLM
    def snapshot_production_files(self, sandbox_root):
        sandbox_root = Path(sandbox_root)
        production_root = sandbox_root / "src" / "main" / "java"

        snapshot = {}

        if not production_root.exists():
            return snapshot

        for file_path in sorted(production_root.rglob("*.java")):
            if not file_path.is_file():
                continue

            relative_path = file_path.relative_to(sandbox_root).as_posix()
            snapshot[relative_path] = file_path.read_text(encoding="utf-8", errors="replace")

        return snapshot

    # write before/after files + diff patch for one repair attempt
    def write_attempt_artifacts(self, task_name, attempt, sandbox_root, before_snapshot, changed_files):
        sandbox_root = Path(sandbox_root)

        task_dir = self.prepare_task_dir(task_name)
        attempt_dir = task_dir / f"attempt_{attempt}"
        before_dir = attempt_dir / "before"
        after_dir = attempt_dir / "after"

        before_dir.mkdir(parents=True, exist_ok=True)
        after_dir.mkdir(parents=True, exist_ok=True)

        patch_parts = []

        for relative_path in sorted(changed_files):
            after_path = sandbox_root / relative_path

            before_content = before_snapshot.get(relative_path, "")

            if after_path.exists():
                after_content = after_path.read_text(encoding="utf-8", errors="replace")
            else:
                after_content = ""

            self.write_nested_file(before_dir, relative_path, before_content)
            self.write_nested_file(after_dir, relative_path, after_content)

            diff_lines = difflib.unified_diff(
                before_content.splitlines(keepends=True),
                after_content.splitlines(keepends=True),
                fromfile=f"before/{relative_path}",
                tofile=f"after/{relative_path}"
            )

            patch_text = "".join(diff_lines)

            if patch_text.strip():
                patch_parts.append(patch_text)

        if patch_parts:
            full_patch = "\n".join(patch_parts)
        else:
            full_patch = "No textual changes detected.\n"

        patch_file = attempt_dir / f"attempt_{attempt}.patch"
        patch_file.write_text(full_patch, encoding="utf-8")

        return {
            "artifact_dir": str(attempt_dir),
            "patch_file": str(patch_file),
            "changed_files": list(changed_files)
        }

    def write_nested_file(self, root_dir, relative_path, content):
        target_path = Path(root_dir) / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")