# EvalOS

EvalOS is a production-grade runtime for improving LLM output reliability while reducing token cost through selective repair generation. It dynamically generates criteria, evaluates responses, and repairs only failed dimensions while preserving the successful ones.

## Core pipeline

User Query
-> Dynamic Criteria Generation
-> Response Generation
-> Criteria Evaluation
-> Failed Criteria Detection
-> Selective Repair
-> Final Response

## Design goals

- Async-first, streaming-compatible architecture
- Modular, extensible interfaces
- Provider-agnostic runtime abstraction
- Structured outputs and metrics
- Production-grade retries and timeouts

## Public API

```python
from evalos import Pipeline

pipeline = Pipeline(
    model="gpt-4o-mini",
    repair_strategy="selective",
    max_repairs=2,
)

response = await pipeline.generate(
    query="Explain transformers",
    optimize_for=["clarity", "accuracy", "depth"],
)

print(response.text)
print(response.metrics)

# Print Observability Trace (Timeline Graph & Before/After Comparison)
print(response.format_trace())
```

### Streaming

```python
async for event in pipeline.stream(query="Explain transformers", optimize_for=["clarity"]):
    if event.type == "text":
        print(event.data, end="")
```

## Package layout

- evalos.pipeline: Orchestrates the end-to-end runtime
- evalos.criteria: Dynamic criteria generation
- evalos.eval: Criterion-aware evaluation engine
- evalos.repair: Selective repair engine
- evalos.providers: Provider abstraction and LiteLLM adapter
- evalos.metrics: Metrics and timing helpers
- evalos.retry: Retry and backoff utilities
- evalos.logging: Structured logging configuration
- evalos.types: Core schemas
- evalos.errors: Exception hierarchy
- evalos.streaming: Streaming event types

## Testing

- pytest with pytest-asyncio

## Roadmap

- More provider adapters
- Additional evaluation strategies
- Extended observability hooks
