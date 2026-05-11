import json
import urllib.request
import urllib.error

# this is the LLM communication layer
# doesnt write files, run maven or log
# has only one responsability:
# send a task/error feedback to Ollama, force the model to return JSON, parse + validate, and return clean Java code strings or repair file edits
class LLMClient:
    def __init__(self, model="agent-coder", url="http://localhost:11434/api/generate"):
        self.model = model
        self.url = url

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
            with urllib.request.urlopen(request) as response:
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
                - Java string literals must remain quoted.
                - Java regex backslashes must be escaped inside Java strings.
                - for whitespace splitting, the Java source must contain: split("\\\\s+")
                - never write invalid Java such as split(\\s+).
                - if Maven reports "illegal character: '\\'", check for an unquoted or incorrectly escaped backslash.
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
                - modify only the existing production Java source files needed to fix the bug
                - preserve public method signatures
                - do not modify tests
                - do not modify pom.xml
                - do not create new files
                - preserve existing package declarations exactly when a file already has one
                - do not add a package declaration to a file that did not already have one
                - preserve existing public class names and file names
                - produce Java 17 compatible code

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
                    "path": "src/main/java/TransferService.java",
                    "content": "public class TransferService {{\\n    // corrected code here\\n}}"
                    }}
                ]
                }}

                Example valid output for two changed files:
                {{
                "files": [
                    {{
                    "path": "src/main/java/ClassA.java",
                    "content": "public class ClassA {{\\n    // corrected code here\\n}}"
                    }},
                    {{
                    "path": "src/main/java/ClassB.java",
                    "content": "public class ClassB {{\\n    // corrected code here\\n}}"
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
        