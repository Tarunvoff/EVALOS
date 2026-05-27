from __future__ import annotations

import re

from pydantic import BaseModel, Field

from evalos.rag.retriever import RetrievedDocument, CitationMapping
from evalos.rag.canonical import canonicalize_claims
from evalos.rag.dependency import ClaimDependency, apply_dependency_penalty, build_dependency_graph
from evalos.rag.schema import Provenance
from evalos.rag.schema import SCHEMA_VERSION


class ClaimSupport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    canonical_claim_id: str
    external_claim_id: str
    claim: str
    support_score: float
    doc_id: str | None = None
    support_type: str
    reason: str | None = None


class GroundingResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    grounding_score: float
    unsupported_claims: list[ClaimSupport] = Field(default_factory=list)
    supported_claims: list[ClaimSupport] = Field(default_factory=list)
    partial_claims: list[ClaimSupport] = Field(default_factory=list)
    citation_alignment_score: float = 0.0
    total_claims: int = 0
    claim_map: dict[str, str] = Field(default_factory=dict)
    canonical_claims: list[dict[str, str]] = Field(default_factory=list)


class GroundingEvaluator:
    def __init__(
        self,
        *,
        support_threshold: float = 0.75,
        partial_threshold: float = 0.45,
        citation_threshold: float = 0.6,
    ) -> None:
        self._support_threshold = support_threshold
        self._partial_threshold = partial_threshold
        self._citation_threshold = citation_threshold

    def evaluate(
        self,
        *,
        retrieved_documents: list[RetrievedDocument],
        generated_response: str,
        citations: list[CitationMapping] | None = None,
        claim_map: dict[str, str] | None = None,
        dependencies: list[dict[str, object]] | None = None,
    ) -> GroundingResult:
        claims = _extract_claims(generated_response)
        resolved_map = claim_map or _build_claim_map(claims)
        canonical = canonicalize_claims(
            claim_map=resolved_map,
            provided_order=sorted(resolved_map.keys()),
            provenance=Provenance(origin="generated"),
        )
        canonical_lookup = {item.external_claim_id: item.canonical_claim_id for item in canonical}
        canonical_reverse = {value: key for key, value in canonical_lookup.items()}
        supported: list[ClaimSupport] = []
        partial: list[ClaimSupport] = []
        unsupported: list[ClaimSupport] = []

        for claim_id, claim in resolved_map.items():
            canonical_id = canonical_lookup.get(claim_id, claim_id)
            best_score, best_doc = _best_support(claim, retrieved_documents)
            if best_score >= self._support_threshold:
                supported.append(
                    ClaimSupport(
                        canonical_claim_id=canonical_id,
                        external_claim_id=claim_id,
                        claim=claim,
                        support_score=best_score,
                        doc_id=best_doc,
                        support_type="supported",
                    )
                )
            elif best_score >= self._partial_threshold:
                partial.append(
                    ClaimSupport(
                        canonical_claim_id=canonical_id,
                        external_claim_id=claim_id,
                        claim=claim,
                        support_score=best_score,
                        doc_id=best_doc,
                        support_type="partial",
                        reason="partial_support",
                    )
                )
            else:
                unsupported.append(
                    ClaimSupport(
                        canonical_claim_id=canonical_id,
                        external_claim_id=claim_id,
                        claim=claim,
                        support_score=best_score,
                        doc_id=best_doc,
                        support_type="unsupported",
                        reason="no_support",
                    )
                )

        if dependencies:
            normalized_deps = [ClaimDependency.model_validate(item) for item in dependencies]
            normalized_deps = _normalize_dependency_ids(normalized_deps, canonical_reverse)
            score_map = {item.external_claim_id: item.support_score for item in supported + partial + unsupported}
            graph = build_dependency_graph(normalized_deps)
            adjusted = apply_dependency_penalty(base_scores=score_map, graph=graph)
            supported, partial, unsupported = _reclassify_support(
                supported,
                partial,
                unsupported,
                adjusted,
                self._support_threshold,
                self._partial_threshold,
            )

        total = len(resolved_map)
        score = _weighted_score(len(supported), len(partial), len(unsupported))
        citation_alignment = _citation_alignment(
            citations or [], resolved_map, retrieved_documents, self._citation_threshold
        )

        return GroundingResult(
            grounding_score=score,
            unsupported_claims=unsupported,
            supported_claims=supported,
            partial_claims=partial,
            citation_alignment_score=citation_alignment,
            total_claims=total,
            claim_map=resolved_map,
            canonical_claims=[
                {
                    "canonical_claim_id": item.canonical_claim_id,
                    "external_claim_id": item.external_claim_id,
                    "internal_claim_index": item.internal_claim_index,
                }
                for item in canonical
            ],
        )


def _extract_claims(text: str) -> list[str]:
    sentences = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", text) if chunk.strip()]
    claims: list[str] = []
    for sentence in sentences:
        if _looks_factual(sentence):
            claims.append(sentence)
    return claims


def _build_claim_map(claims: list[str]) -> dict[str, str]:
    return {f"claim_{index}": claim for index, claim in enumerate(claims, start=1)}


def _looks_factual(sentence: str) -> bool:
    if re.search(r"\b\d+\b", sentence):
        return True
    if re.search(r"\b(is|are|was|were|has|have|contains|includes)\b", sentence, re.IGNORECASE):
        return True
    if re.search(r"\b[A-Z][a-z]+\b", sentence):
        return True
    return False


def _best_support(claim: str, documents: list[RetrievedDocument]) -> tuple[float, str | None]:
    best_score = 0.0
    best_doc = None
    for doc in documents:
        score = _support_score(claim, doc.text)
        if score > best_score:
            best_score = score
            best_doc = doc.id
    return best_score, best_doc


def _support_score(claim: str, context: str) -> float:
    claim_tokens = _tokens(claim)
    context_tokens = _tokens(context)
    if not claim_tokens or not context_tokens:
        return 0.0
    overlap = len(set(claim_tokens).intersection(context_tokens))
    return overlap / max(1, len(set(claim_tokens)))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _weighted_score(supported: int, partial: int, unsupported: int) -> float:
    total = supported + partial + unsupported
    if total == 0:
        return 1.0
    return (supported + 0.5 * partial) / max(1, total)


def _citation_alignment(
    citations: list[CitationMapping],
    claim_map: dict[str, str],
    documents: list[RetrievedDocument],
    threshold: float,
) -> float:
    if not citations:
        return 0.0
    doc_lookup = {doc.id: doc.text for doc in documents}
    aligned = 0
    for mapping in citations:
        claim = claim_map.get(mapping.claim_id)
        if not claim:
            continue
        hit = False
        doc_text = doc_lookup.get(mapping.doc_id)
        if doc_text and _support_score(claim, doc_text) >= threshold:
            hit = True
        if hit:
            aligned += 1
    return aligned / max(1, len(citations))


def _reclassify_support(
    supported: list[ClaimSupport],
    partial: list[ClaimSupport],
    unsupported: list[ClaimSupport],
    adjusted: dict[str, float],
    support_threshold: float,
    partial_threshold: float,
) -> tuple[list[ClaimSupport], list[ClaimSupport], list[ClaimSupport]]:
    by_id = {
        item.external_claim_id: item for item in supported + partial + unsupported
    }
    next_supported: list[ClaimSupport] = []
    next_partial: list[ClaimSupport] = []
    next_unsupported: list[ClaimSupport] = []
    for claim_id, item in by_id.items():
        score = adjusted.get(claim_id, item.support_score)
        item.support_score = score
        if score >= support_threshold:
            item.support_type = "supported"
            item.reason = None
            next_supported.append(item)
        elif score >= partial_threshold:
            item.support_type = "partial"
            item.reason = "dependency_penalty" if item.reason is None else item.reason
            next_partial.append(item)
        else:
            item.support_type = "unsupported"
            item.reason = "dependency_penalty" if item.reason is None else item.reason
            next_unsupported.append(item)
    return next_supported, next_partial, next_unsupported


def _normalize_dependency_ids(
    dependencies: list[ClaimDependency],
    canonical_reverse: dict[str, str],
) -> list[ClaimDependency]:
    normalized: list[ClaimDependency] = []
    for dep in dependencies:
        claim_id = canonical_reverse.get(dep.claim_id, dep.claim_id)
        parents = [canonical_reverse.get(parent, parent) for parent in dep.depends_on]
        normalized.append(ClaimDependency(claim_id=claim_id, depends_on=parents))
    return normalized
