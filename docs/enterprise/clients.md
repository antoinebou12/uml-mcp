---
title: Connecting clients to a protected UML-MCP
description: "VS Code / GitHub Copilot, Visual Studio, Claude Code and Cursor against an Entra-protected UML-MCP."
---

# Client setup

Every client starts the same way. The first request gets **401** with
`WWW-Authenticate: Bearer resource_metadata="…"`. The client reads the protected
resource metadata and signs you in. Use the exact `MCP_AUTH_RESOURCE_URL`
(`…/mcp`, no trailing slash).

## VS Code / GitHub Copilot

```json
{
  "servers": {
    "uml-mcp": { "type": "http", "url": "https://mcp.contoso.com/mcp" }
  }
}
```

Template: [`config/vscode_mcp_enterprise.json`](https://github.com/antoinebou12/uml-mcp/blob/main/config/vscode_mcp_enterprise.json).

- `jwt` mode: VS Code recognizes Entra and signs in with its own client
  (`aebc6443-996d-45c2-90f0-388ff96faa56`), which must be **pre-authorized** on the
  API (see [Entra setup](entra-id.md)).
- `entra-proxy` mode: VS Code registers dynamically with the `vscode.dev` or loopback
  redirect and uses PKCE S256.
- On a 403 `insufficient_scope`, VS Code asks you to grant the additional scope (step-up).
- Accounts → *Manage Dynamic Authentication Providers* removes stale registrations.

## Visual Studio

Add the same `servers` entry to `.mcp.json` in the solution folder, or use
[`config/visualstudio_mcp_enterprise.json`](https://github.com/antoinebou12/uml-mcp/blob/main/config/visualstudio_mcp_enterprise.json).
Visual Studio (`04f0c124-f2bc-4f59-8241-bf6df9866bbd`) must be pre-authorized.

## Claude Code

`entra-proxy` (recommended):

```bash
claude mcp add --transport http uml-mcp https://mcp.contoso.com/mcp
```

Claude Code discovers the facade, registers dynamically, opens the browser and
completes PKCE S256 on a loopback redirect.

`jwt` mode only works with a pre-registered public client **and** an Entra App ID URI
equal to the MCP URL. Claude Code sends the RFC 8707 `resource`, which Entra
otherwise rejects with AADSTS9010010:

```bash
claude mcp add --transport http --client-id <public-client-id> --callback-port 8765 \
  uml-mcp https://mcp.contoso.com/mcp
```

## Cursor

```json
{ "mcpServers": { "uml-mcp": { "url": "https://mcp.contoso.com/mcp" } } }
```

Cursor needs dynamic registration, so use **`entra-proxy`**. Current versions use a
loopback redirect, which is allowed by default. Older builds use
`cursor://anysphere.cursor-mcp/oauth/callback`; add it to
`MCP_AUTH_PROXY_ALLOWED_REDIRECT_URIS` if needed.

## GitHub Copilot cloud agent

The custom agent [`.github/agents/uml-mcp.agent.md`](https://github.com/antoinebou12/uml-mcp/blob/main/.github/agents/uml-mcp.agent.md)
runs on github.com without an interactive browser. Point it at the public endpoint or
an internal endpoint without authentication.

## Check it with curl

```bash
curl -i -X POST https://mcp.contoso.com/mcp                        # 401 + WWW-Authenticate
curl -s https://mcp.contoso.com/.well-known/oauth-protected-resource/mcp | jq
TOKEN=$(az account get-access-token --scope api://<client-id>/mcp.read --query accessToken -o tsv)
curl -s -X POST https://mcp.contoso.com/mcp -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'                 # 200
```

The `az` command requires the Azure CLI to be pre-authorized (generator flag
`--preauthorize-azure-cli`).
