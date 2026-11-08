# EVALOS: Phased Engineering Roadmap (Q4 2026 – Q2 2027)

**Date:** November 2026  
**Auditor:** Principal AI Infrastructure Architect  

---

## 1. Roadmap Overview & Timeline

```
2026                    2027
Nov     Dec     Jan     Feb     Mar     Apr     May     Jun
 │       │       │       │       │       │       │       │
 ├─ P0 ──┤                                               │ Phase 0: Repo Recovery
 │   └───┼─ P1 ──┤                                       │ Phase 1: Core Foundation
 │       └───┼───┼─ P2 ──┤                               │ Phase 2: Verification Engine
 │           └───┼───┼───┼─ P3 ──┤                       │ Phase 3: Surgical Repair
 │               └───┼───┼───┼───┼─ P4 ──┤               │ Phase 4: SDK & Proxy Gateway
 │                   └───┼───┼───┼───┼───┼─ P5 ──┤       │ Phase 5: Agent Supervision
 │                       └───┼───┼───┼───┼───┼───┼─ P6 ──┤ Phase 6: Observability UI
 │                           └───┼───┼───┼───┼───┼───┼───┘ Phase 7: Enterprise Scale
```

---

## 2. Phase-by-Phase Execution Plan

### Phase 0: Repository Recovery & Packaging Stabilization (Weeks 1–2)
*Goal: Fix all blocking crashes, broken dependencies, and latent bugs to achieve clean developer setup.*
- **Tasks:**
  1. Fix `pyproject.toml` dependency declarations (`fastapi`, `uvicorn` in core; lazy-import `matplotlib` in benchmarks).
  2. Fix `src/evalos/rag/citation.py` `support.claim_id` $\to$ `canonical_claim_id` / `external_claim_id`.
  3. Fix Next.js JSX syntax errors in `apps/web/src/app/repair-timeline/page.tsx` (`&gt;`).
  4. Expand test suite with real Ollama integration tests and citation validation tests.
- **Deliverables:** `pytest` passes 100%, `evalos --help` runs cleanly, `pnpm build` compiles with zero errors.

### Phase 1: Core Reliability Foundation & Pipeline Decoupling (Weeks 3–4)
*Goal: Dismantle the 1,760-line monolithic `pipeline.py` into a clean, testable composite architecture.*
- **Tasks:**
  1. Deconstruct `Pipeline` into clean stages: `RequestStage`, `VerificationStage`, `EvaluationStage`, `RepairStage`.
  2. Implement an invariant-based rollback coordinator.
  3. Fix the adaptive threshold formula in `adaptive_thresholds.py` to eliminate the positive failure feedback loop.
  4. Refactor `SQLiteMemoryStorage` to use normalized relational tables with indexed lookups.
- **Deliverables:** Refactored pipeline with $<300$ LOC per module; normalized SQLite database schema.

### Phase 2: Verification Engine & Semantic Grounding (Weeks 5–8)
*Goal: Replace flawed unigram token overlap with high-accuracy semantic grounding and contradiction detection.*
- **Tasks:**
  1. Implement Stage 1 lexical fast-filter (stopword-stripped token precision).
  2. Integrate Stage 2 lightweight ONNX-runtime cross-encoder (e.g. `deberta-v3-small` / MiniLM) for local CPU entailment.
  3. Build precise character-span citation matcher that maps claims to exact source document offsets.
  4. Fix claim extraction regex to handle compound sentences and clause decomposition.
- **Deliverables:** Negation-proof grounding engine executing in $<20\text{ms}$; 100% accurate citation span verification.

### Phase 3: Surgical Repair & Invariant Rollback (Weeks 9–12)
*Goal: Turn selective repair into a bulletproof, deterministic delta engine.*
- **Tasks:**
  1. Replace `str.replace()` in `repair.py` with character-offset span splicing.
  2. Implement dynamic offset recalculation for multi-section edits.
  3. Enforce strict section locking ensuring unmodified sections are mathematically invariant.
  4. Add repair streaming: stream individual section deltas as they are generated.
- **Deliverables:** Robust multi-section repair engine with zero offset collision bugs.

### Phase 4: OpenAI-Compatible Proxy Gateway & SDK (Weeks 13–16)
*Goal: Provide zero-friction developer adoption.*
- **Tasks:**
  1. Build `/v1/chat/completions` proxy endpoint in FastAPI supporting full OpenAI schema.
  2. Implement SSE streaming through the proxy with inline repair event notifications.
  3. Publish lightweight Python SDK (`pip install evalos`) with synchronous and asynchronous clients.
  4. Expand benchmark suite to 100+ realistic enterprise RAG and financial fixtures.
- **Deliverables:** Drop-in proxy gateway working with `openai.OpenAI(base_url="...")`; public PyPI release v0.2.0.

### Phase 5: Agent Runtime Supervision & Tool Interception (Weeks 17–20)
*Goal: Move from static JSON trace grading to active, in-flight agent supervision.*
- **Tasks:**
  1. Build middleware hooks for LangChain, LangGraph, and AutoGen.
  2. Intercept live tool calls before execution to validate argument schemas against Pydantic models.
  3. Detect hallucinated tool calls and sandboxed execution anomalies in real time.
- **Deliverables:** Working LangGraph supervisor plugin intercepting unauthorized or hallucinated tool invocations.

### Phase 6: Developer Dashboard & Observability UI (Weeks 21–24)
*Goal: Deliver a world-class, real-time developer observability dashboard.*
- **Tasks:**
  1. Connect Next.js frontend to FastAPI backend via WebSocket / SSE for live trace visualization.
  2. Build interactive Repair Timeline visualizing before/after delta diffs and rollback events.
  3. Implement OpenTelemetry (OTLP) exporter streaming spans to Datadog, Langfuse, and Jaeger.
- **Deliverables:** Polished Next.js 16 dashboard displaying live generation, repair deltas, and telemetry.

### Phase 7: Enterprise Hardening & Production Scale (Weeks 25–28)
*Goal: Enterprise clustering, multi-tenancy, and high-throughput deployment.*
- **Tasks:**
  1. Distributed Redis state cache for cluster-wide adaptive memory.
  2. Multi-tenant policy configuration and RBAC.
  3. Containerized Helm charts and Docker Compose production deployment bundles.
- **Deliverables:** Enterprise-ready v1.0.0 release.

