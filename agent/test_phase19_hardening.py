import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent.error_extractor import ErrorExtractor
from agent.file_rewriter import FileRewriter
from agent.project_analyzer import ProjectAnalyzer
from agent.project_sandbox import ProjectSandbox
from agent.source_context import SourceContextBuilder


class Phase19HardeningTests(unittest.TestCase):
    def write_file(self, root, relative_path, content):
        path = Path(root) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_file_rewriter_validates_all_files_before_mutating_anything(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.write_file(
                root,
                "src/main/java/App.java",
                "public class App { public int value() { return 1; } }\n"
            )

            rewriter = FileRewriter(root)

            with self.assertRaises(RuntimeError):
                rewriter.apply_files([
                    {
                        "path": "src/main/java/App.java",
                        "content": "public class App { public int value() { return 2; } }\n"
                    },
                    {
                        "path": "src/test/java/AppTest.java",
                        "content": "public class AppTest {}\n"
                    }
                ])

            content = (root / "src/main/java/App.java").read_text(encoding="utf-8")
            self.assertIn("return 1", content)
            self.assertNotIn("return 2", content)

    def test_file_rewriter_restores_backups_if_write_fails_mid_attempt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.write_file(
                root,
                "src/main/java/App.java",
                "public class App { public int value() { return 1; } }\n"
            )
            self.write_file(
                root,
                "src/main/java/Other.java",
                "public class Other { public int value() { return 10; } }\n"
            )

            rewriter = FileRewriter(root)
            original_write_file_safely = rewriter.write_file_safely

            def failing_write(target_path, content):
                if target_path.name == "Other.java":
                    raise OSError("simulated write failure")

                original_write_file_safely(target_path, content)

            rewriter.write_file_safely = failing_write

            with self.assertRaises(RuntimeError):
                rewriter.apply_files([
                    {
                        "path": "src/main/java/App.java",
                        "content": "public class App { public int value() { return 2; } }\n"
                    },
                    {
                        "path": "src/main/java/Other.java",
                        "content": "public class Other { public int value() { return 20; } }\n"
                    }
                ])

            app_content = (root / "src/main/java/App.java").read_text(encoding="utf-8")
            other_content = (root / "src/main/java/Other.java").read_text(encoding="utf-8")

            self.assertIn("return 1", app_content)
            self.assertIn("return 10", other_content)
            self.assertNotIn("return 2", app_content)
            self.assertNotIn("return 20", other_content)

    def test_source_context_excludes_hidden_tests_by_tracked_path_not_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.write_file(
                root,
                "src/main/java/App.java",
                "public class App { public int value() { return 1; } }\n"
            )
            self.write_file(
                root,
                "src/test/java/AppTest.java",
                "public class AppTest {}\n"
            )
            self.write_file(
                root,
                "src/test/java/AppEdgeCaseTest.java",
                "public class AppEdgeCaseTest {}\n"
            )

            builder = SourceContextBuilder()

            context = builder.build(
                sandbox_root=root,
                hidden_test_paths={"src/test/java/AppEdgeCaseTest.java"}
            )

            self.assertIn("FILE: src/main/java/App.java", context)
            self.assertIn("FILE: src/test/java/AppTest.java", context)
            self.assertNotIn("AppEdgeCaseTest", context)

    def test_source_context_selected_paths_excludes_hidden_tests_by_tracked_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.write_file(
                root,
                "src/main/java/App.java",
                "public class App { public int value() { return 1; } }\n"
            )
            self.write_file(
                root,
                "src/test/java/AppEdgeCaseTest.java",
                "public class AppEdgeCaseTest {}\n"
            )

            builder = SourceContextBuilder()

            context = builder.build(
                sandbox_root=root,
                selected_paths=[
                    "src/main/java/App.java",
                    "src/test/java/AppEdgeCaseTest.java"
                ],
                hidden_test_paths={"src/test/java/AppEdgeCaseTest.java"}
            )

            self.assertIn("FILE: src/main/java/App.java", context)
            self.assertNotIn("AppEdgeCaseTest", context)

    def test_project_analyzer_excludes_hidden_tests_by_tracked_path_not_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.write_file(
                root,
                "src/main/java/App.java",
                "public class App { public int value() { return 1; } }\n"
            )
            self.write_file(
                root,
                "src/test/java/AppTest.java",
                "public class AppTest {}\n"
            )
            self.write_file(
                root,
                "src/test/java/AppEdgeCaseTest.java",
                "public class AppEdgeCaseTest {}\n"
            )

            analyzer = ProjectAnalyzer()

            analysis = analyzer.analyze(
                sandbox_root=root,
                hidden_test_paths={"src/test/java/AppEdgeCaseTest.java"}
            )

            public_test_paths = [
                file_info.relative_path
                for file_info in analysis.public_test_files
            ]

            self.assertIn("src/test/java/AppTest.java", public_test_paths)
            self.assertNotIn("src/test/java/AppEdgeCaseTest.java", public_test_paths)

    def test_project_sandbox_tracks_injected_hidden_test_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_project = root / "source_project"
            hidden_tests = root / "hidden_tests"
            agent_root = root / "agent_root"

            self.write_file(source_project, "pom.xml", "<project></project>\n")
            self.write_file(
                source_project,
                "src/main/java/App.java",
                "public class App {}\n"
            )
            self.write_file(
                hidden_tests,
                "src/test/java/AppEdgeCaseTest.java",
                "public class AppEdgeCaseTest {}\n"
            )

            repair_task = SimpleNamespace(
                name="sample_task",
                project_dir=source_project,
                hidden_tests_dir=hidden_tests
            )

            sandbox = ProjectSandbox(agent_root)
            result = sandbox.prepare_task(repair_task)

            self.assertIn(
                "src/test/java/AppEdgeCaseTest.java",
                result.hidden_test_paths
            )
            self.assertTrue(
                (result.sandbox_root / "src/test/java/AppEdgeCaseTest.java").exists()
            )

    def test_error_extractor_uses_configured_timeout_seconds(self):
        summary = ErrorExtractor.extract_errors(
            raw_output="[INFO] Running tests\n",
            timed_out=True,
            timeout_seconds=30
        )

        self.assertIn("Maven timed out after 30 seconds.", summary)
        self.assertNotIn("15 seconds", summary)


if __name__ == "__main__":
    unittest.main()