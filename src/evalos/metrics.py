from __future__ import annotations

def timer() -> float:
import time


class Timer:
    def __init__(self) -> None:
        self.start = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        end = time.perf_counter()
        self.elapsed_ms = (end - self.start) * 1000.0
