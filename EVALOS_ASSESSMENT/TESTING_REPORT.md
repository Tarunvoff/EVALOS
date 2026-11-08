# EVALOS: Comprehensive Testing & Empirical Verification Report

**Date:** November 2026  
**Auditor:** Senior AI Quality & Systems Reliability Engineer  

---

## 1. Test Suite Execution Summary

All tests were executed using `pytest` in the local Python 3.13 virtual environment:

```
Platform: Windows (Python 3.13.7, pytest-9.0.3, pluggy-1.6.0)
Root Directory: C:\EVALOS
Config File: pyproject.toml
Test Discovery: 24 collected items across 5 test files
```

### 1.1 Test Execution Results (After Initial Repository Recovery)

```
============================= test session starts =============================
collected 24 items

tests/test_integration_adaptive_memory.py::test_repair_regression_and_locking PASSED [  4%]
tests/test_integration_adaptive_memory.py::test_adaptive_threshold_caps_and_decay PASSED [  8%]
tests/test_integration_adaptive_memory.py::test_confidence_weighting PASSED [ 12%]
tests/test_integration_adaptive_memory.py::test_cold_start_protection PASSED [ 16%]
tests/test_integration_adaptive_memory.py::test_memory_versioning_migration PASSED [ 20%]
tests/test_integration_adaptive_memory.py::test_full_pipeline_stability PASSED [ 25%]
tests/test_integration_adaptive_memory.py::test_multi_provider_consistency PASSED [ 29%]
tests/test_integration_adaptive_memory.py::test_observability_trace_and_metrics PASSED [ 33%]
tests/test_integration_adaptive_memory.py::test_long_run_stability PASSED [ 37%]
tests/test_memory.py::test_memory_record_and_get PASSED                  [ 41%]
tests/test_observability.py::test_format_trace PASSED                    [ 45%]
tests/test_observability.py::test_trace_render_includes_repair_lineage PASSED [ 50%]
tests/test_pipeline.py::test_pipeline_selective_repair PASSED            [ 54%]
tests/test_pipeline.py::test_pipeline_stream PASSED                      [ 58%]
tests/test_schema_governance.py::test_canonical_claim_determinism PASSED [ 62%]
tests/test_schema_governance.py::test_dependency_penalty_applies PASSED  [ 66%]
tests/test_schema_governance.py::test_reasoning_tool_validation PASSED   [ 70%]
tests/test_schema_governance.py::test_citation_schema_version_mismatch PASSED [ 75%]
tests/test_schema_governance.py::test_snapshot_trace_stability PASSED    [ 79%]
tests/test_schema_governance.py::test_snapshot_trace_orders_dependencies PASSED [ 83%]
tests/test_schema_governance.py::test_dependency_descendants_traversal PASSED [ 87%]
tests/test_schema_governance.py::test_citation_missing_schema_version_repairs_and_provenance PASSED [ 91%]
tests/test_schema_governance.py::test_invalid_agent_trace_schema PASSED  [ 95%]
tests/test_schema_governance.py::test_snapshot_generation_response_determinism PASSED [100%]

============================= 24 passed in 8.12s ==============================
```

---

## 2. Forensic Discovery of Latent Production Bugs

While the 24 unit/integration tests pass, targeted empirical testing of untested codepaths revealed **four critical, blocking production defects**:

---

### Bug 1: Fatal `AttributeError` in Citation Evaluation (`src/evalos/rag/citation.py`)

- **Trigger:** Calling `CitationEvaluator().evaluate()` when retrieved documents and generated claims are present.
- **Empirical Execution Command:**
  ```bash
  uv run python -c "from evalos.rag.citation import CitationEvaluator; from evalos.rag.grounding import GroundingResult, ClaimSupport; g = GroundingResult(grounding_score=1.0, supported_claims=[ClaimSupport(canonical_claim_id='c1', external_claim_id='e1', claim='test', support_score=1.0, support_type='supported')]); ce = CitationEvaluator(); ce.evaluate(retrieved_documents=[], citations=[], grounding=g)"
  ```
- **Error Traceback:**
  ```
  File "C:\EVALOS\src\evalos\rag\citation.py", line 55, in evaluate
    if support.claim_id not in mapping_lookup:
       ^^^^^^^^^^^^^^^^
  AttributeError: 'ClaimSupport' object has no attribute 'claim_id'
  ```
- **Root Cause:** In `src/evalos/rag/grounding.py` (line 14), `ClaimSupport` attributes were renamed to `canonical_claim_id` and `external_claim_id`. `citation.py` (lines 55, 58) was never updated, referencing obsolete `support.claim_id`.
- **Severity:** **CRITICAL**. Any RAG query with supported claims that invokes citation validation crashes the application runtime with an unhandled 500 error.

---

### Bug 2: Production Build Failure in Next.js Frontend (`apps/web`)

- **Trigger:** Running `pnpm --prefix apps/web build` (Next.js production build).
- **Error Output:**
  ```
  Error: Turbopack build failed with 4 errors:
  ./src/app/repair-timeline/page.tsx:32:47
  Unexpected token. Did you mean `{'>'}` or `&gt;`?
    32 | {item.before.toFixed(2)} -> {item.after.toFixed(2)}
       |                           ^
  ./src/app/repair-timeline/page.tsx:78:26: grounding -> align claims with retrieved docs
  ./src/app/repair-timeline/page.tsx:81:25: citation -> include span-level evidence
  ./src/app/repair-timeline/page.tsx:84:26: reasoning -> add causal justification
  ```
- **Root Cause:** Raw unescaped `->` arrows written directly inside JSX elements without curly braces or HTML entities (`&gt;`).
- **Severity:** **HIGH**. The web application cannot be deployed or built for production.

---

### Bug 3: Immediate Crash of Benchmark CLI on Import (`src/evalos/benchmarks/`)

- **Trigger:** Running `uv run python -m evalos.benchmarks.cli --help`.
- **Error Output:**
  ```
  File "C:\EVALOS\src\evalos\benchmarks\charts.py", line 6, in <module>
    import matplotlib.pyplot as plt
  ModuleNotFoundError: No module named 'matplotlib'
  ```
- **Root Cause:** `evalos.benchmarks.__init__.py` imports `BenchmarkRunner`, which imports `reporting.py`, which unconditionally imports `charts.py` (`matplotlib`). However, `matplotlib` is listed as an optional dependency in `pyproject.toml` (`[project.optional-dependencies] bench = ["matplotlib"]`).
- **Severity:** **MEDIUM**. The advertised benchmark suite cannot run in standard environments.

---

### Bug 4: Immediate Crash of FastAPI Backend on Startup (`apps/api/`)

- **Trigger:** Running `python apps/api/main.py`.
- **Error Output:**
  ```
  File "C:\EVALOS\src\evalos\api\app.py", line 8, in <module>
    from fastapi import FastAPI, HTTPException
  ModuleNotFoundError: No module named 'fastapi'
  ```
- **Root Cause:** `fastapi` and `uvicorn` are relegated to `[project.optional-dependencies] api = [...]` rather than main runtime dependencies, breaking the quickstart instructions documented in `README.md`.
- **Severity:** **MEDIUM**. Fresh installs fail the primary documented startup command.

---

## 3. Test Coverage Gaps & Mock Dependency Analysis

| Module | Real Tests | Mocked / Fake Tests | Untested Critical Codepaths | Risk Level |
| :--- | :--- | :--- | :--- | :--- |
| `evalos.pipeline` | 0 | 2 (`FakeProvider`) | Streaming with real LLM, timeout fallbacks, token budget exhaustion | **HIGH** |
| `evalos.repair` | 0 | 2 (`FakeProvider`) | Real LLM JSON malformation, overlapping section deltas, boundary shifts | **HIGH** |
| `evalos.eval` | 0 | 1 (`AdaptiveFakeProvider`) | Strictness prompt parsing, temperature variations, calibration | **MEDIUM** |
| `evalos.rag.grounding` | 0 | Indirect via schema test | Real text negation, tokenization edge cases, multi-document ranking | **CRITICAL** |
| `evalos.rag.citation` | 0 | 0 | Non-empty citation evaluation (crashed with `AttributeError`) | **CRITICAL** |
| `evalos.rag.agent_eval` | 1 | 0 | Real agent traces with multiple identical tool names, nested arguments | **MEDIUM** |
| `evalos.memory` | 7 | 2 | Concurrent multi-process file contention, SQLite corruptions | **HIGH** |
| `evalos.benchmarks` | 0 | 0 | Entire benchmark suite (runner, scoring, charts) completely untested! | **CRITICAL** |

### Summary
The existing test suite relies heavily on hardcoded synthetic mocks (`AdaptiveFakeProvider`, `FakeProvider`) that return predictable strings (`"REPAIRED"`, `"WORSE"`, `"A\n\nB"`). There are **zero tests** executing against real local LLMs (Ollama) or live cloud providers, and **zero tests** exercising `evalos.benchmarks` or `evalos.rag.citation`.

