from __future__ import annotations

import sys
from pathlib import Path
import pytest

from evalos.benchmarks.models import BenchmarkConfig, BenchmarkRun


def test_core_package_import():
    import evalos

    assert evalos is not None


def test_api_app_import_and_init():
    from evalos.api.app import app

    assert app.title == "EvalOS API"


def test_benchmarks_package_import_without_matplotlib():
    import evalos.benchmarks

    assert evalos.benchmarks is not None


def test_render_charts_raises_clear_importerror_without_matplotlib(monkeypatch):
    from evalos.benchmarks.charts import render_charts

    # Ensure matplotlib import fails
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", None)

    run = BenchmarkRun(
        config=BenchmarkConfig(model="m", provider="p"),
        cases=[],
        results=[],
    )

    with pytest.raises(ImportError) as exc_info:
        render_charts(Path("."), run)

    assert "The 'matplotlib' package is required to render benchmark charts" in str(exc_info.value)
    assert "pip install 'evalos[bench]'" in str(exc_info.value)

