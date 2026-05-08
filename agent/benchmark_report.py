from pathlib import Path
from datetime import datetime
import csv
import json

# writes aggregate benchmark for all repair tasks
class BenchmarkReportWriter:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def write(self, results, config):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = self.reports_dir / f"repair_benchmark_{timestamp}.json"
        csv_file = self.reports_dir / f"repair_benchmark_{timestamp}.csv"

        data = self.build_report_data(results, config)

        json_file.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8"
        )

        self.write_csv(csv_file, results)

        return json_file, csv_file

    def build_report_data(self, results, config):
        total_tasks = len(results)
        solved_tasks = sum(1 for result in results if result.solved)
        failed_tasks = total_tasks - solved_tasks

        if total_tasks == 0:
            pass_rate = 0.0
        else:
            pass_rate = solved_tasks / total_tasks

        total_seconds = sum(result.total_seconds for result in results)

        return {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "model": config["model"],
            "max_attempts": config["max_attempts"],
            "docker_image": config["docker_image"],
            "timeout_seconds": config["timeout_seconds"],
            "total_tasks": total_tasks,
            "solved_tasks": solved_tasks,
            "failed_tasks": failed_tasks,
            "pass_rate": round(pass_rate, 3),
            "total_seconds": round(total_seconds, 3),
            "tasks": [
                {
                    "task_name": result.task_name,
                    "task_dir": result.task_dir,
                    "final_status": result.final_status,
                    "solved": result.solved,
                    "repair_attempts": result.repair_attempts,
                    "total_seconds": result.total_seconds,
                    "final_error_type": result.final_error_type,
                    "summary_file": result.summary_file,
                    "log_file": result.log_file
                }
                for result in results
            ]
        }

    def write_csv(self, csv_file, results):
        with csv_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            writer.writerow([
                "task_name",
                "task_dir",
                "final_status",
                "solved",
                "repair_attempts",
                "total_seconds",
                "final_error_type",
                "summary_file",
                "log_file"
            ])

            for result in results:
                writer.writerow([
                    result.task_name,
                    result.task_dir,
                    result.final_status,
                    result.solved,
                    result.repair_attempts,
                    result.total_seconds,
                    result.final_error_type,
                    result.summary_file,
                    result.log_file
                ])