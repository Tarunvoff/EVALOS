from __future__ import annotations

from evalos.observability.snapshot import snapshot_generation_response, snapshot_trace
from evalos.observability.tracer import Trace
from evalos.rag.canonical import canonicalize_claims
from evalos.rag.dependency import (
    apply_dependency_penalty,
    build_dependency_graph,
    ClaimDependency,
    descendants_for_claims,
)
from evalos.rag.validation import validate_agent_trace, validate_citations
from evalos.rag.retriever import RetrievedDocument
from evalos.types import CriterionResult, EvaluationResult, GenerationResponse, Metrics, Section, Usage


def test_canonical_claim_determinism():
    claim_map = {
        "claim_b": "Beta",
        "claim_a": "Alpha",
    }
    first = canonicalize_claims(claim_map=claim_map, provided_order=sorted(claim_map.keys()))
    second = canonicalize_claims(claim_map=claim_map, provided_order=sorted(claim_map.keys()))
    assert [item.canonical_claim_id for item in first] == [item.canonical_claim_id for item in second]


def test_dependency_penalty_applies():
    base_scores = {"claim_1": 0.2, "claim_2": 0.9}
    deps = [ClaimDependency(claim_id="claim_2", depends_on=["claim_1"])]
    graph = build_dependency_graph(deps)
    adjusted = apply_dependency_penalty(base_scores=base_scores, graph=graph, penalty=0.15)
    assert adjusted["claim_2"] < base_scores["claim_2"]


def test_reasoning_tool_validation():
    trace = {
        "plan": [
            {"step_id": 1, "goal": "think", "tool": "", "status": "success"}
        ],
        "tool_calls": [],
        "reasoning_chain": [],
        "tools_allowed": [],
        "tools_used": [],
        "errors": [],
    }
    result = validate_agent_trace(agent_trace=trace)
    assert any(item.code == "missing_tool" for item in result.errors)

    trace_reasoning = {
        "plan": [
            {"step_id": 1, "goal": "think", "tool": "reasoning", "status": "success"}
        ],
        "tool_calls": [],
        "reasoning_chain": ["ok"],
        "tools_allowed": [],
        "tools_used": [],
        "errors": [],
    }
    result_ok = validate_agent_trace(agent_trace=trace_reasoning)
    assert result_ok.valid is True


def test_citation_schema_version_mismatch():
    docs = [RetrievedDocument(id="doc_1", text="Alpha beta gamma")]
    citations = [
        {
            "schema_version": "0.9",
            "claim_id": "claim_1",
            "doc_id": "doc_1",
            "span": {"start": 0, "end": 5},
            "text": "Alpha",
        }
    ]
    result = validate_citations(
        retrieved_documents=docs,
        generated_response="Alpha",
        citations=citations,
    )
    assert any(item.code == "schema_version_mismatch" for item in result.errors)


def test_snapshot_trace_stability():
    trace = Trace.start(model="m", provider="p", query="q")
    trace.add_step("step_one", data={"a": 1}, timestamp=trace.start_ts + 1.0)
    payload = snapshot_trace(trace)
    assert payload["start_ts"] == 0.0
    assert payload["steps"][0]["name"] == "request_start"
    assert payload["steps"][1]["name"] == "step_one"


def test_snapshot_trace_orders_dependencies():
    trace = Trace.start(model="m", provider="p", query="q")
    trace.claim_dependencies = [
        {"claim_id": "claim_b", "depends_on": []},
        {"claim_id": "claim_a", "depends_on": ["claim_b"]},
    ]
    payload = snapshot_trace(trace)
    assert payload["claim_dependencies"][0]["claim_id"] == "claim_a"


def test_dependency_descendants_traversal():
    deps = [
        ClaimDependency(claim_id="claim_2", depends_on=["claim_1"]),
        ClaimDependency(claim_id="claim_3", depends_on=["claim_2"]),
    ]
    graph = build_dependency_graph(deps)
    descendants = descendants_for_claims(graph, ["claim_1"])
    assert descendants == {"claim_2", "claim_3"}


def test_citation_missing_schema_version_repairs_and_provenance():
    docs = [RetrievedDocument(id="doc_1", text="Alpha beta gamma")]
    citations = [
        {
            "claim_id": "claim_1",
            "doc_id": "doc_1",
            "span": {"start": 0, "end": 5},
            "text": "Alpha",
        }
    ]
    result = validate_citations(
        retrieved_documents=docs,
        generated_response="Alpha",
        citations=citations,
    )
    assert result.repaired is True
    assert result.citations[0].provenance is not None
    assert result.citations[0].provenance.origin == "caller"


def test_invalid_agent_trace_schema():
    trace = {
        "plan": [
            {"step_id": 1, "goal": "think", "tool": None, "status": "success"}
        ],
        "tool_calls": [],
        "reasoning_chain": [],
        "tools_allowed": [],
        "tools_used": [],
        "errors": [],
    }
    result = validate_agent_trace(agent_trace=trace)
    assert any(item.code == "invalid_agent_trace" for item in result.errors)


def test_snapshot_generation_response_determinism():
    result_b = CriterionResult(
        name="beta",
        score=0.6,
        passed=False,
        confidence=0.8,
        affected_section="s2",
    )
    result_a = CriterionResult(
        name="alpha",
        score=0.9,
        passed=True,
        confidence=0.8,
        affected_section="s1",
    )
    evaluation = EvaluationResult(
        results=[result_b, result_a],
        passed=False,
        failed=["beta", "alpha"],
        weighted_score=0.75,
        pass_rate=0.5,
        sections=[Section(id="s2", text="B", start=0, end=1), Section(id="s1", text="A", start=0, end=1)],
    )
    metrics = Metrics(
        provider="p",
        model="m",
        latency_ms=1.0,
        usage=Usage(),
    )
    response = GenerationResponse(text="ok", metrics=metrics, evaluation=evaluation)
    snapshot = snapshot_generation_response(response)
    assert [item["name"] for item in snapshot["evaluation"]["results"]] == ["alpha", "beta"]
    assert snapshot["evaluation"]["failed"] == ["alpha", "beta"]
