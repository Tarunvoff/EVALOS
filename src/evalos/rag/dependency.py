from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field

from evalos.rag.schema import SCHEMA_VERSION, validate_schema_version


class ClaimDependency(BaseModel):
    schema_version: str = SCHEMA_VERSION
    claim_id: str
    depends_on: list[str] = Field(default_factory=list)


def validate_dependencies(
    *,
    claim_ids: set[str],
    dependencies: list[ClaimDependency],
) -> list[str]:
    errors: list[str] = []
    for dep in dependencies:
        ok, _, _ = validate_schema_version(dep.schema_version, allow_missing=False)
        if not ok:
            errors.append("schema_version_mismatch")
        if dep.claim_id not in claim_ids:
            errors.append("unknown_claim_id")
        for parent in dep.depends_on:
            if parent not in claim_ids:
                errors.append("unknown_dependency")
    return errors


def build_dependency_graph(
    dependencies: list[ClaimDependency],
) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = defaultdict(list)
    for dep in dependencies:
        graph[dep.claim_id].extend(dep.depends_on)
    return graph


def canonicalize_dependencies(
    *,
    dependencies: list[ClaimDependency],
    external_to_canonical: dict[str, str],
) -> list[ClaimDependency]:
    canonical: list[ClaimDependency] = []
    for dep in dependencies:
        canonical.append(
            ClaimDependency(
                claim_id=external_to_canonical.get(dep.claim_id, dep.claim_id),
                depends_on=[external_to_canonical.get(item, item) for item in dep.depends_on],
            )
        )
    return canonical


def descendants_for_claims(
    graph: dict[str, list[str]],
    roots: list[str],
) -> set[str]:
    reverse: dict[str, list[str]] = defaultdict(list)
    for child, parents in graph.items():
        for parent in parents:
            reverse[parent].append(child)

    seen: set[str] = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        for child in reverse.get(node, []):
            if child in seen:
                continue
            seen.add(child)
            stack.append(child)
    return seen


def apply_dependency_penalty(
    *,
    base_scores: dict[str, float],
    graph: dict[str, list[str]],
    penalty: float = 0.15,
) -> dict[str, float]:
    adjusted = dict(base_scores)
    for claim_id, parents in graph.items():
        if not parents:
            continue
        parent_min = min(base_scores.get(parent, 1.0) for parent in parents)
        if parent_min < 0.5:
            adjusted[claim_id] = max(0.0, adjusted.get(claim_id, 0.0) - penalty)
    return adjusted
