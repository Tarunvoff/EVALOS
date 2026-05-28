# EvalOS

EvalOS is an AI reliability runtime with selective repair, provenance-aware evaluation, grounding verification, and rollback protection. It turns raw generation into observable, stable outputs with traceable repairs.

## Why EvalOS

- Dynamic criteria generation and adversarial evaluation
- Selective repair with rollback safety
- RAG grounding validation + hallucination detection
- Citation precision checks with span validation
- Agent reliability evaluation and tool correctness
- Adaptive memory for faster convergence
- Deterministic provenance tracking and schema governance

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system diagram.

## Quickstart (local LLM)

Backend (FastAPI + Ollama):

```bash
set EVALOS_OLLAMA_BASE_URL=http://localhost:11434
set EVALOS_OLLAMA_MODEL=llama3:latest
python apps/api/main.py
```

Frontend (Next.js demo UI):

```bash
cd apps/web
pnpm dev
```

Open http://localhost:3000.

## Benchmarks

Run the benchmark suite:

```bash
python -m evalos.benchmarks.cli run --model llama3:latest --provider litellm
```

Outputs:

- JSON benchmark reports
- CSV exports
- Markdown summaries
- Charts (cost vs quality, hallucination reduction)

## Demo Scenarios

Curated demos live in [docs/demos](docs/demos). Each demo includes before/after outputs, metrics delta, trace visualization, and repair reasoning.

## Core Pipeline (Simplified)

User Query
-> Criteria Generation
-> Response Generation
-> Evaluation
-> Selective Repair
-> Trace + Metrics

## Public API (Python)

```python
from evalos import Pipeline

pipeline = Pipeline(
    model="llama3:latest",
    repair_strategy="selective",
    max_repairs=2,
)

response = await pipeline.generate(
    query="Explain transformers",
    optimize_for=["clarity", "accuracy", "depth"],
)

print(response.text)
print(response.metrics)
print(response.format_trace())
```

### Streaming

```python
async for event in pipeline.stream(query="Explain transformers", optimize_for=["clarity"]):
    if event.type == "text":
        print(event.data, end="")
```

## Repository Layout

- apps/web: Next.js demo UI
- apps/api: FastAPI entrypoint
- benchmarks: benchmark fixtures + reports
- docs: architecture, demos, release notes
- src/evalos: core runtime

## Docs

- [docs/quickstart.md](docs/quickstart.md)
- [docs/benchmarks.md](docs/benchmarks.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/contributing.md](docs/contributing.md)
