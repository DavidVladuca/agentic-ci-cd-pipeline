from pathlib import Path

from agent.llm_client import LLMClient
from agent.workspace import WorkspaceManager
from agent.maven_runner import MavenRunner
from agent.error_extractor import ErrorExtractor  

# This is the controller.
# It wires the system together:
# LLMClient → WorkspaceManager → MavenRunner → ErrorExtractor  
# At this stage, it runs a retry feedback loop.  
def main():
    # __file__ = path of current file (controller.py),  resolve() = absolute path
    project_root = Path(__file__).resolve().parents[1]

    # if path is wrong, kill it imediatly
    if not (project_root / "pom.xml").exists():
        raise RuntimeError(f"Could not find pom.xml at project root: {project_root}")

    task_prompt = """
        Create a Java class App with a static method add(int a, int b) that returns the sum.
        Create a JUnit 5 test class AppTest that verifies the add method.
        """.strip()

    max_attempts = 5  
    last_error_summary = None  
    seen_errors = set()  # to see if we are stuck in a loop with the same error

    print("[CONTROLLER] Starting Phase 2 feedback-loop run") 
    print("[CONTROLLER] Project root:", project_root)
    print("[CONTROLLER] Max attempts:", max_attempts)  

    llm = LLMClient(model="agent-coder")
    workspace = WorkspaceManager(project_root)
    maven = MavenRunner(project_root, timeout_seconds=15)

    for attempt in range(1, max_attempts + 1):  
        print()  
        print(f"[CONTROLLER] Attempt {attempt}/{max_attempts}")  

        try:  
            if last_error_summary is None:  
                print("[CONTROLLER] Calling LLM for initial generation...")  
            else:  
                print("[CONTROLLER] Calling LLM with previous Maven error feedback...")  

            generated = llm.generate_code(  
                task_prompt=task_prompt,  
                previous_error=last_error_summary  
            )  

            # testing line -> to see if the retry loop works
            # if attempt == 1:
            #     generated["main_class"] = generated["main_class"].replace("return a + b;", "return a + ;")

        # this is for catching errors before Maven runs!!!
        except RuntimeError as e:  
            error_summary = f"LLM generation failed before Maven could run:\n{e}"  
            normalized_error = ErrorExtractor.normalize_error(error_summary)  

            print("[CONTROLLER] LLM FAILURE")  
            print(error_summary)  

            # got same error again, we are stuck
            if normalized_error in seen_errors:  
                print("[CONTROLLER] Repeated LLM failure detected. Stopping.")  
                return  

            seen_errors.add(normalized_error)  
            last_error_summary = error_summary  
            continue  
        
        print("[CONTROLLER] Writing generated Java files...")  
        workspace.write_java_files(  
            main_class=generated["main_class"],  
            test_class=generated["test_class"]  
        )  

        print("[CONTROLLER] Running Maven tests...")  
        result = maven.run_tests()  

        print("[CONTROLLER] Maven exit code:", result.exit_code)  

        if result.success:  
            print("[CONTROLLER] BUILD SUCCESS")  
            print(f"[CONTROLLER] Passed on attempt {attempt}/{max_attempts}")  
            return  

        print("[CONTROLLER] BUILD FAILURE")  

        error_summary = ErrorExtractor.extract_errors(  
            raw_output=result.combined_output,  
            timed_out=result.timed_out  
        )  

        print("[CONTROLLER] Extracted Maven failure:")  
        print(error_summary)  

        normalized_error = ErrorExtractor.normalize_error(error_summary)  

        # got same error again, we are stuck
        if normalized_error in seen_errors:  
            print("[CONTROLLER] Repeated Maven error detected. Stopping.")  
            return  

        seen_errors.add(normalized_error)  
        last_error_summary = error_summary  

    print()  
    print(f"[CONTROLLER] FAILED after {max_attempts} attempts.")  


if __name__ == "__main__":
    main()