from pathlib import Path

# applies the changes requested by the LLM after validation
class FileRewriter:
    def __init__(self, sandbox_root):
        self.sandbox_root = Path(sandbox_root).resolve()
        self.production_root = self.sandbox_root / "src" / "main" / "java"

    def apply_files(self, files):
        written_paths = []

        if not files:
            raise RuntimeError("LLM repair output did not include any files to write.")

        for file_entry in files:
            raw_path = file_entry["path"].replace("\\", "/")
            content = file_entry["content"]

            relative_path = self.normalize_path(raw_path)
            self.validate_path(relative_path)

            target_path = (self.sandbox_root / relative_path).resolve()
            self.validate_target_path(target_path, relative_path)

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

            written_paths.append(relative_path)

        return written_paths

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
                f"LLM tried to create a new file. Phase 11 only allows editing existing production files: {relative_path}"
            )

        try:
            target_path.relative_to(self.production_root)
        except ValueError as e:
            raise RuntimeError(
                f"LLM may only modify files under src/main/java/, got: {relative_path}"
            ) from e