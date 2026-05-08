import json
import urllib.request
import urllib.error

# this is the LLM communication layer
# doesnt write files, run maven or log
# has only one responsability:
# send a task/error feedback to Ollama, force the model to return JSON, parse + validate
# and return clean Java code strings or repair file edits
class LLMClient:
    def __init__(self, model="agent-coder", url="http://localhost:11434/api/generate"):
        self.model = model
        self.url = url

    def generate_code(self, task_prompt, previous_error=None):
        # if no error -> normal prompt
        # if error -> repair prompt with error details
        if previous_error is None:
            prompt = self.build_initial_prompt(task_prompt)
        else:
            prompt = self.build_repair_prompt(task_prompt, previous_error)

        code_json = self.call_ollama_json(prompt)
        self.validate_code_json(code_json)

        return code_json

    def generate_repair_files(self, task_prompt, source_context, previous_error):
        prompt = self.build_file_repair_prompt(
            task_prompt=task_prompt,
            source_context=source_context,
            previous_error=previous_error
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

                {self.common_rules()}

                Task:
                {task_prompt}
                """.strip()

    # if Maven fails, we get here, and we fix based on error
    def build_repair_prompt(self, task_prompt, previous_error):
        return f"""
                The previous generated Java code failed when Maven ran the tests.

                Original task:
                {task_prompt}

                Maven failure output:
                {previous_error}

                Generate corrected Java code and corrected JUnit tests.

                {self.common_rules()}
                """.strip()

    # these are some shared rules (in both cases they must be respected)
    def common_rules(self):
        return """
                Return only a raw JSON object.

                The JSON object must have exactly these keys:
                - main_class
                - test_class

                Rules:
                - path must be the exact relative path shown after FILE:
                - if repairing App.java, use "src/main/java/App.java", not "App.java"
                - path must be under src/main/java/
                - content must contain the full corrected Java file content
                - do not modify files under src/test/java/
                - do not modify hidden tests
                - do not modify public tests
                - do not modify pom.xml
                - do not include Markdown
                - do not explain anything
                - do not include extra keys

                Example valid output:
                {{
                  "files": [
                    {{
                      "path": "src/main/java/App.java",
                      "content": "public class App {{\\n    // corrected code here\\n}}"
                    }}
                  ]
                }}
                """.strip()

    def build_file_repair_prompt(self, task_prompt, source_context, previous_error):
        return f"""
                You are repairing an existing Java Maven project.

                You will receive:
                - the repair task
                - the current source files
                - the latest Maven/JUnit failure output

                Your job:
                - modify the production Java source code to satisfy the task
                - preserve public method signatures
                - do not modify tests
                - do not modify pom.xml
                - do not add package declarations
                - keep all classes in the default package
                - produce Java 17 compatible code

                Repair task:
                {task_prompt}

                Current source context:
                {source_context}

                Latest Maven/JUnit failure:
                {previous_error}

                Return only a raw JSON object.

                The JSON object must have exactly one key:
                - files

                files must be a non-empty array.

                Each file entry must have exactly these keys:
                - path
                - content

                Rules:
                - path must be a relative path under src/main/java/
                - content must contain the full corrected Java file content
                - do not include Markdown
                - do not explain anything
                - do not include extra keys
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