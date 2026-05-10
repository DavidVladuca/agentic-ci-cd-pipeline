from dataclasses import dataclass
from pathlib import Path

from agent.project_importer import ProjectImporter, ProjectImportResult
from agent.project_repair_report import ProjectRepairReportWriter
from agent.repair_pipeline import RepairPipeline, RepairRunResult
from agent.repair_task import RepairTask


@dataclass
class ProjectRepairWorkflowResult:
    import_result: ProjectImportResult
    repair_result: RepairRunResult
    markdown_report: Path


# coordinates importing a project, running the repair pipeline, and writing the project report
class ProjectRepairWorkflow:
    def __init__(
        self,
        project_root,
        logger,
        log_file,
        model,
        max_attempts,
        docker_image,
        timeout_seconds
    ):
        self.project_root = Path(project_root).resolve()
        self.logger = logger
        self.log_file = log_file
        self.model = model
        self.max_attempts = max_attempts
        self.docker_image = docker_image
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        project_dir=None,
        zip_file=None,
        git_url=None,
        task_file=None,
        hidden_tests_dir=None,
        name=None
    ):
        importer = ProjectImporter(self.project_root)

        import_result = importer.import_project(
            project_dir=project_dir,
            zip_file=zip_file,
            git_url=git_url,
            name=name
        )

        self.logger.info("[PROJECT_REPAIR] Imported source type: %s", import_result.source_type)
        self.logger.info("[PROJECT_REPAIR] Imported source: %s", import_result.source)
        self.logger.info("[PROJECT_REPAIR] Import root: %s", import_result.import_root)
        self.logger.info("[PROJECT_REPAIR] Maven project dir: %s", import_result.project_dir)
        self.logger.info("[PROJECT_REPAIR] Repair run name: %s", import_result.run_name)

        repair_task = RepairTask.from_project(
            project_dir=import_result.project_dir,
            task_file=task_file,
            hidden_tests_dir=hidden_tests_dir,
            name=import_result.run_name
        )

        pipeline = RepairPipeline(
            project_root=self.project_root,
            logger=self.logger,
            log_file=self.log_file,
            model=self.model,
            max_attempts=self.max_attempts,
            docker_image=self.docker_image,
            timeout_seconds=self.timeout_seconds
        )

        repair_result = pipeline.run_repair_task(repair_task)

        report_writer = ProjectRepairReportWriter(self.project_root)

        markdown_report = report_writer.write(
            repair_result=repair_result,
            import_result=import_result,
            config={
                "model": self.model,
                "max_attempts": self.max_attempts,
                "docker_image": self.docker_image,
                "timeout_seconds": self.timeout_seconds
            }
        )

        return ProjectRepairWorkflowResult(
            import_result=import_result,
            repair_result=repair_result,
            markdown_report=markdown_report
        )