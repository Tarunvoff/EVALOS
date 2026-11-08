# EVALOS: Technical Debt & Architectural Risk Register

**Date:** November 2026  
**Auditor:** Principal AI Systems Architect  

---

## 1. Technical Debt Inventory

| ID | Category | Subsystem | Description of Debt / Defect | Severity | Remediation Effort | Architectural Consequence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TD-01** | **Packaging** | `pyproject.toml` | Optional dependencies (`fastapi`, `matplotlib`) imported unconditionally in root modules | **CRITICAL** | 2 hours | CLI `--help` and `apps/api/main.py` crash on default install. |
| **TD-02** | **Runtime Defect** | `evalos.rag.citation` | `support.claim_id` renamed in `grounding.py` but left un-migrated in `citation.py` | **CRITICAL** | 1 hour | Unhandled `AttributeError` crashes any RAG pipeline run with citations. |
| **TD-03** | **Frontend** | `apps/web` | JSX syntax errors (unescaped `->` arrows) in `repair-timeline/page.tsx` | **HIGH** | 1 hour | Next.js production build (`next build`) fails with Turbopack parse errors. |
| **TD-04** | **Architecture** | `evalos.pipeline` | Monolithic God-Object: `Pipeline` exceeds 1,760 lines with 20+ mixed concerns | **HIGH** | 3 days | High coupling; modifications to repair logic regularly break evaluation or memory. |
| **TD-05** | **Algorithm** | `evalos.rag.grounding` | Naive unigram token overlap without stopword filtering or negation handling | **HIGH** | 2 days | Direct factual contradictions (negations) classified as 100% supported. |
| **TD-06** | **Algorithm** | `evalos.repair` | Delta application uses string replacement (`replace(text, delta, 1)`) | **HIGH** | 2 days | Duplicate section content replaces wrong occurrence; offset desynchronization. |
| **TD-07** | **Concurrency** | `evalos.memory.storage` | Synchronous monolithic JSON serialization under a threading lock on every save | **HIGH** | 2 days | Zero horizontal scaling; file handle contention chokes concurrent API requests. |
| **TD-08** | **Algorithm** | `evalos.memory` | Adaptive threshold formula tightens thresholds when models fail | **HIGH** | 1 day | Induces positive failure feedback loop; causes cascading repair exhaustion. |
| **TD-09** | **Architecture** | `apps/api/state.py` | Global in-memory variable `state.last_trace` used for trace retrieval | **MEDIUM** | 1 day | Multi-worker deployments (Gunicorn/Uvicorn) lose traces across process boundaries. |
| **TD-10** | **Algorithm** | `evalos.rag.agent_eval` | Superficial string-matching of static JSON trace keys | **MEDIUM** | 2 days | Zero real runtime agent monitoring; misleading "agent reliability" claims. |
| **TD-11** | **Testing** | `tests/` | 100% reliance on synthetic mock providers; zero live Ollama or provider integration tests | **MEDIUM** | 2 days | Provider edge cases, streaming truncations, and JSON formatting errors go undetected. |
| **TD-12** | **Docs / Demo** | `docs/demos/` | All 7 demo scenario markdown files are 10-line bulleted outlines | **LOW** | 1 day | Marketing promise of before/after metrics and trace walkthroughs is false. |

---

## 2. In-Depth Root Cause & Remediation Profiles

### TD-01: Packaging & Dependency Decoupling
- **Root Cause:** Developers separated `bench` and `api` dependencies to keep the core package lightweight, but introduced hard imports in `evalos/benchmarks/__init__.py` and `apps/api/main.py`.
- **Remediation:**
  1. Move `fastapi` and `uvicorn` into core dependencies, or guard `evalos/api/app.py` imports with lazy loading and informative runtime error messages.
  2. Implement lazy importing in `evalos/benchmarks/reporting.py` so `charts.py` (`matplotlib`) is only imported when chart generation is explicitly requested.

### TD-04: Monolithic Pipeline Refactoring
- **Root Cause:** Feature creep during the May 27–June 2 sprint. New features (ensembles, confidence weighting, oscillation damping, RAG repair) were appended directly into `Pipeline` methods and module-level helper functions.
- **Remediation Plan:** Deconstruct `Pipeline` into a clean composite pipeline using an event-driven or middleware architecture:
  ```
  PipelineContext
  ├── RequestStage (generation, streaming)
  ├── VerificationStage (grounding, citations, schema validation)
  ├── EvaluationStage (ensemble scoring, criteria generation)
  ├── RepairStage (selective delta calculation, rollback check)
  └── InstrumentationStage (tracer, memory adapter, metrics)
  ```

### TD-05: Grounding Entailment Upgrade
- **Root Cause:** Initial prototype relied on quick string tokenization to avoid heavy machine learning dependencies.
- **Remediation:** Replace unigram token overlap with a dual-stage verification pipeline:
  1. **Stage 1 (Lexical Fast-Path):** Stopword-filtered, lemmatized BM25 or token precision to discard completely unrelated text in $<1\text{ms}$.
  2. **Stage 2 (Semantic Entailment):** An optional lightweight ONNX-runtime cross-encoder (e.g. MiniLM or DeBERTa-v3 quantized) or an LLM-guided NLI prompt (`premise`, `hypothesis` $\to$ `entails`, `contradicts`, `neutral`).

### TD-07: Concurrent Storage Architecture
- **Root Cause:** `JsonMemoryStorage` and `SQLiteMemoryStorage` were implemented as quick key-value persistence layers without schema design.
- **Remediation:**
  1. Design a normalized SQLite schema with dedicated tables: `model_evaluations`, `criterion_failures`, `repair_outcomes`, `section_stability`.
  2. Use standard SQL queries with indexed lookups (`WHERE model = ? AND domain = ?`) rather than deserializing the entire historical database into memory on every request.
  3. Support pluggable external stores (PostgreSQL / Redis) for enterprise deployments.

