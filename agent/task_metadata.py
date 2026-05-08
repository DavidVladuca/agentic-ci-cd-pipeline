from dataclasses import dataclass
from pathlib import Path
import json


# metadata -> the type and difficulty of a repair task
@dataclass
class TaskMetadata:
    difficulty: str = "unknown"
    category: str = "unknown"
    description: str = ""
    expected_error_type: str | None = None

    @staticmethod
    def load(task_dir):
        task_dir = Path(task_dir)
        metadata_file = task_dir / "task.json"

        if not metadata_file.exists():
            return TaskMetadata()

        try:
            data = json.loads(metadata_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid task.json in {task_dir}: {e}") from e

        if not isinstance(data, dict):
            raise RuntimeError(f"task.json must contain a JSON object: {metadata_file}")

        difficulty = data.get("difficulty", "unknown")
        category = data.get("category", "unknown")
        description = data.get("description", "")
        expected_error_type = data.get("expected_error_type")

        if not isinstance(difficulty, str):
            raise RuntimeError(f"task.json difficulty must be a string: {metadata_file}")

        if not isinstance(category, str):
            raise RuntimeError(f"task.json category must be a string: {metadata_file}")

        if not isinstance(description, str):
            raise RuntimeError(f"task.json description must be a string: {metadata_file}")

        if expected_error_type is not None and not isinstance(expected_error_type, str):
            raise RuntimeError(f"task.json expected_error_type must be a string or null: {metadata_file}")

        return TaskMetadata(
            difficulty=difficulty.strip() or "unknown",
            category=category.strip() or "unknown",
            description=description.strip(),
            expected_error_type=expected_error_type.strip() if isinstance(expected_error_type, str) else None
        )