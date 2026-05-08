from pathlib import Path

from agent.logger_config import setup_logger
from agent.repair_cli import parse_repair_cli_args
from agent.repair_pipeline import RepairPipeline


# This is the V2 single task repair controller
# RepairPipeline does the actual repair loop!!!
def main(argv=None):
    args = parse_repair_cli_args(argv)

    # __file__ = path of current file (repair_controller.py), resolve() = absolute path
    project_root = Path(__file__).resolve().parents[1]

    # if path is wrong, kill it imediatly
    if not (project_root / "pom.xml").exists():
        raise RuntimeError(f"Could not find pom.xml at project root: {project_root}")

    # setup logger
    logger, log_file = setup_logger(project_root)

    logger.info("[REPAIR] Starting single-task repair run")
    logger.info("[REPAIR] Project root: %s", project_root)
    logger.info("[REPAIR] Task dir: %s", args.task_dir)
    logger.info("[REPAIR] Model: %s", args.model)
    logger.info("[REPAIR] Max attempts: %s", args.max_attempts)
    logger.info("[REPAIR] Docker image: %s", args.docker_image)
    logger.info("[REPAIR] Docker/Maven timeout: %s seconds", args.timeout)
    logger.info("[REPAIR] Log file: %s", log_file)

    pipeline = RepairPipeline(
        project_root=project_root,
        logger=logger,
        log_file=log_file,
        model=args.model,
        max_attempts=args.max_attempts,
        docker_image=args.docker_image,
        timeout_seconds=args.timeout
    )

    result = pipeline.run_task(args.task_dir)

    logger.info("[REPAIR] Single-task result: %s", result.final_status)


if __name__ == "__main__":
    main()