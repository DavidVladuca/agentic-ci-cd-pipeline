from pathlib import Path # just to not use string paths everywhere
import subprocess
import os
import time

# isolates Maven execution   
# controller.py should not know how subprocesses work, just if Maven passed or failed
class MavenResult:
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


class MavenRunner:
    def __init__(self, project_root, timeout_seconds=15):
        self.project_root = Path(project_root)
        self.timeout_seconds = timeout_seconds # to prevent infinite loops

    # run "mvn clean test" and return result
    def run_tests(self):
        if os.name == "nt": # windows needs mvn.cmd, not mvn
            command = ["mvn.cmd", "clean", "test"]
        else:
            command = ["mvn", "clean", "test"]

        start_time = time.perf_counter()

        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root, # from where to run
                capture_output=True,
                text=True, # response as string, not bytes
                encoding="utf-8",
                errors="replace", # if characters cant be decoded, replace with [bad byte], not crash
                timeout=self.timeout_seconds
            )

            duration_seconds = time.perf_counter() - start_time

            return MavenResult(
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
                duration_seconds=duration_seconds
            )

        # if timeout, we get here and return exit_code -1 (not normal mvn failure, but timeout)
        except subprocess.TimeoutExpired as e:
            duration_seconds = time.perf_counter() - start_time

            return MavenResult(
                exit_code=-1,
                stdout=self.to_text(e.stdout),
                stderr=self.to_text(e.stderr),
                timed_out=True,
                duration_seconds=duration_seconds
            )

    # timeout can be sometimes not a string, so we make it a text to be sure
    @staticmethod
    def to_text(value):
        if value is None:
            return ""

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        return str(value)