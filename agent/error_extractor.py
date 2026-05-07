class ErrorExtractor:
    @staticmethod
    def extract_errors(raw_output, timed_out=False):
        if raw_output is None: # just in case
            raw_output = ""

        prefix = ""
        if timed_out:
            prefix = "Maven timed out after 15 seconds.\n"

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
        # if not -> take last 40 lines of raw output (to have something to work with)
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

        if not summary:  # new
            summary = "No Maven output captured."  # new

        return prefix + summary

    @staticmethod
    def normalize_error(error_summary):
        normalized = error_summary.lower()
        normalized = " ".join(normalized.split())
        return normalized


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