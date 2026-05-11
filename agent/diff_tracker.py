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

    # snapshot all production Java files before the LLM edit is applied
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

    # write before/after files and a unified diff patch for one repair attempt
    def write_attempt_artifacts(self, task_name, attempt, sandbox_root, before_snapshot, changed_files):
        sandbox_root = Path(sandbox_root)

        task_dir = self.prepare_task_dir(task_name)
        attempt_dir = task_dir / f"attempt_{attempt}"
        before_dir = attempt_dir / "before"
        after_dir = attempt_dir / "after"

        before_dir.mkdir(parents=True, exist_ok=True)
        after_dir.mkdir(parents=True, exist_ok=True)

        patch_file = attempt_dir / f"attempt_{attempt}.patch"

        after_snapshot = self.snapshot_production_files(sandbox_root)

        patch_text = self.build_patch_text(
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            changed_files=changed_files
        )

        for relative_path in sorted(changed_files):
            before_content = before_snapshot.get(relative_path, "")
            after_content = after_snapshot.get(relative_path, "")

            self.write_nested_file(before_dir, relative_path, before_content)
            self.write_nested_file(after_dir, relative_path, after_content)

        patch_file.write_text(patch_text, encoding="utf-8")

        return {
            "artifact_dir": str(attempt_dir),
            "patch_file": str(patch_file),
            "changed_files": list(changed_files)
        }

    # write final patch artifacts from original broken code to final repaired code
    def write_final_repair_artifacts(self, task_name, sandbox_root, initial_snapshot):
        sandbox_root = Path(sandbox_root)

        task_dir = self.prepare_task_dir(task_name)
        before_dir = task_dir / "final_before"
        after_dir = task_dir / "final_after"

        before_dir.mkdir(parents=True, exist_ok=True)
        after_dir.mkdir(parents=True, exist_ok=True)

        final_snapshot = self.snapshot_production_files(sandbox_root)
        changed_files = self.detect_changed_files(initial_snapshot, final_snapshot)

        patch_text = self.build_patch_text(
            before_snapshot=initial_snapshot,
            after_snapshot=final_snapshot,
            changed_files=changed_files
        )

        for relative_path in changed_files:
            before_content = initial_snapshot.get(relative_path, "")
            after_content = final_snapshot.get(relative_path, "")

            self.write_nested_file(before_dir, relative_path, before_content)
            self.write_nested_file(after_dir, relative_path, after_content)

        final_patch_file = task_dir / "final_repair.patch"
        final_patch_file.write_text(patch_text, encoding="utf-8")

        return {
            "artifact_dir": str(task_dir),
            "final_patch_file": str(final_patch_file),
            "changed_files": changed_files
        }

    def detect_changed_files(self, before_snapshot, after_snapshot):
        all_paths = set(before_snapshot.keys()) | set(after_snapshot.keys())
        changed_files = []

        for relative_path in sorted(all_paths):
            before_content = before_snapshot.get(relative_path, "")
            after_content = after_snapshot.get(relative_path, "")

            if before_content != after_content:
                changed_files.append(relative_path)

        return changed_files

    def build_patch_text(self, before_snapshot, after_snapshot, changed_files):
        patch_parts = []

        for relative_path in sorted(changed_files):
            before_content = before_snapshot.get(relative_path, "")
            after_content = after_snapshot.get(relative_path, "")

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
            return "\n".join(patch_parts)

        return "No textual changes detected.\n"

    def write_nested_file(self, root_dir, relative_path, content):
        target_path = Path(root_dir) / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
    
    # restore src/main/java from a production-file snapshot
    def restore_production_snapshot(self, sandbox_root, snapshot):
        sandbox_root = Path(sandbox_root)
        production_root = sandbox_root / "src" / "main" / "java"

        if production_root.exists():
            for file_path in sorted(production_root.rglob("*.java")):
                if file_path.is_file():
                    file_path.unlink()

        for relative_path, content in snapshot.items():
            self.write_nested_file(
                root_dir=sandbox_root,
                relative_path=relative_path,
                content=content
            )

    def read_patch_file(self, patch_file, max_chars=4000):
        if patch_file is None:
            return None

        patch_path = Path(patch_file)

        if not patch_path.exists():
            return None

        text = patch_path.read_text(encoding="utf-8", errors="replace")

        if len(text) <= max_chars:
            return text

        return text[-max_chars:]