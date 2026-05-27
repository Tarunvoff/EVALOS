from __future__ import annotations

import asyncio

import typer

from evalos.benchmarks.models import BenchmarkConfig
from evalos.benchmarks.runner import BenchmarkRunner, replay

app = typer.Typer(add_completion=False)


@app.command()
def run(
    model: str = typer.Option("llama3:latest", "--model"),
    provider: str = typer.Option("litellm", "--provider"),
    strategies: list[str] = typer.Option(
        ["vanilla", "retry", "best_of_n", "evalos"], "--strategy"
    ),
    seed: int = typer.Option(42, "--seed"),
    best_of_n: int = typer.Option(3, "--best-of-n"),
    retry_attempts: int = typer.Option(2, "--retry-attempts"),
    max_repairs: int = typer.Option(2, "--max-repairs"),
    output_dir: str = typer.Option("benchmarks/reports", "--output-dir"),
) -> None:
    config = BenchmarkConfig(
        model=model,
        provider=provider,
        seed=seed,
        best_of_n=best_of_n,
        retry_attempts=retry_attempts,
        max_repairs=max_repairs,
        output_dir=output_dir,
    )

    async def _run() -> None:
        runner = BenchmarkRunner(config)
        await runner.run(strategies=strategies)

    asyncio.run(_run())


@app.command()
def replay_run(path: str = typer.Option(..., "--run")) -> None:
    replay(path)
