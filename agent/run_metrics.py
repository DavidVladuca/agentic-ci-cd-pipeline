from pathlib import Path
from datetime import datetime
import json
import time

# collects run metrics, and writes a summary at the end
class RunMetrics:
    def __init__(self, task_prompt, max_attempts):
        self.task_prompt = task_prompt
        self.max_attempts = max_attempts
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.run_start = time.perf_counter()
        self.final_status = "RUNNING"
        self.total_seconds = None
        self.attempts = []

    def add_attempt(
        self,
        attempt,
        status,
        llm_seconds=0.0,
        workspace_seconds=0.0,
        maven_seconds=0.0,
        attempt_seconds=0.0,
        exit_code=None,
        error_type=None,
        error_summary=None
    ):
        self.attempts.append({
            "attempt": attempt,
            "status": status,
            "llm_seconds": round(llm_seconds, 3),
            "workspace_seconds": round(workspace_seconds, 3),
            "maven_seconds": round(maven_seconds, 3),
            "attempt_seconds": round(attempt_seconds, 3),
            "exit_code": exit_code,
            "error_type": error_type,
            "error_summary": self.shorten(error_summary)
        })

    def finish(self, final_status):
        self.final_status = final_status
        self.total_seconds = round(time.perf_counter() - self.run_start, 3)
    
    def to_dict(self, log_file=None):
        return {
            "started_at": self.started_at,
            "final_status": self.final_status,
            "total_seconds": self.total_seconds,
            "max_attempts": self.max_attempts,
            "task_prompt": self.task_prompt,
            "log_file": str(log_file) if log_file else None,
            "attempts": self.attempts
        }

    def write_summary(self, project_root, log_file=None):
        logs_dir = Path(project_root) / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # microseconds prevent filename collisions during benchmark runs!!!
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        summary_file = logs_dir / f"run_summary_{timestamp}.json"

        summary_file.write_text(
            json.dumps(self.to_dict(log_file), indent=2),
            encoding="utf-8"
        )

        return summary_file

    @staticmethod
    def shorten(text, max_chars=2000):
        if text is None:
            return None

        if len(text) <= max_chars:
            return text

        return text[-max_chars:]