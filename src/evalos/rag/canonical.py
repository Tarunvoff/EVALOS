from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

from evalos.rag.schema import SCHEMA_VERSION, Provenance


class CanonicalClaim(BaseModel):
    schema_version: str = SCHEMA_VERSION
    internal_claim_index: int
    external_claim_id: str
    canonical_claim_id: str
    text: str
    provenance: Provenance | None = None


def canonicalize_claims(
    *,
    claim_map: dict[str, str],
    provided_order: list[str] | None = None,
    provenance: Provenance | None = None,
) -> list[CanonicalClaim]:
    if provided_order:
        ordered = [cid for cid in provided_order if cid in claim_map]
    else:
        ordered = sorted(claim_map.keys())

    canonical: list[CanonicalClaim] = []
    for index, claim_id in enumerate(ordered, start=1):
        text = claim_map[claim_id]
        canonical_id = _canonical_id(claim_id, text)
        canonical.append(
            CanonicalClaim(
                internal_claim_index=index,
                external_claim_id=claim_id,
                canonical_claim_id=canonical_id,
                text=text,
                provenance=provenance,
            )
        )
    return canonical


def build_canonical_id_map(canonical_claims: list[CanonicalClaim]) -> dict[str, str]:
    return {
        item.external_claim_id: item.canonical_claim_id
        for item in canonical_claims
    }


def remap_claim_id(
    claim_id: str,
    *,
    external_to_canonical: dict[str, str],
) -> str:
    return external_to_canonical.get(claim_id, claim_id)


def _canonical_id(claim_id: str, text: str) -> str:
    digest = hashlib.sha256(f"{claim_id}::{text}".encode("utf-8")).hexdigest()
    return f"c_{digest[:16]}"
