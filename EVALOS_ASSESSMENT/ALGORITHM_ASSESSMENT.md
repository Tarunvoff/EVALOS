# EVALOS: Deep Algorithmic Audit & Scientific Evaluation

**Date:** November 2026  
**Auditor:** Senior LLM Reliability Researcher & AI Systems Scientist  

---

## 1. Grounding & Evidence Verification Algorithm

### 1.1 Current Implementation (`src/evalos/rag/grounding.py`)
EVALOS determines whether a generated claim is "supported" by retrieved context using the following unigram token overlap formula:

$$\text{SupportScore}(\text{claim}, \text{context}) = \frac{|\text{Tokens}(\text{claim}) \cap \text{Tokens}(\text{context})|}{|\text{Tokens}(\text{claim})|}$$

Where $\text{Tokens}(t)$ is computed via `re.findall(r"[a-z0-9]+", t.lower())`.
A claim is classified as:
- **`supported`** if $\text{SupportScore} \ge 0.75$
- **`partial`** if $0.45 \le \text{SupportScore} < 0.75$
- **`unsupported`** if $\text{SupportScore} < 0.45$

### 1.2 Mathematical & Semantic Critique

#### Critical Failure 1: Total Blindness to Negation (Contradiction Misclassified as Supported)
Consider a retrieved evidence document:
> **Document:** *"The merger between Company A and Company B was completed in 2024 for \$5 billion."*  
> Tokens: `{"the", "merger", "between", "company", "a", "and", "b", "was", "completed", "in", "2024", "for", "5", "billion"}` (14 tokens).

Now consider an erroneous or hallucinatory LLM output:
> **Claim:** *"The merger between Company A and Company B was not completed in 2024."*  
> Tokens: `{"the", "merger", "between", "company", "a", "and", "b", "was", "not", "completed", "in", "2024"}` (12 tokens).

Intersection: 11 tokens out of 12 match!
$$\text{SupportScore} = \frac{11}{12} = 0.9167 \ge 0.75 \implies \mathbf{SUPPORTED}$$
**Verdict:** A direct factual contradiction and severe business hallucination is certified by EVALOS as **100% Supported** with high confidence.

#### Critical Failure 2: High Sensitivity to Stopwords
Because common grammatical glue words (`is`, `the`, `was`, `in`, `and`, `of`, `to`) are not filtered, any long, syntactically complex sentence will accumulate a baseline overlap of 0.40–0.50 with *any* topical paragraph, routinely triggering false "partial" support classifications.

#### Scientifically Sound Alternative: Natural Language Inference (NLI) & DeBERTa Cross-Encoder
Modern grounding (as practiced by state-of-the-art systems such as Patronus Lynx or Guardrails) requires cross-encoder entailment modeling:
$$P(\text{Entailment} \mid \text{Premise}, \text{Hypothesis}) \in [0, 1]$$
Small, fast local models (e.g. `deberta-v3-small` or quantized small cross-encoders running via ONNX) execute in $<15\text{ms}$ on CPU and evaluate true semantic entailment and contradiction.

---

## 2. Hallucination Detection Algorithm (`src/evalos/rag/hallucination.py`)

### 2.1 Current Implementation
```python
spans = [item.claim for item in grounding.unsupported_claims]
score = len(spans) / max(1, grounding.total_claims)
```
- **Analysis:** This is not an algorithmic hallucination detector; it is merely an arithmetic ratio directly derivative of the flawed token-overlap score.
- **Risk Classification:**
  - $\text{Score} \ge 0.65 \implies \text{critical}$
  - $\text{Score} \ge 0.40 \implies \text{high}$
  - $\text{Score} \ge 0.20 \implies \text{medium}$
  - Else $\implies \text{low}$
- **Critique:** If the grounding evaluator fails to catch an unsupported claim (due to the stopword/negation flaw), the hallucination detector records a score of $0.0$ and reports "low risk".

---

## 3. Selective Section Repair Algorithm (`src/evalos/repair.py`)

### 3.1 Mechanism of Action
1. Text is partitioned into paragraph-level sections:
   `Section(id="s1", text=..., start=0, end=150)`
2. The LLM is prompted with JSON instructions:
   `"Return ONLY deltas for the affected sections. Do NOT modify locked_sections."`
3. Received JSON deltas are applied via `_apply_deltas`:
```python
for delta in deltas:
    if delta.section_id in section_lookup:
        section = section_lookup[delta.section_id]
        updated_text = updated_text.replace(section.text, delta.revised_text, 1)
```

### 3.2 Algorithmic Vulnerabilities
1. **Duplicate Text Collision:** If two sections contain identical boilerplate (e.g. repeated table headers, disclaimers, or code comments), `updated_text.replace(section.text, ..., 1)` will replace the *first* occurrence in the document regardless of which section ID was targeted!
2. **Offset Desynchronization:** If Section 1 is repaired and changes in length, all downstream start/end character offsets stored in `EvaluationResult.sections` become immediately invalid. Subsequent repair turns operate on corrupt offsets.
3. **Sentence Boundary Mutilation:** If a repair changes tense or removes introductory clauses, it regularly introduces grammatical artifacts at the boundaries of adjacent unmodified sections.

---

## 4. Rollback Protection Algorithm (`src/evalos/pipeline.py`)

### 4.1 Implementation Logic
```python
if new_eval.weighted_score < current_eval.weighted_score:
    rollback_count += 1
    # Do not update current_text; break out of repair loop
    break
```

### 4.2 Critical Scientific Evaluation
- **The Core Flaw: Weighted Score as a Proxy for Truth:**
  `weighted_score` is computed by an LLM-as-a-judge evaluating criteria such as `clarity`, `depth`, and `conciseness`.
  - Suppose a model generates a factual claim: *"Revenue grew by 12% to \$1.2B"*, but scores low (0.50) on `clarity` because of clunky grammar.
  - The repair pass simplifies the grammar into: *"Revenue doubled to \$2.4B"* (a total hallucination, but beautifully written!).
  - The evaluator judges the revised output: `clarity` jumps to 0.95! Weighted score increases from 0.50 to 0.90!
  - **EVALOS accepts the hallucinated repair and treats it as a success!**
- **Conclusion:** Score-based rollback protects against *evaluator degradation*, NOT *factual regression*. Rollback protection must be anchored to strict, non-negotiable verification invariants (e.g., grounding score $\ge 0.85$, zero schema violations), not subjective weighted LLM scores.

---

## 5. Adaptive Memory Algorithm (`src/evalos/memory/adaptive_thresholds.py`)

### 5.1 The Threshold Adaptation Formula
```python
def recommend_threshold(*, base_threshold: float, avg_score: float, failure_rate: float) -> float:
    penalty = max(0.0, 0.85 - avg_score) * 0.05
    risk_adjust = failure_rate * 0.1
    recommended = base_threshold + penalty + risk_adjust
    return min(0.98, max(0.5, recommended))
```

### 5.2 Mathematical Analysis: The Inductive Failure Loop
Let a model have a baseline threshold of $T_0 = 0.70$.
1. If the model achieves an average score of $0.60$ and fails $60\%$ of the time:
   $$\text{penalty} = (0.85 - 0.60) \times 0.05 = 0.0125$$
   $$\text{risk\_adjust} = 0.60 \times 0.10 = 0.0600$$
   $$T_1 = 0.70 + 0.0125 + 0.0600 = 0.7725$$
2. On subsequent runs, the model is now evaluated against $T_1 = 0.7725$ (a much harder threshold).
3. The model's failure rate naturally increases to $80\%$, and its average score remains $\sim 0.60$.
4. The system calculates:
   $$T_2 = 0.70 + 0.0125 + 0.0800 = 0.7925$$
**Mathematical Result:** The system enters an asymptotic failure loop, punishing weaker models by making requirements progressively stricter until every query fails and exhausts all repair budgets.

---

## 6. Agent Reliability Evaluation (`src/evalos/rag/agent_eval.py`)

### 6.1 Algorithmic Reality vs. Claim
EVALOS claims to provide **Agent Reliability Evaluation and Tool Correctness Verification**.
- **Reality:** The system has zero runtime integration with agent execution environments (LangChain, AutoGen, CrewAI, or raw tool execution loops).
- It simply inspects a static JSON dictionary passed in the user request.
- **Reasoning Consistency Algorithm:**
```python
for call in tool_calls:
    for key in call.output.keys():
        if key and key.lower() in reasoning_text:
            hits += 1
            break
```
If a tool output is `{"result": 42}`, the algorithm checks if the word `"result"` appears anywhere in the agent's thoughts. This is a superficial cosmetic heuristic with zero semantic or causal validity.

