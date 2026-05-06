from pathlib import Path

from agent.llm_client import LLMClient
from agent.workspace import WorkspaceManager
from agent.maven_runner import MavenRunner

# This is the controller.
# It wires the system together:
# LLMClient → WorkspaceManager → MavenRunner
# At this stage, it runs once. No retry loop yet.
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

    print("[CONTROLLER] Starting Phase 1 MVP run")
    print("[CONTROLLER] Project root:", project_root)

    llm = LLMClient(model="agent-coder")
    workspace = WorkspaceManager(project_root)
    maven = MavenRunner(project_root, timeout_seconds=15)

    print("[CONTROLLER] Calling LLM...")
    generated = llm.generate_code(task_prompt)

    print("[CONTROLLER] Writing generated Java files...")
    workspace.write_java_files(
        main_class=generated["main_class"],
        test_class=generated["test_class"]
    )

    print("[CONTROLLER] Running Maven tests...")
    result = maven.run_tests()

    print("[CONTROLLER] Maven exit code:", result.exit_code)

    if result.timed_out:
        print("[CONTROLLER] Maven timed out.")
        print(result.combined_output)
        return

    if result.success:
        print("[CONTROLLER] BUILD SUCCESS")
    else:
        print("[CONTROLLER] BUILD FAILURE")
        print(result.combined_output)


if __name__ == "__main__":
    main()