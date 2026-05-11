# Java Repair Agent

A local autonomous Java repair agent that explores what happens when an LLM is placed inside a real software-engineering feedback loop.

Instead of asking a model to simply generate code, this project builds the surrounding system an agent needs to behave like a repair tool: isolated execution, structured model outputs, safe patch application, retry logic, rollback, hidden-test validation, and reproducible reports.

The goal was to understand agentic software engineering from the inside. I wanted to build the control loop myself: how the agent selects context, how it constrains the model, how it tests a patch, how it detects failure, and how it records evidence for every repair attempt.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Main Features](#main-features)
3. [Engineering Process](#engineering-process)
4. [Phase Summary](#phase-summary)
5. [Architecture](#architecture)
6. [How to Run](#how-to-run)
7. [Demo](#demo)
8. [Benchmark Results](#benchmark-results)
9. [Artifacts and Reports](#artifacts-and-reports)
10. [Limitations](#limitations)
11. [Final Notes](#final-notes)

---

## Project Overview

Java Repair Agent is a local program-repair pipeline for Java projects.

Given a broken Maven project, it:

1. copies the project into a sandbox,
2. injects hidden tests,
3. runs Maven/JUnit inside Docker,
4. extracts the failure,
5. selects relevant Java source files,
6. asks a local LLM for a strict JSON patch,
7. validates and applies production-only edits,
8. reruns the tests,
9. retries with feedback when the patch fails,
10. writes logs, metrics, reports, and patch artifacts.

The core idea is:

> The LLM proposes a repair. Docker, Maven, and JUnit decide whether it is valid.

This is intentionally local-first: the model runs through Ollama, repair attempts run in Docker, and the benchmark can be reproduced without relying on a cloud coding agent. Benchmark results are included later in the README after the architecture and usage sections.

---

## Main Features

- **Local LLM repair loop** — uses Ollama to generate structured file edits instead of conversational suggestions.
- **Strict JSON contract** — rejects invalid model outputs before they can touch the project.
- **Docker sandboxing** — runs Maven/JUnit in an isolated, resource-limited container.
- **Hidden-test benchmark** — evaluates repairs without leaking hidden test source into the LLM prompt.
- **Production-only patching** — the model cannot edit tests, `pom.xml`, hidden tests, or create arbitrary new files.
- **Multi-file repair support** — can patch multiple existing Java files in one attempt.
- **Patch artifacts** — stores attempt-level diffs, before/after snapshots, and final repair patches.
- **Retry with feedback** — failed attempts feed Maven/JUnit errors and previous patch context back into the model.
- **Rollback and stagnation handling** — rolls back compilation regressions and detects repeated no-change patches.
- **Benchmark reporting** — generates Markdown, JSON, and CSV reports with pass rate, timings, changed files, and failure status.

---

## Engineering Process

This project started after I first learned about AI agents in class. Existing tools already provide agent-like interfaces, but I wanted to understand the mechanics by building the loop myself: how an agent decides what to send to a model, how it validates the response, how it runs code safely, and how it knows whether it actually improved anything.

The first version was a code generator. It asked a local model to generate `App.java` and `AppTest.java`, then ran Maven until the tests passed. That worked, but it exposed the obvious weakness: the system was only as good as the handwritten tests.

The second version became a repair agent. Instead of generating a toy project from scratch, it loaded broken Java projects, injected hidden tests, selected relevant files, asked the model for patches, and validated them in Docker. This made the project much closer to a real software-engineering workflow.

While building the project from scratch, I split the core ideas into phases so that each capability could be designed, tested, and validated independently. The phase summary below shows how the project evolved from a small code-generation experiment into a sandboxed Java repair pipeline with benchmark reporting, patch artifacts, rollback, stagnation detection, and repository-level repair support.

The current version is still not a production coding agent, but it has the infrastructure that makes one possible. I stopped improving the benchmark once further gains would have required task-specific prompt tuning. That felt like the right engineering decision: the project should show what the system can do, but also where the current local model and heuristic file selection reach their limit.

---

## Phase Summary

### V1 — Code Generation Agent

| Phase | Summary |
|---|---|
| Phase 0 | Set up Java, Maven, UTF-8 encoding, Ollama, Docker, and JSON-only model output. |
| Phase 1 | Built the first prompt → JSON → write files → Maven test loop. |
| Phase 2 | Added retries using Maven/JUnit failure feedback. |
| Phase 3 | Added logging, timing metrics, error classification, and run summaries. |
| Phase 4 | Moved test execution into Docker. |
| Phase 5 | Cleaned configuration and CLI support for the first stable version. |

### V2 — Java Program Repair Agent

| Phase | Summary |
|---|---|
| Phase 6 | Added benchmark repair tasks with broken projects and hidden tests. |
| Phase 7 | Changed from code generation to patching existing production files. |
| Phase 8 | Added reusable repair pipeline and benchmark runner. |
| Phase 9 | Added task metadata and grouped benchmark statistics. |
| Phase 10 | Added patch artifacts and before/after snapshots. |
| Phase 11 | Added multi-file repair and stricter file safety rules. |
| Phase 12 | Added real-project repair mode. |

### V3 — Repository-Level Repair Direction

| Phase | Summary |
|---|---|
| Phase 13 | Added final patch export from original broken code to final repaired code. |
| Phase 14 | Hardened Docker execution with stricter sandbox limits. |
| Phase 15 | Added human-readable Markdown benchmark reports. |
| Phase 16 | Added local folder, zip, and GitHub import support. |
| Phase 17 | Added project analysis and heuristic source-file selection. |
| Phase 18 | Unified repair workflows and single-project reports. |
| Phase 19 | Hardened hidden-test exclusion, atomic writes, timeout reporting, and benchmark validity checks. |
| Phase 20 | Expanded benchmark coverage across more Java bug categories. |
| Phase 21 | Added the main CLI and dependency-prefetch support. |
| Phase 22 | Added rollback after compilation regressions. |
| Phase 23 | Expanded the benchmark to 25 tasks and evaluated hard-task limits. |
| Phase 24 | Cleaned the repository for presentation: docs, logging, constants, docstrings, and tests. |

---

## Architecture

The system is organized around one repair loop:

```text
Task / Project
    ↓
Sandbox copy + hidden tests
    ↓
Docker baseline test
    ↓
Failure extraction
    ↓
Relevant file selection
    ↓
LLM JSON patch
    ↓
Safe file rewrite
    ↓
Docker validation
    ↓
Retry or final report
```

Core components:

| Component | Role |
|---|---|
| `cli_main.py` | Main command-line interface. |
| `repair_pipeline.py` | Coordinates the full repair loop. |
| `llm_client.py` | Calls Ollama and validates strict JSON repair output. |
| `docker_runner.py` | Runs Maven/JUnit inside Docker. |
| `project_sandbox.py` | Copies projects and injects hidden tests. |
| `project_analyzer.py` + `file_selector.py` | Finds likely relevant source files. |
| `file_rewriter.py` | Applies safe production-only edits. |
| `diff_tracker.py` | Writes patches and before/after snapshots. |
| `repair_strategy.py` | Decides when to retry, rollback, expand context, or stop. |
| `benchmark_report.py` | Writes benchmark reports. |

The design keeps the LLM as only one part of the system. The surrounding infrastructure controls safety, validation, execution, and reporting.

---

## How to Run

### Requirements

- Python 3.10+
- Docker
- Ollama
- Java repair Docker image built from this repository
- Local Ollama model created from the included `Modelfile`

No third-party Python packages are required. The Python code uses the standard library.

---

### Create the local model

```bash
ollama create agent-coder -f Modelfile
```

Ollama must be running locally at:

```text
http://localhost:11434
```

---

### Build the Docker image

```bash
docker build -t agent-pipeline-java .
```

---

### Check the environment

```bash
python -m agent.cli_main doctor
```

---

### Run one repair task

Windows PowerShell:

```powershell
python -m agent.cli_main repair-task --task-dir "bug_tasks\age_validator_wrong_exception_type"
```

Linux/macOS/Git Bash:

```bash
python -m agent.cli_main repair-task --task-dir bug_tasks/age_validator_wrong_exception_type
```

---

### Run the benchmark

```bash
python -m agent.cli_main benchmark --tasks-dir bug_tasks
```

---

### Repair a local project

```bash
python -m agent.cli_main repair-project ^
  --project-dir path\to\project ^
  --task-file path\to\task.txt ^
  --name local_project_test
```

With hidden tests:

```bash
python -m agent.cli_main repair-project ^
  --project-dir path\to\project ^
  --task-file path\to\task.txt ^
  --hidden-tests-dir path\to\hidden_tests ^
  --name local_project_test
```

Without tests, the agent has no reliable correctness oracle. The repair loop is strongest when Maven/JUnit failures provide concrete feedback.

---

## Demo

This demo shows the agent repairing a real stateful data-structure bug: an `LruCache<K, V>` implementation that stores values correctly, but does not maintain proper least-recently-used ordering.

The task is small enough to understand quickly, but non-trivial enough to show the full repair loop: baseline failure detection, source-context selection, LLM patch generation, Docker/Maven validation, and final patch export.

![LRU Cache Repair Demo](docs/demo/lru-cache-repair-demo.gif)

> The waiting section in the GIF is sped up for readability. The run still executes the full local pipeline: doctor check, sandbox setup, baseline test failure, LLM repair generation, patch application, Docker/Maven validation, and final artifact export.

### Demo Task: LRU Cache Repair

**Repair task**

```text
Repair LruCache.

Rules:
- get(key) returns the value or null when absent
- get(key) must mark the key as recently used
- put(key, value) inserts or updates the value
- updating an existing key must not evict another key
- when capacity is exceeded, evict the least recently used key
- preserve the generic public API
```

**Bug metadata**

```json
{
  "difficulty": "hard",
  "category": "stateful-data-structure",
  "description": "LRU cache does not update recency on get and mishandles updates.",
  "expected_error_type": "TEST_FAILURE"
}
```

### Broken Implementation

The original implementation uses `LinkedHashMap`, but it does not refresh recency on `get`, and it evicts before checking whether `put` is only updating an existing key.

```java
import java.util.LinkedHashMap;
import java.util.Map;

public class LruCache<K, V> {
    private final int capacity;
    private final LinkedHashMap<K, V> values = new LinkedHashMap<>();

    public LruCache(int capacity) {
        if (capacity <= 0) {
            throw new IllegalArgumentException("capacity must be positive");
        }

        this.capacity = capacity;
    }

    public V get(K key) {
        return values.get(key);
    }

    public void put(K key, V value) {
        if (values.size() >= capacity) {
            K firstKey = values.keySet().iterator().next();
            values.remove(firstKey);
        }

        values.put(key, value);
    }

    public int size() {
        return values.size();
    }
}
```

### Public Test

The visible test checks only the simplest behavior, so it is not enough to expose the real bug.

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class LruCacheTest {
    @Test
    void storesAndRetrievesSingleValue() {
        LruCache<String, Integer> cache = new LruCache<>(2);

        cache.put("A", 1);

        assertEquals(1, cache.get("A"));
    }
}
```

### Hidden Tests

The hidden tests expose the actual repair requirements: `get` must update recency, and updating an existing key must not evict another entry.

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

public class LruCacheEvictionTest {
    @Test
    void getRefreshesRecencyBeforeEviction() {
        LruCache<String, Integer> cache = new LruCache<>(2);

        cache.put("A", 1);
        cache.put("B", 2);
        assertEquals(1, cache.get("A"));

        cache.put("C", 3);

        assertEquals(1, cache.get("A"));
        assertNull(cache.get("B"));
        assertEquals(3, cache.get("C"));
    }

    @Test
    void updatingExistingKeyDoesNotEvictOtherEntry() {
        LruCache<String, Integer> cache = new LruCache<>(2);

        cache.put("A", 1);
        cache.put("B", 2);
        cache.put("A", 10);

        assertEquals(2, cache.size());
        assertEquals(10, cache.get("A"));
        assertEquals(2, cache.get("B"));
    }
}
```

### What the Demo Shows

In the demo, the agent:

1. Runs `doctor` to verify Docker, Ollama, and the local model are available.
2. Copies the broken project into a sandbox.
3. Runs Maven/JUnit in Docker and confirms the baseline failure.
4. Selects the relevant production file: `src/main/java/LruCache.java`.
5. Sends the task, source context, and failure output to the local LLM.
6. Applies the returned patch safely.
7. Reruns Maven/JUnit inside Docker.
8. Succeeds on the first repair attempt.
9. Exports the final patch artifact.

The important success markers are:

```text
[REPAIR] Baseline failure detected.
[REPAIR] Repair attempt 1/5
[REPAIR] Written files: src/main/java/LruCache.java
[REPAIR] Docker/Maven exit code: 0
[REPAIR] REPAIR SUCCESS
[REPAIR] Final repair patch: artifacts/runs/.../lru_cache_eviction_order/final_repair.patch
```

---

## Benchmark Results

Latest benchmark:

| Difficulty | Solved | Total | Pass Rate |
|---|---:|---:|---:|
| Easy | 7 | 7 | 100% |
| Medium | 11 | 11 | 100% |
| Hard | 4 | 7 | 57% |
| **Total** | **22** | **25** | **88%** |

Benchmark coverage includes:

- compilation errors,
- loop and boundary bugs,
- string parsing bugs,
- null handling,
- exception contracts,
- generic collections,
- equals/hashCode contracts,
- sorting comparators,
- overloaded methods,
- inheritance overrides,
- date boundaries,
- mutable aliasing,
- stateful objects,
- package/import bugs,
- multi-file domain logic,
- parser state machines.

The three failed tasks are hard cases involving parser state machines, subtle multi-file domain logic, and model stagnation. These are kept in the benchmark because they make the result more honest and useful.

---

## Artifacts and Reports

Each run writes evidence to disk.

### Logs

```text
logs/
    agent_run_*.log
    run_summary_*.json
```

### Benchmark reports

```text
reports/
    repair_benchmark_*.json
    repair_benchmark_*.csv
    repair_report_*.md
```

### Patch artifacts

```text
artifacts/runs/<run-id>/<task-name>/
    attempt_1/
        attempt_1.patch
        before/
        after/
    final_before/
    final_after/
    final_repair.patch
```

This makes each benchmark result auditable: the report points to the exact source changes produced by the agent.

---

## Limitations

This is a strong prototype, not a production-grade autonomous software engineer.

Current limitations:

- repair quality depends on the local model,
- the benchmark is curated,
- file selection is heuristic,
- there is no Java AST parser yet,
- there is no call graph or semantic retrieval yet,
- arbitrary GitHub projects may fail because of dependencies,
- without tests, the agent cannot prove correctness,
- complex parser bugs and subtle multi-class invariants remain difficult.

The honest claim is:

> This agent repairs curated Java defects in a Docker sandbox while validating production-only edits, protecting hidden tests, generating patch artifacts, and reporting results.

The dishonest claim would be:

> This agent reliably repairs arbitrary real-world Java repositories.

It does not do that yet.

---

## Final Notes

This was a fun project because it turned "agentic AI" from a vague idea into something concrete.

The most important lesson was that the LLM is only one piece of an agent. The real engineering work is around it: giving it the right context, constraining its output, running code safely, detecting failure, retrying intelligently, and keeping enough artifacts to understand what happened.

This version is an entry point into a larger system. A future version could add:

- automatic test generation,
- mutation testing,
- Java AST parsing,
- call graph construction,
- semantic file retrieval,
- embedding-based context selection,
- better dependency handling,
- continuous repository monitoring,
- automatic issue reproduction,
- patch ranking,
- human-in-the-loop review,
- pull request generation.

The current system already demonstrates a complete local repair loop with measurable results. The next step would be making it more autonomous: not only repairing against existing tests, but also generating better tests and improving the project over time.
