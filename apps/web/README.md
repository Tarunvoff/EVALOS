# EvalOS Demo Frontend

Modern UI for demonstrating EvalOS repair pipelines, hallucination detection, grounding validation, and benchmark insights.

## Run

```bash
pnpm dev
```

Open http://localhost:3000.

## API

Set the backend URL if it is not running on default localhost:8000:

```bash
set NEXT_PUBLIC_EVALOS_API_BASE=http://localhost:8000
```

## Pages

- / - landing and reliability pulse
- /playground - live repair demo UI
- /repair-timeline - repair timeline viewer
- /hallucination-inspector - hallucination overlays
- /grounding-viewer - RAG grounding visualization
- /agent-trace - agent trace viewer
- /benchmarks - benchmark dashboard
- /dashboard - reliability dashboard
