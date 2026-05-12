from __future__ import annotations

import asyncio

import typer

from evalos.pipeline import Pipeline

app = typer.Typer(add_completion=False)


@app.command()
def run(query: str, optimize_for: list[str] = typer.Option(..., "--optimize-for")) -> None:
    """Run EvalOS pipeline once."""

    async def _run() -> None:
        pipeline = Pipeline(model="gpt-4o-mini")
        response = await pipeline.generate(query=query, optimize_for=optimize_for)
        typer.echo(response.text)

    asyncio.run(_run())
