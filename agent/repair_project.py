from pathlib import Path
import argparse

from agent.config import (
    DEFAULT_MODEL,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_DOCKER_TIMEOUT_SECONDS
)
from agent.logger_config import setup_logger
from agent.repair_pipeline import RepairPipeline
from agent.repair_task import RepairTask


# parses commandline arguments for real-project repair mode
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Repair an arbitrary Java Maven project using the local repair agent."
    )

    parser.add_argument(
        "--project-dir",
        required=True,
        help="Path to the Maven project directory to repair."
    )

    parser.add_argument(
        "--task-file",
        required=True,
        help="Path to a text file describing the bug or repair task."
    )

    parser.add_argument(
        "--hidden-tests-dir",
        default=None,
        help="Optional directory containing hidden tests to inject into the project."
    )

    parser.add_argument(
        "--name",
        default=None,
        help="Optional repair run name. Defaults to the project directory name."
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model name. Default: {DEFAULT_MODEL}"
    )

    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=f"Maximum repair attempts. Default: {DEFAULT_MAX_ATTEMPTS}"
    )

    parser.add_argument(
        "--docker-image",
        default=DEFAULT_DOCKER_IMAGE,
        help=f"Docker image used to run Maven/JUnit. Default: {DEFAULT_DOCKER_IMAGE}"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_DOCKER_TIMEOUT_SECONDS,
        help=f"Docker/Maven timeout in seconds. Default: {DEFAULT_DOCKER_TIMEOUT_SECONDS}"
    )

    args = parser.parse_args(argv)

    if args.max_attempts < 1:
        parser.error("--max-attempts must be at least 1")

    if args.timeout < 1:
        parser.error("--timeout must be at least 1")

    return args


# real-project repair entry point
def main(argv=None):
    args = parse_args(argv)

    # __file__ = path of current file (repair_project.py), resolve() = absolute path
    project_root = Path(__file__).resolve().parents[1]

    # if path is wrong, kill it imediatly
    if not (project_root / "pom.xml").exists():
        raise RuntimeError(f"Could not find agent project root pom.xml: {project_root}")

    # setup logger
    logger, log_file = setup_logger(project_root)

    logger.info("[PROJECT_REPAIR] Starting real-project repair run")
    logger.info("[PROJECT_REPAIR] Agent project root: %s", project_root)
    logger.info("[PROJECT_REPAIR] Target project dir: %s", args.project_dir)
    logger.info("[PROJECT_REPAIR] Task file: %s", args.task_file)
    logger.info("[PROJECT_REPAIR] Hidden tests dir: %s", args.hidden_tests_dir)
    logger.info("[PROJECT_REPAIR] Model: %s", args.model)
    logger.info("[PROJECT_REPAIR] Max attempts: %s", args.max_attempts)
    logger.info("[PROJECT_REPAIR] Docker image: %s", args.docker_image)
    logger.info("[PROJECT_REPAIR] Docker/Maven timeout: %s seconds", args.timeout)
    logger.info("[PROJECT_REPAIR] Log file: %s", log_file)

    repair_task = RepairTask.from_project(
        project_dir=args.project_dir,
        task_file=args.task_file,
        hidden_tests_dir=args.hidden_tests_dir,
        name=args.name
    )

    pipeline = RepairPipeline(
        project_root=project_root,
        logger=logger,
        log_file=log_file,
        model=args.model,
        max_attempts=args.max_attempts,
        docker_image=args.docker_image,
        timeout_seconds=args.timeout
    )

    result = pipeline.run_repair_task(repair_task)

    logger.info("[PROJECT_REPAIR] Result: %s", result.final_status)
    logger.info("[PROJECT_REPAIR] Solved: %s", result.solved)
    logger.info("[PROJECT_REPAIR] Artifact dir: %s", result.artifact_dir)


if __name__ == "__main__":
    main()