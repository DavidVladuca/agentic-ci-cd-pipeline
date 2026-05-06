from pathlib import Path # just to not use string paths everywhere
import subprocess
import os

# This isolates Maven execution.    
# The orchestrator should not know how subprocesses work. It should only care whether Maven passed or failed.
class MavenResult:
    def __init__(self, exit_code, stdout, stderr, timed_out):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out

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
        try:
            command = ["mvn.cmd", "clean", "test"] if os.name == "nt" else ["mvn", "clean", "test"]
            completed = subprocess.run(
                command,
                cwd=self.project_root, # from where to run
                capture_output=True,
                text=True, # response as string, not bytes
                encoding="utf-8",
                errors="replace", # if characters cant be decoded, replace with [bad byte], not crash
                timeout=self.timeout_seconds
            )

            return MavenResult(
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False
            )

        # if timeout, we get here and return exit_code -1 (not normal mvn failure, but timeout)
        except subprocess.TimeoutExpired as e:
            return MavenResult(
                exit_code=-1,
                stdout=e.stdout or "",
                stderr=e.stderr or "",
                timed_out=True
            )