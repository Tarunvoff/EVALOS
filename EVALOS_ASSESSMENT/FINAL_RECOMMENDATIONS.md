# EVALOS: Final Strategic Recommendations & Decision Blueprint

**Date:** November 2026  
**Auditor:** Principal AI Systems Architect & Technical Product Strategist  

---

## 1. Direct Engineering & Product Answers

### 1. What was EVALOS originally supposed to become?
EVALOS was conceived as an **all-in-one AI Reliability Operating System**: an ambitious platform combining in-flight selective repair, RAG grounding, citation verification, agent tool-misuse detection, adaptive memory, benchmarking, an observability trace viewer, a FastAPI backend, and a Next.js web application.

### 2. What has actually been developed?
An 18-day proof-of-concept sprint produced:
- A working core async generation and repair orchestrator (`pipeline.py`).
- Provider abstraction over LiteLLM and local Ollama (`providers/`).
- Dynamic criteria generation and LLM-as-a-judge scoring (`criteria.py`, `eval.py`).
- Prototype section-level selective repair and rollback tracking (`repair.py`).
- A heuristic token-overlap grounding engine and schema validator (`rag/`).
- An experimental memory decay and failure tracker (`memory/`).
- An incomplete FastAPI backend and a Next.js frontend with build-breaking syntax errors.

### 3. What works today?
- **Core Pipeline Execution:** Orchestrates generation, evaluation, and selective repair deltas via LiteLLM and Ollama (verified via passing test suite).
- **Criteria Generation:** Dynamically derives actionable criteria with weights and thresholds from prompt goals.
- **Rollback Logic:** Safely reverts responses when evaluation scores degrade after a repair attempt.
- **Schema Validation & Claim Canonicalization:** Robust Pydantic schema validation for citations and dependencies.
- **Trace Snapshotting:** Normalizes request traces deterministically for regression diffing.

### 4. What is broken or incomplete?
- **Citation Evaluation:** Fatal `AttributeError` on `ClaimSupport.claim_id` crashes RAG evaluation.
- **Frontend Web UI:** Next.js production build (`pnpm build`) fails due to unescaped `>` characters in JSX.
- **Backend & CLI Packaging:** Immediate `ModuleNotFoundError` on `fastapi` and `matplotlib` on clean installs.
- **Grounding Algorithm:** Unigram token overlap classifies direct contradictions and negations as 100% supported.
- **Adaptive Memory Feedback Loop:** Formula tightens thresholds on failing models, inducing positive failure loops.
- **Agent Evaluation:** Superficial static JSON string check; does not monitor live agent executions.
- **Curated Demos:** 100% of demo files in `docs/demos/` are 10-line bulleted markdown outlines.

### 5. What is technically valuable?
The **in-flight selective section repair and rollback engine** is a genuine, defensible innovation. Saving 50%+ of tokens and 40%+ of latency by surgically editing flawed spans rather than regenerating entire responses—combined with guaranteed rollback safety—is a capability that neither Langfuse, Phoenix, nor Guardrails AI provides.

### 6. What should be removed or abandoned?
1. **Abandon Superficial Agent Trace Parsing:** Delete `evalos.rag.agent_eval` in its current static form. Replace it only when true live runtime tool-interception middleware is built.
2. **Abandon Broken Matplotlib Benchmark Charts:** Remove unneeded heavy plotting libraries from the core package; emit clean JSON/CSV and let the web UI or external tools render charts.
3. **Deprecate Unigram Token Overlap Grounding:** Replace with lightweight semantic cross-encoders.

### 7. What is the strongest product opportunity?
The strongest market opportunity is **The Active LLM Reliability Proxy & Runtime (The "Envoy for GenAI")**. Positioning EVALOS as an inline, drop-in reverse proxy (`base_url="http://localhost:8000/v1"`) that intercepts completions, enforces semantic grounding invariants, and executes surgical selective repair with rollback protection.

### 8. What should EVALOS become?
EVALOS should become the **standard open-source reliability runtime for mission-critical RAG and structured enterprise LLM workloads**.

### 9. Why would developers adopt it?
Because it delivers immediate, measurable ROI:
- **Zero code changes:** Works with existing OpenAI SDK / LangChain clients by pointing `base_url` to the proxy.
- **Lower inference bills:** Reduces retry token waste by 50%+.
- **Guaranteed safety:** Rollback protection ensures the model never delivers an answer worse than its initial draft.
- **Local first:** Runs seamlessly on local Ollama / vLLM instances without sending data to third-party SaaS clouds.

### 10. What should the first production-ready version (v0.2.0) contain?
1. Flawless packaging (`pip install evalos` works out-of-the-box).
2. Bug-free citation verification and dual-stage semantic grounding (ONNX NLI).
3. Offset-based deterministic selective repair.
4. Hard invariant-enforced rollback protection.
5. Drop-in OpenAI-compatible proxy endpoint (`/v1/chat/completions`).
6. Automated head-to-head benchmark CLI proving token savings and regression prevention against Vanilla, Retry, and Best-of-N.

---

## 2. The First Ten Engineering Tasks

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Task 1: Fix Packaging & Optional Dependency Leaks                                │
│ • Move `fastapi` and `uvicorn` to core dependencies in pyproject.toml.          │
│ • Lazy-import `matplotlib` in `reporting.py` so CLI never crashes on --help.     │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Task 2: Fix Latent Citation AttributeError                                       │
│ • Update `src/evalos/rag/citation.py` (lines 55, 58) to use                      │
│   `canonical_claim_id` and `external_claim_id`. Add automated regression test.  │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Task 3: Repair Next.js JSX Syntax in apps/web                                    │
│ • Escape `->` arrows with `&gt;` in `repair-timeline/page.tsx`.                   │
│ • Verify `pnpm build` completes with zero errors.                                │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Task 4: Fix Adaptive Threshold Feedback Loop                                     │
│ • Invert the penalty formula in `adaptive_thresholds.py` so failing models are   │
│   not penalized with impossible thresholds; cap upward drift at +0.03 max.       │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Task 5: Upgrade Grounding to Dual-Stage Entailment                               │
│ • Add stopword filtering and lemmatization to Stage 1 lexical overlap.           │
│ • Integrate quantized local ONNX cross-encoder for Stage 2 semantic NLI.         │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Task 6: Implement Offset-Based Character Span Splicing                           │
│ • Replace `str.replace()` in `repair.py` with exact character index slicing.     │
│ • Dynamically adjust downstream section offsets when text lengths expand/shrink. │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Task 7: Enforce Invariant-Based Rollback Protection                              │
│ • Update rollback logic in `pipeline.py` to trigger not just on weighted score,  │
│   but whenever hard grounding invariants (score >= 0.75) are violated.           │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Task 8: Deliver Drop-In OpenAI Proxy Endpoint                                    │
│ • Implement `/v1/chat/completions` route in `src/evalos/api/app.py` accepting    │
│   standard OpenAI request bodies and returning streaming/synchronous responses.  │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Task 9: Refactor Monolithic `pipeline.py` into Modular Stages                    │
│ • Split `pipeline.py` into `stages/request.py`, `stages/verification.py`,        │
│   `stages/evaluation.py`, and `stages/repair.py`.                                │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Task 10: Ship Real End-to-End Automated Benchmark                                │
│ • Create 50 realistic RAG evaluation fixtures with subtle factual traps.         │
│ • Implement automated cost, latency, and quality comparison reporting.          │
└──────────────────────────────────────────────────────────────────────────────────┘
```

