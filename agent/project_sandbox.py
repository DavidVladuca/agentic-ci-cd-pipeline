from pathlib import Path
import shutil

# copies the broken Java project into the repair sandbox
# and then inject hidden tests
class ProjectSandbox:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.base_dir = self.project_root / ".sandbox" / "repair_workspace"

    def prepare_task(self, repair_task):
        sandbox_root = self.base_dir / repair_task.name

        if sandbox_root.exists():
            shutil.rmtree(sandbox_root)

        shutil.copytree(repair_task.project_dir, sandbox_root)

        self.copy_tree_contents(
            source_dir=repair_task.hidden_tests_dir,
            target_dir=sandbox_root
        )

        return sandbox_root

    def copy_tree_contents(self, source_dir, target_dir):
        source_dir = Path(source_dir)
        target_dir = Path(target_dir)

        for source_path in source_dir.rglob("*"):
            relative_path = source_path.relative_to(source_dir)
            target_path = target_dir / relative_path

            if source_path.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)