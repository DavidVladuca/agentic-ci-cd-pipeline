from pathlib import Path


# applies the changes requested by the LLM after validation
class FileRewriter:
    def __init__(self, sandbox_root):
        self.sandbox_root = Path(sandbox_root).resolve()
        self.production_root = self.sandbox_root / "src" / "main" / "java"

    def apply_files(self, files):
        write_plan = self.build_write_plan(files)

        backups = {}

        for relative_path, target_path, _content in write_plan:
            backups[target_path] = target_path.read_text(
                encoding="utf-8",
                errors="replace"
            )

        written_paths = []

        try:
            for relative_path, target_path, content in write_plan:
                self.write_file_safely(target_path, content)
                written_paths.append(relative_path)

        except Exception as e:
            self.restore_backups(backups)

            raise RuntimeError(
                "Failed while applying LLM file edits. "
                "The sandbox files modified during this attempt were restored."
            ) from e

        return written_paths

    def build_write_plan(self, files):
        if not files:
            raise RuntimeError("LLM repair output did not include any files to write.")

        write_plan = []
        seen_relative_paths = set()

        for file_entry in files:
            raw_path = file_entry["path"].replace("\\", "/")
            content = file_entry["content"]

            relative_path = self.normalize_path(raw_path)
            self.validate_path(relative_path)

            if relative_path in seen_relative_paths:
                raise RuntimeError(f"Duplicate normalized repair file path: {relative_path}")

            seen_relative_paths.add(relative_path)

            target_path = (self.sandbox_root / relative_path).resolve()
            self.validate_target_path(target_path, relative_path)

            write_plan.append((relative_path, target_path, content))

        return write_plan

    # if LLM returns "App.java", map it to "src/main/java/App.java" for example
    def normalize_path(self, raw_path):
        raw_path = raw_path.strip()

        if "/" in raw_path:
            return raw_path

        if not raw_path.endswith(".java"):
            return raw_path

        matches = list(self.production_root.rglob(raw_path))

        if len(matches) == 1:
            return matches[0].relative_to(self.sandbox_root).as_posix()

        if len(matches) > 1:
            raise RuntimeError(
                f"LLM returned ambiguous file name '{raw_path}'. "
                f"Use the full relative path under src/main/java/."
            )

        return raw_path

    def validate_path(self, relative_path):
        path = Path(relative_path)

        if path.is_absolute():
            raise RuntimeError(f"LLM tried to write an absolute path: {relative_path}")

        if ".." in path.parts:
            raise RuntimeError(f"LLM tried to escape sandbox with path: {relative_path}")

        if not relative_path.startswith("src/main/java/"):
            raise RuntimeError(
                f"LLM may only modify production Java files under src/main/java/, got: {relative_path}"
            )

        if not relative_path.endswith(".java"):
            raise RuntimeError(f"LLM may only modify .java files, got: {relative_path}")

    def validate_target_path(self, target_path, relative_path):
        try:
            target_path.relative_to(self.sandbox_root)
        except ValueError as e:
            raise RuntimeError(f"Refusing to write outside sandbox: {relative_path}") from e

        if not target_path.exists():
            raise RuntimeError(
                f"LLM tried to create a new file. "
                f"Phase 19 only allows editing existing production files: {relative_path}"
            )

        if not target_path.is_file():
            raise RuntimeError(f"LLM target path is not a file: {relative_path}")

        try:
            target_path.relative_to(self.production_root)
        except ValueError as e:
            raise RuntimeError(
                f"LLM may only modify files under src/main/java/, got: {relative_path}"
            ) from e

    def write_file_safely(self, target_path, content):
        temporary_path = target_path.with_name(target_path.name + ".agent_tmp")

        try:
            temporary_path.write_text(content, encoding="utf-8")
            temporary_path.replace(target_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def restore_backups(self, backups):
        for target_path, original_content in backups.items():
            target_path.write_text(original_content, encoding="utf-8")