# EvalOS Benchmarks

This suite compares vanilla generation, retry generation, best-of-N sampling, and EvalOS runtime.

## Run

```bash
python -m evalos.benchmarks.cli run --model llama3:latest --provider litellm
```

Outputs are written to `benchmarks/reports/<timestamp>`:
- `benchmark_results.json`
- `benchmark_results.csv`
- `summary.md`
- `charts/*.png`

## Replay

```bash
python -m evalos.benchmarks.cli replay-run --run benchmarks/reports/<timestamp>/benchmark_results.json
```

## Fixtures

Add JSONL files in `benchmarks/fixtures/`. Each line is a single case with:
- `id`, `domain`, `prompt`
- optional `retrieved_documents`, `citations`, `agent_trace`
