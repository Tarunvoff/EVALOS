# Contributing

Thanks for helping make EvalOS reliable and observable.

## Setup

```bash
python -m venv .venv
# bash:
# . .venv/bin/activate
# PowerShell:
# .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Lint and Tests

```bash
python -m pytest
```

## Guidelines

- Keep changes focused and documented.
- Add or update tests for new behavior.
- Prefer deterministic fixtures.
