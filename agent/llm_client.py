import json
import urllib.request
import urllib.error

class LLMClient:
    """Handles all Ollama API communication, prompt construction, JSON parsing, and repair output validation."""
    def __init__(
        self,
        model="agent-coder",
        url="http://localhost:11434/api/generate",
        request_timeout_seconds=180
    ):
        self.model = model
        self.url = url
        self.request_timeout_seconds = request_timeout_seconds

    def generate_code(self, task_prompt, previous_error=None):
        # if no error -> normal prompt
        # if error -> retry prompt with error details
        if previous_error is None:
            prompt = self.build_initial_prompt(task_prompt)
        else:
            prompt = self.build_retry_prompt(task_prompt, previous_error)

        code_json = self.call_ollama_json(prompt)
        self.validate_code_json(code_json)

        return code_json

    def generate_repair_files(
        self,
        task_prompt,
        source_context,
        previous_error,
        previous_patch=None,
        strategy_note=None
    ):
        prompt = self.build_file_repair_prompt(
            task_prompt=task_prompt,
            source_context=source_context,
            previous_error=previous_error,
            previous_patch=previous_patch,
            strategy_note=strategy_note
        )

        repair_json = self.call_ollama_json(prompt)
        self.validate_repair_json(repair_json)

        return repair_json

    def call_ollama_json(self, prompt):
        payload = {
            "model": self.model,
            "stream": False, # wait for the full response before returning
            "format": "json",
            "prompt": prompt
        }

        request_data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            self.url,
            data=request_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        # send request and read response
        try:
            with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to call Ollama API: {e}") from e

        # parse the outer JSON response
        try:
            outer_json = json.loads(raw_body)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ollama returned invalid outer JSON: {raw_body}") from e

        if "response" not in outer_json:
            raise RuntimeError(f"Ollama response missing 'response' field: {outer_json}")

        model_response = outer_json["response"]

        # parse the model response
        try:
            return json.loads(model_response)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Model response was not valid JSON: {model_response}") from e

    # we add constraints before the task (to make the model reliable)
    def build_initial_prompt(self, task_prompt):
        return f"""
                You are generating Java code for a Maven project.

                {self.common_code_generation_rules()}

                Task:
                {task_prompt}
                """.strip()

    # if generation, schema validation, compilation, or tests fail, we get here and retry
    def build_retry_prompt(self, task_prompt, previous_error):
        return f"""
                The previous attempt failed.

                The failure may have been:
                - invalid JSON schema
                - invalid Java code
                - Maven compilation failure
                - JUnit test failure

                Original task:
                {task_prompt}

                Failure output:
                {previous_error}

                Generate a corrected response.

                {self.common_code_generation_rules()}
                """.strip()

    def java_repair_safety_rules(self):
        return """
                Java source correctness rules:
                - content must be valid Java source after JSON decoding.
                - content must contain the complete Java file, not a fragment.
                - content must include all needed imports, class declaration, methods, and final closing brace.
                - Java string literals must remain quoted.
                - Java regex backslashes must be escaped inside Java strings.
                - for whitespace splitting, the Java source must contain: split("\\\\s+")
                - never write invalid Java such as split(\\s+).
                - if Maven reports "illegal character: '\\'", check for an unquoted or incorrectly escaped backslash.
                - if Maven reports "reached end of file while parsing", the previous output was truncated or had unbalanced braces.
                """.strip()

    # these are shared rules for V1 code-generation mode
    def common_code_generation_rules(self):
        return """
                Return only a raw JSON object.

                The JSON object must have exactly these keys:
                - main_class
                - test_class

                main_class must be a JSON string.
                test_class must be a JSON string.

                Do not make main_class an object.
                Do not make test_class an object.
                Do not include file paths.
                Do not include arrays.
                Do not include nested JSON objects.

                Required JSON shape:
                {
                  "main_class": "public class App {\\n    // full Java source here\\n}",
                  "test_class": "import org.junit.jupiter.api.Test;\\npublic class AppTest {\\n    // full JUnit 5 test source here\\n}"
                }

                Rules:
                - main_class must contain one complete Java class named App.
                - test_class must contain one complete JUnit 5 test class named AppTest.
                - Do not use package declarations.
                - Do not use Markdown.
                - Do not explain anything.
                - Do not include extra keys.
                - The Java code must compile with Java 17.
                - The test class must test the main class.
                """.strip()

    def build_file_repair_prompt(
        self,
        task_prompt,
        source_context,
        previous_error,
        previous_patch=None,
        strategy_note=None
    ):
        strategy_section = self.optional_prompt_section(
            title="Repair strategy note",
            content=strategy_note
        )

        patch_section = self.optional_prompt_section(
            title="Previous patch diff",
            content=previous_patch
        )
        return f"""
                You are repairing an existing Java Maven project.

                You will receive:
                - the repair task
                - the current source files
                - the latest Maven/JUnit failure output

                There may be multiple production Java files.

                Your job:
                - understand the project structure
                - identify which existing production Java file or files contain the bug
                - modify every existing production Java source file needed to fix the bug
                - do not assume the bug is only in the file named by the stack trace
                - inspect collaborator classes when the task mentions multiple classes
                - preserve all public method signatures exactly
                - preserve public return types exactly
                - preserve public parameter lists exactly
                - preserve existing package declarations exactly when a file already has one
                - do not add a package declaration to a file that did not already have one
                - preserve existing public class names and file names
                - do not modify tests
                - do not modify hidden tests
                - do not modify public tests
                - do not modify pom.xml
                - do not create new files
                - produce Java 17 compatible code

                Important repair rules:
                - If a previous patch compiled but tests still failed, the fix was logically incomplete.
                - If the same test failure repeats, reconsider collaborator classes and boundary conditions.
                - If the task names multiple production classes, at least consider whether more than one file must change.
                - If a helper method contains the broken logic, fix the helper method instead of only patching the caller.
                - For conflict/range/overlap bugs, preserve the domain rule: reject only when the same relevant resource conflicts and the time ranges strictly overlap.
                - Adjacent ranges are not overlapping when the task says adjacency is allowed.
                - Do not fix adjacency by negating the whole conflict condition; fix the overlap helper method.
                - If a repeated test failure remains after editing a caller/collection class, do not keep patching the same caller only.
                - Inspect helper/domain methods in the provided context that encode the failing rule.
                - For conflict/overlap/range tasks, the core bug is often in the range/helper class, not only in the collection class.
                - If adjacent ranges should be allowed, the overlap condition must use strict inequality: start < otherEnd && otherStart < end.
                - Do not implement overlap logic inconsistently in multiple places; prefer fixing the helper method that defines overlap semantics.
                - Do not change a method return type to make a local comparison easier.
                - For integer division that needs decimal arithmetic, cast one operand to double instead of changing method signatures.
                - Add imports only when the edited file actually uses that imported class.
                - Avoid introducing BigDecimal unless it is clearly necessary and the original public signatures still remain unchanged.
                - For time ranges, adjacent ranges are not overlapping unless the task explicitly says otherwise.
                - For half-open time intervals, overlap is usually: start < otherEnd && otherStart < end.
                - Do not use <= for overlap checks when adjacent intervals should be allowed.
                - If a task mentions conflict logic, inspect both the collection class and the domain object/helper method that defines conflicts or overlaps.

                String and parser repair rules:
                - Prefer simple indexOf, substring, and character-by-character parsing over complex regular expressions.
                - For delimiter parsing where values may contain the delimiter, split only at the first delimiter.
                - For key:value parsing where the value may contain ':', use indexOf(':') once, then substring before and after that index.
                - Do not use split(":") for key:value parsing when values may contain ':'.
                - For key:value parsing, reject a missing separator.
                - For key:value parsing, reject a blank trimmed key.
                - For key:value parsing, trim both the key and the value.
                - For CSV or quoted formats, use a small state-machine loop over characters.
                - Do not use String.split for CSV-style quoted fields.
                - Avoid Pattern/Matcher unless the existing project already uses them.
                - Avoid complex Java regex string literals because escaping errors often break compilation.
                - Remember that String.split drops trailing empty fields unless called with a negative limit.

                Interval and range overlap rules:
                - For strict non-inclusive overlap, use start.isBefore(otherEnd) && otherStart.isBefore(end).
                - Do not use !start.isAfter(otherEnd) when adjacent ranges should be allowed.

                Java escaping rules:
                - Returned content must be valid Java source after JSON decoding.
                - Backslashes required in Java string literals must be escaped correctly in JSON.
                - A Java regex "\\s+" must appear inside the JSON content as "\\\\s+".
                - A Java quote character is safest as a char literal: '"'.
                - Do not output partial Java files.
                - Do not output unterminated string literals.

                Repair task:
                {task_prompt}

                Current source context:
                {source_context}

                Latest Maven/JUnit failure:
                {previous_error}

                {strategy_section}

                {patch_section}
                
                {self.java_repair_safety_rules()}

                Return only a raw JSON object.

                The JSON object must have exactly one key:
                - files

                files must be a non-empty array.

                Each file entry must have exactly these keys:
                - path
                - content

                Rules:
                - return only files that need to be changed
                - if you change a file, content must contain the complete corrected Java file
                - if multiple files need coordinated changes, return all changed files in the files array
                - do not return a file whose content is unchanged
                - do not use placeholders
                - do not use comments instead of implementation
                - do not change public APIs to satisfy tests
                - compile mentally before returning the JSON
                - path must be the exact relative path shown after FILE:
                - path must be under src/main/java/
                - content must be valid Java source after JSON decoding
                - Java string literals must remain quoted
                - Java regex backslashes must be escaped inside Java strings
                - for whitespace splitting, the Java source must contain: split("\\\\s+")
                - never write invalid Java such as split(\\s+)
                - path must refer to an existing production Java file
                - path may include package directories under src/main/java/
                - content must contain the full corrected Java file content
                - do not modify files under src/test/java/
                - do not modify hidden tests
                - do not modify public tests
                - do not modify pom.xml
                - do not include Markdown
                - do not explain anything
                - do not include extra keys

                Example valid output for one changed file:
                {{
                "files": [
                    {{
                    "path": "src/main/java/Counter.java",
                    "content": "public class Counter {{\\n    public int increment(int value) {{\\n        return value + 1;\\n    }}\\n}}"
                    }}
                ]
                }}

                Example valid output for two changed files:
                {{
                "files": [
                    {{
                    "path": "src/main/java/Range.java",
                    "content": "public class Range {{\\n    public boolean contains(int value) {{\\n        return value >= 0 && value <= 10;\\n    }}\\n}}"
                    }},
                    {{
                    "path": "src/main/java/RangeService.java",
                    "content": "public class RangeService {{\\n    public boolean accepts(int value) {{\\n        return new Range().contains(value);\\n    }}\\n}}"
                    }}
                ]
                }}
                """.strip()

    # verify if the LLM followed the constraints from the prompt
    def validate_code_json(self, code_json):
        if not isinstance(code_json, dict):
            raise RuntimeError("Model output must be a JSON object.")

        expected_keys = {"main_class", "test_class"}
        actual_keys = set(code_json.keys())

        if actual_keys != expected_keys:
            raise RuntimeError(
                f"Model JSON must contain exactly {expected_keys}, got {actual_keys}"
            )

        for key in expected_keys:
            value = code_json[key]

            if not isinstance(value, str):
                raise RuntimeError(f"{key} must be a string.")

            if not value.strip():
                raise RuntimeError(f"{key} must not be empty.")
    
    @staticmethod
    def optional_prompt_section(title, content):
        if content is None:
            return ""

        text = str(content).strip()

        if not text:
            return ""

        return f"""
                {title}:
                {text}
                """.strip()

    def validate_repair_file_content(self, path, content):
        stripped = content.strip()

        # Catches truncated LLM outputs where the model stopped mid-file before the final closing brace.
        if not stripped.endswith("}"):
            raise RuntimeError(
                f"Repair file content appears incomplete for path: {path}. "
                "Java source should usually end with a closing brace."
            )

        invalid_fragments = [
            r"split(\s+)",
            r"split(\\s+)",
            r"split(\s*)",
            r"split(\\s*)"
        ]

        for fragment in invalid_fragments:
            if fragment in content:
                raise RuntimeError(
                    f"Repair file content contains invalid Java string/regex syntax "
                    f"for path: {path}: {fragment}"
                )

        placeholder_fragments = [
            "// corrected code here",
            "TODO",
            "throw new UnsupportedOperationException",
            "return null; //",
            "implementation here"
        ]

        for fragment in placeholder_fragments:
            if fragment in content:
                raise RuntimeError(
                    f"Repair file content appears to contain placeholder code "
                    f"for path: {path}: {fragment}"
                )

    # verify if the LLM followed the repair-file schema
    def validate_repair_json(self, repair_json):
        if not isinstance(repair_json, dict):
            raise RuntimeError("Repair output must be a JSON object.")

        expected_keys = {"files"}
        actual_keys = set(repair_json.keys())

        if actual_keys != expected_keys:
            raise RuntimeError(
                f"Repair JSON must contain exactly {expected_keys}, got {actual_keys}"
            )

        files = repair_json["files"]

        if not isinstance(files, list):
            raise RuntimeError("Repair JSON 'files' must be a list.")

        if not files:
            raise RuntimeError("Repair JSON 'files' must not be empty.")

        seen_paths = set()

        for file_entry in files:
            if not isinstance(file_entry, dict):
                raise RuntimeError("Each repair file entry must be a JSON object.")

            expected_file_keys = {"path", "content"}
            actual_file_keys = set(file_entry.keys())

            if actual_file_keys != expected_file_keys:
                raise RuntimeError(
                    f"Each repair file entry must contain exactly {expected_file_keys}, got {actual_file_keys}"
                )

            path = file_entry["path"]
            content = file_entry["content"]

            if not isinstance(path, str):
                raise RuntimeError("Repair file path must be a string.")

            if not path.strip():
                raise RuntimeError("Repair file path must not be empty.")

            if path in seen_paths:
                raise RuntimeError(f"Duplicate repair file path: {path}")

            seen_paths.add(path)

            if not isinstance(content, str):
                raise RuntimeError(f"Repair file content must be a string for path: {path}")

            if not content.strip():
                raise RuntimeError(f"Repair file content must not be empty for path: {path}")
            
            self.validate_repair_file_content(path, content)
        