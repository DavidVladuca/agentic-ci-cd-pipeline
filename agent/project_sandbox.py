from dataclasses import dataclass
from pathlib import Path
import logging
import shutil


@dataclass
class ProjectSandboxResult:
    sandbox_root: Path
    hidden_test_paths: set[str]


# copies the broken Java project into the repair sandbox
# and then injects hidden tests if they exist
class ProjectSandbox:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.base_dir = self.project_root / ".sandbox" / "repair_workspace"

        self.ignored_project_names = {
            ".git",
            "target",
            ".idea",
            ".vscode",
            "__pycache__",
            ".pytest_cache",
            "logs",
            "reports",
            "artifacts",
            ".sandbox"
        }

    def prepare_task(self, repair_task):
        sandbox_root = self.base_dir / repair_task.name

        if sandbox_root.exists():
            logging.getLogger("agent_pipeline").info("[Sandbox] Removing existing sandbox: %s", sandbox_root)
            shutil.rmtree(sandbox_root)

        shutil.copytree(
            repair_task.project_dir,
            sandbox_root,
            ignore=self.ignore_project_noise
        )

        hidden_test_paths = set()

        if repair_task.hidden_tests_dir is not None:
            hidden_test_paths = self.copy_tree_contents(
                source_dir=repair_task.hidden_tests_dir,
                target_dir=sandbox_root
            )

        return ProjectSandboxResult(
            sandbox_root=sandbox_root,
            hidden_test_paths=hidden_test_paths
        )

    def ignore_project_noise(self, directory, names):
        ignored = set()

        for name in names:
            if name in self.ignored_project_names:
                ignored.add(name)

        return ignored

    def copy_tree_contents(self, source_dir, target_dir):
        source_dir = Path(source_dir)
        target_dir = Path(target_dir)

        copied_paths = set()

        for source_path in source_dir.rglob("*"):
            relative_path = source_path.relative_to(source_dir)
            target_path = target_dir / relative_path

            if source_path.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            if target_path.exists(): 
                raise RuntimeError(
                    "Hidden test injection would overwrite an existing project file: "
                    f"{target_path.relative_to(target_dir).as_posix()}"
                )

            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

            copied_paths.add(target_path.relative_to(target_dir).as_posix())

        return copied_paths