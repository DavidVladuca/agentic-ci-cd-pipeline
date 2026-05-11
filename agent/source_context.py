from pathlib import Path
import logging


# reads selected source files from the repair sandbox and builds context for the LLM
# hidden test source files are not included
class SourceContextBuilder:
    def __init__(self, max_chars=12000):
        self.max_chars = max_chars

    # make one combined context string from selected sandbox files
    def build(self, sandbox_root, selected_paths=None, hidden_test_paths=None):
        sandbox_root = Path(sandbox_root).resolve()
        hidden_test_paths = self.normalize_hidden_test_paths(hidden_test_paths)

        if selected_paths is None:
            files = []
            files.extend(self.collect_files(sandbox_root / "src" / "main" / "java"))
            files.extend(
                self.collect_public_test_files(
                    directory=sandbox_root / "src" / "test" / "java",
                    sandbox_root=sandbox_root,
                    hidden_test_paths=hidden_test_paths
                )
            )
        else:
            files = self.resolve_selected_files(
                sandbox_root=sandbox_root,
                selected_paths=selected_paths,
                hidden_test_paths=hidden_test_paths
            )

        if not files:
            raise RuntimeError(f"No Java source files selected for context in sandbox: {sandbox_root}")

        sections = []
        total_chars = 0

        for file_path in files:
            relative_path = file_path.relative_to(sandbox_root).as_posix()
            content = file_path.read_text(encoding="utf-8", errors="replace")

            section = (
                f"FILE: {relative_path}\n"
                f"{content}"
            )

            section_cost = len(section) + 8

            if sections and total_chars + section_cost > self.max_chars:
                logging.getLogger("agent_pipeline").warning(
                    "[SourceContext] Skipping %s (~%d chars): would exceed context budget of %d chars. "
                    "Context may be incomplete.",
                    relative_path, section_cost, self.max_chars
                )
                continue

            sections.append(section)
            total_chars += section_cost

        # If the selected file is larger than the budget, include it anyway.
        # Truncating Java source can make the model return broken full-file rewrites.
        if not sections:
            file_path = files[0]
            relative_path = file_path.relative_to(sandbox_root).as_posix()
            content = file_path.read_text(encoding="utf-8", errors="replace")
            sections.append(
                f"FILE: {relative_path}\n"
                f"{content}"
            )

        return "\n\n---\n\n".join(sections)

    def resolve_selected_files(self, sandbox_root, selected_paths, hidden_test_paths):
        files = []

        for selected_path in selected_paths:
            relative_path = Path(selected_path)

            if relative_path.is_absolute():
                raise RuntimeError(f"Selected context path must be relative: {selected_path}")

            if ".." in relative_path.parts:
                raise RuntimeError(f"Selected context path escapes sandbox: {selected_path}")

            path_text = relative_path.as_posix()

            if not (
                path_text.startswith("src/main/java/")
                or path_text.startswith("src/test/java/")
            ):
                raise RuntimeError(f"Selected context path is not a Java source/test path: {selected_path}")

            if not path_text.endswith(".java"):
                raise RuntimeError(f"Selected context path is not a Java file: {selected_path}")

            if path_text in hidden_test_paths:
                continue

            # Legacy safety fallback.
            if path_text.startswith("src/test/java/") and "hidden" in relative_path.name.lower():
                continue

            absolute_path = (sandbox_root / relative_path).resolve()

            try:
                absolute_path.relative_to(sandbox_root)
            except ValueError as e:
                raise RuntimeError(f"Selected context path escapes sandbox: {selected_path}") from e

            if not absolute_path.exists():
                raise RuntimeError(f"Selected context file does not exist: {selected_path}")

            if not absolute_path.is_file():
                raise RuntimeError(f"Selected context path is not a file: {selected_path}")

            files.append(absolute_path)

        return files

    def collect_files(self, directory):
        directory = Path(directory)

        if not directory.exists():
            return []

        return sorted(
            path for path in directory.rglob("*.java")
            if path.is_file()
        )

    def collect_public_test_files(self, directory, sandbox_root, hidden_test_paths):
        directory = Path(directory)

        if not directory.exists():
            return []

        files = []

        for path in directory.rglob("*.java"):
            if not path.is_file():
                continue

            relative_path = path.relative_to(sandbox_root).as_posix()

            if relative_path in hidden_test_paths:
                continue

            # Legacy safety fallback.
            if "hidden" in path.name.lower():
                continue

            files.append(path)

        return sorted(files)

    @staticmethod
    def normalize_hidden_test_paths(hidden_test_paths):
        if hidden_test_paths is None:
            return set()

        return {
            str(path).replace("\\", "/")
            for path in hidden_test_paths
        }