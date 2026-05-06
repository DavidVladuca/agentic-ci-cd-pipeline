from pathlib import Path
import shutil

# The model may generate different code every time.
# If you do not wipe the folders first, old files can remain and create fake errors.
# That would make the agent debug the wrong problem.
class WorkspaceManager:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.main_dir = self.project_root / "src" / "main" / "java"
        self.test_dir = self.project_root / "src" / "test" / "java"

    def write_java_files(self, main_class, test_class):
        self.reset_directory(self.main_dir)
        self.reset_directory(self.test_dir)

        self.write_file(self.main_dir / "App.java", main_class)
        self.write_file(self.test_dir / "AppTest.java", test_class)

    def reset_directory(self, path):
        if path.exists():
            shutil.rmtree(path)

        path.mkdir(parents=True, exist_ok=True)

    def write_file(self, path, content):
        path.write_text(content, encoding="utf-8")