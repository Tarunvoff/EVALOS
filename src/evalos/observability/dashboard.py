from __future__ import annotations

from evalos.observability.tracer import Trace


def render_trace_cli(trace: Trace) -> str:
    return trace.render()
