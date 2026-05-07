import json
import urllib.request
import urllib.error

# This file is the LLM communication layer of your project.
# It does not compile Java.
# It does not write files.
# It does not run Maven.
# That separation matters because when something breaks, you can tell exactly where it broke.
# It has one responsibility:
# Send a task/error feedback to Ollama, force the model to return JSON, parse that JSON, validate it, and return clean Java code strings.  # modified
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
            code_json = json.loads(model_response)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Model response was not valid JSON: {model_response}") from e

        self.validate_code_json(code_json)

        return code_json

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
                - main_class must contain one complete Java class named App.
                - test_class must contain one complete JUnit 5 test class named AppTest.
                - Do not use package declarations.
                - Do not use Markdown.
                - Do not explain anything.
                - Do not include extra keys.
                - The Java code must compile with Java 17.
                - The test class must test the main class.
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