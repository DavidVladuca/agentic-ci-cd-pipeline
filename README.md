# Local CI/CD Pipeline Code Generator — V1

This branch contains the first prototype of the project: a local CI/CD-style Java code-generation loop.

V1 asks a local Ollama model to generate Java source code and JUnit tests, writes them into a Maven project, runs `mvn clean test`, captures build/test failures, and retries with feedback until the code passes or the attempt limit is reached.

This version was mainly built to explore the basic agent loop:

```text
Prompt → LLM JSON output → write Java files → run Maven/JUnit → feed back errors → retry
```

The main project is now **V2**, available on the `mainV2` branch.

V2 evolves this prototype into a Docker-sandboxed Java program-repair agent that works on existing Maven projects, applies patch-based fixes, validates repairs against public and hidden tests, tracks regressions, and produces benchmark reports and patch artifacts.

For the full architecture, benchmark results, demo, and engineering process, see the README on the `mainV2` branch.
