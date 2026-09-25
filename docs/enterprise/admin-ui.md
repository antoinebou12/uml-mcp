---
title: Admin console
description: "Read-only UML-MCP enterprise auth console: effective config, IdP health, recent denials, token tester and generators."
---

# Admin console (read-only)

Enable it with `MCP_ADMIN_UI=true` (Helm: `admin.enabled=true`). It is served at
`/admin` and returns 404 when disabled.

- **Who:** users with the Entra app role **`MCP.Admin`**. The API returns 401 without
  a token and 403 without the role.
- **Sign-in:**
  - `entra-proxy` mode: the **Sign in (SSO)** button uses PKCE S256 through the
    server's facade.
  - `jwt` mode: paste an access token, for example
    `az account get-access-token --scope api://<client-id>/mcp.read --query accessToken -o tsv`.
- **What you see:**
  - effective configuration with secrets redacted
  - preflight result (PKCE S256 advertised? JWKS reachable?)
  - signing-key health
  - the client support matrix
  - the last 401/403 decisions on this replica (reason, client, tenant; never tokens)
- **Token tester:** paste any token to see which check fails, for example
  `invalid_audience` for a Microsoft Graph token. The token is never stored or echoed.
- **Generators:** Entra app manifest, `az` script, Helm values, and VS Code, Visual
  Studio, Cursor and Claude Code configs. The same generators are available as a CLI:
  `python -m mcp_core.auth generate <kind>`.

The console is intentionally **read-only**. Configuration changes go through env
vars and the ConfigMap (GitOps), so every change is reviewed and versioned.
