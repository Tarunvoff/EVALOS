# Quickstart

## Backend (local LLM via Ollama)

```bash
pip install -e ".[api]"
set EVALOS_OLLAMA_BASE_URL=http://localhost:11434
set EVALOS_OLLAMA_MODEL=llama3:latest
python apps/api/main.py
```

## Frontend

```bash
cd apps/web
set NEXT_PUBLIC_EVALOS_API_BASE=http://localhost:8000
pnpm dev
```

Open http://localhost:3000.

## Benchmark Suite

```bash
python -m evalos.benchmarks.cli run --model llama3:latest --provider litellm
```
