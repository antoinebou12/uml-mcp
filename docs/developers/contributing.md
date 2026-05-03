---
title: Contributing
description: How to set up a dev environment and contribute changes to UML-MCP.
---

# Contributing

Thanks for your interest in improving UML-MCP. The full guidelines live in the repo root; this page summarises the most useful entry points.

| Document | Why |
| --- | --- |
| [`CONTRIBUTING.md`](https://github.com/antoinebou12/uml-mcp/blob/main/CONTRIBUTING.md) | Local setup, branching model, commit and PR conventions. |
| [`CODE_OF_CONDUCT.md`](https://github.com/antoinebou12/uml-mcp/blob/main/CODE_OF_CONDUCT.md) | Community expectations. |
| [`SECURITY.md`](https://github.com/antoinebou12/uml-mcp/blob/main/SECURITY.md) | How to responsibly report a security issue. |

## Quick setup

```bash
git clone https://github.com/antoinebou12/uml-mcp.git
cd uml-mcp
uv sync --all-groups
uv run pre-commit install   # if pre-commit hooks are available
uv run pytest tests/ -v
```

## Pull request checklist

- [ ] Tests pass (`uv run pytest tests/ -v`).
- [ ] Lint clean (`uv run ruff check .` and `uv run ruff format --check .`).
- [ ] Public-facing changes are reflected in the docs (`docs/`).
- [ ] If you touched MCP tools/resources/prompts, the [Reference](../reference/index.md) section still matches reality.
- [ ] If you added an env var, update [Configuration](../configuration.md).

## Reporting issues

- Bug reports: open a [GitHub issue](https://github.com/antoinebou12/uml-mcp/issues/new) with reproduction steps.
- Security: see [`SECURITY.md`](https://github.com/antoinebou12/uml-mcp/blob/main/SECURITY.md). Do **not** post details in a public issue.
- Feature requests: an issue with use case and an example call goes a long way.

!!! tip "Working on docs only?"

    Run `uv run mkdocs serve` and edit pages live; rebuilds are typically sub-second. The [Deploy docs workflow](https://github.com/antoinebou12/uml-mcp/blob/main/.github/workflows/docs.yml) publishes to GitHub Pages on every push to `main`.
