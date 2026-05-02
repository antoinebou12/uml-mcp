## Learned User Preferences

- Pin `astral-sh/setup-uv` in GitHub Actions to a full release tag (for example `v8.1.0`) or an explicit commit SHA; do not use a bare `@v8` ref, because that action is not published as a floating major tag and Actions fails to resolve it.

## Learned Workspace Facts

- Python dependencies and the lockfile are driven by `uv` (`pyproject.toml`, `uv.lock`); after constraint changes, expect `uv lock` / `uv sync` and CI parity with `uv lock --check` where applicable.
- Multi-version Python work in this repo has treated 3.12 as the primary baseline while also exercising 3.14 in CI matrices when supported; widening `requires-python` and regenerating the lock goes with that pattern.
