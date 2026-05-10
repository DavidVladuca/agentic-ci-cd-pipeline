# this class extracts errors and useful info, classifies and normalizes them
class ErrorExtractor:
    @staticmethod
    def extract_errors(raw_output, timed_out=False, timeout_seconds=None):
        if raw_output is None:
            raw_output = ""

        prefix = ""

        if timed_out:
            if timeout_seconds is None:
                prefix = "Maven timed out.\n"
            else:
                prefix = f"Maven timed out after {timeout_seconds} seconds.\n"

        useful_lines = []

        for line in raw_output.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if stripped.startswith("[INFO]"):
                continue

            # we want to know more than just errors
            useful_lines.append(stripped)

        # if we have useful lines -> take last 40
        # if not -> take last 40 lines of raw output
        if useful_lines:
            selected_lines = useful_lines[-40:]
        else:
            raw_lines = []

            for line in raw_output.splitlines():
                stripped = line.strip()

                if stripped:
                    raw_lines.append(stripped)

            selected_lines = raw_lines[-40:]

        summary = "\n".join(selected_lines)

        if not summary:
            summary = "No Maven output captured."

        return prefix + summary

    @staticmethod
    def normalize_error(error_summary):
        normalized = error_summary.lower()
        normalized = " ".join(normalized.split())
        return normalized

    @staticmethod
    # cluster errors so that small changes dont make it seem like a new error
    def fingerprint_error(error_summary, error_type):
        normalized = ErrorExtractor.normalize_error(error_summary)

        if error_type == "COMPILATION_ERROR":
            if "illegal start of expression" in normalized:
                return "COMPILATION_ERROR:illegal start of expression"

            if "cannot find symbol" in normalized:
                return "COMPILATION_ERROR:cannot find symbol"

            if "package does not exist" in normalized:
                return "COMPILATION_ERROR:package does not exist"

            if "reached end of file while parsing" in normalized:
                return "COMPILATION_ERROR:reached end of file while parsing"

            return "COMPILATION_ERROR"

        if error_type == "TEST_FAILURE":
            if "expected:" in normalized and "but was:" in normalized:
                return "TEST_FAILURE:assertion mismatch"

            return "TEST_FAILURE"

        if error_type == "DEPENDENCY_RESOLUTION_ERROR":
            return "DEPENDENCY_RESOLUTION_ERROR"

        if error_type == "DOCKER_ERROR":
            return "DOCKER_ERROR"

        if error_type == "SANDBOX_ERROR":
            return "SANDBOX_ERROR"

        if error_type == "TIMEOUT":
            return "TIMEOUT"

        if error_type == "LLM_ERROR":
            return "LLM_ERROR"

        if error_type == "JAVA_VERSION_ERROR":
            return "JAVA_VERSION_ERROR"

        return normalized

    @staticmethod
    def classify_error(error_summary, timed_out=False):
        if timed_out:
            return "TIMEOUT"

        if error_summary is None:
            return "UNKNOWN_ERROR"

        lowered = error_summary.lower()

        if (
            "llm generation failed" in lowered
            or "failed to call ollama api" in lowered
            or "ollama returned invalid outer json" in lowered
            or "model response was not valid json" in lowered
            or "model json must contain exactly" in lowered
            or "model output must be a json object" in lowered
        ):
            return "LLM_ERROR"

        if (
            "docker executable not found" in lowered
            or "cannot connect to the docker daemon" in lowered
            or "error response from daemon" in lowered
            or "docker daemon" in lowered
        ):
            return "DOCKER_ERROR"

        if (
            "read-only file system" in lowered
            or "permission denied" in lowered
            or "operation not permitted" in lowered
            or "no-new-privileges" in lowered
            or "pids-limit" in lowered
            or "mounts denied" in lowered
            or "invalid mount config" in lowered
        ):
            return "SANDBOX_ERROR"

        if (
            "could not transfer artifact" in lowered
            or "could not be resolved" in lowered
            or "failed to collect dependencies" in lowered
            or "unknown host" in lowered
            or "temporary failure in name resolution" in lowered
            or "cannot access central" in lowered
        ):
            return "DEPENDENCY_RESOLUTION_ERROR"

        if (
            "requirejavaversion failed" in lowered
            or "detected jdk" in lowered and "allowed range" in lowered
            or "is not in the allowed range" in lowered
            or "maven-enforcer-plugin" in lowered and "requirejavaversion" in lowered
        ):
            return "JAVA_VERSION_ERROR"

        if (
            "compilation error" in lowered
            or "compilation failure" in lowered
            or "cannot find symbol" in lowered
            or "package does not exist" in lowered
            or "class, interface, enum, or record expected" in lowered
            or "illegal start of expression" in lowered
            or "reached end of file while parsing" in lowered
        ):
            return "COMPILATION_ERROR"

        if (
            "assertionfailederror" in lowered
            or ("expected:" in lowered and "but was:" in lowered)
            or "there are test failures" in lowered
            or "test failures" in lowered
            or "failures:" in lowered
        ):
            return "TEST_FAILURE"

        if "timed out" in lowered:
            return "TIMEOUT"

        if "build failure" in lowered:
            return "BUILD_FAILURE"

        return "UNKNOWN_ERROR"


if __name__ == "__main__":
    sample_output = """
        [INFO] Scanning for projects...
        [INFO] Building agent-pipeline
        [ERROR] COMPILATION ERROR :
        [ERROR] /src/main/java/App.java:[3,15] cannot find symbol
        symbol:   method add(int,int)
        location: class App
        [INFO] BUILD FAILURE
        """

    extracted = ErrorExtractor.extract_errors(sample_output)

    print("----- EXTRACTED ERROR -----")
    print(extracted)

    print("----- NORMALIZED ERROR -----")
    print(ErrorExtractor.normalize_error(extracted))

    print("----- ERROR TYPE -----")
    print(ErrorExtractor.classify_error(extracted))