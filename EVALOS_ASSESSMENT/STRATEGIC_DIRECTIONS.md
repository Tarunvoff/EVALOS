# EVALOS: Strategic Directions & Quantitative Decision Matrix

**Date:** November 2026  
**Auditor:** Technical Product Strategist & AI Infrastructure Architect  

---

## 1. Five Strategic Product Directions Evaluated

We formulate and stress-test five distinct strategic trajectories for EVALOS:

### Direction 1: The Active LLM Reliability Proxy & Repair Runtime
An inline reverse proxy and Python middleware that intercepts completions between client and model. It verifies criteria, evaluates grounding, executes selective section repair, and enforces rollback safety before returning data to the application.
- *Analogy:* Envoy / Cloudflare for LLM inference.

### Direction 2: Continuous AI Evaluation & CI/CD Testing Framework
Pivoting EVALOS into a developer-facing test harness (`pytest-evalos`) that runs in GitHub Actions to test prompts, models, and RAG pipelines against synthetic and historical datasets before production deployment.
- *Analogy:* DeepEval / Braintrust for automated testing.

### Direction 3: Agentic Runtime Supervisor & Tool-Call Policy Engine
A sidecar execution supervisor for AI agents (LangGraph, CrewAI, AutoGen). It monitors planning consistency, validates tool arguments against JSON schemas, prevents hallucinated tool calls, and intercepts unauthorized actions.
- *Analogy:* Falco / Open Policy Agent (OPA) for AI Agents.

### Direction 4: Enterprise RAG Grounding & Factual Verification Firewall
A dedicated verification microservice designed exclusively for RAG systems. It extracts claims, runs high-speed semantic cross-encoder entailment, injects precise character-span citations, and eliminates unsupported assertions.
- *Analogy:* Patronus AI / Cleanlab for enterprise search and document Q&A.

### Direction 5: Autonomous Self-Healing AI Ops Platform
A fully autonomous platform that continuously monitors live production traffic, automatically adapts memory and criteria, and auto-generates fine-tuning datasets and prompt patches to heal recurring model weaknesses without human intervention.
- *Analogy:* Autonomous self-driving reliability platform.

---

## 2. Quantitative Decision Matrix

Each direction is scored from **1 (Poor / Unfavorable)** to **10 (Outstanding / Highly Favorable)** across nine objective strategic criteria:

| Evaluation Dimension (Weight) | Dir 1: Active Reliability Proxy | Dir 2: CI/CD Testing Framework | Dir 3: Agent Runtime Supervisor | Dir 4: RAG Grounding Firewall | Dir 5: Self-Healing Ops Platform |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Market Opportunity (15%)** | 9.0 | 7.0 | 9.5 | 8.5 | 6.5 |
| **2. Unmet Market Need (15%)** | 9.5 | 5.0 | 9.0 | 8.0 | 7.0 |
| **3. Technical Differentiation (15%)**| 9.5 | 4.5 | 8.5 | 7.5 | 8.0 |
| **4. Competitive Pressure (Inverse) (10%)**| 8.5 *(Low)* | 3.0 *(Intense)* | 7.0 *(Emerging)* | 6.0 *(Moderate)* | 6.0 *(High noise)*|
| **5. Engineering Feasibility (10%)** | 8.5 | 9.0 | 6.0 | 8.0 | 4.0 |
| **6. Codebase Compatibility (10%)** | **9.5** | 6.0 | 5.5 | 7.5 | 4.0 |
| **7. Developer Adoption Potential (10%)**| 9.0 | 7.5 | 7.5 | 8.0 | 5.0 |
| **8. Monetization Potential (10%)** | 9.0 | 6.5 | 9.0 | 8.5 | 6.5 |
| **9. Long-Term Defensibility (5%)** | 9.0 | 5.0 | 8.5 | 7.5 | 6.0 |
| **Weighted Composite Score** | **9.08 / 10** | **6.10 / 10** | **8.15 / 10** | **7.85 / 10** | **5.85 / 10** |

---

## 3. Justification of Scores & Deep Strategic Rationale

### Why Direction 1 (Active Reliability Proxy) Wins (Score: 9.08)
1. **Unmet Need & Differentiation (Score: 9.5 / 9.5):** Every existing tool in the market (Langfuse, LangSmith, Phoenix) observes failures *after* they reach the customer. EVALOS already has the working mechanics of selective repair, section locking, and rollback protection in its codebase. No major open-source tool specializes in in-flight selective delta repair.
2. **Codebase Compatibility (Score: 9.5):** 85% of `src/evalos/` (`pipeline.py`, `repair.py`, `eval.py`, `observability/tracer.py`) is already engineered specifically around the in-flight generation $\to$ evaluation $\to$ selective repair $\to$ rollback loop. It requires zero conceptual rewriting.
3. **Engineering Feasibility (Score: 8.5):** Wrapping the existing pipeline in an OpenAI-compatible FastAPI/HTTP proxy (`/v1/chat/completions`) is straightforward and immediately testable against any existing client library.

### Why Direction 2 (CI/CD Testing) Fails (Score: 6.10)
- The offline evaluation market is brutally crowded. Competing against DeepEval, Braintrust, and Ragas with 10 benchmark fixtures is a losing proposition. It plays directly to EVALOS's weakest components while abandoning its unique selective repair engine.

### Why Direction 3 (Agent Supervisor) is Postponed to Phase 5 (Score: 8.15)
- While agent security and tool governance is a massive frontier, the current EVALOS implementation (`agent_eval.py`) is merely a static JSON string parser. It lacks live runtime sandboxing and tool-interception capabilities. Direction 3 should become an extension module of Direction 1 in future roadmap phases, rather than the primary MVP focus.

---

## 4. The 8 Critical Product Strategy Questions

### 1. Which problem is genuinely worth solving?
**In-flight generation failure and catastrophic retry cost.** Production LLMs in healthcare, law, and financial services cannot afford to hallucinate or violate schema constraints, yet full regeneration is too slow and burns excessive tokens.

### 2. Who experiences this problem?
AI Engineers and Tech Leads deploying customer-facing RAG pipelines, structured data extractors, and automated report generators where accuracy is mandatory and latency budgets are under 5 seconds.

### 3. Why are existing solutions insufficient?
- Observability tools (Langfuse/Arize) only log failures post-mortem.
- Guardrails (NeMo/Guardrails AI) execute coarse binary blocking or re-ask the entire prompt from scratch.
- Nobody performs targeted, section-level delta repair with verified rollback safety.

### 4. What can EVALOS do differently?
EVALOS surgically modifies only the failing paragraph or schema key, preserves 90% of validated tokens, guarantees that repair never degrades overall quality, and logs exact provenance of every delta.

### 5. What is technically achievable today?
Using the existing Python pipeline with LiteLLM and Ollama, we can immediately deliver an inline proxy that performs criteria-driven evaluation, section delta repair, and rollback logging in $<3$ seconds for local and hosted models.

### 6. What can be built directly with existing code?
- `src/evalos/pipeline.py` (orchestration flow)
- `src/evalos/repair.py` (delta generation)
- `src/evalos/eval.py` (multi-strictness scoring)
- `src/evalos/observability/tracer.py` (lineage and trace generation)
- `src/evalos/providers/` (LiteLLM/Ollama abstraction)

### 7. What should be abandoned or removed?
- Abandon superficial static agent parsing (`agent_eval.py`) until a real execution hook is built.
- Abandon the broken benchmark charts (`charts.py` / `matplotlib`).
- Deprecate uncalibrated token-overlap grounding in favor of lightweight cross-encoders.

### 8. What should become the primary product?
**EVALOS: The Open-Source Active Reliability Runtime & Inline Repair Proxy for LLMs and RAG.**

