from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class JavaFileInfo:
    relative_path: str
    absolute_path: Path
    kind: str
    content: str
    package_name: str | None
    class_names: list[str]
    method_names: list[str]
    imports: list[str]
    size_chars: int


@dataclass
class ProjectAnalysis:
    sandbox_root: Path
    files: list[JavaFileInfo]
    production_files: list[JavaFileInfo]
    public_test_files: list[JavaFileInfo]
    by_path: dict[str, JavaFileInfo]
    by_class_name: dict[str, list[JavaFileInfo]]
    hidden_test_paths: set[str]


# scans a sandboxed Maven project and extracts metadata for file selection
class ProjectAnalyzer:
    CLASS_PATTERN = re.compile(
        r"\b(?:public\s+|protected\s+|private\s+|abstract\s+|final\s+|static\s+)*"
        r"(?:class|interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)"
    )

    PACKAGE_PATTERN = re.compile(
        r"^\s*package\s+([A-Za-z_][A-Za-z0-9_.]*);",
        re.MULTILINE
    )

    IMPORT_PATTERN = re.compile(
        r"^\s*import\s+(?:static\s+)?([A-Za-z_][A-Za-z0-9_.*]*);",
        re.MULTILINE
    )

    METHOD_PATTERN = re.compile(
        r"^\s*"
        r"(?:public|protected|private|static|final|synchronized|abstract|native|default\s+)*"
        r"[A-Za-z_][A-Za-z0-9_<>\[\], ?]*\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*"
        r"\([^;]*\)\s*"
        r"(?:throws\s+[A-Za-z0-9_.,\s]+)?"
        r"(?:\{|$)",
        re.MULTILINE
    )

    CONTROL_WORDS = {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "throw",
        "new",
        "assert",
        "assertEquals",
        "assertTrue",
        "assertFalse",
        "assertThrows",
        "assertNull",
        "assertNotNull"
    }

    def analyze(self, sandbox_root, hidden_test_paths=None):
        sandbox_root = Path(sandbox_root).resolve()
        hidden_test_paths = self.normalize_hidden_test_paths(hidden_test_paths)

        production_paths = self.collect_java_files(sandbox_root / "src" / "main" / "java")
        public_test_paths = self.collect_public_test_files(
            directory=sandbox_root / "src" / "test" / "java",
            sandbox_root=sandbox_root,
            hidden_test_paths=hidden_test_paths
        )

        production_files = [
            self.analyze_file(sandbox_root, path, "production")
            for path in production_paths
        ]

        public_test_files = [
            self.analyze_file(sandbox_root, path, "public_test")
            for path in public_test_paths
        ]

        files = production_files + public_test_files

        by_path = {}
        by_class_name = {}

        for file_info in files:
            by_path[file_info.relative_path] = file_info

            for class_name in file_info.class_names:
                by_class_name.setdefault(class_name, []).append(file_info)

        return ProjectAnalysis(
            sandbox_root=sandbox_root,
            files=files,
            production_files=production_files,
            public_test_files=public_test_files,
            by_path=by_path,
            by_class_name=by_class_name,
            hidden_test_paths=hidden_test_paths
        )

    def analyze_file(self, sandbox_root, file_path, kind):
        content = file_path.read_text(encoding="utf-8", errors="replace")
        relative_path = file_path.relative_to(sandbox_root).as_posix()

        return JavaFileInfo(
            relative_path=relative_path,
            absolute_path=file_path,
            kind=kind,
            content=content,
            package_name=self.extract_package(content),
            class_names=self.extract_class_names(content),
            method_names=self.extract_method_names(content),
            imports=self.extract_imports(content),
            size_chars=len(content)
        )

    def collect_java_files(self, directory):
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

            # just to be sure V1 still works
            if "hidden" in path.name.lower():
                continue

            files.append(path)

        return sorted(files)

    def extract_package(self, content):
        match = self.PACKAGE_PATTERN.search(content)

        if not match:
            return None

        return match.group(1)

    def extract_imports(self, content):
        return sorted(set(self.IMPORT_PATTERN.findall(content)))

    def extract_class_names(self, content):
        return sorted(set(self.CLASS_PATTERN.findall(content)))

    def extract_method_names(self, content):
        method_names = []

        for match in self.METHOD_PATTERN.finditer(content):
            name = match.group(1)

            if name in self.CONTROL_WORDS:
                continue

            method_names.append(name)

        return sorted(set(method_names))

    @staticmethod
    def normalize_hidden_test_paths(hidden_test_paths):
        if hidden_test_paths is None:
            return set()

        return {
            str(path).replace("\\", "/")
            for path in hidden_test_paths
        }