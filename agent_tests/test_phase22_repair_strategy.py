import tempfile
import unittest
from pathlib import Path

from agent.diff_tracker import DiffTracker
from agent.repair_strategy import RepairStrategy

# unit tests for Phase 22 repair strategy behavior
# checks rollback decisions, repeated-error handling, context expansion and snapshot restore
class Phase22RepairStrategyTests(unittest.TestCase):
    def write_file(self, root, relative_path, content):
        path = Path(root) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_test_failure_means_project_compiled(self):
        self.assertTrue(
            RepairStrategy.error_type_means_project_compiled("TEST_FAILURE")
        )

    def test_compilation_error_triggers_rollback_when_compiling_snapshot_exists(self):
        self.assertTrue(
            RepairStrategy.should_rollback_compilation_regression(
                error_type="COMPILATION_ERROR",
                has_last_compiling_snapshot=True
            )
        )

    def test_compilation_error_does_not_trigger_rollback_without_snapshot(self):
        self.assertFalse(
            RepairStrategy.should_rollback_compilation_regression(
                error_type="COMPILATION_ERROR",
                has_last_compiling_snapshot=False
            )
        )

    def test_repeated_error_expands_context_once(self):
        decision = RepairStrategy.decide_after_maven_failure(
            error_type="TEST_FAILURE",
            repeated_count=1,
            context_already_expanded=False,
            has_last_compiling_snapshot=True
        )

        self.assertFalse(decision.should_stop)
        self.assertTrue(decision.should_expand_context)

    def test_repeated_error_after_expansion_continues_briefly(self):
        decision = RepairStrategy.decide_after_maven_failure(
            error_type="TEST_FAILURE",
            repeated_count=1,
            context_already_expanded=True,
            has_last_compiling_snapshot=True
        )

        self.assertFalse(decision.should_stop)
        self.assertFalse(decision.should_expand_context)

    def test_repeated_error_after_expansion_stops_at_threshold(self):
        decision = RepairStrategy.decide_after_maven_failure(
            error_type="TEST_FAILURE",
            repeated_count=3,
            context_already_expanded=True,
            has_last_compiling_snapshot=True
        )

        self.assertTrue(decision.should_stop)
        self.assertFalse(decision.should_expand_context)

    def test_restore_production_snapshot_restores_previous_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.write_file(
                root,
                "src/main/java/App.java",
                "public class App { public int value() { return 1; } }\n"
            )

            tracker = DiffTracker(root)
            snapshot = tracker.snapshot_production_files(root)

            self.write_file(
                root,
                "src/main/java/App.java",
                "public class App { public int value() { return 999; } }\n"
            )

            tracker.restore_production_snapshot(root, snapshot)

            content = (root / "src/main/java/App.java").read_text(encoding="utf-8")

            self.assertIn("return 1", content)
            self.assertNotIn("return 999", content)


if __name__ == "__main__":
    unittest.main()