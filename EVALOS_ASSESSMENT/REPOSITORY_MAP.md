# EVALOS: Complete Repository Map & Architectural Inventory

**Date:** November 2026  
**Scope:** Full repository map across `c:\EVALOS`  

---

## 1. Directory Tree & Layout Overview

```
c:\EVALOS
├── .env                              # Local environment variables (Ollama host, model name)
├── .evalos_memory.json               # Serialized state of Adaptive Memory (JSON store)
├── .gitignore                        # Git exclusion rules
├── LICENSE                           # MIT License
├── pyproject.toml                    # Hatchling build specification & dependency configuration
├── README.md                         # Project documentation and marketing pitch
├── uv.lock                           # Locked dependency resolution (uv package manager)
├── .github/
│   ├── copilot-instructions.md       # LLM development instructions
│   └── workflows/
│       ├── ci.yml                    # GitHub Actions CI (runs pytest on push/PR)
│       └── publish.yml               # Package publish workflow (stub)
├── apps/
│   ├── api/                          # FastAPI Backend Application
│   │   ├── main.py                   # Uvicorn entrypoint (host/port configuration)
│   │   └── README.md                 # API quickstart
│   └── web/                          # Next.js Frontend Application
│       ├── package.json              # Next.js 16 + React 19 + Tailwind CSS dependencies
│       ├── pnpm-lock.yaml            # pnpm dependency lock
│       ├── next.config.ts            # Next.js configuration
│       └── src/
│           ├── app/                  # App Router pages (Dashboard, Playground, etc.)
│           └── components/           # UI components (MetricCard, Panel, Shell)
├── benchmarks/                       # Benchmark Fixtures and Docs
│   ├── README.md                     # Benchmark documentation
│   └── fixtures/                     # Test datasets (10 JSONL items across 5 domains)
├── docs/                             # Documentation, architecture guides, demo outlines
│   ├── architecture.md               # High-level Mermaid system diagram
│   ├── benchmarks.md                 # Benchmark methodology notes
│   ├── contributing.md               # Contributor instructions
│   ├── demos.md                      # Index of demo scenarios
│   ├── evalos-features.md            # Comprehensive feature documentation
│   ├── oss-release.md                # Open-source release announcement draft
│   ├── quickstart.md                 # Setup guide
│   ├── roadmap.md                    # Roadmap milestones
│   ├── screenshots.md                # UI screenshot placeholders
│   └── demos/                        # Demo scenarios (stubs)
├── src/evalos/                       # Core Python Package Source
│   ├── __init__.py                   # Package exports
│   ├── cli.py                        # Typer CLI runner
│   ├── config.py                     # Pydantic configuration models
│   ├── criteria.py                   # Dynamic criteria generator
│   ├── errors.py                     # Custom exception hierarchy
│   ├── eval.py                       # LLM-as-a-judge evaluator
│   ├── logging.py                    # Structured logging setup (structlog)
│   ├── metrics.py                    # Quality/efficiency metric definitions
│   ├── pipeline.py                   # Monolithic execution orchestration runtime
│   ├── repair.py                     # Selective section-level repair engine
│   ├── retry.py                      # Resilient retry configuration
│   ├── streaming.py                  # SSE streaming types
│   ├── types.py                      # Core Pydantic domain models
│   ├── utils.py                      # JSON extraction helpers
│   ├── api/                          # FastAPI app routes, schemas, and state
│   ├── benchmarks/                   # Benchmark runner, reporting, charts, scoring
│   ├── memory/                       # Adaptive memory models, analytics, storage
│   ├── observability/                # Tracing, timelines, heatmaps, snapshots
│   ├── providers/                    # LiteLLM, Ollama, and resilient provider adapters
│   └── rag/                          # Grounding, citations, hallucination, agent evaluation
└── tests/                            # Pytest Test Suite
    ├── conftest.py                   # Pytest fixtures and mock setups
    ├── test_integration_adaptive_memory.py
    ├── test_memory.py
    ├── test_observability.py
    ├── test_pipeline.py
    └── test_schema_governance.py
```

---

## 2. Deep Module-by-Module Inspection

### 2.1 Core Runtime Engine (`src/evalos/`)

#### A. Pipeline Orchestrator (`src/evalos/pipeline.py`)
- **Purpose:** Central coordinator that executes the full generation lifecycle: Criteria generation $\to$ Memory lookup $\to$ Generation $\to$ RAG verification $\to$ Evaluation $\to$ Selective Repair Loop $\to$ Rollback Protection $\to$ Metrics & Trace.
- **Dependencies:** `eval.py`, `repair.py`, `criteria.py`, `memory/`, `rag/`, `observability/`, `providers/`.
- **Inputs:** `query: str`, `optimize_for: list[str]`, optional `retrieved_documents`, `citations`, `agent_trace`.
- **Outputs:** `GenerationResponse` (contains final text, evaluation results, repair records, metrics, trace).
- **Status:** **FUNCTIONAL (with architectural coupling)**. File is >1,700 lines; contains extensive helper functions and business logic that belong in separate domains.

#### B. Selective Repair Engine (`src/evalos/repair.py`)
- **Purpose:** Builds targeted prompts that force the LLM to output minimal JSON deltas for failed sections rather than rewriting whole responses.
- **Dependencies:** `types.py`, `config.py`, `utils.py`, `providers/base.py`.
- **Inputs:** `response_text`, `evaluation: EvaluationResult`, `locked_sections: set[str]`.
- **Outputs:** `tuple[repaired_text, list[RepairDelta], list[str], list[str], int, float, bool]`.
- **Status:** **FUNCTIONAL PROTOTYPE**. Relies on naive string replacement (`_apply_deltas`) which fails if section boundaries shift.

#### C. LLM-as-a-Judge Evaluator (`src/evalos/eval.py`)
- **Purpose:** Scores responses against active criteria using strictness profiles (`relaxed`, `balanced`, `strict`, `adversarial`).
- **Dependencies:** `types.py`, `config.py`, `utils.py`, `providers/base.py`.
- **Inputs:** `query`, `response_text`, `criteria: list[Criterion]`.
- **Outputs:** `EvaluationResult` (scores, passed/failed flags, rationales, affected sections).
- **Status:** **FUNCTIONAL**. Structured JSON prompting parses well; threshold adjustments apply accurately.

#### D. Criteria Generator (`src/evalos/criteria.py`)
- **Purpose:** Dynamically constructs 3 to 6 evaluation criteria tailored to the query and `optimize_for` tags.
- **Dependencies:** `types.py`, `config.py`, `providers/base.py`.
- **Inputs:** `query`, `optimize_for: list[str]`.
- **Outputs:** `list[Criterion]` (name, description, weight, threshold, severity).
- **Status:** **COMPLETE**. Clean implementation with robust JSON extraction fallback.

---

### 2.2 RAG Verification & Governance (`src/evalos/rag/`)

| File | Purpose | Inputs / Outputs | Implementation Status | Latent Flaws / Notes |
| :--- | :--- | :--- | :--- | :--- |
| `grounding.py` | Evaluates support for claims against retrieved documents | In: docs, response<br>Out: `GroundingResult` | **PARTIAL** | Pure unigram token overlap. Fails on negation, antonyms, and paraphrases. |
| `hallucination.py` | Detects hallucination rate and risk levels | In: `GroundingResult`<br>Out: `HallucinationResult` | **COMPLETE (Trivial)** | Simply calculates $\frac{\text{unsupported}}{\text{total}}$. No semantic analysis. |
| `citation.py` | Verifies citations against source document spans | In: docs, citations, grounding<br>Out: `CitationResult` | **BROKEN** | Line 55 references `support.claim_id` causing fatal `AttributeError`. |
| `agent_eval.py` | Evaluates agent tool correctness, planning, reasoning | In: `AgentTrace`<br>Out: `AgentEvalResult` | **PROTOTYPE** | Static string matching against user-provided JSON. Does not monitor execution. |
| `repair_rag.py` | Applies `remove`, `replace`, `cite` actions to fix RAG errors | In: text, docs, grounding, citation<br>Out: `RAGRepairResult` | **FUNCTIONAL** | LLM-driven or fallback regex sentence deletion. |
| `dependency.py` | Builds DAG of claim dependencies; penalizes children | In: `ClaimDependency`<br>Out: adjusted scores | **COMPLETE** | Sound graph traversal; correctly penalizes downstream dependent claims. |
| `canonical.py` | Canonicalizes claim IDs across runs | In: claim dict<br>Out: `CanonicalClaim` list | **COMPLETE** | Deterministic SHA-256 ID generation. |
| `validation.py` | Validates schemas of citations and agent traces | In: dicts<br>Out: `ValidationReport` | **COMPLETE** | Thorough Pydantic-based schema validation. |

---

### 2.3 Adaptive Memory (`src/evalos/memory/`)

- **`memory.py`:** Core coordinator storing model failure rates, domain failure rates, strategy success rates, and section stability. Supports exponential decay of historical samples.
- **`adaptive_thresholds.py`:** Computes dynamic thresholds. *Flaw:* Penalizes failing models by making thresholds stricter, inducing death spirals.
- **`storage.py`:** Provides `JsonMemoryStorage` and `SQLiteMemoryStorage`. Both serialize the entire state into a single atomic blob. Zero row-level indexing or multi-worker concurrency safety.
- **`analytics.py` & `models.py`:** Clean data models and reporting summaries.

---

### 2.4 Observability & Tracing (`src/evalos/observability/`)

- **`tracer.py`:** Captures request lifecycle steps, latency breakdowns, criteria, evaluations, and repairs. Produces formatted ASCII traces.
- **`snapshot.py`:** Normalizes traces by zero-basing timestamps and sorting dependencies for deterministic regression testing.
- **`timelines.py` & `heatmaps.py`:** ASCII visualizations for console and markdown rendering.
- **`dashboard.py`:** Incomplete stub (contains 4 lines of code).

---

### 2.5 API & Web Applications (`apps/`)

- **`apps/api/` (FastAPI):**
  - Exposes `/generate`, `/trace`, `/benchmark/run`, `/benchmark/results`, `/dashboard/metrics`, `/agent/eval`.
  - *Status:* **BROKEN OUT-OF-THE-BOX**. Missing `fastapi` and `uvicorn` in base dependencies. In-memory state (`state.last_trace`) lost on reload or multiple workers.
- **`apps/web/` (Next.js 16 + React 19):**
  - Modern dark-themed dashboard with Playground, Grounding Viewer, Repair Timeline, and Benchmarks.
  - *Status:* **BROKEN BUILD**. Turbopack compilation fails on 4 unescaped `>` characters in `repair-timeline/page.tsx`.

---

### 2.6 Benchmarks (`benchmarks/` & `src/evalos/benchmarks/`)

- **Runner & Strategies:** Compares `vanilla`, `retry`, `best_of_n`, and `evalos`.
- **Fixtures:** 10 total examples across 5 domains (`factual_qa`, `hallucination_heavy`, `rag_qa`, `reasoning`, `tool_use`).
- *Status:* **BROKEN RUNNER**. `evalos.benchmarks.__init__` crashes on missing `matplotlib` unless the optional `[bench]` extra is manually installed.

