from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from evalos.rag.schema import SCHEMA_VERSION, Provenance


class RetrievedDocument(BaseModel):
    id: str
    text: str
    source: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CitationSpan(BaseModel):
    start: int
    end: int


class CitationMapping(BaseModel):
    schema_version: str = SCHEMA_VERSION
    claim_id: str
    doc_id: str
    span: CitationSpan
    text: str
    provenance: Provenance | None = None


def normalize_documents(documents: list[RetrievedDocument | dict[str, Any] | str]) -> list[RetrievedDocument]:
    normalized: list[RetrievedDocument] = []
    for index, item in enumerate(documents, start=1):
        if isinstance(item, RetrievedDocument):
            normalized.append(item)
            continue
        if isinstance(item, str):
            normalized.append(
                RetrievedDocument(id=f"doc_{index}", text=item, source=None, metadata={})
            )
            continue
        if isinstance(item, dict):
            text = item.get("text") or item.get("content") or item.get("body") or ""
            doc_id = item.get("id") or item.get("doc_id") or f"doc_{index}"
            normalized.append(
                RetrievedDocument(
                    id=str(doc_id),
                    text=str(text),
                    source=item.get("source"),
                    score=item.get("score"),
                    metadata={
                        key: value
                        for key, value in item.items()
                        if key not in {"text", "content", "body", "id", "doc_id", "source", "score"}
                    },
                )
            )
    return normalized


def flatten_context(documents: list[RetrievedDocument]) -> str:
    return "\n\n".join(doc.text for doc in documents)
