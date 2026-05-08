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
            "average_seconds_per_task": self.average(total_seconds, total_tasks),
            "average_repair_attempts": self.average(
                sum(result.repair_attempts for result in results),
                total_tasks
            ),
            "by_difficulty": self.group_stats(results, "difficulty"),
            "by_category": self.group_stats(results, "category"),
            "tasks": [
                self.task_to_dict(result)
                for result in results
            ]
        }

    def task_to_dict(self, result):
        return {
            "task_name": result.task_name,
            "task_dir": result.task_dir,
            "difficulty": result.difficulty,
            "category": result.category,
            "description": result.description,
            "expected_error_type": result.expected_error_type,
            "baseline_status": result.baseline_status,
            "baseline_error_type": result.baseline_error_type,
            "final_status": result.final_status,
            "solved": result.solved,
            "repair_attempts": result.repair_attempts,
            "total_seconds": result.total_seconds,
            "final_error_type": result.final_error_type,
            "summary_file": result.summary_file,
            "log_file": result.log_file,
            "artifact_dir": result.artifact_dir,
            "final_patch_file": result.final_patch_file,
            "changed_files": result.changed_files,
            "patch_files": result.patch_files
        }

    def group_stats(self, results, field_name):
        groups = {}

        for result in results:
            key = getattr(result, field_name)

            if key not in groups:
                groups[key] = {
                    "total_tasks": 0,
                    "solved_tasks": 0,
                    "failed_tasks": 0,
                    "pass_rate": 0.0,
                    "total_seconds": 0.0
                }

            groups[key]["total_tasks"] += 1
            groups[key]["total_seconds"] += result.total_seconds

            if result.solved:
                groups[key]["solved_tasks"] += 1
            else:
                groups[key]["failed_tasks"] += 1

        for key, value in groups.items():
            value["total_seconds"] = round(value["total_seconds"], 3)
            value["pass_rate"] = self.average(
                value["solved_tasks"],
                value["total_tasks"]
            )

        return groups

    def write_csv(self, csv_file, results):
        with csv_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            writer.writerow([
                "task_name",
                "task_dir",
                "difficulty",
                "category",
                "expected_error_type",
                "baseline_status",
                "baseline_error_type",
                "final_status",
                "solved",
                "repair_attempts",
                "total_seconds",
                "final_error_type",
                "summary_file",
                "log_file",
                "artifact_dir",
                "final_patch_file",
                "changed_files",
                "patch_files"
            ])

            for result in results:
                writer.writerow([
                    result.task_name,
                    result.task_dir,
                    result.difficulty,
                    result.category,
                    result.expected_error_type,
                    result.baseline_status,
                    result.baseline_error_type,
                    result.final_status,
                    result.solved,
                    result.repair_attempts,
                    result.total_seconds,
                    result.final_error_type,
                    result.summary_file,
                    result.log_file,
                    result.artifact_dir,
                    result.final_patch_file,
                    ";".join(result.changed_files),
                    ";".join(result.patch_files)
                ])

    @staticmethod
    def average(total, count):
        if count == 0:
            return 0.0

        return round(total / count, 3)