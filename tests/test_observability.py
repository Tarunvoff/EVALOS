from __future__ import annotations

from evalos.observability.tracer import Trace
from evalos.rag.schema import Provenance
from evalos.types import GenerationResponse, Metrics, Usage, RepairRecord

def test_format_trace():
    metrics = Metrics(
        provider="test-provider",
        model="test-model",
        latency_ms=150.5,
        retries=2,
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        quality_before=0.5,
        tokens_saved_vs_retry=15.0
    )
    
    repair = RepairRecord(
        attempt=1,
        failed_criteria=["clarity"],
        repaired_text="fixed text",
        score_before=0.5,
        score_after=0.9
    )
    
    response = GenerationResponse(
        text="fixed text",
        initial_text="broken text",
        metrics=metrics,
        repairs=[repair]
    )
    
    trace = response.format_trace()
    
    # Assertions
    assert "=== EvalOS Request Trace ===" in trace
    assert "Model: test-model | Provider: test-provider" in trace
    assert "Latency: 150.5ms | Retries: 2" in trace
    assert "Tokens: 30 (saved vs retry: 15.0)" in trace
    assert "--- Repair Timeline Graph ---" in trace
    assert "Initial Score: 0.50" in trace
    assert "v Attempt 1 -> Score: 0.90 (Repaired: clarity)" in trace
    assert "--- Before/After Comparison ---" in trace
    assert "[Before]\nbroken text" in trace
    assert "[After]\nfixed text" in trace


def test_trace_render_includes_repair_lineage():
    trace = Trace.start(model="m", provider="p", query="q")
    trace.repairs = [
        RepairRecord(
            attempt=1,
            failed_criteria=["clarity"],
            repaired_text="fixed",
            score_before=0.4,
            score_after=0.8,
            provenance=Provenance(origin="repair", derived_from=["clarity"], repair_generation=1),
        )
    ]
    output = trace.render()
    assert "Repair Lineage" in output
    assert "gen 1" in output
