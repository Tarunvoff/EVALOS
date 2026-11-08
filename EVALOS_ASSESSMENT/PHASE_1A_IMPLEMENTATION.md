# EVALOS: Phase 1A Implementation Report

**Date:** November 2026  
**Auditor / Engineer:** Senior Python Infrastructure Engineer  
**Task:** Phase 1A — Baseline Establishment & Python Packaging Stabilization  

---

## 1. Root Causes Identified

1. **Missing Backend Runtime Dependencies in Core:**
   `fastapi` and `uvicorn` were placed in `[project.optional-dependencies] api = [...]` rather than main runtime dependencies, causing `from evalos.api.app import app` and `python apps/api/main.py` to fail immediately with `ModuleNotFoundError` on standard installations.
2. **Hard Import Coupling with Optional Visualization Dependency:**
   `src/evalos/benchmarks/__init__.py` imported `BenchmarkRunner`, which imported `export_reports` from `reporting.py`, which eagerly imported `from evalos.benchmarks.charts import render_charts`, which executed `import matplotlib.pyplot as plt` at the top of `charts.py`. This caused `evalos-bench --help`, `import evalos.benchmarks`, and `from evalos.api.app import app` to crash if `matplotlib` was not installed.
3. **Deprecated UV Dev Dependency Syntax:**
   `pyproject.toml` declared `[tool.uv] dev-dependencies = [...]`, which triggered deprecation warnings on every `uv` execution.

---

## 2. Changes Implemented

### 2.1 `pyproject.toml`
- **Added Core Runtime Dependencies:**
  ```toml
  dependencies = [
    "pydantic>=2.6",
    "litellm>=1.40.0",
    "structlog>=24.1.0",
    "typer>=0.12.3",
    "anyio>=4.4.0",
    "httpx>=0.27.0",
    "fastapi>=0.112.0",
    "uvicorn>=0.30.0",
  ]
  ```
  *Rationale:* FastAPI and Uvicorn power `src/evalos/api/app.py` and `apps/api/main.py`, which constitute the primary documented backend service for EVALOS.
- **Retained Backward Compatibility:**
  Kept `api = ["fastapi>=0.112.0", "uvicorn>=0.30.0"]` under `[project.optional-dependencies]` so legacy install scripts specifying `.[api]` continue to work seamlessly.
- **Modernized Dev Dependency Group:**
  Replaced deprecated `[tool.uv] dev-dependencies` with modern standard `[dependency-groups] dev = [...]`.

### 2.2 `src/evalos/benchmarks/charts.py`
- **Implemented Lazy Execution-Boundary Import:**
  Removed top-level `import matplotlib.pyplot as plt`. Added a guarded lazy loader:
  ```python
  def _get_pyplot() -> Any:
      try:
          import matplotlib.pyplot as plt
          return plt
      except ImportError as exc:
          raise ImportError(
              "The 'matplotlib' package is required to render benchmark charts. "
              "Install it with: pip install 'evalos[bench]'"
          ) from exc
  ```
  *Rationale:* Prevents `matplotlib` from being imported during unrelated operations (`import evalos.benchmarks`, `evalos-bench --help`, or `evalos.api.app` import).
  *Explicit Error Handling:* When chart generation is actually invoked via `render_charts()`, it provides a clear, actionable error message instructing the user how to install the optional `[bench]` extra, satisfying rule B2 without silent suppression.

### 2.3 `tests/test_packaging.py`
- Added 4 automated regression tests to verify:
  1. `evalos` core imports.
  2. `evalos.api.app` imports and initializes `app.title`.
  3. `evalos.benchmarks` imports without `matplotlib` present.
  4. `render_charts` raises the explicit, actionable `ImportError` when `matplotlib` is missing.

---

## 3. Files Modified & Added

| File Path | Type | Nature of Change |
| :--- | :--- | :--- |
| `pyproject.toml` | Modified | Added `fastapi` and `uvicorn` to core dependencies; modernized `dependency-groups.dev`. |
| `src/evalos/benchmarks/charts.py` | Modified | Refactored `matplotlib` import into `_get_pyplot()` lazy boundary with helpful error. |
| `uv.lock` | Modified | Updated lockfile reflecting synchronized dependencies (`fastapi`, `uvicorn`, `starlette`). |
| `tests/test_packaging.py` | Added | 4 regression tests for core import, backend init, lazy benchmark import, and chart error. |

---

## 4. Verification Commands & Outputs

1. **Virtual Environment Sync:**
   ```bash
   uv sync
   ```
   *Output:* Installed `fastapi`, `uvicorn`, `starlette`, `opentelemetry-api`. Zero warnings.
2. **Clean Virtualenv Test (`TEMP/evalos_test_env_p1a`):**
   ```bash
   uv pip install -e .
   ```
   *Output:* Successfully installed without optional extras.
   - `evalos` import: **OK**
   - `from evalos.api.app import app`: **OK** (`app.title == "EvalOS API"`)
   - `evalos.benchmarks` import: **OK**
   - `evalos --help`: **OK**
   - `evalos-bench --help`: **OK**
3. **Regression Test Suite:**
   ```bash
   uv run pytest
   ```
   *Output:* **28 passed in 5.57s** (24 original tests + 4 packaging tests).

