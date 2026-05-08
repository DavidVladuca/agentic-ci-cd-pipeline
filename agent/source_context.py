from pathlib import Path

# reads source files from the repair sandbox and builds context for the LLM
# hidden test source files are not included
class SourceContextBuilder:
    def __init__(self, max_chars=12000):
        self.max_chars = max_chars

    # make one combined context string from sandbox files
    def build(self, sandbox_root):
        sandbox_root = Path(sandbox_root)
        files = []

        files.extend(self.collect_files(sandbox_root / "src" / "main" / "java"))
        files.extend(self.collect_public_test_files(sandbox_root / "src" / "test" / "java"))

        if not files:
            raise RuntimeError(f"No Java source files found in sandbox: {sandbox_root}")

        sections = []

        for file_path in files:
            relative_path = file_path.relative_to(sandbox_root).as_posix()
            content = file_path.read_text(encoding="utf-8", errors="replace")

            sections.append(
                f"FILE: {relative_path}\n"
                f"{content}"
            )

        context = "\n\n---\n\n".join(sections)

        if len(context) > self.max_chars:
            context = context[-self.max_chars:]

        return context

    def collect_files(self, directory):
        directory = Path(directory)

        if not directory.exists():
            return []

        return sorted(
            path for path in directory.rglob("*.java")
            if path.is_file()
        )

    def collect_public_test_files(self, directory):
        directory = Path(directory)

        if not directory.exists():
            return []

        files = []

        for path in directory.rglob("*.java"):
            if not path.is_file():
                continue

            name = path.name.lower()

            if "hidden" in name:
                continue

            files.append(path)

        return sorted(files)