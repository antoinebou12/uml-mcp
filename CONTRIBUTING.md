# Contributing to UML-MCP

Thank you for considering contributing. This document explains how to set up your environment, run tests, and submit changes.

## Code of conduct

By participating, you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting started

### Prerequisites

- Python 3.12 (matches `requires-python` in `pyproject.toml`)
- [uv](https://docs.astral.sh/uv/), [Poetry](https://python-poetry.org/), or pip

### Development setup

1. Fork and clone the repo:

   ```bash
   git clone https://github.com/YOUR_USERNAME/uml-mcp.git
   cd uml-mcp
   ```

2. Create a virtual environment and install dependencies (including dev):

   **With uv (recommended):**
   ```bash
   uv sync --all-groups
   ```

   **With Poetry:**
   ```bash
   poetry install --with dev
   ```

   **With pip:**
   ```bash
   pip install -e ".[dev]"
   # or: pip install -e . -r requirements-dev.txt
   ```

3. (Optional) Install pre-commit hooks so lint/format run before each commit:

   ```bash
   uv run pre-commit install
   # or: poetry run pre-commit install
   ```

## Development workflow

### Running the server

From the project root:

```bash
python server.py
# or: uv run python server.py
# or: poetry run python server.py
```

### Running tests

```bash
uv run pytest
# or: poetry run pytest
# or: pytest
```

With coverage:

```bash
uv run pytest --cov=mcp_core --cov=tools --cov-report=term-missing
```

### Linting and formatting

- **Lint:** `uv run ruff check .` (use `--fix` for auto-fixes).
- **Format:** `uv run ruff format .` (or use pre-commit for both).
- **Type check:** `uv run ty check` (optional, gradual adoption).

Make sure tests and lint pass before opening a pull request.

## Pull requests

1. Create a branch from `main`: `git checkout -b fix/short-description` or `feature/short-description`.
2. Make your changes; keep commits focused and messages clear.
3. Run tests and lint (see above).
4. Push to your fork and open a PR using the [pull request template](.github/PULL_REQUEST_TEMPLATE.md).
5. Fill in the checklist in the template (tests, docs, style).
6. Address review feedback; we may ask for small edits.

## Reporting issues

- **Bugs:** Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).
- **Features:** Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md).

Include OS, Python version, and how you run the server when relevant.

## Security

See [SECURITY.md](SECURITY.md) for how to report vulnerabilities.

## Maintaining `requirements.txt` (Vercel / pip)

Production dependencies for Vercel and `pip install -r requirements.txt` are exported from the lockfile:

```bash
uv lock
uv export --no-dev --no-hashes -o requirements.txt
```

Run this after changing runtime dependencies in `pyproject.toml` / `uv.lock`, then commit the updated `requirements.txt`.

**Transitive pins:** Some packages are pinned only in `[tool.uv] override-dependencies` in `pyproject.toml` (they are not direct Poetry deps). Dependabot is configured for the `uv` ecosystem so PRs target `uv.lock` consistently. After merging a dependency PR, re-export `requirements.txt` if the lockfile changed so CI’s “export matches `requirements.txt`” step stays green.

## Documentation

- User-facing docs are under `docs/` (e.g. MkDocs).
- Update `docs/` and README when changing behavior or configuration.

Thanks for contributing.
