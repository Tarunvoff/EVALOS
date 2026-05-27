from __future__ import annotations

from dataclasses import dataclass

from evalos.benchmarks.models import BenchmarkRun
from evalos.observability.tracer import Trace


@dataclass
class AppState:
    last_trace: Trace | None = None
    last_benchmark: BenchmarkRun | None = None


state = AppState()
