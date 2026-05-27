from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from evalos.rag.agent_eval import AgentTrace, PlanStep, ToolCall
from evalos.rag.canonical import build_canonical_id_map, canonicalize_claims
from evalos.rag.grounding import _build_claim_map, _extract_claims
from evalos.rag.retriever import CitationMapping, CitationSpan, RetrievedDocument
from evalos.rag.schema import SCHEMA_VERSION, Provenance, validate_schema_version


class ValidationIssue(BaseModel):
    code: str
    message: str
    claim_id: str | None = None
    doc_id: str | None = None
    field: str | None = None


class CitationValidationResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    valid: bool
    citations: list[CitationMapping] = Field(default_factory=list)
    errors: list[ValidationIssue] = Field(default_factory=list)
    repaired: bool = False
    claim_map: dict[str, str] = Field(default_factory=dict)
    citation_precision: float = 0.0
    canonical_claims: list[dict[str, object]] = Field(default_factory=list)
    canonical_id_map: dict[str, str] = Field(default_factory=dict)


class AgentValidationResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    valid: bool
    trace: AgentTrace
    errors: list[ValidationIssue] = Field(default_factory=list)
    repaired: bool = False
    hallucinated_tools: list[str] = Field(default_factory=list)


def validate_citations(
    *,
    retrieved_documents: list[RetrievedDocument],
    generated_response: str,
    citations: list[dict[str, Any]] | list[CitationMapping] | None,
    claim_map: dict[str, str] | None = None,
) -> CitationValidationResult:
    claim_map = claim_map or _build_claim_map(_extract_claims(generated_response))
    doc_lookup = {doc.id: doc.text for doc in retrieved_documents}
    errors: list[ValidationIssue] = []
    repaired = False
    normalized: list[CitationMapping] = []
    default_provenance = Provenance(origin="caller")

    raw_items = citations or []
    for item in raw_items:
        mapping, was_repaired, item_errors = _normalize_citation(
            item,
            claim_map,
            doc_lookup,
            default_provenance=default_provenance,
        )
        if was_repaired:
            repaired = True
        if item_errors:
            errors.extend(item_errors)
        if mapping:
            normalized.append(mapping)

    canonical = canonicalize_claims(
        claim_map=claim_map,
        provided_order=sorted(claim_map.keys()),
    )
    canonical_id_map = build_canonical_id_map(canonical)
    canonical_claims = [
        {
            "canonical_claim_id": item.canonical_claim_id,
            "external_claim_id": item.external_claim_id,
            "internal_claim_index": item.internal_claim_index,
        }
        for item in canonical
    ]

    for mapping in normalized:
        if mapping.claim_id not in claim_map:
            errors.append(
                ValidationIssue(
                    code="unknown_claim_id",
                    message="claim_id not found in extracted claims",
                    claim_id=mapping.claim_id,
                    doc_id=mapping.doc_id,
                    field="claim_id",
                )
            )
        else:
            claim_text = claim_map[mapping.claim_id]
            if not _is_atomic_claim(claim_text):
                errors.append(
                    ValidationIssue(
                        code="compound_claim",
                        message="claim_id maps to a compound claim",
                        claim_id=mapping.claim_id,
                        field="claim_id",
                    )
                )

    span_total = 0
    span_supported = 0
    for mapping in normalized:
        doc_text = doc_lookup.get(mapping.doc_id)
        span_len = max(0, mapping.span.end - mapping.span.start)
        span_total += span_len
        if not doc_text:
            continue
        if mapping.span.start < 0 or mapping.span.end > len(doc_text):
            continue
        if doc_text[mapping.span.start : mapping.span.end] != mapping.text:
            continue
        span_supported += span_len

    citation_precision = span_supported / max(1, span_total)
    return CitationValidationResult(
        valid=len(errors) == 0,
        citations=normalized,
        errors=errors,
        repaired=repaired,
        claim_map=claim_map,
        citation_precision=citation_precision,
        canonical_claims=canonical_claims,
        canonical_id_map=canonical_id_map,
    )


def validate_agent_trace(
    *,
    agent_trace: dict[str, Any] | AgentTrace,
    claim_dependencies: list[dict[str, Any]] | None = None,
) -> AgentValidationResult:
    errors: list[ValidationIssue] = []
    repaired = False

    try:
        trace = AgentTrace.model_validate(agent_trace)
    except Exception:
        return AgentValidationResult(
            valid=False,
            trace=AgentTrace(),
            errors=[
                ValidationIssue(
                    code="invalid_agent_trace",
                    message="agent_trace failed schema validation",
                )
            ],
            repaired=False,
            hallucinated_tools=[],
        )
    if trace.schema_version != SCHEMA_VERSION:
        errors.append(
            ValidationIssue(
                code="schema_version_mismatch",
                message="agent_trace schema_version mismatch",
                field="schema_version",
            )
        )
    if not trace.tools_used:
        trace.tools_used = [call.tool_name for call in trace.tool_calls]
        repaired = True
    if trace.tools_allowed is None:
        trace.tools_allowed = []
        repaired = True

    for step in trace.plan:
        if not isinstance(step.tool, str) or not step.tool.strip():
            errors.append(
                ValidationIssue(
                    code="missing_tool",
                    message="plan step tool must be explicit",
                    field="plan.tool",
                )
            )
            continue
        if step.tool.lower().strip() == "reasoning":
            continue
        if step.tool.lower().strip() in {"none", ""}:
            errors.append(
                ValidationIssue(
                    code="invalid_reasoning_tool",
                    message="reasoning steps must use tool=reasoning",
                    field="plan.tool",
                )
            )

    hallucinated = []
    if trace.tools_allowed:
        for tool in trace.tools_used:
            if tool not in trace.tools_allowed:
                hallucinated.append(tool)
                errors.append(
                    ValidationIssue(
                        code="hallucinated_tool",
                        message="tool not in tools_allowed",
                        field="tools_used",
                    )
                )

    plan_tools = _plan_tool_set(trace.plan)
    for call in trace.tool_calls:
        if call.tool_name not in plan_tools:
            errors.append(
                ValidationIssue(
                    code="tool_call_not_in_plan",
                    message="tool_call missing plan step",
                    field="tool_calls",
                )
            )

    for step in trace.plan:
        if _is_reasoning_step(step):
            continue
        if not _call_for_tool(step.tool, trace.tool_calls):
            errors.append(
                ValidationIssue(
                    code="plan_step_missing_call",
                    message="plan step missing tool_call",
                    field="plan",
                )
            )

    if trace.tool_calls and not trace.reasoning_chain:
        errors.append(
            ValidationIssue(
                code="missing_reasoning_chain",
                message="reasoning_chain required when tool_calls exist",
                field="reasoning_chain",
            )
        )

    return AgentValidationResult(
        valid=len(errors) == 0,
        trace=trace,
        errors=errors,
        repaired=repaired,
        hallucinated_tools=hallucinated,
    )


def _normalize_citation(
    item: CitationMapping | dict[str, Any],
    claim_map: dict[str, str],
    doc_lookup: dict[str, str],
    *,
    default_provenance: Provenance,
) -> tuple[CitationMapping | None, bool, list[ValidationIssue]]:
    errors: list[ValidationIssue] = []
    repaired = False
    if isinstance(item, CitationMapping):
        mapping = item
        ok, _, _ = validate_schema_version(mapping.schema_version, allow_missing=False)
        if not ok:
            errors.append(
                ValidationIssue(
                    code="schema_version_mismatch",
                    message="citation schema_version mismatch",
                    field="schema_version",
                )
            )
    elif isinstance(item, dict):
        schema_version = item.get("schema_version")
        ok, was_repaired, _ = validate_schema_version(schema_version, allow_missing=True)
        if not ok:
            errors.append(
                ValidationIssue(
                    code="schema_version_mismatch",
                    message="citation schema_version mismatch",
                    field="schema_version",
                )
            )
        if was_repaired:
            repaired = True
        mapping = _repair_citation_dict(item, claim_map, doc_lookup, default_provenance)
        if mapping is None:
            errors.append(
                ValidationIssue(
                    code="invalid_citation",
                    message="citation missing required fields",
                )
            )
            return None, True, errors
        repaired = True
    else:
        errors.append(
            ValidationIssue(
                code="invalid_citation",
                message="citation must be mapping object",
            )
        )
        return None, False, errors

    doc_text = doc_lookup.get(mapping.doc_id)
    if not mapping.doc_id or mapping.doc_id not in doc_lookup:
        errors.append(
            ValidationIssue(
                code="missing_doc_id",
                message="doc_id not found in retrieved documents",
                claim_id=mapping.claim_id,
                doc_id=mapping.doc_id,
                field="doc_id",
            )
        )
    if mapping.span.start < 0 or mapping.span.end <= mapping.span.start:
        errors.append(
            ValidationIssue(
                code="invalid_span",
                message="span must be positive and start < end",
                claim_id=mapping.claim_id,
                doc_id=mapping.doc_id,
                field="span",
            )
        )
    if doc_text:
        if mapping.span.end > len(doc_text):
            errors.append(
                ValidationIssue(
                    code="span_out_of_bounds",
                    message="span exceeds document length",
                    claim_id=mapping.claim_id,
                    doc_id=mapping.doc_id,
                    field="span",
                )
            )
        else:
            span_text = doc_text[mapping.span.start : mapping.span.end]
            if mapping.text != span_text:
                errors.append(
                    ValidationIssue(
                        code="span_text_mismatch",
                        message="text must match span content",
                        claim_id=mapping.claim_id,
                        doc_id=mapping.doc_id,
                        field="text",
                    )
                )
    return mapping, repaired, errors


def _repair_citation_dict(
    item: dict[str, Any],
    claim_map: dict[str, str],
    doc_lookup: dict[str, str],
    default_provenance: Provenance,
) -> CitationMapping | None:
    claim_id = item.get("claim_id")
    if not claim_id and "claim" in item:
        claim_text = str(item.get("claim", ""))
        for candidate_id, text in claim_map.items():
            if text == claim_text:
                claim_id = candidate_id
                break
    doc_id = item.get("doc_id")
    span = item.get("span")
    text = item.get("text")

    if not claim_id or not doc_id:
        return None

    doc_text = doc_lookup.get(str(doc_id), "")
    if isinstance(span, dict):
        span_obj = CitationSpan(start=int(span.get("start", 0)), end=int(span.get("end", 0)))
    else:
        span_obj = None

    if span_obj is None and isinstance(text, str) and doc_text:
        idx = doc_text.find(text)
        if idx >= 0:
            span_obj = CitationSpan(start=idx, end=idx + len(text))
    if span_obj is not None and not text and doc_text:
        text = doc_text[span_obj.start : span_obj.end]

    if span_obj is None or not isinstance(text, str):
        return None

    provenance = item.get("provenance")
    if provenance:
        provenance_obj = Provenance.model_validate(provenance)
    else:
        provenance_obj = default_provenance

    return CitationMapping(
        claim_id=str(claim_id),
        doc_id=str(doc_id),
        span=span_obj,
        text=text,
        provenance=provenance_obj,
    )


def _is_atomic_claim(claim: str) -> bool:
    lowered = claim.lower()
    if " and " in lowered or " or " in lowered:
        return False
    if ";" in lowered:
        return False
    if len(re.findall(r",", lowered)) >= 2:
        return False
    return True


def _plan_tool_set(plan: list[PlanStep]) -> set[str]:
    return {step.tool for step in plan if step.tool and step.tool.lower().strip() != "reasoning"}


def _is_reasoning_step(step: PlanStep) -> bool:
    normalized = step.tool.lower().strip()
    return normalized == "reasoning"


def _call_for_tool(tool: str, tool_calls: list[ToolCall]) -> bool:
    return any(call.tool_name == tool for call in tool_calls)
