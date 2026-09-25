---
title: Enterprise SSO (Entra ID / OAuth 2.1)
description: "Protect a self-hosted UML-MCP with Microsoft Entra ID or any OAuth 2.1 / OpenID Connect provider: RFC 9728 metadata, clear 401/403/404, Docker and Helm."
tags:
  - enterprise
  - security
  - entra-id
---

# Enterprise SSO for UML-MCP

UML-MCP can require **OAuth 2.1 bearer tokens** on its Streamable HTTP endpoint
(`/mcp`) and REST API. Tokens come from **Microsoft Entra ID** (first-class) or any
OAuth 2.1 / OpenID Connect provider (Keycloak, Okta, Auth0, …). It is **opt-in**:
the public endpoint `https://uml-mcp.vercel.app/mcp` stays open, and
`MCP_AUTH_MODE` defaults to `none`.

!!! tip "Five-minute path"
    1. Register the API in Entra: `python -m mcp_core.auth generate az-script > register.sh && bash register.sh`
       ([details](entra-id.md)).
    2. Deploy with Helm: `--set auth.mode=jwt --set auth.resourceUrl=https://mcp.contoso.com/mcp`
       plus tenant and client IDs ([Kubernetes](kubernetes.md)).
    3. Add `https://mcp.contoso.com/mcp` in VS Code / Copilot. The first call returns
       **401** and the client signs you in automatically ([clients](clients.md)).

## Pick a mode

| Mode | What the server does | Use it when |
| --- | --- | --- |
| `none` (default) | No authentication | Public or trusted-network deployments, Vercel |
| `jwt` | Validates Entra / OIDC access tokens (JWKS, RS256) and publishes RFC 9728 metadata pointing to your IdP | VS Code / GitHub Copilot, Visual Studio, and clients with a pre-registered client ID |
| `entra-proxy` | Everything in `jwt`, **plus** an OAuth authorization-server facade: RFC 8414 metadata, RFC 7591 dynamic registration, **S256-only PKCE**, consent page | Claude Code, Cursor and other clients that need dynamic client registration (Entra has none) |

## Client support

| Client | `jwt` | `entra-proxy` |
| --- | --- | --- |
| VS Code / GitHub Copilot | ✅ (VS Code client ID pre-authorized) | ✅ |
| Visual Studio | ✅ (pre-authorized) | ✅ |
| Claude Code | ⚠️ only with `--client-id` and an App ID URI equal to the MCP URL | ✅ |
| Cursor | ❌ (needs DCR) | ✅ |
| Copilot cloud agent (github.com) | ❌ no interactive sign-in: use an internal no-auth endpoint | ❌ |

## Status codes (the contract)

| Status | Meaning | Response |
| --- | --- | --- |
| **401** | No token, or the token is invalid, expired or for another service | `WWW-Authenticate: Bearer resource_metadata="…", scope="…"`, plus a JSON `reason` and a `missing` hint |
| **403** | Valid token, but not enough permission (for example, a read-only token calling `generate_uml`) | `WWW-Authenticate: Bearer error="insufficient_scope", scope="…"`; the client steps up |
| **404** | The route does not exist or the feature is disabled (admin console, proxy endpoints) | FastAPI default; never an auth challenge |
| **405** | Wrong HTTP method (for example `POST` on metadata, or `GET /mcp` in stateless mode) | `Allow` header |
| **400** | Malformed request: token in the query string, duplicate headers, ambiguous JSON | `error="invalid_request"` |
| **503** | IdP signing keys unreachable and not cached (fail closed) | `Retry-After` |

The exact reason codes are listed in [troubleshooting](troubleshooting.md#reason-codes).

## Read more

- [Architecture](architecture.md): how the pieces fit, with sequence diagrams
- [OAuth 2.1, OpenID Connect and MSAL](oauth-oidc.md): concepts, token types, MSAL examples, the three ways around Entra's gaps
- [Readiness checklist](checklist.md): tick every line before announcing the URL
- [Microsoft Entra ID setup](entra-id.md): Expose an API, scopes, v2 tokens, pre-authorized clients
- [Configuration reference](configuration.md): env vars and the JSON file
- [Client setup](clients.md): VS Code, Copilot, Visual Studio, Claude Code, Cursor
- [Kubernetes (Helm)](kubernetes.md) and [Docker](../deploy/docker.md#enterprise-sso-optional)
- [Admin console](admin-ui.md), [Security model](security.md), [Troubleshooting](troubleshooting.md)
