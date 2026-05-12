from pathlib import Path
import subprocess
import time


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

# executes Maven and JUnit builds inside sandbox
# has strict resource and network constraints!!!
class DockerRunner:
    def __init__(
        self,
        sandbox_root,
        image_name="agent-pipeline-java",
        timeout_seconds=30,
        maven_repo_host_dir=None,
        offline=True,
        network_enabled=False
    ):
        self.sandbox_root = Path(sandbox_root).resolve()
        self.image_name = image_name
        self.timeout_seconds = timeout_seconds

        self.maven_repo_host_dir = (
            Path(maven_repo_host_dir).resolve()
            if maven_repo_host_dir is not None
            else None
        )

        self.offline = offline
        self.network_enabled = network_enabled

        # sandbox policy
        self.container_user = "10001:10001"
        self.memory_limit = "1g"
        self.cpu_limit = "1.0"
        self.pids_limit = "128"
        self.tmpfs_limit = "128m"

        # default image-preloaded repo used by benchmark tasks
        self.image_maven_repo = "/home/agent/.m2/repository"

        # project-specific mounted repo used by dependency-prefetch mode
        self.mounted_maven_repo = "/maven-repo"

    def run_tests(self):
        return self.run_maven(
            maven_args=["clean", "test"],
            offline=self.offline,
            network_enabled=self.network_enabled
        )

    def run_dependency_prefetch(self):
        if self.maven_repo_host_dir is None:
            raise RuntimeError("Dependency prefetch requires a host-mounted Maven repository.")

        return self.run_maven(
            maven_args=["-B", "dependency:go-offline"],
            offline=False,
            network_enabled=True
        )

    def run_maven(self, maven_args, offline=None, network_enabled=None):
        if offline is None:
            offline = self.offline

        if network_enabled is None:
            network_enabled = self.network_enabled

        command = self.build_base_command(network_enabled=network_enabled)

        command.append(self.image_name)
        command.append("mvn")

        if offline:
            command.append("-o")

        command.append(f"-Dmaven.repo.local={self.maven_repo_container_path()}")
        command.extend(maven_args)

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

    def build_base_command(self, network_enabled):
        command = [
            "docker",
            "run",
            "--rm",
        ]

        if network_enabled:
            command.extend(["--network", "bridge"])
        else:
            command.extend(["--network", "none"])

        command.extend([
            "--memory", self.memory_limit,
            "--memory-swap", self.memory_limit,
            "--cpus", self.cpu_limit,
            "--pids-limit", self.pids_limit,

            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",

            "--read-only",

            "--tmpfs", f"/tmp:rw,nosuid,nodev,exec,size={self.tmpfs_limit}",

            "--user", self.container_user,

            "-e", "HOME=/tmp",
            "-e", "MAVEN_CONFIG=/tmp/.m2",
            "-e", "MAVEN_OPTS=-Dstyle.color=never",
        ])

        if self.maven_repo_host_dir is not None:
            self.maven_repo_host_dir.mkdir(parents=True, exist_ok=True)
            command.extend([
                "-v", f"{self.maven_repo_host_dir}:/maven-repo:rw"
            ])

        command.extend([
            "-v", f"{self.sandbox_root}:/workspace:rw",
            "-w", "/workspace",
        ])

        return command

    def maven_repo_container_path(self):
        if self.maven_repo_host_dir is not None:
            return self.mounted_maven_repo

        return self.image_maven_repo

    def describe_security_policy(self):
        return {
            "network": "bridge" if self.network_enabled else "none",
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
            "maven_repo_host_dir": str(self.maven_repo_host_dir) if self.maven_repo_host_dir else None,
            "maven_repo_container": self.maven_repo_container_path(),
            "offline": self.offline
        }

    @staticmethod
    def to_text(value):
        if value is None:
            return ""

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        return str(value)