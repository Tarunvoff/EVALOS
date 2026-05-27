from __future__ import annotations

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class Provenance(BaseModel):
    schema_version: str = SCHEMA_VERSION
    origin: str
    derived_from: list[str] = Field(default_factory=list)
    repair_generation: int = 0


def validate_schema_version(
    value: str | None,
    *,
    allow_missing: bool = True,
) -> tuple[bool, bool, str]:
    if value is None:
        if allow_missing:
            return True, True, SCHEMA_VERSION
        return False, False, SCHEMA_VERSION
    if value != SCHEMA_VERSION:
        return False, False, value
    return True, False, value
