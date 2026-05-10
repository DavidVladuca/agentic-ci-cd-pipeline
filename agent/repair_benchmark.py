from pathlib import Path
import argparse

from agent.benchmark_report import BenchmarkReportWriter
from agent.config import (
    DEFAULT_MODEL,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_DOCKER_TIMEOUT_SECONDS
)
from agent.logger_config import setup_logger
from agent.repair_pipeline import RepairPipeline, RepairRunResult


# parses commandline arguments for benchmark mode
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the Java repair agent across a suite of repair tasks."
    )

    parser.add_argument(
        "--tasks-dir",
        required=True,
        help="Directory containing repair task folders, for example bug_tasks."
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
        help=f"Maximum repair attempts per task. Default: {DEFAULT_MAX_ATTEMPTS}"
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


# finds valid repair task directories 
def discover_task_dirs(tasks_dir):
    tasks_dir = Path(tasks_dir).resolve()

    if not tasks_dir.exists():
        raise RuntimeError(f"Tasks directory does not exist: {tasks_dir}")

    task_dirs = []

    for child in sorted(tasks_dir.iterdir()):
        if not child.is_dir():
            continue

        if (
            (child / "task.txt").exists()
            and (child / "project").exists()
            and (child / "hidden_tests").exists()
        ):
            task_dirs.append(child)

    if not task_dirs:
        raise RuntimeError(f"No repair tasks found in: {tasks_dir}")

    return task_dirs


# benchmark the task suite
def main(argv=None):
    args = parse_args(argv)

    # __file__ = path of current file (repair_benchmark.py), resolve() = absolute path
    project_root = Path(__file__).resolve().parents[1]

    # if path is wrong, kill it imediatly
    if not (project_root / "pom.xml").exists():
        raise RuntimeError(f"Could not find pom.xml at project root: {project_root}")

    # setup logger
    logger, log_file = setup_logger(project_root)

    logger.info("[BENCHMARK] Starting repair benchmark run")
    logger.info("[BENCHMARK] Project root: %s", project_root)
    logger.info("[BENCHMARK] Tasks dir: %s", args.tasks_dir)
    logger.info("[BENCHMARK] Model: %s", args.model)
    logger.info("[BENCHMARK] Max attempts per task: %s", args.max_attempts)
    logger.info("[BENCHMARK] Docker image: %s", args.docker_image)
    logger.info("[BENCHMARK] Docker/Maven timeout: %s seconds", args.timeout)
    logger.info("[BENCHMARK] Log file: %s", log_file)

    task_dirs = discover_task_dirs(args.tasks_dir)

    logger.info("[BENCHMARK] Found %s repair tasks", len(task_dirs))

    pipeline = RepairPipeline(
        project_root=project_root,
        logger=logger,
        log_file=log_file,
        model=args.model,
        max_attempts=args.max_attempts,
        docker_image=args.docker_image,
        timeout_seconds=args.timeout
    )

    results = []

    for index, task_dir in enumerate(task_dirs, start=1):
        logger.info("")
        logger.info("[BENCHMARK] Running task %s/%s: %s", index, len(task_dirs), task_dir.name)

        try:
            result = pipeline.run_task(task_dir)
            results.append(result)

            logger.info(
                "[BENCHMARK] Task result: %s | solved=%s | difficulty=%s | category=%s | attempts=%s | seconds=%.3f",
                result.final_status,
                result.solved,
                result.difficulty,
                result.category,
                result.repair_attempts,
                result.total_seconds
            )

        except RuntimeError as e:
            logger.error("[BENCHMARK] Task crashed before producing a normal result: %s", task_dir)
            logger.error(str(e))

            results.append(
                RepairRunResult(
                    task_name=task_dir.name,
                    task_dir=str(task_dir),
                    difficulty="unknown",
                    category="unknown",
                    description="Task crashed before metadata could be loaded.",
                    expected_error_type=None,
                    baseline_status="TASK_CRASHED",
                    baseline_error_type="TASK_CRASHED",
                    final_status="TASK_CRASHED",
                    solved=False,
                    total_seconds=0.0,
                    repair_attempts=0,
                    final_error_type="TASK_CRASHED",
                    summary_file="",
                    log_file=str(log_file),
                    artifact_dir="",
                    final_patch_file=None,
                    changed_files=[],
                    patch_files=[]
                )
            )

            continue

    report_writer = BenchmarkReportWriter(project_root)

    report_files = report_writer.write(
        results=results,
        config={
            "model": args.model,
            "max_attempts": args.max_attempts,
            "docker_image": args.docker_image,
            "timeout_seconds": args.timeout
        }
    )

    solved = sum(1 for result in results if result.solved)
    total = len(results)

    logger.info("")
    logger.info("[BENCHMARK] Finished benchmark")
    logger.info("[BENCHMARK] Solved: %s/%s", solved, total)

    if total == 0:
        logger.info("[BENCHMARK] Pass rate: 0.000")
    else:
        logger.info("[BENCHMARK] Pass rate: %.3f", solved / total)

    logger.info("[BENCHMARK] JSON report: %s", report_files["json"])
    logger.info("[BENCHMARK] CSV report: %s", report_files["csv"])
    logger.info("[BENCHMARK] Markdown report: %s", report_files["markdown"])


if __name__ == "__main__":
    main()