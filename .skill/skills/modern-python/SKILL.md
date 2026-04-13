---
name: modern-python
description: Modern Python tooling and best practices using uv, ruff, ty, and pytest. Covers project setup with pyproject.toml (PEP 735), src layout, linting/formatting with ruff, type checking with ty, testing with pytest and coverage, pre-commit with prek, and security (pip-audit, detect-secrets, actionlint). Use when setting up or working on Python projects, replacing pip/virtualenv with uv, replacing flake8/black/mypy with ruff/ty, adding pre-commit or security scanning, or when the user mentions uv, ruff, ty, pytest, or cookiecutter-python patterns.
---

# Modern Python

Modern Python tooling and practices: uv for dependencies, ruff for lint/format, ty for type checking, pytest for tests. Use for this project and when setting up or refactoring Python codebases.

## When to Use

- Setting up or changing Python project structure and tooling
- Replacing pip/virtualenv with uv
- Replacing flake8/black/isort with ruff, or mypy with ty
- Adding pre-commit hooks and security scanning
- Writing or reviewing tests with pytest and coverage

## Legacy Command Guidance

Prefer **uv** over raw `python`/`pip`. When about to run legacy commands, use:

| Legacy command | Use instead |
|----------------|-------------|
| `python` | `uv run python` |
| `python script.py` | `uv run script.py` |
| `pip install pkg` | `uv add pkg` or `uv run --with pkg` |
| `pip uninstall pkg` | `uv remove pkg` |
| `pip freeze` | `uv export` |
| `python -m pip install` | `uv add` / `uv sync` |

Commands that already use `uv run` (e.g. `uv run pytest`) do not need changing.

## Project Structure and pyproject.toml

- **Layout**: Prefer a `src/` layout (package under `src/<package_name>/`). This project uses top-level packages (`mcp_core`, `tools`); when adding new packages, keep them at repo root or under a clear namespace.
- **Config**: Single `pyproject.toml` at repo root.
- **Python**: This repo targets Python 3.12 only (`requires-python` in `pyproject.toml`).
- **Dependency groups** (PEP 735): Put dev/test/lint deps in dependency groups where the tool supports them.

## Linting and Formatting (ruff)

- Use **ruff** for both linting and formatting (replaces flake8, black, isort, pyupgrade).
- Configure in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.format]`.

Run:

- `uv run ruff check .`
- `uv run ruff format .`

Fix auto-fixable issues: `uv run ruff check --fix .`

## Type Checking (ty)

- Use **ty** instead of mypy/pyright for faster type checking when introducing it.
- Configure in `pyproject.toml` under `[tool.ty]` if needed.

Run: `uv run ty check`

## Unit Testing (pytest)

- Use **pytest** for all tests; prefer it over unittest for new code.
- **Layout**: `tests/` at repo root; use `conftest.py` for shared fixtures.
- **Coverage**: Use `pytest-cov`. Enforce a minimum coverage threshold so CI fails when coverage drops.

Run:

- `uv run pytest`
- `uv run pytest --cov=mcp_core --cov=tools --cov-report=term-missing`
- `uv run pytest -v tests/`

**Good practices:**

- Use `@pytest.fixture` for setup/teardown and shared state.
- Use `@pytest.mark.parametrize` for multiple inputs/outputs.
- Prefer descriptive test names and clear assertion messages.
- Keep tests fast; use mocks for I/O or external services when appropriate.

## Pre-commit and Security

- Use **prek** or **pre-commit** for hooks (ruff, ty, pytest, detect-secrets).
- **Dependencies**: Run `uv run pip-audit` or use in CI.
- **Secrets**: Use **detect-secrets** in pre-commit or CI.
- **GitHub Actions**: Use **actionlint** for workflow syntax.

## Quick Checklist

- [ ] Project uses `pyproject.toml` with clear `requires-python` and dependency groups
- [ ] Dependencies managed with uv where possible; avoid bare `pip install` in instructions
- [ ] Lint/format with ruff; type check with ty or mypy as configured
- [ ] Tests with pytest; coverage enforced in config or CI
- [ ] Pre-commit runs lint, format, and tests where appropriate
- [ ] Security: pip-audit, detect-secrets; optional actionlint, Dependabot
