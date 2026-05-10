from pathlib import Path
from datetime import datetime


# writes a human-readable Markdown report for one project repair run
class ProjectRepairReportWriter:
    def __init__(self, project_root):
        self.project_root = Path(project_root).resolve()
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def write(self, repair_result, import_result, config):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"project_repair_report_{timestamp}.md"

        lines = []

        lines.append("# Java Project Repair Report")
        lines.append("")
        lines.append(f"Generated at: `{datetime.now().isoformat(timespec='seconds')}`")
        lines.append("")

        self.append_source_section(lines, import_result)
        self.append_configuration_section(lines, config)
        self.append_result_summary(lines, repair_result)
        self.append_changed_files(lines, repair_result)
        self.append_artifacts(lines, repair_result, report_file)
        self.append_failure_details(lines, repair_result)

        report_file.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8"
        )

        return report_file

    def append_source_section(self, lines, import_result):
        lines.append("## Project Source")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        lines.append(f"| Source type | {self.md_cell(import_result.source_type)} |")
        lines.append(f"| Source | {self.inline_path_or_text(import_result.source)} |")
        lines.append(f"| Import root | {self.inline_path(import_result.import_root)} |")
        lines.append(f"| Maven project dir | {self.inline_path(import_result.project_dir)} |")
        lines.append(f"| Repair run name | {self.md_cell(import_result.run_name)} |")
        lines.append("")

    def append_configuration_section(self, lines, config):
        lines.append("## Run Configuration")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        lines.append(f"| Model | {self.md_cell(config['model'])} |")
        lines.append(f"| Max attempts | {self.md_cell(config['max_attempts'])} |")
        lines.append(f"| Docker image | {self.md_cell(config['docker_image'])} |")
        lines.append(f"| Timeout seconds | {self.md_cell(config['timeout_seconds'])} |")
        lines.append("")

    def append_result_summary(self, lines, repair_result):
        lines.append("## Result Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(f"| Task name | {self.md_cell(repair_result.task_name)} |")
        lines.append(f"| Final status | {self.md_cell(repair_result.final_status)} |")
        lines.append(f"| Solved | {self.md_cell(repair_result.solved)} |")
        lines.append(f"| Baseline status | {self.md_cell(repair_result.baseline_status)} |")
        lines.append(f"| Baseline error type | {self.md_cell(repair_result.baseline_error_type)} |")
        lines.append(f"| Final error type | {self.md_cell(repair_result.final_error_type)} |")
        lines.append(f"| Repair attempts | {self.md_cell(repair_result.repair_attempts)} |")
        lines.append(f"| Total seconds | {repair_result.total_seconds:.3f}s |")
        lines.append(f"| Difficulty | {self.md_cell(repair_result.difficulty)} |")
        lines.append(f"| Category | {self.md_cell(repair_result.category)} |")
        lines.append("")

    def append_changed_files(self, lines, repair_result):
        lines.append("## Changed Files")
        lines.append("")

        if not repair_result.changed_files:
            lines.append("No production files were changed.")
            lines.append("")
            return

        for changed_file in repair_result.changed_files:
            lines.append(f"- `{self.escape_backticks(changed_file)}`")

        lines.append("")

    def append_artifacts(self, lines, repair_result, report_file):
        lines.append("## Artifacts")
        lines.append("")
        lines.append(f"- Markdown report: {self.inline_path(report_file)}")
        lines.append(f"- Final patch file: {self.inline_path(repair_result.final_patch_file)}")
        lines.append(f"- Artifact directory: {self.inline_path(repair_result.artifact_dir)}")
        lines.append(f"- Run summary file: {self.inline_path(repair_result.summary_file)}")
        lines.append(f"- Log file: {self.inline_path(repair_result.log_file)}")

        if repair_result.patch_files:
            lines.append("- Attempt patches:")

            for patch_file in repair_result.patch_files:
                lines.append(f"  - {self.inline_path(patch_file)}")

        lines.append("")

    def append_failure_details(self, lines, repair_result):
        if repair_result.solved:
            return

        lines.append("## Failure Details")
        lines.append("")
        lines.append(f"- Final status: `{self.escape_backticks(repair_result.final_status)}`")
        lines.append(f"- Final error type: `{self.escape_backticks(repair_result.final_error_type)}`")
        lines.append(f"- Baseline error type: `{self.escape_backticks(repair_result.baseline_error_type)}`")
        lines.append("")
        lines.append(
            "For detailed failure output, inspect the run summary file and log file listed above."
        )
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

    def inline_path_or_text(self, value):
        if value is None:
            return "-"

        text = str(value)

        if text.startswith("http://") or text.startswith("https://"):
            return self.md_cell(text)

        return self.inline_path(text)

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
        if value is None:
            return "-"

        return str(value).replace("`", "'")