from __future__ import annotations

import json
from typing import Any

from evalos.observability.tracer import Trace
from evalos.observability.snapshot import snapshot_trace


def export_trace_json(trace: Trace, *, indent: int = 2) -> str:
    payload = trace.model_dump(mode="json")
    return json.dumps(payload, indent=indent, ensure_ascii=True, sort_keys=True)


def pretty_trace(trace: Trace) -> str:
    return trace.render()


def export_trace_snapshot_json(trace: Trace, *, indent: int = 2) -> str:
    payload = snapshot_trace(trace)
    return json.dumps(payload, indent=indent, ensure_ascii=True, sort_keys=True)


def trace_log_record(trace: Trace) -> dict[str, Any]:
    return {
        "event": "evalos_trace",
        "trace": trace.model_dump(mode="json"),
    }
