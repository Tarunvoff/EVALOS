# EVALOS: Architectural Audit & Executive Summary

**Date:** November 2026  
**Auditor:** Principal AI Systems Architect & Infrastructure Researcher  
**Target:** EVALOS Core Runtime, Apps, and Tooling  
**Repository Working Directory:** `c:\EVALOS`  

---

## 1. Executive Synopsis

EVALOS was envisioned as an **AI Reliability Runtime** designed to solve the critical problem of non-deterministic, hallucinatory, and poorly grounded LLM and agent outputs. Rather than serving merely as another passive observability dashboard, EVALOS proposed an active, in-flight execution loop:
$$\text{Generation} \longrightarrow \text{Evaluation} \longrightarrow \text{Selective Repair} \longrightarrow \text{Rollback Protection} \longrightarrow \text{Deterministic Provenance}$$

Following a comprehensive technical and empirical audit of the entire repository, we deliver the following bottom-line assessment:

### Core Diagnosis: High-Potential Concept Burdened by Prototype Drift & Heuristic Brittleness
1. **The Core Thesis is Highly Defensible:** In-flight, selective section-level repair with rollback safety is fundamentally superior to wasteful, non-deterministic, full-sequence retry (`vanilla retry` or `best-of-N`). It saves tokens, reduces latency, and prevents catastrophic regression.
2. **Implementation vs. Marketing Gap is Severe:** The marketing claims in `README.md` and `docs/demos/` depict a polished, production-ready system with working demos, automated charts, and live dashboards. In reality:
   - All demo files in `docs/demos/*.md` are 10-line markdown stubs with no empirical data.
   - The Next.js frontend in `apps/web` fails production build with syntax errors in `repair-timeline/page.tsx`.
   - The FastAPI backend in `apps/api` cannot start in default virtual environments due to undeclared runtime dependencies (`fastapi`, `uvicorn` relegated to optional groups).
   - The Benchmark CLI fails on startup due to an unhandled optional import of `matplotlib`.
   - The citation evaluation module (`evalos.rag.citation`) contains a fatal `AttributeError` on `ClaimSupport.claim_id`.
3. **Algorithm Primitives are Fragile Heuristics:**
   - **Grounding & Hallucination:** Rely on naive unigram token-overlap sets without stopword filtering or semantic parsing. Negations (e.g., *"The tower is not in Paris"*) achieve >85% overlap with positive documents, masquerading as "supported".
   - **Selective Repair:** Text replacement relies on naive section slicing and string substitutions that fail when revised texts expand or shift boundary offsets.
   - **Adaptive Memory:** Adjusts evaluation thresholds upward upon repeated failures, triggering a positive feedback loop that guarantees cascading failure for borderline models.
   - **Agent Reliability:** Merely parses static user-provided JSON traces against hardcoded string checks; it does not intercept, monitor, or sandbox real tool executions.

---

## 2. High-Level Metrics & Repository Vitals

| Metric | Measured Value | Evidence / Notes |
| :--- | :--- | :--- |
| **Total Git Commits** | 8 commits | Spanning May 12, 2026 – May 29, 2026 |
| **Tracked Source Files** | 68 files | Core Python package, API, Web UI, Benchmarks, Docs |
| **Python Package Lines of Code** | ~4,800 LOC | `src/evalos` (excluding comments and docstrings) |
| **Unit / Integration Tests** | 24 tests | `tests/test_*.py` |
| **Test Suite Pass Rate** | 24 / 24 passing (100%)* | *After resolving missing helper functions in `pipeline.py` |
| **FastAPI Backend Status** | **BROKEN** out-of-the-box | `ModuleNotFoundError: No module named 'fastapi'` |
| **Next.js Frontend Build Status** | **BROKEN** | Turbopack compilation error: unescaped `>` in JSX |
| **Benchmark CLI Status** | **BROKEN** out-of-the-box | `ModuleNotFoundError: No module named 'matplotlib'` |
| **Citation Evaluation Status** | **BROKEN** (Latent Bug) | `AttributeError: 'ClaimSupport' object has no attribute 'claim_id'` |
| **Database Architecture** | Single-file JSON / SQLite | Monolithic state dump; zero concurrency safety |

---

## 3. Key Findings Across Evaluation Pillars

### A. Core Runtime (`src/evalos/pipeline.py`)
- **Strengths:** Clean async flow; supports provider abstraction via LiteLLM and Ollama; tracks token usage and granular step latencies (`latency_breakdown`); supports event streaming.
- **Flaws:** Monolithic file (>1,700 lines) coupling generation, prompt templating, memory adaptation, RAG validation, and trace logging. Rollback evaluation logic was initially inverted, breaking repair degradation safety.

### B. Selective Repair Engine (`src/evalos/repair.py`)
- **Strengths:** Clear prompt taxonomy directing the LLM to output section-level deltas instead of full rewrites; tracks edit distance ratios and token costs.
- **Flaws:** Naive character offset delta application. If section 1 text length changes, section 2 offsets become invalid. "Trust region violation" initially reverted the text back to draft without allowing re-evaluation.

### C. RAG Grounding & Hallucination Verification (`src/evalos/rag/`)
- **Strengths:** Implements claim canonicalization and dependency penalty graphs (`ClaimDependency`) where child claims inherit penalties from weak parents.
- **Flaws:** Token-overlap heuristic fails completely on semantic entailment, numerical precision, and negation. Hallucination detection is a trivial 1-line ratio of unsupported claims. Citation evaluation crashes with `AttributeError`.

### D. Adaptive Memory (`src/evalos/memory/`)
- **Strengths:** Exponential decay on historical observations; tracking of model-specific and domain-specific failure frequencies.
- **Flaws:** Threshold recommendation formula raises difficulty when models fail, exacerbating failure rates. Synchronous file writes on every evaluation run choke multi-tenant throughput.

### E. Observability & Tracing (`src/evalos/observability/`)
- **Strengths:** Deterministic schema snapshotting (`snapshot_trace`) normalizing timestamps for differential comparisons; ASCII timeline and lineage graphs.
- **Flaws:** In-memory single-trace buffer in FastAPI state (`state.last_trace`). No persistent trace storage, OpenTelemetry export, or query engine.

---

## 4. Strategic Recommendation

EVALOS should **NOT** be rewritten from scratch, nor should it attempt to become a generic passive observability dashboard (a market saturated by LangSmith, Langfuse, and Arize Phoenix). 

Instead, EVALOS must pivot decisively into an **Active Runtime Reliability Proxy & Verification Engine (Inline RAG & Agent Policy Firewall)**. 
By focusing on **in-flight verification, deterministic semantic grounding, and constrained selective repair**, EVALOS occupies the vacant whitespace between passive observability (Langfuse) and crude pre-call guardrails (NeMo / Guardrails AI).

