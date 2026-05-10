from pathlib import Path
from datetime import datetime
import csv
import json


# writes aggregate benchmark reports for all repair tasks
class BenchmarkReportWriter:
    def __init__(self, project_root):
        self.project_root = Path(project_root).resolve()
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def write(self, results, config):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        json_file = self.reports_dir / f"repair_benchmark_{timestamp}.json"
        csv_file = self.reports_dir / f"repair_benchmark_{timestamp}.csv"
        markdown_file = self.reports_dir / f"repair_report_{timestamp}.md"

        data = self.build_report_data(results, config)

        json_file.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8"
        )

        self.write_csv(csv_file, results)
        self.write_markdown(
            markdown_file=markdown_file,
            data=data,
            json_file=json_file,
            csv_file=csv_file
        )

        return {
            "json": json_file,
            "csv": csv_file,
            "markdown": markdown_file
        }

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

    def write_markdown(self, markdown_file, data, json_file, csv_file):
        lines = []

        lines.append("# Java Repair Benchmark Report")
        lines.append("")
        lines.append(f"Generated at: `{data['created_at']}`")
        lines.append("")

        self.append_run_configuration(lines, data)
        self.append_summary(lines, data)
        self.append_group_section(lines, "Results by Difficulty", data["by_difficulty"])
        self.append_group_section(lines, "Results by Category", data["by_category"])
        self.append_task_table(lines, data["tasks"])
        self.append_failed_tasks(lines, data["tasks"])
        self.append_changed_files(lines, data["tasks"])
        self.append_artifacts(lines, markdown_file, json_file, csv_file)

        markdown_file.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8"
        )

    def append_run_configuration(self, lines, data):
        lines.append("## Run Configuration")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        lines.append(f"| Model | {self.md_cell(data['model'])} |")
        lines.append(f"| Max attempts | {self.md_cell(data['max_attempts'])} |")
        lines.append(f"| Docker image | {self.md_cell(data['docker_image'])} |")
        lines.append(f"| Timeout seconds | {self.md_cell(data['timeout_seconds'])} |")
        lines.append("")

    def append_summary(self, lines, data):
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---:|")
        lines.append(f"| Total tasks | {data['total_tasks']} |")
        lines.append(f"| Solved tasks | {data['solved_tasks']} |")
        lines.append(f"| Failed tasks | {data['failed_tasks']} |")
        lines.append(f"| Pass rate | {self.percent(data['pass_rate'])} |")
        lines.append(f"| Total runtime | {data['total_seconds']:.3f}s |")
        lines.append(f"| Average runtime per task | {data['average_seconds_per_task']:.3f}s |")
        lines.append(f"| Average repair attempts | {data['average_repair_attempts']:.3f} |")
        lines.append("")

    def append_group_section(self, lines, title, groups):
        lines.append(f"## {title}")
        lines.append("")

        if not groups:
            lines.append("No data.")
            lines.append("")
            return

        lines.append("| Group | Total | Solved | Failed | Pass Rate | Total Seconds |")
        lines.append("|---|---:|---:|---:|---:|---:|")

        for group_name in sorted(groups.keys()):
            group = groups[group_name]

            lines.append(
                "| "
                f"{self.md_cell(group_name)} | "
                f"{group['total_tasks']} | "
                f"{group['solved_tasks']} | "
                f"{group['failed_tasks']} | "
                f"{self.percent(group['pass_rate'])} | "
                f"{group['total_seconds']:.3f}s |"
            )

        lines.append("")

    def append_task_table(self, lines, tasks):
        lines.append("## Task Results")
        lines.append("")

        if not tasks:
            lines.append("No tasks were executed.")
            lines.append("")
            return

        lines.append(
            "| Task | Result | Difficulty | Category | Baseline Error | "
            "Final Status | Attempts | Seconds | Changed Files | Final Patch |"
        )
        lines.append(
            "|---|---|---|---|---|---|---:|---:|---|---|"
        )

        for task in tasks:
            result = "PASS" if task["solved"] else "FAIL"
            changed_files = self.inline_file_list(task["changed_files"])
            final_patch = self.inline_path(task["final_patch_file"])

            lines.append(
                "| "
                f"{self.md_cell(task['task_name'])} | "
                f"{result} | "
                f"{self.md_cell(task['difficulty'])} | "
                f"{self.md_cell(task['category'])} | "
                f"{self.md_cell(task['baseline_error_type'])} | "
                f"{self.md_cell(task['final_status'])} | "
                f"{task['repair_attempts']} | "
                f"{task['total_seconds']:.3f}s | "
                f"{changed_files} | "
                f"{final_patch} |"
            )

        lines.append("")

    def append_failed_tasks(self, lines, tasks):
        failed_tasks = [task for task in tasks if not task["solved"]]

        lines.append("## Failed Tasks")
        lines.append("")

        if not failed_tasks:
            lines.append("No failed tasks.")
            lines.append("")
            return

        for task in failed_tasks:
            lines.append(f"### {task['task_name']}")
            lines.append("")
            lines.append(f"- Final status: `{task['final_status']}`")
            lines.append(f"- Final error type: `{task['final_error_type']}`")
            lines.append(f"- Baseline error type: `{task['baseline_error_type']}`")
            lines.append(f"- Summary file: {self.inline_path(task['summary_file'])}")
            lines.append(f"- Log file: {self.inline_path(task['log_file'])}")
            lines.append(f"- Artifact directory: {self.inline_path(task['artifact_dir'])}")
            lines.append("")

    def append_changed_files(self, lines, tasks):
        lines.append("## Changed Files")
        lines.append("")

        any_changed_files = False

        for task in tasks:
            changed_files = task["changed_files"]

            if not changed_files:
                continue

            any_changed_files = True

            lines.append(f"### {task['task_name']}")
            lines.append("")

            for changed_file in changed_files:
                lines.append(f"- `{changed_file}`")

            lines.append("")

        if not any_changed_files:
            lines.append("No production files were changed.")
            lines.append("")

    def append_artifacts(self, lines, markdown_file, json_file, csv_file):
        lines.append("## Report Artifacts")
        lines.append("")
        lines.append(f"- Markdown report: {self.inline_path(markdown_file)}")
        lines.append(f"- JSON report: {self.inline_path(json_file)}")
        lines.append(f"- CSV report: {self.inline_path(csv_file)}")
        lines.append("")

    def display_path(self, path_value):
        if path_value is None:
            return ""

        if str(path_value).strip() == "":
            return ""

        path = Path(path_value)

        try:
            return path.resolve().relative_to(self.project_root).as_posix()
        except (ValueError, OSError):
            return str(path_value).replace("\\", "/")

    def inline_path(self, path_value):
        display = self.display_path(path_value)

        if not display:
            return "-"

        return f"`{self.escape_backticks(display)}`"

    def inline_file_list(self, files):
        if not files:
            return "-"

        return ", ".join(
            f"`{self.escape_backticks(file_path)}`"
            for file_path in files
        )

    @staticmethod
    def md_cell(value):
        if value is None:
            return "-"

        text = str(value)

        if not text.strip():
            return "-"

        text = text.replace("\n", "<br>")
        text = text.replace("|", "\\|")

        return text

    @staticmethod
    def escape_backticks(value):
        return str(value).replace("`", "'")

    @staticmethod
    def percent(value):
        return f"{value * 100:.1f}%"

    @staticmethod
    def average(total, count):
        if count == 0:
            return 0.0

        return round(total / count, 3)