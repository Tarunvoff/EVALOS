# EVALOS: MVP Specification & Empirical Demonstration Plan

**Date:** November 2026  
**Auditor:** Technical Product Strategist & AI Systems Architect  

---

## 1. Feature Prioritization Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│ P0: Essential Core MVP Capabilities (Must Have to Ship v0.2.0)        │
│ 1. Packaging & Import Recovery (Fix FastAPI & Matplotlib dependencies) │
│ 2. Citation Attribute Bug Fix (`support.claim_id` resolution)          │
│ 3. Robust Offset-Based Selective Section Repair Engine                 │
│ 4. Invariant-Enforced Rollback Protection                              │
│ 5. Dual-Stage Semantic Grounding (BM25 + NLI Entailment)               │
│ 6. Drop-in OpenAI-Compatible Proxy Gateway (`/v1/chat/completions`)    │
│ 7. Automated End-to-End Baseline Benchmark Comparison                  │
├────────────────────────────────────────────────────────────────────────┤
│ P1: Important Production Enhancements (Fast Follow v0.3.0)            │
│ 1. Next.js Web UI JSX Fix & Real-Time SSE Repair Timeline              │
│ 2. Streaming Selective Repair (Delta chunk streaming)                  │
│ 3. Normalized SQLite Persistence (Multi-worker concurrency safety)     │
│ 4. OpenTelemetry (OTLP) Span & Trace Exporter                          │
├────────────────────────────────────────────────────────────────────────┤
│ P2: Advanced Enterprise Horizons (v1.0.0+)                             │
│ 1. Live Agent Tool-Call Interception Middleware                        │
│ 2. Distributed Memory Cluster (PostgreSQL + Redis)                     │
│ 3. High-Throughput Rust Ingress Gateway                                │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. P0 Feature Specifications (Technical Details)

### Feature 1: Packaging & Import Recovery
- **Purpose:** Ensure standard `pip install evalos` and `uv run evalos` commands work out-of-the-box without crashing on missing optional dependencies.
- **Implementation:** Promote `fastapi` and `uvicorn` to core dependencies in `pyproject.toml`. Refactor `src/evalos/benchmarks/reporting.py` to lazy-import `charts.py` only when `--charts` flag is passed.
- **Acceptance Criteria:** `evalos --help` and `evalos-bench --help` execute with return code 0 on a clean virtualenv without optional extras installed.
- **Complexity:** Low (2 hours).

### Feature 2: Citation Attribute Fix & Span Alignment
- **Purpose:** Eliminate unhandled 500 crashes during RAG citation verification.
- **Implementation:** Update `src/evalos/rag/citation.py` (lines 55, 58) to use `support.canonical_claim_id` and `support.external_claim_id`.
- **Acceptance Criteria:** `CitationEvaluator().evaluate()` executes cleanly on non-empty supported claim sets with 100% test pass rate.
- **Complexity:** Low (1 hour).

### Feature 3: Robust Offset-Based Selective Section Repair
- **Purpose:** Stop relying on crude `str.replace()` and implement deterministic span replacement.
- **Implementation:** Replace text slices using exact character start/end intervals: `text[:start] + revised_text + text[end:]`. Recalculate and shift downstream section offsets dynamically.
- **Acceptance Criteria:** Multi-section repairs with identical boilerplate or shifting lengths apply without corrupting neighboring text.
- **Complexity:** Medium (1 day).

### Feature 4: Invariant-Enforced Rollback Protection
- **Purpose:** Prevent repair passes from introducing hallucinations while chasing subjective evaluation scores.
- **Implementation:** Rollback triggers if `new_score < old_score` **OR** if any hard invariant is violated (e.g., grounding score drops below 0.75, or a previously passed critical criterion fails).
- **Acceptance Criteria:** A repair that improves `clarity` but drops `grounding` is rejected and rolled back to checkpoint.
- **Complexity:** Medium (1 day).

### Feature 5: Dual-Stage Semantic Grounding
- **Purpose:** Eliminate negation blindness and false-positive unigram token overlap.
- **Implementation:** Stage 1 filters with stopword-stripped lexical overlap. Stage 2 runs a local quantized ONNX cross-encoder model to classify true entailment vs. contradiction.
- **Acceptance Criteria:** *"The merger was not completed in 2024"* against a document stating *"The merger was completed in 2024"* is correctly classified as **Contradiction / Unsupported**.
- **Complexity:** High (3 days).

### Feature 6: OpenAI-Compatible Drop-In Reverse Proxy
- **Purpose:** Allow any existing codebase (OpenAI Python SDK, LangChain, LlamaIndex) to use EVALOS by changing only `base_url`.
- **Implementation:** Add `/v1/chat/completions` route to `src/evalos/api/app.py` accepting standard OpenAI schemas and forwarding through `Pipeline`.
- **Acceptance Criteria:** `client = openai.OpenAI(base_url="http://localhost:8000/v1"); client.chat.completions.create(...)` executes and returns repaired text transparently.
- **Complexity:** Medium (2 days).

---

## 3. The Compelling End-to-End Benchmark Demonstration

To prove EVALOS delivers measurable, superior reliability, the MVP includes a flagship automated benchmark comparing four execution strategies across 100 RAG questions with subtle factual traps:

### The Scenario
- **Task:** 1,000-word financial analysis summarizing quarterly earnings across 3 retrieved SEC 10-Q filing documents.
- **Target Invariants:** 
  1. 100% of numerical figures must have exact document span citations.
  2. Grounding score $\ge 0.85$.
  3. Zero factual contradictions.

### Empirical Head-to-Head Comparison Projection

| Strategy | Mechanism | Quality Pass Rate | Average Latency | Average Tokens Used | Estimated Cost per 1k Requests | Regressions Introduced |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Vanilla Generation** | Single raw LLM completion; no checks | 42.0% | **2.4s** | **850 tokens** | \$4.25 | N/A (Baseline) |
| **2. Full Retry (3x)** | If score $<0.70$, re-prompt entire query from scratch | 68.0% | 6.8s | 2,410 tokens | \$12.05 | High (fixes Point A, breaks Point B) |
| **3. Best-of-3 Sampling** | Generate 3 parallel candidates; pick best score | 71.0% | 3.1s *(high concurrency)* | 2,550 tokens | \$12.75 | None (picks best) |
| **4. EVALOS Runtime (MVP)** | Intercept, verify spans, repair *only* failing section, rollback if degraded | **89.0%** | **3.8s** | **1,080 tokens** | **\$5.40** | **0.0% (Zero Regressions via Rollback)** |

### Value Realization Summary
- **Compared to Full Retry:** EVALOS achieves **+21% higher quality pass rate**, saves **55% on token costs**, and runs **1.8x faster**.
- **Compared to Best-of-N:** EVALOS saves **58% on inference bills** while eliminating regression risk through section locking and invariant rollback protection.

