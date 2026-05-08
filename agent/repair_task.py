from dataclasses import dataclass
from pathlib import Path

# dataclass for the repair task + format validity checks
@dataclass
class RepairTask:
    name: str
    task_dir: Path
    prompt: str
    project_dir: Path
    hidden_tests_dir: Path

    @staticmethod
    def load(task_dir):
        task_dir = Path(task_dir).resolve()

        if not task_dir.exists():
            raise RuntimeError(f"Repair task directory does not exist: {task_dir}")

        prompt_file = task_dir / "task.txt"
        project_dir = task_dir / "project"
        hidden_tests_dir = task_dir / "hidden_tests"

        if not prompt_file.exists():
            raise RuntimeError(f"Repair task is missing task.txt: {prompt_file}")

        if not project_dir.exists():
            raise RuntimeError(f"Repair task is missing project directory: {project_dir}")

        if not (project_dir / "pom.xml").exists():
            raise RuntimeError(f"Repair task project is missing pom.xml: {project_dir}")

        if not hidden_tests_dir.exists():
            raise RuntimeError(f"Repair task is missing hidden_tests directory: {hidden_tests_dir}")

        prompt = prompt_file.read_text(encoding="utf-8").strip()

        if not prompt:
            raise RuntimeError(f"Repair task prompt is empty: {prompt_file}")

        return RepairTask(
            name=task_dir.name,
            task_dir=task_dir,
            prompt=prompt,
            project_dir=project_dir,
            hidden_tests_dir=hidden_tests_dir
        )