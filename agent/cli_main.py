from pathlib import Path
import argparse
import sys

from agent.config import (
    DEFAULT_MODEL,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_DOCKER_TIMEOUT_SECONDS,
    DEFAULT_DEPENDENCY_TIMEOUT_SECONDS
)
from agent.doctor import Doctor


def build_parser():
    parser = argparse.ArgumentParser(
        description="Local Docker-sandboxed Java repair agent."
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    add_doctor_parser(subparsers)
    add_benchmark_parser(subparsers)
    add_repair_task_parser(subparsers)
    add_repair_project_parser(subparsers)

    return parser


def add_common_runtime_args(parser):
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


def add_doctor_parser(subparsers):
    parser = subparsers.add_parser(
        "doctor",
        help="Check whether the local repair-agent environment is ready."
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model name to check. Default: {DEFAULT_MODEL}"
    )

    parser.add_argument(
        "--docker-image",
        default=DEFAULT_DOCKER_IMAGE,
        help=f"Docker image to check. Default: {DEFAULT_DOCKER_IMAGE}"
    )

    parser.set_defaults(handler=handle_doctor)


def add_benchmark_parser(subparsers):
    parser = subparsers.add_parser(
        "benchmark",
        help="Run the repair benchmark suite."
    )

    parser.add_argument(
        "--tasks-dir",
        required=True,
        help="Directory containing repair task folders, for example bug_tasks."
    )

    add_common_runtime_args(parser)
    parser.set_defaults(handler=handle_benchmark)


def add_repair_task_parser(subparsers):
    parser = subparsers.add_parser(
        "repair-task",
        help="Run one benchmark-style repair task."
    )

    parser.add_argument(
        "--task-dir",
        required=True,
        help="Path to a repair task directory, for example bug_tasks/off_by_one_sum."
    )

    add_common_runtime_args(parser)
    parser.set_defaults(handler=handle_repair_task)


def add_repair_project_parser(subparsers):
    parser = subparsers.add_parser(
        "repair-project",
        help="Repair a Java Maven project from a local folder, zip, or GitHub URL."
    )

    input_group = parser.add_mutually_exclusive_group(required=True)

    input_group.add_argument(
        "--project-dir",
        default=None,
        help="Path to a local Maven project directory to repair."
    )

    input_group.add_argument(
        "--zip",
        dest="zip_file",
        default=None,
        help="Path to a zip file containing a Maven project."
    )

    input_group.add_argument(
        "--git-url",
        default=None,
        help="HTTPS GitHub repository URL to clone and repair."
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
        help="Optional repair run name. Defaults to the project/repo/zip name."
    )

    parser.add_argument(
        "--prepare-deps",
        action="store_true",
        help=(
            "Run online Maven dependency prefetch before offline repair attempts. "
            "Use this for real Maven projects with dependencies not already cached."
        )
    )

    parser.add_argument(
        "--dependency-timeout",
        type=int,
        default=DEFAULT_DEPENDENCY_TIMEOUT_SECONDS,
        help=f"Dependency prefetch timeout in seconds. Default: {DEFAULT_DEPENDENCY_TIMEOUT_SECONDS}"
    )

    add_common_runtime_args(parser)
    parser.set_defaults(handler=handle_repair_project)


def handle_doctor(args):
    project_root = find_project_root()

    doctor = Doctor(
        project_root=project_root,
        docker_image=args.docker_image,
        model=args.model
    )

    checks = doctor.run_all()

    print("")
    print("Local SWE Team doctor")
    print("=====================")
    print(f"Project root: {project_root}")
    print("")

    failed_required = False

    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")

        if check.required and not check.passed:
            failed_required = True

    print("")

    if failed_required:
        print("Doctor result: FAILED")
        return 1

    print("Doctor result: OK")
    return 0


def handle_benchmark(args):
    from agent.repair_benchmark import main as benchmark_main

    argv = [
        "--tasks-dir", args.tasks_dir,
        "--model", args.model,
        "--max-attempts", str(args.max_attempts),
        "--docker-image", args.docker_image,
        "--timeout", str(args.timeout)
    ]

    benchmark_main(argv)
    return 0


def handle_repair_task(args):
    from agent.repair_controller import main as repair_task_main

    argv = [
        "--task-dir", args.task_dir,
        "--model", args.model,
        "--max-attempts", str(args.max_attempts),
        "--docker-image", args.docker_image,
        "--timeout", str(args.timeout)
    ]

    repair_task_main(argv)
    return 0


def handle_repair_project(args):
    from agent.repair_project import main as repair_project_main

    argv = [
        "--task-file", args.task_file,
        "--model", args.model,
        "--max-attempts", str(args.max_attempts),
        "--docker-image", args.docker_image,
        "--timeout", str(args.timeout),
        "--dependency-timeout", str(args.dependency_timeout)
    ]

    if args.project_dir is not None:
        argv.extend(["--project-dir", args.project_dir])

    if args.zip_file is not None:
        argv.extend(["--zip", args.zip_file])

    if args.git_url is not None:
        argv.extend(["--git-url", args.git_url])

    if args.hidden_tests_dir is not None:
        argv.extend(["--hidden-tests-dir", args.hidden_tests_dir])

    if args.name is not None:
        argv.extend(["--name", args.name])

    if args.prepare_deps:
        argv.append("--prepare-deps")

    repair_project_main(argv)
    return 0


def find_project_root():
    project_root = Path(__file__).resolve().parents[1]

    if not (project_root / "pom.xml").exists():
        raise RuntimeError(f"Could not find agent project root pom.xml: {project_root}")

    return project_root


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if hasattr(args, "dependency_timeout") and args.dependency_timeout < 1:
        parser.error("--dependency-timeout must be at least 1")

    if hasattr(args, "max_attempts") and args.max_attempts < 1:
        parser.error("--max-attempts must be at least 1")

    if hasattr(args, "timeout") and args.timeout < 1:
        parser.error("--timeout must be at least 1")

    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))