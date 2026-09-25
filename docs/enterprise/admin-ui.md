---
title: Admin console
description: "Read-only UML-MCP admin dashboard: activity/audit, metrics, rate limits, effective configuration, lint, tools, clients, token tester and generators."
---

# Admin console (enterprise)

!!! info "Full tour"
    The console (pages, screenshots, local mode, Stop) is documented in
    **[Admin console](../admin/index.md)**. This page covers the enterprise specifics:
    sign-in, the `MCP.Admin` role, and the opt-in write access
    (`admin.allow_write`, `admin.allow_stop`).

Enable it with `MCP_ADMIN_UI=true` (Helm: `admin.enabled=true`; YAML: `auth.admin_ui: true`).
It is served at `/admin` and returns 404 when disabled.

- **Who:** users with the Entra app role **`MCP.Admin`**. The API returns 401 without
  a token and 403 without the role.
- **Sign-in:**
  - `entra-proxy` mode: the **Sign in (SSO)** button uses PKCE S256 through the
    server's facade.
  - `jwt` mode: paste an access token, for example
    `az account get-access-token --scope api://<client-id>/mcp.read --query accessToken -o tsv`.

## Tabs

| Tab | Shows | API |
| --- | --- | --- |
| **Overview** | Version, mode, uptime, preflight (PKCE S256 advertised? JWKS reachable?), signing-key health, metadata | `/admin/api/overview` |
| **Activity** | Audit trail with filters (status, decision, operation, user, time), paging, and **JSONL export** | `/admin/api/audit`, `/admin/api/audit/export` |
| **Metrics** | Calls, error rate, denials, p50/p95 per tool, resource and prompt; top denial reasons; sink errors | `/admin/api/metrics` (Prometheus: `/metrics`) |
| **Rate limits** | Effective policy, the busiest buckets (keys hashed), 429 counts per scope | `/admin/api/rate-limits` |
| **Configuration** | Effective `uml-mcp.yaml` sections with the **source** of each value (default, file, env), redacted auth settings, and a **download `uml-mcp.yaml`** button (generate only; never applied) | `/admin/api/config`, `/admin/api/config/download` |
| **Lint** | `uml-mcp lint` results for tools, prompts, resources and config | `/admin/api/lint` |
| **Tools** | Enabled/disabled, read/write classification, annotations, per-tool rate limit | `/admin/api/tools` |
| **Clients** | Support matrix and generated configs | `/admin/api/overview` |
| **Token tester** | Paste any token to see which check fails, e.g. `invalid_audience` for a Microsoft Graph token; never stored or echoed | `POST /admin/api/token-check` |
| **Generators** | Entra app manifest, `az` script, Helm values, VS Code, Visual Studio, Cursor, Claude Code configs (CLI: `python -m mcp_core.auth generate <kind>`) | `/admin/api/generate/{kind}` |

Activity, Metrics and Rate limits are **per replica**, because they are in-memory.
Use your SIEM and Prometheus for the fleet-wide view ([Operations](operations.md)).
Turn the audit trail on with `audit.enabled: true` and the `memory` sink in
[`uml-mcp.yaml`](../configuration/uml-mcp-yaml.md).

## Local mode (no SSO)

For a single-user or lab install without enterprise auth, set
`admin.allow_local_without_auth: true`. The same dashboard is then served at
`http://127.0.0.1:8000/admin`, but **only to loopback socket peers**. Any other
client gets 404, and `X-Forwarded-For` is never trusted for this check. The
setting is ignored while auth is enabled.

## Read-only by design

The console never changes the running server. Configuration changes go through
`uml-mcp.yaml`, env vars and the ConfigMap (GitOps), so every change is reviewed
and versioned.
