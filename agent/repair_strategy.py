from dataclasses import dataclass


@dataclass
class RepairDecision:
    should_rollback: bool
    should_expand_context: bool
    should_stop: bool
    strategy_note: str | None


class RepairStrategy:
    COMPILED_ERROR_TYPES = {
        "TEST_FAILURE"
    }

    REGRESSION_ERROR_TYPES = {
        "COMPILATION_ERROR"
    }

    INFRASTRUCTURE_ERROR_TYPES = {
        "DEPENDENCY_RESOLUTION_ERROR",
        "DOCKER_ERROR",
        "SANDBOX_ERROR",
        "TIMEOUT",
        "JAVA_VERSION_ERROR"
    }

    @classmethod
    def error_type_means_project_compiled(cls, error_type):
        return error_type in cls.COMPILED_ERROR_TYPES

    @classmethod
    def is_infrastructure_error(cls, error_type):
        return error_type in cls.INFRASTRUCTURE_ERROR_TYPES

    @classmethod
    def should_rollback_compilation_regression(cls, error_type, has_last_compiling_snapshot):
        return (
            has_last_compiling_snapshot
            and error_type in cls.REGRESSION_ERROR_TYPES
        )

    @classmethod
    def decide_after_maven_failure(
        cls,
        error_type,
        repeated_count,
        context_already_expanded,
        has_last_compiling_snapshot
    ):
        should_rollback = cls.should_rollback_compilation_regression(
            error_type=error_type,
            has_last_compiling_snapshot=has_last_compiling_snapshot
        )

        strategy_note = None

        if should_rollback:
            strategy_note = (
                "The previous repair patch introduced a compilation error. "
                "The sandbox was rolled back to the last known compiling source state. "
                "Do not repeat the invalid edit. Produce valid Java source that compiles."
            )

        if repeated_count <= 0:
            return RepairDecision(
                should_rollback=should_rollback,
                should_expand_context=False,
                should_stop=False,
                strategy_note=strategy_note
            )

        if not context_already_expanded:
            expansion_note = (
                "The same Maven/JUnit error appeared again. "
                "The next attempt will use expanded project context."
            )

            if strategy_note:
                strategy_note = strategy_note + " " + expansion_note
            else:
                strategy_note = expansion_note

            return RepairDecision(
                should_rollback=should_rollback,
                should_expand_context=True,
                should_stop=False,
                strategy_note=strategy_note
            )

        stop_note = (
            "The same Maven/JUnit error repeated even after expanded context. "
            "Stopping to avoid wasting repair attempts."
        )

        if strategy_note:
            strategy_note = strategy_note + " " + stop_note
        else:
            strategy_note = stop_note

        return RepairDecision(
            should_rollback=should_rollback,
            should_expand_context=False,
            should_stop=True,
            strategy_note=strategy_note
        )