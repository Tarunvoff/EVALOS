# Benchmarks

## Run locally

```bash
pip install -e ".[bench]"
python -m evalos.benchmarks.cli run --model llama3:latest --provider litellm
```

## Outputs

- JSON results
- CSV summary
- Markdown report
- Charts (cost vs quality, hallucination reduction)

## Replay

```bash
python -m evalos.benchmarks.cli replay-run --run benchmarks/reports/<timestamp>/benchmark_results.json
```
