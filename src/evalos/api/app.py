from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from evalos.api.schemas import (
    AgentEvalRequest,
    AgentEvalResponse,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
    DashboardMetricsResponse,
    GenerateRequest,
    TraceResponse,
)
from evalos.api.state import state
from evalos.benchmarks.models import BenchmarkConfig
from evalos.benchmarks.reporting import export_reports
from evalos.benchmarks.runner import BenchmarkRunner, load_run
from evalos.pipeline import Pipeline
from evalos.rag.agent_eval import AgentReliabilityEvaluator
from evalos.rag.validation import validate_agent_trace

app = FastAPI(title="EvalOS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _configure_ollama() -> tuple[str, str]:
    base_url = os.getenv("EVALOS_OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("EVALOS_OLLAMA_MODEL", "llama3:latest")
    os.environ.setdefault("OLLAMA_API_BASE", base_url)
    return base_url, model


def _resolve_model(provider: str, model: str) -> str:
    if provider == "litellm" and not model.startswith("ollama/"):
        return f"ollama/{model}"
    return model


@app.on_event("startup")
async def _startup() -> None:
    _configure_ollama()


@app.post("/generate")
async def generate(request: GenerateRequest) -> Any:
    provider = request.provider or os.getenv("EVALOS_PROVIDER", "litellm")
    base_url, default_model = _configure_ollama()
    model = request.model or os.getenv("EVALOS_MODEL", default_model)
    resolved_model = _resolve_model(provider, model)

    pipeline = Pipeline(model=resolved_model, provider=provider)

    if request.stream:
        return StreamingResponse(
            _stream_generate(pipeline, request),
            media_type="text/event-stream",
        )

    response = await pipeline.generate(
        query=request.prompt,
        optimize_for=request.optimize_for,
        domain=request.domain,
        retrieved_documents=request.retrieved_documents,
        citations=request.citations,
        agent_trace=request.agent_trace,
        claim_map=request.claim_map,
        claim_dependencies=request.claim_dependencies,
    )
    if response.trace:
        state.last_trace = response.trace
    return response.model_dump(mode="json")


async def _stream_generate(pipeline: Pipeline, request: GenerateRequest) -> AsyncIterator[str]:
    async for event in pipeline.stream(
        query=request.prompt,
        optimize_for=request.optimize_for,
        domain=request.domain,
        retrieved_documents=request.retrieved_documents,
        citations=request.citations,
        agent_trace=request.agent_trace,
        claim_map=request.claim_map,
        claim_dependencies=request.claim_dependencies,
    ):
        payload = event.data
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        yield f"event: {event.type}\n" f"data: {json.dumps(payload)}\n\n"
        if event.type == "done" and isinstance(payload, dict) and payload.get("trace"):
            state.last_trace = payload.get("trace")


@app.post("/trace", response_model=TraceResponse)
async def trace(request: GenerateRequest) -> TraceResponse:
    provider = request.provider or os.getenv("EVALOS_PROVIDER", "litellm")
    base_url, default_model = _configure_ollama()
    model = request.model or os.getenv("EVALOS_MODEL", default_model)
    resolved_model = _resolve_model(provider, model)

    pipeline = Pipeline(model=resolved_model, provider=provider)
    response = await pipeline.generate(
        query=request.prompt,
        optimize_for=request.optimize_for,
        domain=request.domain,
        retrieved_documents=request.retrieved_documents,
        citations=request.citations,
        agent_trace=request.agent_trace,
        claim_map=request.claim_map,
        claim_dependencies=request.claim_dependencies,
    )
    if not response.trace:
        raise HTTPException(status_code=500, detail="Trace not available")
    state.last_trace = response.trace
    return TraceResponse(trace=response.trace.model_dump(mode="json"))


@app.post("/benchmark/run", response_model=BenchmarkRunResponse)
async def run_benchmark(request: BenchmarkRunRequest) -> BenchmarkRunResponse:
    base_url, default_model = _configure_ollama()
    provider = request.provider or os.getenv("EVALOS_PROVIDER", "litellm")
    model = request.model or os.getenv("EVALOS_MODEL", default_model)
    resolved_model = _resolve_model(provider, model)

    config = BenchmarkConfig(
        model=resolved_model,
        provider=provider,
        output_dir=request.output_dir,
    )
    runner = BenchmarkRunner(config)
    run = await runner.run(strategies=request.strategies, export=False)
    output_dir = export_reports(run)
    state.last_benchmark = run
    return BenchmarkRunResponse(
        output_dir=str(output_dir),
        run_id=output_dir.name,
        result_path=str(output_dir / "benchmark_results.json"),
    )


@app.get("/benchmark/results")
async def benchmark_results(run: str) -> Any:
    if not Path(run).exists():
        raise HTTPException(status_code=404, detail="Run file not found")
    run_data = load_run(run)
    return run_data.model_dump(mode="json")


@app.get("/dashboard/metrics", response_model=DashboardMetricsResponse)
async def dashboard_metrics() -> DashboardMetricsResponse:
    summary = None
    if state.last_benchmark:
        summary = {
            "run_id": state.last_benchmark.config.run_id,
            "result_count": len(state.last_benchmark.results),
        }
    trace_payload = state.last_trace.model_dump(mode="json") if state.last_trace else None
    return DashboardMetricsResponse(benchmark_summary=summary, last_trace=trace_payload)


@app.get("/hallucinations")
async def hallucinations() -> Any:
    if not state.last_trace:
        raise HTTPException(status_code=404, detail="No trace available")
    return state.last_trace.hallucination


@app.get("/grounding")
async def grounding() -> Any:
    if not state.last_trace:
        raise HTTPException(status_code=404, detail="No trace available")
    return state.last_trace.grounding


@app.post("/agent/eval", response_model=AgentEvalResponse)
async def agent_eval(request: AgentEvalRequest) -> AgentEvalResponse:
    validation = validate_agent_trace(agent_trace=request.agent_trace)
    evaluator = AgentReliabilityEvaluator()
    result = evaluator.evaluate(trace=validation.trace)
    return AgentEvalResponse(**result.model_dump())
