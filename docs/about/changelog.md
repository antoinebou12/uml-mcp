---
title: Changelog
description: How to find release notes and tagged versions of UML-MCP.
---

# Changelog

Release notes and tagged versions live on GitHub:

- [GitHub Releases](https://github.com/antoinebou12/uml-mcp/releases): full notes per tag.
- [Compare across tags](https://github.com/antoinebou12/uml-mcp/compare): diff between any two versions.
- [Commit history](https://github.com/antoinebou12/uml-mcp/commits/main): full commit history on `main`.

!!! tip "Subscribe"

    Use GitHub's "Watch → Custom → Releases" to get an email or notification on every release.

## 1.4.0

- Optional enterprise SSO for HTTP deployments: `MCP_AUTH_MODE=jwt` (Entra ID / OIDC token validation) and `entra-proxy` (RFC 8414 / 7591 facade with S256-only PKCE). Includes RFC 9728 metadata, strict 401/403/404 separation and a read-only admin console. See [Enterprise](../enterprise/README.md).
- Helm chart (`deploy/helm/uml-mcp`), Entra app-registration templates, `docker-compose.enterprise.yml`.
- GitHub Copilot custom agent (`.github/agents`), skill mirror and `SOUL.md`.
- One configuration file, [`uml-mcp.yaml`](../configuration/uml-mcp-yaml.md) (defaults < file < env), plus `uml-mcp config init|show|validate|path` with `local` / `docker` / `enterprise` profiles and a Helm `config:` value.
- MXCP-style [audit trail](../enterprise/operations.md) for every tool, resource, prompt and REST call (user, session, policy decision/reason, duration, redacted inputs), with sinks for a rotating JSONL file, stdout and the dashboard. Also configurable logging (JSON, rotation), in-process metrics and an optional Prometheus `/metrics`.
- Configurable rate limiting: token buckets per IP or principal, route and per-tool limits, trusted proxies, failed-auth throttling and `RateLimit-*` headers.
- `uml-mcp lint` ([rules](../developers/linting.md)), run in CI with `--strict`.
- Local install path: `uml-mcp client install --client vscode|cursor|claude-desktop|claude-code` ([guide](../installation.md)).
- Admin dashboard tabs: Activity (filters, JSONL export), Metrics, Rate limits, Configuration (sources, YAML download), Lint and Tools. A loopback-only local mode is also available.
- Admin console rebuilt with React/Vite/shadcn: setup form, schema-driven settings with save/reset/live apply, live logs, charts, Stop, dark/light, mobile layout ([tour](../admin/index.md)).
- `uml-mcp setup` wizard (Typer + tqdm), `uml-mcp admin`, and `scripts/install.py` (Python + typer + tqdm only) ([installation](../installation.md)).
- Plugins v1: extra MCP tools and diagram renderers via entry points ([plugins](../plugins/index.md)).
- `uml-mcp lint` grades servers like `mcpx` (score, grade, token budget); optional OpenTelemetry tracing.
- `uml-mcp lint` scores 100/100 with extended MCP rules (SEP-986 names, titles, hints, output schemas, server instructions) and documented exceptions (`lint_ignore`, `--ignore`).
- Fixed `uml://examples` / `uml://templates` sources that real Kroki rejected (erd, symbolator, wireviz, bytefield, structurizr) and the Structurizr docs example. Every example, template and docs diagram is now rendered through a real Kroki in CI ([testing](../testing.md)).

## Versioning

UML-MCP follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: breaking change to the MCP tool surface or HTTP API.
- **MINOR**: new tools, resources, prompts, diagram types, or backwards-compatible behavior.
- **PATCH**: bug fixes, docs, performance.

The current package version is set in [`pyproject.toml`](https://github.com/antoinebou12/uml-mcp/blob/main/pyproject.toml). The `uml://server-info` resource exposes the running server's version at runtime.
