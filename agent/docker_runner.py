from pathlib import Path
import subprocess
import time

# runs Maven inside Docker
# controller.py should not execute generated Java directly on the host machine
class DockerResult:
    def __init__(self, exit_code, stdout, stderr, timed_out, duration_seconds=0.0):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        self.duration_seconds = duration_seconds

    @property
    def success(self):
        return self.exit_code == 0 and not self.timed_out

    @property
    def combined_output(self):
        return (self.stdout or "") + "\n" + (self.stderr or "")


class DockerRunner:
    def __init__(self, sandbox_root, image_name="agent-pipeline-java", timeout_seconds=30):
        self.sandbox_root = Path(sandbox_root).resolve()
        self.image_name = image_name
        self.timeout_seconds = timeout_seconds # higher timeout on Dockersince they are slower 

    # run "mvn -o clean test" inside Docker and return result
    # added -o so that it stays offline and doesn't download anything
    def run_tests(self):
        command = [
            "docker",
            "run",
            "--rm",
            "--network", "none",
            "--memory", "1g",
            "--cpus", "1.0",
            "-v", f"{self.sandbox_root}:/workspace",
            "-w", "/workspace",
            self.image_name,
            "mvn",
            "-o",
            "clean",
            "test"
        ]

        start_time = time.perf_counter()

        try:
            completed = subprocess.run(
                command,
                cwd=self.sandbox_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds
            )

            duration_seconds = time.perf_counter() - start_time

            return DockerResult(
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
                duration_seconds=duration_seconds
            )

        except subprocess.TimeoutExpired as e:
            duration_seconds = time.perf_counter() - start_time

            return DockerResult(
                exit_code=-1,
                stdout=self.to_text(e.stdout),
                stderr=self.to_text(e.stderr),
                timed_out=True,
                duration_seconds=duration_seconds
            )

        except FileNotFoundError as e:
            duration_seconds = time.perf_counter() - start_time

            return DockerResult(
                exit_code=-1,
                stdout="",
                stderr=f"Docker executable not found. Is Docker installed and running?\n{e}",
                timed_out=False,
                duration_seconds=duration_seconds
            )

    # timeout output can be sometimes not a string, so we make it a text to be sure
    @staticmethod
    def to_text(value):
        if value is None:
            return ""

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        return str(value)