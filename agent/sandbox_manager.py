from pathlib import Path
import shutil # for file operations

# manages the sandbox workspace used by Docker
# generated code should be tested here, not in the real project root
class SandboxManager:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.sandbox_root = self.project_root / ".sandbox" / "java_workspace"

    def prepare(self):
        # clean sandbox directory
        if self.sandbox_root.exists():
            shutil.rmtree(self.sandbox_root)

        self.sandbox_root.mkdir(parents=True, exist_ok=True)

        source_pom = self.project_root / "pom.xml"
        target_pom = self.sandbox_root / "pom.xml"

        if not source_pom.exists():
            raise RuntimeError(f"Could not find pom.xml at project root: {self.project_root}")

        shutil.copy2(source_pom, target_pom)

        return self.sandbox_root 