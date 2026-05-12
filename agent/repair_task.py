from dataclasses import dataclass
from pathlib import Path

from agent.task_metadata import TaskMetadata

# dataclass for the repair task + format validity checks
@dataclass
class RepairTask:
    name: str
    task_dir: Path
    prompt: str
    project_dir: Path
    hidden_tests_dir: Path | None
    metadata: TaskMetadata  

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

        metadata = TaskMetadata.load(task_dir)

        return RepairTask(
            name=task_dir.name,
            task_dir=task_dir,
            prompt=prompt,
            project_dir=project_dir,
            hidden_tests_dir=hidden_tests_dir,
            metadata=metadata
        )

    # build a repair task directly from a Maven project directory
    @staticmethod
    def from_project(project_dir, task_file, hidden_tests_dir=None, name=None):
        project_dir = Path(project_dir).resolve()
        task_file = Path(task_file).resolve()

        if not project_dir.exists():
            raise RuntimeError(f"Project directory does not exist: {project_dir}")

        if not project_dir.is_dir():
            raise RuntimeError(f"Project path is not a directory: {project_dir}")

        if not (project_dir / "pom.xml").exists():
            raise RuntimeError(f"Project directory is missing pom.xml: {project_dir}")

        if not task_file.exists():
            raise RuntimeError(f"Task file does not exist: {task_file}")

        prompt = task_file.read_text(encoding="utf-8").strip()

        if not prompt:
            raise RuntimeError(f"Task file is empty: {task_file}")

        resolved_hidden_tests_dir = None

        if hidden_tests_dir is not None:
            resolved_hidden_tests_dir = Path(hidden_tests_dir).resolve()

            if not resolved_hidden_tests_dir.exists():
                raise RuntimeError(f"Hidden tests directory does not exist: {resolved_hidden_tests_dir}")

            if not resolved_hidden_tests_dir.is_dir():
                raise RuntimeError(f"Hidden tests path is not a directory: {resolved_hidden_tests_dir}")

        if name is None:
            task_name = project_dir.name
        else:
            task_name = name.strip()

            if not task_name:
                raise RuntimeError("Task name must not be empty.")

        metadata = TaskMetadata(
            difficulty="real-project",
            category="external-project",
            description=f"Real project repair task from {project_dir}",
            expected_error_type=None
        )

        return RepairTask(
            name=task_name,
            task_dir=project_dir,
            prompt=prompt,
            project_dir=project_dir,
            hidden_tests_dir=resolved_hidden_tests_dir,
            metadata=metadata
        )