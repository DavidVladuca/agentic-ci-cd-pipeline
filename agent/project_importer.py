from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from datetime import datetime
import re
import shutil
import stat
import subprocess
import zipfile


@dataclass
class ProjectImportResult:
    source_type: str
    source: str
    import_root: Path | None
    project_dir: Path
    run_name: str


# imports local folders, zip files, or GitHub repos into a safe local Maven project directory
class ProjectImporter:
    def __init__(
        self,
        project_root,
        max_zip_bytes=200 * 1024 * 1024,
        max_zip_members=5000,
        git_timeout_seconds=120
    ):
        self.project_root = Path(project_root).resolve()
        self.imports_root = self.project_root / ".sandbox" / "imports"
        self.imports_root.mkdir(parents=True, exist_ok=True)

        self.max_zip_bytes = max_zip_bytes
        self.max_zip_members = max_zip_members
        self.git_timeout_seconds = git_timeout_seconds

        self.ignored_names = {
            ".git",
            "target",
            "__pycache__",
            ".pytest_cache",
            ".idea",
            ".vscode",
            ".DS_Store",
            "__MACOSX"
        }

    def import_project(self, project_dir=None, zip_file=None, git_url=None, name=None):
        selected_sources = [
            value is not None
            for value in [project_dir, zip_file, git_url]
        ]

        if sum(selected_sources) != 1:
            raise RuntimeError(
                "Exactly one project input must be provided: --project-dir, --zip, or --git-url."
            )

        if project_dir is not None:
            return self.import_local_project(project_dir, name)

        if zip_file is not None:
            return self.import_zip_project(zip_file, name)

        return self.import_git_project(git_url, name)

    def import_local_project(self, project_dir, name=None):
        project_dir = self.validate_project_dir(project_dir)
        run_name = self.safe_name(name or project_dir.name)

        return ProjectImportResult(
            source_type="local",
            source=str(project_dir),
            import_root=None,
            project_dir=project_dir,
            run_name=run_name
        )

    def import_zip_project(self, zip_file, name=None):
        zip_path = Path(zip_file).resolve()

        if not zip_path.exists():
            raise RuntimeError(f"Zip file does not exist: {zip_path}")

        if not zip_path.is_file():
            raise RuntimeError(f"Zip path is not a file: {zip_path}")

        if zip_path.suffix.lower() != ".zip":
            raise RuntimeError(f"Expected a .zip file, got: {zip_path}")

        run_name = self.safe_name(name or zip_path.stem)
        import_root = self.create_import_root("zip", run_name)

        self.extract_zip_safely(zip_path, import_root)

        project_dir = self.find_maven_project_root(import_root)

        return ProjectImportResult(
            source_type="zip",
            source=str(zip_path),
            import_root=import_root,
            project_dir=project_dir,
            run_name=run_name
        )

    def import_git_project(self, git_url, name=None):
        self.validate_github_url(git_url)

        repo_name = self.repo_name_from_url(git_url)
        run_name = self.safe_name(name or repo_name)
        import_root = self.create_import_root("git", run_name)

        command = [
            "git",
            "clone",
            "--depth",
            "1",
            git_url,
            str(import_root)
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.git_timeout_seconds
            )
        except FileNotFoundError as e:
            raise RuntimeError("Git executable not found. Install Git and make sure it is on PATH.") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Git clone timed out after {self.git_timeout_seconds} seconds.") from e

        if completed.returncode != 0:
            raise RuntimeError(
                "Git clone failed.\n"
                f"STDOUT:\n{completed.stdout}\n"
                f"STDERR:\n{completed.stderr}"
            )

        git_dir = import_root / ".git"
        self.remove_tree_allowing_readonly(git_dir)

        project_dir = self.find_maven_project_root(import_root)

        return ProjectImportResult(
            source_type="git",
            source=git_url,
            import_root=import_root,
            project_dir=project_dir,
            run_name=run_name
        )

    def extract_zip_safely(self, zip_path, import_root):
        total_uncompressed_bytes = 0
        extracted_members = 0

        try:
            archive = zipfile.ZipFile(zip_path)
        except zipfile.BadZipFile as e:
            raise RuntimeError(f"Invalid zip file: {zip_path}") from e

        with archive:
            for zip_info in archive.infolist():
                relative_path = self.safe_zip_member_path(zip_info)

                if relative_path is None:
                    continue

                if self.is_zip_symlink(zip_info):
                    raise RuntimeError(f"Refusing to extract zip symlink: {zip_info.filename}")

                if zip_info.is_dir():
                    continue

                extracted_members += 1
                if extracted_members > self.max_zip_members:
                    raise RuntimeError(
                        f"Zip has too many files. Limit is {self.max_zip_members} extracted files."
                    )

                total_uncompressed_bytes += zip_info.file_size
                if total_uncompressed_bytes > self.max_zip_bytes:
                    raise RuntimeError(
                        f"Zip is too large after extraction. Limit is {self.max_zip_bytes} bytes."
                    )

                target_path = (import_root / relative_path).resolve()

                try:
                    target_path.relative_to(import_root.resolve())
                except ValueError as e:
                    raise RuntimeError(f"Zip member escapes import directory: {zip_info.filename}") from e

                if target_path.exists():
                    raise RuntimeError(f"Zip contains duplicate target path: {relative_path}")

                target_path.parent.mkdir(parents=True, exist_ok=True)

                with archive.open(zip_info) as source_file:
                    with target_path.open("wb") as target_file:
                        shutil.copyfileobj(source_file, target_file)

    def safe_zip_member_path(self, zip_info):
        raw_name = zip_info.filename.replace("\\", "/").strip()

        if not raw_name:
            return None

        pure_path = PurePosixPath(raw_name)

        if pure_path.is_absolute():
            raise RuntimeError(f"Zip contains absolute path: {zip_info.filename}")

        parts = pure_path.parts

        if not parts:
            return None

        if any(part == ".." for part in parts):
            raise RuntimeError(f"Zip contains parent-directory escape: {zip_info.filename}")

        if ":" in parts[0]:
            raise RuntimeError(f"Zip contains drive-like path: {zip_info.filename}")

        if any(part in self.ignored_names for part in parts):
            return None

        return Path(*parts)

    def find_maven_project_root(self, root_dir):
        root_dir = Path(root_dir).resolve()

        if (root_dir / "pom.xml").exists():
            return root_dir

        pom_files = []

        for pom_file in root_dir.rglob("pom.xml"):
            relative_parts = pom_file.relative_to(root_dir).parts

            if any(part in self.ignored_names for part in relative_parts):
                continue

            pom_files.append(pom_file)

        if not pom_files:
            raise RuntimeError(f"No Maven pom.xml found under imported project: {root_dir}")

        candidates = sorted(
            (pom_file.parent for pom_file in pom_files),
            key=lambda path: (len(path.relative_to(root_dir).parts), str(path))
        )

        shallowest_depth = len(candidates[0].relative_to(root_dir).parts)
        shallowest_candidates = [
            candidate for candidate in candidates
            if len(candidate.relative_to(root_dir).parts) == shallowest_depth
        ]

        if len(shallowest_candidates) > 1:
            formatted = "\n".join(str(candidate) for candidate in shallowest_candidates)
            raise RuntimeError(
                "Multiple Maven project roots found at the same depth. "
                "Pass a more specific project directory instead.\n"
                f"{formatted}"
            )

        return shallowest_candidates[0]

    def validate_project_dir(self, project_dir):
        project_dir = Path(project_dir).resolve()

        if not project_dir.exists():
            raise RuntimeError(f"Project directory does not exist: {project_dir}")

        if not project_dir.is_dir():
            raise RuntimeError(f"Project path is not a directory: {project_dir}")

        if not (project_dir / "pom.xml").exists():
            raise RuntimeError(f"Project directory is missing pom.xml: {project_dir}")

        return project_dir

    def create_import_root(self, source_type, run_name):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        import_root = self.imports_root / f"{timestamp}_{source_type}_{run_name}"
        import_root.mkdir(parents=True, exist_ok=False)
        return import_root

    def validate_github_url(self, git_url):
        if not isinstance(git_url, str):
            raise RuntimeError("Git URL must be a string.")

        git_url = git_url.strip()

        if not git_url:
            raise RuntimeError("Git URL must not be empty.")

        if any(char.isspace() for char in git_url):
            raise RuntimeError(f"Git URL must not contain whitespace: {git_url}")

        if not git_url.startswith("https://github.com/"):
            raise RuntimeError(
                "Phase 16 only supports HTTPS GitHub URLs, for example: "
                "https://github.com/user/repo.git"
            )

        parts = git_url.removeprefix("https://github.com/").strip("/").split("/")

        if len(parts) < 2:
            raise RuntimeError(f"GitHub URL must include owner and repo: {git_url}")

    def repo_name_from_url(self, git_url):
        cleaned = git_url.rstrip("/")
        repo_name = cleaned.split("/")[-1]

        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        return self.safe_name(repo_name)

    @staticmethod
    def is_zip_symlink(zip_info):
        file_type = (zip_info.external_attr >> 16) & 0o170000
        return file_type == stat.S_IFLNK
    
    # better windows file delition
    # (Windows Git files can be read-only, so we chmod everything first, then delete the directory tree)
    def remove_tree_allowing_readonly(self, path):
        path = Path(path)

        if not path.exists():
            return

        for child in sorted(path.rglob("*"), reverse=True):
            try:
                child.chmod(stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass

        try:
            path.chmod(stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass

        try:
            shutil.rmtree(path)
        except PermissionError as e:
            raise RuntimeError(
                "Failed to remove cloned .git directory. "
                "On Windows this is usually caused by read-only Git pack files "
                "or another process temporarily holding the files. "
                f"Path: {path}"
            ) from e

    @staticmethod
    def safe_name(value):
        text = str(value or "").strip()

        if not text:
            text = "project"

        text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
        text = text.strip("._-")

        if not text:
            text = "project"

        return text[:80]