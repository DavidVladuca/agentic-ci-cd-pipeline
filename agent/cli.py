import argparse
from pathlib import Path

from agent.config import (
    AgentConfig,
    DEFAULT_TASK_PROMPT,
    DEFAULT_MODEL,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_DOCKER_TIMEOUT_SECONDS
)


# parses command-line arguments and turns them into an AgentConfig
def parse_cli_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the local Docker-sandboxed Java coding agent."
    )

    task_group = parser.add_mutually_exclusive_group()

    task_group.add_argument(
        "--task",
        type=str,
        help="Task prompt to send to the LLM."
    )

    task_group.add_argument(
        "--task-file",
        type=str,
        help="Path to a text file containing the task prompt."
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Ollama model name. Default: {DEFAULT_MODEL}"
    )

    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=f"Maximum retry attempts. Default: {DEFAULT_MAX_ATTEMPTS}"
    )

    parser.add_argument(
        "--docker-image",
        type=str,
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

    if args.task_file:
        task_path = Path(args.task_file)

        if not task_path.exists():
            parser.error(f"--task-file does not exist: {task_path}")

        task_prompt = task_path.read_text(encoding="utf-8").strip()

        if not task_prompt:
            parser.error(f"--task-file is empty: {task_path}")

    elif args.task:
        task_prompt = args.task.strip()

        if not task_prompt:
            parser.error("--task must not be empty")

    else:
        task_prompt = DEFAULT_TASK_PROMPT

    return AgentConfig(
        task_prompt=task_prompt,
        model=args.model,
        max_attempts=args.max_attempts,
        docker_image=args.docker_image,
        docker_timeout_seconds=args.timeout
    )