from __future__ import annotations

from pydantic import BaseModel, Field

from evalos.rag.grounding import GroundingResult, _support_score
from evalos.rag.schema import SCHEMA_VERSION
from evalos.rag.retriever import CitationMapping, RetrievedDocument


class CitationIssue(BaseModel):
    claim_id: str
    claim: str | None = None
    doc_id: str | None = None
    reason: str | None = None


class CitationResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    citation_accuracy_score: float
    citation_precision: float = 0.0
    missing_citations: list[CitationIssue] = Field(default_factory=list)
    incorrect_citations: list[CitationIssue] = Field(default_factory=list)
    irrelevant_citations: list[CitationIssue] = Field(default_factory=list)
    over_cited_references: list[CitationIssue] = Field(default_factory=list)


class CitationEvaluator:
    def __init__(self, *, support_threshold: float = 0.6, max_docs_per_claim: int = 2) -> None:
        self._support_threshold = support_threshold
        self._max_docs = max_docs_per_claim

    def evaluate(
        self,
        *,
        retrieved_documents: list[RetrievedDocument],
        citations: list[CitationMapping] | None,
        grounding: GroundingResult,
        claim_map: dict[str, str] | None = None,
    ) -> CitationResult:
        citations = citations or []
        doc_lookup = {doc.id: doc.text for doc in retrieved_documents}
        claim_lookup = claim_map or grounding.claim_map
        mapping_lookup: dict[str, list[CitationMapping]] = {}
        for mapping in citations:
            mapping_lookup.setdefault(mapping.claim_id, []).append(mapping)

        missing: list[CitationIssue] = []
        incorrect: list[CitationIssue] = []
        irrelevant: list[CitationIssue] = []
        over_cited: list[CitationIssue] = []
        aligned = 0

        supported_claims = grounding.supported_claims + grounding.partial_claims
        for support in supported_claims:
            if support.claim_id not in mapping_lookup:
                missing.append(
                    CitationIssue(
                        claim_id=support.claim_id,
                        claim=support.claim,
                        reason="missing",
                    )
                )

        span_total = 0
        span_supported = 0
        for claim_id, mappings in mapping_lookup.items():
            claim_text = claim_lookup.get(claim_id)
            if len(mappings) > self._max_docs:
                over_cited.append(
                    CitationIssue(
                        claim_id=claim_id,
                        claim=claim_text,
                        reason="over_cited",
                    )
                )
            matched = False
            for mapping in mappings:
                doc_text = doc_lookup.get(mapping.doc_id)
                span_len = max(0, mapping.span.end - mapping.span.start)
                span_total += span_len
                if not doc_text:
                    incorrect.append(
                        CitationIssue(
                            claim_id=claim_id,
                            claim=claim_text,
                            doc_id=mapping.doc_id,
                            reason="missing_doc",
                        )
                    )
                    continue
                if mapping.span.end > len(doc_text) or mapping.span.start < 0:
                    incorrect.append(
                        CitationIssue(
                            claim_id=claim_id,
                            claim=claim_text,
                            doc_id=mapping.doc_id,
                            reason="span_out_of_bounds",
                        )
                    )
                    continue
                span_text = doc_text[mapping.span.start : mapping.span.end]
                if span_text != mapping.text:
                    incorrect.append(
                        CitationIssue(
                            claim_id=claim_id,
                            claim=claim_text,
                            doc_id=mapping.doc_id,
                            reason="span_text_mismatch",
                        )
                    )
                    continue
                span_supported += span_len
                if not claim_text:
                    incorrect.append(
                        CitationIssue(
                            claim_id=claim_id,
                            doc_id=mapping.doc_id,
                            reason="unknown_claim_id",
                        )
                    )
                    continue
                score = _support_score(claim_text, doc_text)
                if score >= self._support_threshold:
                    matched = True
                else:
                    irrelevant.append(
                        CitationIssue(
                            claim_id=claim_id,
                            claim=claim_text,
                            doc_id=mapping.doc_id,
                            reason="irrelevant",
                        )
                    )
            if matched:
                aligned += 1
            else:
                incorrect.append(
                    CitationIssue(
                        claim_id=claim_id,
                        claim=claim_text,
                        reason="no_support",
                    )
                )

        if not citations and not supported_claims:
            score = 1.0
        else:
            score = aligned / max(1, len(citations))
        if span_total == 0:
            citation_precision = 1.0 if not citations else 0.0
        else:
            citation_precision = span_supported / max(1, span_total)

        return CitationResult(
            citation_accuracy_score=score,
            citation_precision=citation_precision,
            missing_citations=missing,
            incorrect_citations=incorrect,
            irrelevant_citations=irrelevant,
            over_cited_references=over_cited,
        )
