---
title: OAuth 2.1, OpenID Connect and MSAL primer
description: "How OAuth 2.1, OpenID Connect, Microsoft Entra ID and MSAL fit together for a protected UML-MCP server."
---

# OAuth 2.1, OpenID Connect and MSAL

UML-MCP is an **OAuth 2.1 resource server**. It never logs anyone in by itself (in
`jwt` mode). It only **validates access tokens** that an authorization server
issued for it.

| Concept | Role in UML-MCP |
| --- | --- |
| **OAuth 2.1** (authorization) | Clients obtain an *access token* with Authorization Code + **PKCE S256** and send it as `Authorization: Bearer …` on every request. |
| **OpenID Connect** (authentication) | A layer on top of OAuth that adds the *ID token* and discovery (`/.well-known/openid-configuration`). UML-MCP uses OIDC discovery and the JWKS for **signature keys**, but **rejects ID tokens** (`id_token_not_accepted`). Only access tokens are accepted. |
| **Microsoft Entra ID** | The authorization server (and OpenID provider). It issues v2 access tokens for your API with `aud` = API client ID, `scp` for delegated access, and `roles` for app-only access. |
| **MSAL** ([Microsoft Authentication Library](https://learn.microsoft.com/en-us/entra/identity-platform/msal-overview)) | The client-side library that acquires tokens: VS Code, Visual Studio and the Azure CLI all use MSAL. **The server doesn't need MSAL.** Validating a token only needs the JWKS and the rules below. |
| **RFC 9728** protected resource metadata | How an MCP client learns *which* authorization server and scopes to use, starting from a 401. |

## Which token for which caller?

| Caller | OAuth flow | Token contents | UML-MCP permission |
| --- | --- | --- | --- |
| Developer in VS Code / Copilot, Visual Studio | Authorization Code + PKCE (MSAL, pre-authorized client) | `scp: "mcp.read mcp.write"` | read / write |
| Claude Code, Cursor | Authorization Code + PKCE through `entra-proxy` (DCR) | same as above | read / write |
| CI job, daemon, agent service | Client credentials (`scope=api://<id>/.default`) | `roles: ["MCP.Write.All"]`, no `scp` | per role |
| Admin | Any of the above, and the user has the `MCP.Admin` role | `roles: ["MCP.Admin"]` | admin console |

## Getting tokens with MSAL (examples)

```python
# pip install msal — app-only (daemon) token for UML-MCP
import msal

app = msal.ConfidentialClientApplication(
    client_id="<daemon-client-id>",
    authority="https://login.microsoftonline.com/<tenant-id>",
    client_credential="<secret or certificate>",
)
result = app.acquire_token_for_client(scopes=["api://<api-client-id>/.default"])
token = result["access_token"]  # send as Authorization: Bearer <token>
```

```bash
# Developer token for testing (Azure CLI is an MSAL client; pre-authorize it first)
az account get-access-token --scope api://<api-client-id>/mcp.read --query accessToken -o tsv
```

Ready-to-run requests (discovery, 401, client credentials, 403, DCR) are in
[`tests/http/entra-auth.http`](https://github.com/antoinebou12/uml-mcp/blob/main/tests/http/entra-auth.http)
for the VS Code REST Client or the JetBrains HTTP client.

## The three conflicts with Entra, and the three ways out

Entra ID diverges from the MCP authorization spec in three places:

1. no Dynamic Client Registration
2. no `code_challenge_methods_supported` in its discovery document
3. it rejects the RFC 8707 `resource` parameter that MCP clients send (AADSTS9010010)

| Path | How | When |
| --- | --- | --- |
| **Pre-authorized clients** (`jwt`) | Expose scopes, pre-authorize the organization's MCP clients (VS Code, Visual Studio). No proxy, no secret, no DCR. | **Recommended for production.** This is Microsoft's own recommendation. |
| **Client-side bridge** | Users connect through a local stdio auth bridge that omits `resource`. The server stays a pure resource server. | When a single client misbehaves and can't be pre-authorized |
| **Registration facade** (`entra-proxy`) | UML-MCP exposes RFC 8414/7591 endpoints and brokers the login with its own confidential credential | Clients that require DCR (Claude Code, Cursor). Keep it opt-in; prefer a proven gateway if your organization already runs one. |

## Libraries and references

- MSAL overview: <https://learn.microsoft.com/en-us/entra/identity-platform/msal-overview>
- Access token claims and validation: <https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens>
- Protected web API, scopes and app roles: <https://learn.microsoft.com/en-us/entra/identity-platform/scenario-protected-web-api-verification-scope-app-roles>
- [fastapi-azure-auth](https://github.com/vibber-ai/fastapi-azure-auth): a proven Entra ID resource-server library for FastAPI. It is a good fit if you protect other FastAPI services the same way. UML-MCP applies the same rules (v2 issuer, tenant/audience checks, scopes and roles) in its own ASGI layer, so it can return MCP-specific 401/403 challenges.
- MCP authorization specification (2025-11-25) and SEP-2207 (refresh tokens / `offline_access`)
- RFC 6749/6750 (OAuth 2.0 / Bearer), OAuth 2.1 draft, RFC 7636 (PKCE), RFC 8414, RFC 7591, RFC 8707, RFC 9728, RFC 9207, OpenID Connect Core and Discovery 1.0
