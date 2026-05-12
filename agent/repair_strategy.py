from dataclasses import dataclass


@dataclass
class RepairDecision:
    should_rollback: bool
    should_expand_context: bool
    should_stop: bool
    strategy_note: str | None

# decides how the repair loop should react to different types of failures
# handles rollback, repeated errors, expanded context and stopping conditions
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
    def repeated_failure_strategy_note(cls):
        return (
            "The same Maven/JUnit error appeared again after the previous patch. "
            "The previous fix was incomplete, targeted the wrong method, or failed to repair "
            "the helper class that defines the real domain rule. "
            "Do not keep making small edits to the same caller if the rule belongs in a collaborator. "
            "Re-read every provided production file. "
            "If the task mentions multiple classes, consider coordinated edits across multiple files. "

            "Do not fix one failing assertion by blindly negating or inverting a whole predicate. "
            "If previous failures include both expected true/was false and expected false/was true cases, "
            "the solution usually needs a more precise condition, not a polarity flip. "
            "A correct predicate must satisfy all listed examples at the same time. "

            "If the failure involves parsing, quoted delimiters, escaped characters, "
            "or trailing empty fields, avoid complex regex; prefer a small character-by-character "
            "state machine. "
            "A correct state machine for quoted-delimiter formats must handle at least three distinct "
            "cases: (1) a delimiter outside quotes ends the current field; "
            "(2) a delimiter inside quotes is literal data; "
            "(3) an escape sequence inside quotes, such as two consecutive quote characters, "
            "produces one literal quote character in the output and advances past both characters. "
            "If your previous implementation did not handle case (3), it will silently strip or "
            "misplace characters in escaped fields. "
            "Also preserve trailing empty fields explicitly when the loop ends. "

            "If the failure involves overlap, conflict, ranges, intervals, dates, times, "
            "boundaries, or adjacency, inspect the helper/domain method that defines the range "
            "or overlap semantics, not only the caller. "
            "Be explicit about inclusive versus exclusive endpoints. "
            "If adjacency is allowed, touching endpoints must not count as overlap. "
            "A correct strict-overlap predicate is: leftStart < rightEnd and rightStart < leftEnd. "
            "In Java date/time APIs, !x.isAfter(y) is equivalent to x <= y and is inclusive — "
            "it treats touching endpoints as overlapping. "
            "For non-inclusive adjacency, use x.isBefore(y), which is strict less-than. "
            "Do not invert an entire caller condition just to satisfy one failing assertion; "
            "fix the underlying domain predicate instead. "

            "If the failure involves decimal arithmetic, do not change public method signatures. "
            "Use double arithmetic or local BigDecimal values only when compatible with existing public APIs."
        )
    
    @classmethod
    def rollback_strategy_note(cls):
        return (
            "The previous repair patch introduced a compilation error. "
            "The sandbox was rolled back to the last known compiling source state. "
            "Do not repeat the invalid edit. "
            "Produce valid Java 17 source. "
            "Preserve public method signatures, return types, and parameter lists exactly. "
            "If you introduce a class from java.math, java.util, or another package, "
            "the edited file must include the required import. "
            "Prefer simple fixes over complex regex or signature changes."
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

        notes = []

        if should_rollback:
            notes.append(cls.rollback_strategy_note())

        if repeated_count > 0:
            notes.append(cls.repeated_failure_strategy_note())

        strategy_note = " ".join(notes) if notes else None

        # first time seeing this error -> continue
        if repeated_count <= 0:
            return RepairDecision(
                should_rollback=should_rollback,
                should_expand_context=False,
                should_stop=False,
                strategy_note=strategy_note
            )

        # first repeat -> send context
        if not context_already_expanded:
            expansion_note = (
                "The next attempt will use expanded project context. "
                "Use that expanded context to inspect related production classes, not only the stack-trace file. "
                "Return every production file that needs to change."
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

        # after the explained context, do not stop instantly
        # hard tasks seem to need one or two more attempts after the model has seen the full local design
        if repeated_count < 3:
            post_expansion_note = (
                "The same error still repeats after expanded context. "
                "Do not repeat the previous patch. "
                "Make a materially different repair. "
                "Prefer fixing the domain/helper method that defines the rule instead of patching symptoms in the caller."
            )

            if strategy_note:
                strategy_note = strategy_note + " " + post_expansion_note
            else:
                strategy_note = post_expansion_note

            return RepairDecision(
                should_rollback=should_rollback,
                should_expand_context=False,
                should_stop=False,
                strategy_note=strategy_note
            )

        # only stop after several repeats
        stop_note = (
            "The same Maven/JUnit error repeated multiple times even after expanded context. "
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