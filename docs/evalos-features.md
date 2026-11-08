# EvalOS Feature Documentation

## Overview

EvalOS is a reliability runtime for LLM and RAG systems. It turns raw generations into evaluated, repaired, and traceable outputs with provenance, selective repair, grounding checks, and rollback safety.

Key goals:
- Detect weak or unsafe outputs early.
- Apply minimal, targeted repairs instead of full regeneration.
- Validate RAG grounding, citations, and tool use.
- Maintain traceability and analytics across runs.
- Adapt criteria and thresholds over time with memory.

## End-to-End Pipeline Design

The primary runtime is implemented in `Pipeline.generate()` and `Pipeline.stream()`.

High-level flow:
1. **Criteria generation** (optional override).
2. **Memory adaptation** (thresholds, weights, strictness).
3. **LLM response generation**.
4. **RAG validation** (grounding, hallucination, citation, agent trace).
5. **Evaluation** against criteria.
6. **Selective repair** with rollback protection.
7. **Metrics + trace** emission and memory updates.

### Full Pipeline Steps (Generate)

1) Criteria generation
- If `criteria_override` is missing, criteria are generated per query using the criteria model.
- Criteria include name, threshold, weight, and severity.

2) Memory influence
- Strictness is adapted using model and domain risk history.
- Threshold and weight overrides are computed if failure history warrants tightening.

3) Generation
- Uses configured provider + model.
- Tracks latency and usage.

4) RAG reliability and schema validation
- If retrieved documents or citations are provided, claims are extracted and normalized.
- Citations and agent traces are schema-validated before scoring.
- Grounding, hallucination, and citation accuracy are computed.
- If unsupported claims or missing citations exist, a RAG repair pass is attempted.

5) Evaluation
- A separate evaluator LLM scores the output against the criteria, producing an `EvaluationResult`.

6) Selective repair loop
- For each repair attempt (up to `max_repairs`), only failed sections are edited.
- Repairs are re-evaluated; if the score drops, a rollback is recorded.

7) Final metrics and trace
- Metrics include quality deltas, repair efficiency, memory adaptation, and RAG metrics.
- The trace records every step, latency, and repair lineage.

### Streaming Path
The streaming path mirrors generate, but starts by streaming text from the provider, then performs RAG checks, evaluation, and emits a final `StreamEvent` with the full response.

## Feature-by-Feature Design

### 1) Criteria Generation
- **Purpose:** Build task-specific evaluation criteria from the query and goals.
- **How it works:** The criteria model generates a JSON list of criteria with thresholds and weights.
- **Impact:** Drives targeted evaluation and selective repair rather than generic scoring.

Key behaviors:
- Criteria are tailored to `optimize_for` (e.g., accuracy, depth, clarity).
- Supports different quality profiles (general, research, coding, etc.).

### 2) Adversarial Evaluation
- **Purpose:** Judge output quality and locate weak sections.
- **How it works:** The evaluator prompts the model to score each criterion, assigning a score, failure reason, and affected section.
- **Strictness controls:** `relaxed`, `balanced`, `strict`, `adversarial`, plus `strict_mode`.

Evaluation output:
- Per-criterion score, pass/fail, reason, affected section.
- Overall weighted score and pass rate.

### 3) Selective Repair
- **Purpose:** Repair only failing content, minimizing tokens and risk of regression.
- **How it works:**
  - Failures map to repair instructions with strategies.
  - The repair model produces section deltas (not full rewrites).
  - Deltas are applied and re-evaluated.

Rollback protection:
- If the repaired output scores lower than the prior evaluation, it rolls back and logs a rollback event.

Repair strategies:
- Default strategies are mapped from criteria names (clarity, accuracy, depth, etc.).
- Memory can bias strategies for repeated failures.

### 4) RAG Grounding
- **Purpose:** Verify claims against retrieved evidence.
- **Claim extraction:** Heuristic sentence extraction for factual-looking claims.
- **Support scoring:** Token overlap ratio between claim and doc text.

Classification:
- `supported` if score >= 0.75
- `partial` if score >= 0.45
- `unsupported` otherwise

Grounding score:
- Weighted formula: $\frac{supported + 0.5 \cdot partial}{total}$

Dependencies:
- If claim dependencies are provided, claims inherit penalties from weak parents.

### 5) Hallucination Detection
- **Purpose:** Quantify unsupported claims in the response.
- **Derived from grounding:**
  $$\text{hallucination\_score} = \frac{unsupported\_claims}{total\_claims}$$
- **Risk levels:**
  - critical >= 0.65
  - high >= 0.40
  - medium >= 0.20
  - low otherwise

### 6) Citation Validation
- **Purpose:** Ensure citations point to correct evidence spans.
- **Validation checks:**
  - doc_id exists
  - span bounds are valid
  - span text matches citation text
  - claim ID is valid and atomic
- **Citation accuracy:** ratio of aligned citations to total.
- **Citation precision:** ratio of cited span length that matches the document.

### 7) RAG Repair
- **Purpose:** Fix unsupported or uncited claims with minimal edits.
- **Actions:** `remove`, `replace`, `cite`.
- **Fallback:** If no provider is configured, unsupported claims are removed and missing citations are flagged.
- **Post-repair:** Grounding and hallucination scores are recomputed.

### 8) Agent Reliability Evaluation
- **Purpose:** Evaluate tool usage and plan alignment in agent traces.
- **Scores:**
  - tool correctness
  - planning order consistency
  - execution alignment with plan
  - hallucinated tool usage
  - reasoning consistency

### 9) Adaptive Memory
- **Purpose:** Learn from historical failures and repairs.
- **Stored statistics:** model/domain failure rates, threshold history, repair strategy success, section stability.
- **Adaptations:**
  - raise strictness when risk rises
  - tighten thresholds and increase weights for recurrent failures
  - bias repair strategies toward proven strategies
- **Decay:** older observations decay to avoid stale bias.

### 10) Observability and Tracing
- **Trace** includes:
  - all steps with timestamps
  - criteria, evaluation, repairs, rollbacks
  - RAG metrics and agent evaluation
  - provenance and schema validation
- **Snapshot** normalizes traces for stable comparison and reporting.

### 11) Benchmarks
- Benchmark suite compares strategies: `vanilla`, `retry`, `best_of_n`, `evalos`.
- Produces JSON, CSV, Markdown, and charts (cost vs quality, hallucination reduction).

### 12) API and UI
- FastAPI endpoints for generation, traces, benchmarks, and agent eval.
- Streaming endpoint emits `text`, `evaluation`, `metrics`, and `trace` events.
- Web UI consumes trace and benchmark outputs.

## RAG Pipeline Data Flow

Input:
- `retrieved_documents` (docs with id, text, metadata)
- `citations` (claim_id, doc_id, span, text)
- optional `claim_map` and `claim_dependencies`

Flow:
1. Normalize documents and citations.
2. Validate citations and agent traces (schema checks).
3. Extract claims, build or use provided `claim_map`.
4. Canonicalize claim IDs for cross-run stability.
5. Run grounding + hallucination + citation scoring.
6. If issues are detected, run RAG repair.
7. Recompute scores after repair.
8. Record RAG signals into memory.

Outputs:
- Grounding score, hallucination score, citation accuracy/precision.
- Unsupported claims list (used for repair or downstream gating).

## Repair and Rollback Policy

Selective repair operates under strict safety rules:
- Only failed sections are modified.
- Stable sections can be locked.
- Score decreases trigger rollback and stop further repairs.

This prevents the common failure mode of "over-repair" where improvements in one criterion break others.

## Latency and Overhead Analysis

EvalOS adds reliability stages beyond standard generation. The main contributors:

### Latency Breakdown (Generate)
- `criteria_ms`: criteria generation
- `generation_ms`: base response generation
- `rag_ms`: grounding + citation + hallucination + optional RAG repair
- `evaluation_ms`: adversarial evaluation
- `repair_ms`: selective repair
- `reevaluation_ms`: scoring after each repair
- `memory_ms`: memory updates
- `total_ms`: end-to-end

### Why latency increases
- **Extra LLM calls:** evaluation and repair each invoke a model call.
- **RAG validation pass:** claim extraction + doc matching + optional RAG repair.
- **Multiple attempts:** selective repair can re-run evaluation multiple times.

### Where overhead stays low
- RAG scoring is lightweight token overlap, not dense semantic embedding.
- Repair is localized by sections and does not rewrite full outputs.
- Adaptive memory reduces repeated failures, lowering average repair attempts over time.

### Practical mitigation strategies
- Lower `max_repairs` for latency-sensitive paths.
- Skip RAG validation when no retrieved docs are supplied.
- Use smaller eval/repair models while keeping a larger generation model.

## Configuration and Extension Points

Key config options:
- `model`, `provider`, `timeout_s`, `max_repairs`
- `evaluation_strictness` and `strict_mode`
- `criteria_model`, `eval_model`, `repair_model` overrides

Extension points:
- Implement a custom provider via `BaseProvider`.
- Inject custom `Memory` backends.
- Supply your own criteria via `criteria_override`.
- Provide claim maps, dependencies, or agent traces for richer analysis.

## Data Schemas

Important structures:
- `Criterion`, `CriterionResult`, `EvaluationResult`
- `RepairRecord`, `RepairDelta`
- `Metrics`, `GenerationResponse`
- `Trace` with step-by-step runtime evidence
- RAG schemas: `ClaimSupport`, `GroundingResult`, `HallucinationResult`, `CitationResult`

## Limitations and Notes

- Claim extraction is heuristic; some factual statements can be missed.
- Grounding uses token overlap, which is fast but not semantic.
- RAG repair is designed for minimal edits and does not rewrite entire responses.
- Agent evaluation depends on provided `agent_trace` schema validity.

## Suggested Reading

- Architecture: docs/architecture.md
- Benchmarks: docs/benchmarks.md
- Demos: docs/demos
- Quickstart: docs/quickstart.md
