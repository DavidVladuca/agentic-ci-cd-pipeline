from pathlib import Path
import subprocess
import time

# runs Maven inside Docker
# controller.py should not execute generated or repaired Java directly on the host machine
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
        self.timeout_seconds = timeout_seconds # higher timeout on Docker since it is slower

        # sandbox policy
        self.container_user = "10001:10001"
        self.memory_limit = "1g"
        self.cpu_limit = "1.0"
        self.pids_limit = "128"
        self.tmpfs_limit = "128m"
        self.maven_repo = "/home/agent/.m2/repository"

    # run "mvn -o clean test" inside Docker and return result
    # added -o so that it stays offline and doesn't download anything
    def run_tests(self):
        command = [
            "docker",
            "run",
            "--rm",

            # no internet access from inside the test container
            "--network", "none",

            # resource limits
            "--memory", self.memory_limit,
            "--memory-swap", self.memory_limit,
            "--cpus", self.cpu_limit,
            "--pids-limit", self.pids_limit,

            # privilege limits
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",

            # make the container filesystem read-only
            # /workspace is still writable because it is a bind mount
            "--read-only",

            # provide a small writable temporary filesystem for Java/Maven temp usage
            "--tmpfs", f"/tmp:rw,nosuid,nodev,exec,size={self.tmpfs_limit}",

            # run as non-root
            "--user", self.container_user,

            # keep HOME away from /root
            "-e", "HOME=/tmp",
            "-e", "MAVEN_CONFIG=/tmp/.m2",
            "-e", "MAVEN_OPTS=-Dstyle.color=never",

            # mount only the sandbox workspace
            "-v", f"{self.sandbox_root}:/workspace:rw",
            "-w", "/workspace",

            self.image_name,

            "mvn",
            "-o",
            f"-Dmaven.repo.local={self.maven_repo}",
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

    # short text summary of the Docker sandbox policy
    def describe_security_policy(self):
        return {
            "network": "none",
            "user": self.container_user,
            "memory": self.memory_limit,
            "memory_swap": self.memory_limit,
            "cpus": self.cpu_limit,
            "pids_limit": self.pids_limit,
            "capabilities": "ALL dropped",
            "no_new_privileges": True,
            "read_only_root_filesystem": True,
            "tmpfs": f"/tmp rw,nosuid,nodev,exec,size={self.tmpfs_limit}",
            "workspace_mount": f"{self.sandbox_root}:/workspace:rw",
            "maven_repo": self.maven_repo
        }

    # timeout output can be sometimes not a string, so we make it a text to be sure
    @staticmethod
    def to_text(value):
        if value is None:
            return ""

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        return str(value)