# EvalOS API

FastAPI backend for EvalOS demos and dashboards.

## Run

```bash
pip install -e ".[api]"
set EVALOS_OLLAMA_BASE_URL=http://localhost:11434
set EVALOS_OLLAMA_MODEL=llama3:latest
python apps/api/main.py
```

API base URL: http://127.0.0.1:8000

## Endpoints

- POST /generate
- POST /trace
- POST /benchmark/run
- GET /benchmark/results
- GET /dashboard/metrics
- GET /hallucinations
- GET /grounding
- POST /agent/eval
