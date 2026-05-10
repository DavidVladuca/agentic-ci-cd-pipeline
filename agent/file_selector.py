from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
import re


@dataclass
class FileSelection:
    selected_paths: list[str]
    reasons_by_path: dict[str, list[str]]
    estimated_chars: int
    candidate_scores: dict[str, int] = field(default_factory=dict)


# selects the smallest useful set of Java files to send to the LLM
class FileSelector:
    def __init__(self, max_context_chars=12000):
        self.max_context_chars = max_context_chars

    def select(self, analysis, task_prompt, error_summary):
        haystack = f"{task_prompt or ''}\n{error_summary or ''}"
        normalized_haystack = haystack.replace("\\", "/")
        lowered_haystack = normalized_haystack.lower()

        scores = defaultdict(int)
        reasons = defaultdict(list)

        self.score_direct_file_mentions(
            analysis=analysis,
            normalized_haystack=normalized_haystack,
            lowered_haystack=lowered_haystack,
            scores=scores,
            reasons=reasons
        )

        self.score_symbol_mentions(
            analysis=analysis,
            normalized_haystack=normalized_haystack,
            lowered_haystack=lowered_haystack,
            scores=scores,
            reasons=reasons
        )

        self.score_hidden_test_class_hints(
            analysis=analysis,
            lowered_haystack=lowered_haystack,
            scores=scores,
            reasons=reasons
        )

        self.score_test_to_production_references(
            analysis=analysis,
            scores=scores,
            reasons=reasons
        )

        self.score_task_prompt_methods(
            analysis=analysis,
            task_prompt=task_prompt or "",
            scores=scores,
            reasons=reasons
        )

        selected_paths = self.choose_with_budget(
            analysis=analysis,
            scores=scores,
            reasons=reasons
        )

        estimated_chars = self.estimate_context_chars(
            analysis=analysis,
            selected_paths=selected_paths
        )

        return FileSelection(
            selected_paths=selected_paths,
            reasons_by_path={
                path: reasons.get(path, [])
                for path in selected_paths
            },
            estimated_chars=estimated_chars,
            candidate_scores=dict(scores)
        )

    def score_direct_file_mentions(
        self,
        analysis,
        normalized_haystack,
        lowered_haystack,
        scores,
        reasons
    ):
        for file_info in analysis.files:
            relative_path = file_info.relative_path
            file_name = Path(relative_path).name

            if relative_path in normalized_haystack:
                self.add_score(
                    scores,
                    reasons,
                    relative_path,
                    100,
                    "relative path appears in failure/task text"
                )

            if file_name.lower() in lowered_haystack:
                self.add_score(
                    scores,
                    reasons,
                    relative_path,
                    80,
                    "file name appears in failure/task text"
                )

    def score_symbol_mentions(
        self,
        analysis,
        normalized_haystack,
        lowered_haystack,
        scores,
        reasons
    ):
        for file_info in analysis.files:
            for class_name in file_info.class_names:
                if self.symbol_mentioned(class_name, normalized_haystack, lowered_haystack):
                    self.add_score(
                        scores,
                        reasons,
                        file_info.relative_path,
                        70,
                        f"class name mentioned: {class_name}"
                    )

    def score_hidden_test_class_hints(
        self,
        analysis,
        lowered_haystack,
        scores,
        reasons
    ):
        for production_file in analysis.production_files:
            for class_name in production_file.class_names:
                possible_test_names = [
                    f"{class_name.lower()}test",
                    f"{class_name.lower()}hiddentest",
                    f"{class_name.lower()}tests",
                    f"{class_name.lower()}hiddentests"
                ]

                if any(test_name in lowered_haystack for test_name in possible_test_names):
                    self.add_score(
                        scores,
                        reasons,
                        production_file.relative_path,
                        90,
                        f"failure mentions a test class likely targeting {class_name}"
                    )

    def score_test_to_production_references(
        self,
        analysis,
        scores,
        reasons
    ):
        production_classes = {}

        for production_file in analysis.production_files:
            for class_name in production_file.class_names:
                production_classes[class_name] = production_file

        # First, selected public tests can pull in production classes they reference.
        for test_file in analysis.public_test_files:
            if scores.get(test_file.relative_path, 0) <= 0:
                continue

            referenced_classes = self.find_referenced_production_classes(
                content=test_file.content,
                production_classes=production_classes
            )

            for class_name in referenced_classes:
                production_file = production_classes[class_name]

                self.add_score(
                    scores,
                    reasons,
                    production_file.relative_path,
                    60,
                    f"referenced by selected test file {test_file.relative_path}"
                )

        # Second, selected production files can pull in nearby production collaborators.
        scored_paths = {
            path for path, score in scores.items()
            if score > 0
        }

        for file_info in analysis.production_files:
            if file_info.relative_path not in scored_paths:
                continue

            referenced_classes = self.find_referenced_production_classes(
                content=file_info.content,
                production_classes=production_classes
            )

            for class_name in referenced_classes:
                production_file = production_classes[class_name]

                if production_file.relative_path == file_info.relative_path:
                    continue

                self.add_score(
                    scores,
                    reasons,
                    production_file.relative_path,
                    30,
                    f"referenced by selected production file {file_info.relative_path}"
                )

    def score_task_prompt_methods(self, analysis, task_prompt, scores, reasons):
        lowered_prompt = task_prompt.lower()

        if not lowered_prompt.strip():
            return

        for file_info in analysis.production_files:
            for method_name in file_info.method_names:
                if len(method_name) < 3:
                    continue

                if method_name.lower() in lowered_prompt:
                    self.add_score(
                        scores,
                        reasons,
                        file_info.relative_path,
                        35,
                        f"method name appears in task prompt: {method_name}"
                    )

    def choose_with_budget(self, analysis, scores, reasons):
        scored_files = [
            file_info
            for file_info in analysis.files
            if scores.get(file_info.relative_path, 0) > 0
        ]

        if not scored_files:
            scored_files = self.fallback_candidates(analysis, scores, reasons)

        scored_files = sorted(
            scored_files,
            key=lambda file_info: (
                -scores.get(file_info.relative_path, 0),
                self.kind_sort_weight(file_info.kind),
                file_info.relative_path
            )
        )

        selected_paths = []
        estimated_chars = 0

        for file_info in scored_files:
            file_cost = self.estimate_file_context_chars(file_info)

            if selected_paths and estimated_chars + file_cost > self.max_context_chars:
                continue

            selected_paths.append(file_info.relative_path)
            estimated_chars += file_cost

        # If the highest-ranked file is huge, include it anyway.
        # A partial Java file is usually worse than a large complete Java file.
        if not selected_paths and scored_files:
            selected_paths.append(scored_files[0].relative_path)

        return selected_paths

    def fallback_candidates(self, analysis, scores, reasons):
        candidates = []

        for file_info in analysis.production_files:
            self.add_score(
                scores,
                reasons,
                file_info.relative_path,
                10,
                "fallback production file candidate"
            )
            candidates.append(file_info)

        for file_info in analysis.public_test_files:
            self.add_score(
                scores,
                reasons,
                file_info.relative_path,
                5,
                "fallback public test candidate"
            )
            candidates.append(file_info)

        return candidates

    def find_referenced_production_classes(self, content, production_classes):
        referenced = []

        for class_name in production_classes.keys():
            if re.search(rf"\b{re.escape(class_name)}\b", content):
                referenced.append(class_name)

        return referenced

    def symbol_mentioned(self, symbol, normalized_haystack, lowered_haystack):
        if not symbol:
            return False

        if re.search(rf"\b{re.escape(symbol)}\b", normalized_haystack):
            return True

        # Important for hidden test names like TransferServiceHiddenTest.
        if symbol.lower() in lowered_haystack:
            return True

        return False

    def estimate_context_chars(self, analysis, selected_paths):
        total = 0

        for path in selected_paths:
            file_info = analysis.by_path.get(path)

            if file_info is None:
                continue

            total += self.estimate_file_context_chars(file_info)

        return total

    @staticmethod
    def estimate_file_context_chars(file_info):
        return len(file_info.content) + len(file_info.relative_path) + 32

    @staticmethod
    def kind_sort_weight(kind):
        if kind == "production":
            return 0

        return 1

    @staticmethod
    def add_score(scores, reasons, path, amount, reason):
        scores[path] += amount

        if reason not in reasons[path]:
            reasons[path].append(reason)