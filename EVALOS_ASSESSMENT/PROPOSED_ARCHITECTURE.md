# EVALOS: Target System Architecture & Technical Specification

**Date:** November 2026  
**Auditor:** Principal AI Systems Architect & AI Infrastructure Engineer  

---

## 1. High-Level System Architecture

The redesigned EVALOS architecture transitions from a monolithic Python script into a clean, layered **Active Reliability Proxy and Middleware Runtime**:

```mermaid
graph TD
  Client["Client Application / Agent (SDK, LangChain, cURL)"]
  
  subgraph "EVALOS Ingress & Gateway Layer"
    Proxy["OpenAI-Compatible Proxy (/v1/chat/completions)"]
    Router["Policy & Rule Router"]
  end

  subgraph "EVALOS Core Reliability Engine"
    Orchestrator["Execution Orchestrator"]
    CriteriaEngine["Criteria & Rubric Engine"]
    ProviderGW["Provider Gateway (LiteLLM / Ollama / vLLM)"]
    
    subgraph "Verification & Evaluation Pipeline"
      SemanticGrounding["Semantic Grounding Engine (NLI / Cross-Encoder)"]
      SchemaValidator["Schema & Invariant Validator"]
      EnsembleJudge["Ensemble Evaluator (Primary / Adversarial)"]
    end

    subgraph "Surgical Recovery Engine"
      SectionLocker["Span & Section Locker"]
      DeltaRepair["Selective Delta Repairer"]
      RollbackGuard["Invariant Rollback Protection Guard"]
    end
  end

  subgraph "State, Memory & Observability"
    AdaptiveMemory["Adaptive Memory Service (Decay & Failure History)"]
    TraceEngine["OTLP Trace & Telemetry Engine"]
    DB[(SQLite / PostgreSQL State Store)]
  end

  Client -->|Chat Completion Request| Proxy
  Proxy --> Router
  Router --> Orchestrator
  Orchestrator --> ProviderGW
  ProviderGW -->|Raw Generation Draft| Orchestrator
  Orchestrator --> SemanticGrounding
  Orchestrator --> SchemaValidator
  Orchestrator --> EnsembleJudge
  EnsembleJudge -->|Evaluation Verdict| Orchestrator
  Orchestrator -->|If Failed| SectionLocker
  SectionLocker --> DeltaRepair
  DeltaRepair --> RollbackGuard
  RollbackGuard -->|Re-Evaluate & Accept/Rollback| Orchestrator
  Orchestrator --> AdaptiveMemory
  Orchestrator --> TraceEngine
  AdaptiveMemory --> DB
  TraceEngine --> DB
  Orchestrator -->|Guaranteed Reliable Response| Proxy
  Proxy -->|Stream / Final Output| Client
```

---

## 2. Request Lifecycle Sequence

```mermaid
sequenceDiagram
  autonumber
  participant Client as Client Application
  participant Proxy as EVALOS Proxy
  participant Gen as Generation Provider
  participant Verify as Grounding / Schema Verifier
  participant Judge as Evaluator Judge
  participant Repair as Selective Repair Engine
  participant Rollback as Rollback Guard

  Client->>Proxy: POST /v1/chat/completions (prompt, optimize_for, docs)
  Proxy->>Gen: Initial Generation Request
  Gen-->>Proxy: Raw Candidate Text
  
  Proxy->>Verify: Validate Claims against Retrieved Documents
  Verify-->>Proxy: Grounding & Citation Report (pass/fail)

  Proxy->>Judge: Score against Criteria (strict/adversarial)
  Judge-->>Proxy: EvaluationResult (score=0.55, failed: [s2])

  alt Score < Threshold OR Grounding Fails
    loop Attempt 1 to Max Repairs (Budgeted)
      Proxy->>Repair: Build Prompt for Failed Section s2 (s1 locked)
      Repair-->>Proxy: Section Delta JSON for s2
      Proxy->>Rollback: Verify Score & Grounding Invariants
      alt Score Improves AND Invariants Hold
        Rollback-->>Proxy: Accept Repaired Output
      else Score Regresses OR Invariants Broken
        Rollback-->>Proxy: Trigger ROLLBACK to Pre-Repair Checkpoint
      end
    end
  end

  Proxy->>Client: Return Verified, Stable Response + Trace Headers
```

---

## 3. Evaluation Lifecycle Diagram

```mermaid
flowchart TD
  In["Candidate Text & Evidence Documents"] --> Split["Structural Section Partitioner"]
  Split --> Extract["Atomic Claim Extractor"]
  
  subgraph "Dual-Stage Grounding"
    Extract --> FastLex["Stage 1: Fast Lexical Filter (BM25 / Lemmatized)"]
    FastLex -->|Candidate Pairs| SemanticCross["Stage 2: Semantic Cross-Encoder (ONNX NLI)"]
    SemanticCross --> Verdict["Entailment / Contradiction Classification"]
  end

  subgraph "Criteria Evaluation"
    In --> CriteriaPrompt["Task Criteria (Generated or Configured)"]
    CriteriaPrompt --> MultiEval["Ensemble Evaluator: Primary + Adversarial"]
    MultiEval --> Consensus["Consensus Score & Disagreement Index"]
  end

  Verdict --> Combine["Confidence-Weighted Score Synthesizer"]
  Consensus --> Combine
  Combine --> FinalEval["Final Evaluation Result (Passed / Failed Spans)"]
```

---

## 4. Repair & Rollback Lifecycle Diagram

```mermaid
stateDiagram-v2
  [*] --> EvaluatingDraft
  EvaluatingDraft --> Passed: Score >= Threshold & Grounded
  EvaluatingDraft --> Repairing: Failures Detected

  state Repairing {
    [*] --> LockStableSections
    LockStableSections --> GenerateDeltas: Prompt Repair Model for Failed Sections
    GenerateDeltas --> ApplyDeltas: Apply Span Changes
    ApplyDeltas --> CheckBudget: Deduct Token Cost
    CheckBudget --> Exhausted: Budget <= 0
    CheckBudget --> Reevaluate: Budget > 0
  }

  Reevaluate --> RollbackTriggered: Score < Previous Score
  Reevaluate --> LowGainRejected: Score Gain < Minimum Improvement
  Reevaluate --> Accepted: Score >= Previous + Invariants Met

  RollbackTriggered --> RestoreCheckpoint: Revert Text & Increment Rollback Count
  RestoreCheckpoint --> RecordMemory
  LowGainRejected --> RestoreCheckpoint
  Accepted --> RecordMemory: Update Successful Repair Lineage
  Passed --> RecordMemory
  Exhausted --> RestoreCheckpoint

  RecordMemory --> FinalEmission
  FinalEmission --> [*]
```

---

## 5. Agent Execution Lifecycle (Target Future Supervisor)

```mermaid
sequenceDiagram
  autonumber
  participant Agent as Agent Planner (ReAct / LangGraph)
  participant Interceptor as EVALOS Agent Supervisor
  participant ToolSandbox as Tool Execution Sandbox
  participant Environment as Real APIs / DBs

  Agent->>Interceptor: Tool Call Dispatch (tool: db_query, args: {...})
  Interceptor->>Interceptor: Schema & Policy Validation (tools_allowed, argument safety)
  alt Tool Not Allowed OR Args Malformed
    Interceptor-->>Agent: Intercepted & Blocked (Error Details returned)
  else Authorized Tool Call
    Interceptor->>ToolSandbox: Execute in Sandboxed Environment
    ToolSandbox->>Environment: Safe Execution
    Environment-->>ToolSandbox: Raw Tool Output
    ToolSandbox-->>Interceptor: Output Telemetry & Return Code
    Interceptor->>Interceptor: Reasoning Consistency & Output Verification
    Interceptor-->>Agent: Deliver Verified Tool Output
  end
```

---

## 6. Policy Enforcement Lifecycle Diagram

```mermaid
flowchart LR
  IncomingReq["Incoming Completion Stream"] --> PolicyCheck{"Policy Engine"}
  
  PolicyCheck -->|Rule 1: Grounding Invariant| GCheck["Require Grounding Score >= 0.80"]
  PolicyCheck -->|Rule 2: Citation Anchor| CCheck["Require Exact Span Citation for Numbers"]
  PolicyCheck -->|Rule 3: Schema Lock| SCheck["Require Valid JSON Structure"]

  GCheck -->|Violated| TriggerRepair["Dispatch Surgical Repair"]
  CCheck -->|Violated| TriggerRepair
  SCheck -->|Violated| TriggerRepair

  TriggerRepair --> VerifyRepair{"Repair Meets Policy?"}
  VerifyRepair -->|Yes| Deliver["Deliver to Client"]
  VerifyRepair -->|No & Rollback Active| SafeFallback["Deliver Best Checked Baseline / Fallback"]
```

---

## 7. Component Boundaries & MVP vs. Future Scope

| Subsystem | Component | MVP Scope (v0.2) | Future Scope (v1.0+) |
| :--- | :--- | :--- | :--- |
| **Ingress** | Proxy Gateway | FastAPI `/v1/chat/completions` (sync + SSE streaming) | High-performance Go/Rust Reverse Proxy |
| **Core** | Pipeline Orchestrator | Decoupled event-driven Python pipeline | Multi-threaded async DAG engine |
| **Verification** | Grounding Engine | Dual-stage (BM25 + lightweight ONNX NLI) | Fine-tuned 8B Lynx model / Hosted API |
| **Verification** | Citation Validator | Fixed `ClaimSupport` attributes + exact span match | Automatic citation re-alignment & fuzzy search |
| **Repair** | Selective Repairer | Robust character-offset replacement + section locking | AST-level JSON & Markdown node replacement |
| **Safety** | Rollback Guard | Invariant-based regression check | Multi-checkpoint tree search (MCTS repair) |
| **Agent** | Agent Supervisor | Clean schema validation of agent traces | Live tool interception middleware (LangGraph/AutoGen) |
| **Memory** | Adaptive Memory | Normalized SQLite with indexed model/domain stats | Distributed Redis + Postgres with team clustering |
| **Telemetry** | Observability | OTLP OpenTelemetry exporter + ASCII console traces | Live streaming React dashboard + ClickHouse |

