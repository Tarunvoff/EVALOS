# EVALOS: Phase 1A Baseline Technical Assessment

**Date:** November 2026  
**Auditor / Engineer:** Senior Python Infrastructure Engineer  
**Stage:** Step A — Baseline Establishment (Pre-Modification)  

---

## 1. Environment & Repository Information

| Parameter | Value | Verification Evidence |
| :--- | :--- | :--- |
| **Repository Root** | `c:\EVALOS` | Working directory |
| **Git Current Branch** | `main` | `git branch` output |
| **Latest Git Commit** | `5c06a5b` | `feat: add initial implementation of EvalOS web app and API` |
| **Working-Tree Status** | Modified unstaged files | Unstaged changes in `config.py`, `pipeline.py`, `repair.py`, `memory.py`, `models.py`, `types.py` (preserved) |
| **Python Version** | Python 3.13.7 | `uv run python --version` |
| **Package Manager** | `uv` / `hatchling` | `pyproject.toml` |
| **Virtual Environment** | `C:\EVALOS\.venv` | Python 3.13 virtual environment |

---

## 2. Existing Dependency Configuration Audit (`pyproject.toml`)

### 2.1 Declared Runtime Dependencies
```toml
dependencies = [
  "pydantic>=2.6",
  "litellm>=1.40.0",
  "structlog>=24.1.0",
  "typer>=0.12.3",
  "anyio>=4.4.0",
  "httpx>=0.27.0",
]
```

### 2.2 Declared Optional Dependencies
```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
  "pytest-asyncio>=0.23.8",
  "ruff>=0.5.0",
  "mypy>=1.10.0",
  "types-requests>=2.32.0",
]
bench = [
  "matplotlib>=3.9.0",
]
api = [
  "fastapi>=0.112.0",
  "uvicorn>=0.30.0",
]
```

### 2.3 Scripts / Entry Points
```toml
[project.scripts]
evalos = "evalos.cli:app"
evalos-bench = "evalos.benchmarks.cli:app"
```

### 2.4 UV Deprecation Warning
`uv` issues the following warning on every invocation:
```
warning: The `tool.uv.dev-dependencies` field (used in `pyproject.toml`) is deprecated and will be removed in a future release; use `dependency-groups.dev` instead
```
`pyproject.toml` contains duplicate dev dependency declarations:
1. Under `[project.optional-dependencies] dev = [...]`
2. Under deprecated `[tool.uv] dev-dependencies = [...]`

---

## 3. Empirical Failure Reproduction (Baseline Test Results)

### Test A: Core Package Import
```bash
uv run python -c "import evalos"
```
- **Status:** **PASS**
- **Result:** `evalos` imports cleanly.

### Test B: FastAPI Backend Import
```bash
uv run python -c "from evalos.api.app import app"
```
- **Status:** **REPRODUCED FAILURE**
- **Traceback:**
  ```
  File "C:\EVALOS\src\evalos\api\app.py", line 8, in <module>
    from fastapi import FastAPI, HTTPException
  ModuleNotFoundError: No module named 'fastapi'
  ```
- **Finding:** `fastapi` is required by `src/evalos/api/app.py` and `apps/api/main.py`. Because it is placed in `[project.optional-dependencies] api = [...]`, normal installation fails the documented backend startup.

### Test C: Benchmark Package Import & CLI
```bash
uv run python -c "import evalos.benchmarks"
uv run python -m evalos.benchmarks.cli --help
```
- **Status:** **REPRODUCED FAILURE**
- **Traceback:**
  ```
  File "C:\EVALOS\src\evalos\benchmarks\__init__.py", line 6, in <module>
    from evalos.benchmarks.runner import BenchmarkRunner
  File "C:\EVALOS\src\evalos\benchmarks\runner.py", line 9, in <module>
    from evalos.benchmarks.reporting import export_reports
  File "C:\EVALOS\src\evalos\benchmarks\reporting.py", line 10, in <module>
    from evalos.benchmarks.charts import render_charts
  File "C:\EVALOS\src\evalos\benchmarks\charts.py", line 6, in <module>
    import matplotlib.pyplot as plt
  ModuleNotFoundError: No module named 'matplotlib'
  ```
- **Finding:** Hard import coupling. `src/evalos/benchmarks/__init__.py` imports `BenchmarkRunner`, which imports `reporting.py`, which unconditionally imports `charts.py` (`matplotlib`). Thus, neither `import evalos.benchmarks` nor the registered entrypoint `evalos-bench --help` can run without `matplotlib`.

### Test D: Isolated Fresh Environment Installation
In a clean, isolated virtualenv (`TEMP/evalos_test_env`):
- `pip install -e .` succeeds.
- Core CLI `evalos --help` succeeds.
- `evalos.api` fails with `ModuleNotFoundError: No module named 'fastapi'`.
- `evalos-bench --help` fails with `ModuleNotFoundError: No module named 'matplotlib'`.

### Test E: Existing Pytest Suite
```bash
uv run pytest
```
- **Status:** **PASS** (24 passed in 4.68s)
- **Note:** Tests currently pass because they mock providers (`FakeProvider`, `AdaptiveFakeProvider`) and do not import `evalos.api` or `evalos.benchmarks`.

---

## 4. Root Causes & Target Files for Phase 1A

1. **`pyproject.toml`:**
   - `fastapi` and `uvicorn` must be evaluated for core runtime vs. dependency declaration.
   - Deprecated `tool.uv.dev-dependencies` must be resolved according to modern `dependency-groups` or consolidated under `project.optional-dependencies`.
2. **`src/evalos/benchmarks/reporting.py` & `src/evalos/benchmarks/__init__.py`:**
   - Eager import of `charts.py` (`matplotlib`) must be replaced with a lazy import at the execution boundary (`render_charts` call site).
   - If `matplotlib` is not installed, running benchmarks without charts or calling `--help` should work seamlessly, while attempting to render charts should raise a clear, helpful `ImportError`.

