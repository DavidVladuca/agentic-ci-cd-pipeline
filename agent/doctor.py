from dataclasses import dataclass
from pathlib import Path
import json
import shutil
import subprocess
import urllib.error
import urllib.request


@dataclass
class DoctorCheck:
    name: str
    passed: bool
    detail: str
    required: bool = True


class Doctor:
    def __init__(
        self,
        project_root,
        docker_image="agent-pipeline-java",
        model="agent-coder",
        ollama_url="http://localhost:11434"
    ):
        self.project_root = Path(project_root).resolve()
        self.docker_image = docker_image
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")

    def run_all(self):
        checks = []

        checks.append(self.check_project_root())
        checks.append(self.check_pom())
        checks.append(self.check_docker_executable())
        checks.append(self.check_docker_daemon())
        checks.append(self.check_docker_image())
        checks.append(self.check_ollama_reachable())
        checks.append(self.check_ollama_model())

        return checks

    def check_project_root(self):
        if self.project_root.exists() and self.project_root.is_dir():
            return DoctorCheck(
                name="Project root",
                passed=True,
                detail=str(self.project_root)
            )

        return DoctorCheck(
            name="Project root",
            passed=False,
            detail=f"Project root does not exist or is not a directory: {self.project_root}"
        )

    def check_pom(self):
        pom_file = self.project_root / "pom.xml"

        if pom_file.exists() and pom_file.is_file():
            return DoctorCheck(
                name="pom.xml",
                passed=True,
                detail=str(pom_file)
            )

        return DoctorCheck(
            name="pom.xml",
            passed=False,
            detail=f"Missing pom.xml at project root: {pom_file}"
        )

    def check_docker_executable(self):
        docker_path = shutil.which("docker")

        if docker_path:
            return DoctorCheck(
                name="Docker executable",
                passed=True,
                detail=docker_path
            )

        return DoctorCheck(
            name="Docker executable",
            passed=False,
            detail="docker executable not found on PATH"
        )

    def check_docker_daemon(self):
        result = self.run_command(["docker", "info"], timeout_seconds=10)

        if result.returncode == 0:
            return DoctorCheck(
                name="Docker daemon",
                passed=True,
                detail="Docker daemon is reachable"
            )

        return DoctorCheck(
            name="Docker daemon",
            passed=False,
            detail=self.command_failure_detail(result)
        )

    def check_docker_image(self):
        result = self.run_command(
            ["docker", "image", "inspect", self.docker_image],
            timeout_seconds=10
        )

        if result.returncode == 0:
            return DoctorCheck(
                name="Docker image",
                passed=True,
                detail=f"Image exists: {self.docker_image}"
            )

        return DoctorCheck(
            name="Docker image",
            passed=False,
            detail=(
                f"Docker image not found: {self.docker_image}. "
                f"Build it with: docker build -t {self.docker_image} ."
            )
        )

    def check_ollama_reachable(self):
        try:
            self.read_ollama_tags()
            return DoctorCheck(
                name="Ollama API",
                passed=True,
                detail=f"Ollama reachable at {self.ollama_url}"
            )
        except RuntimeError as e:
            return DoctorCheck(
                name="Ollama API",
                passed=False,
                detail=str(e)
            )

    def check_ollama_model(self):
        try:
            tags = self.read_ollama_tags()
        except RuntimeError as e:
            return DoctorCheck(
                name="Ollama model",
                passed=False,
                detail=str(e)
            )

        models = tags.get("models", [])

        model_names = set()

        for model_info in models:
            name = model_info.get("name")

            if not name:
                continue

            model_names.add(name)
            model_names.add(name.split(":")[0])

        if self.model in model_names:
            return DoctorCheck(
                name="Ollama model",
                passed=True,
                detail=f"Model available: {self.model}"
            )

        available = sorted(model_names)

        return DoctorCheck(
            name="Ollama model",
            passed=False,
            detail=(
                f"Model not found: {self.model}. "
                f"Available models: {available}"
            )
        )

    def read_ollama_tags(self):
        url = f"{self.ollama_url}/api/tags"

        request = urllib.request.Request(
            url,
            method="GET"
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Could not reach Ollama at {url}: {e}") from e

        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ollama /api/tags returned invalid JSON: {body}") from e

        if not isinstance(data, dict):
            raise RuntimeError(f"Ollama /api/tags returned non-object JSON: {data}")

        return data

    def run_command(self, command, timeout_seconds):
        try:
            return subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds
            )
        except FileNotFoundError as e:
            return subprocess.CompletedProcess(
                args=command,
                returncode=-1,
                stdout="",
                stderr=str(e)
            )
        except subprocess.TimeoutExpired as e:
            return subprocess.CompletedProcess(
                args=command,
                returncode=-1,
                stdout=self.to_text(e.stdout),
                stderr=f"Command timed out after {timeout_seconds} seconds.\n{self.to_text(e.stderr)}"
            )

    @staticmethod
    def command_failure_detail(result):
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if stderr:
            return stderr

        if stdout:
            return stdout

        return f"Command failed with exit code {result.returncode}"

    @staticmethod
    def to_text(value):
        if value is None:
            return ""

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        return str(value)