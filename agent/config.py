from dataclasses import dataclass # for simple configuration class

DEFAULT_MODEL = "agent-coder"
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_DOCKER_IMAGE = "agent-pipeline-java"
DEFAULT_DOCKER_TIMEOUT_SECONDS = 30
DEFAULT_DEPENDENCY_TIMEOUT_SECONDS = 180

DEFAULT_TASK_PROMPT = """
Create a Java class App with a static method add(int a, int b) that returns the sum.
Create a JUnit 5 test class AppTest that verifies the add method.
""".strip()

@dataclass
class AgentConfig:
    # added type checks and defaults
    task_prompt: str = DEFAULT_TASK_PROMPT
    model: str = DEFAULT_MODEL
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    docker_image: str = DEFAULT_DOCKER_IMAGE
    docker_timeout_seconds: int = DEFAULT_DOCKER_TIMEOUT_SECONDS