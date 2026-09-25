---
title: Production readiness checklist
description: "Checklist before announcing a protected UML-MCP URL, mapped to where UML-MCP implements each item."
---

# Checklist before saying "it's ready"

| Area | Check | UML-MCP |
| --- | --- | --- |
| Architecture | MCP is served by the API itself, with no intermediate service or token exchange | ✅ same FastAPI app, `jwt` mode |
| Architecture | No endpoint of your server issues tokens: you validate, the directory issues | ✅ in `jwt`; ⚠️ `entra-proxy` is an opt-in facade |
| Architecture | No incoming `Authorization` header is forwarded to another service | ✅ stripped after validation (tested) |
| Architecture | No client secret needed | ✅ in `jwt` mode |
| Discovery | A call without a token returns 401 with `WWW-Authenticate` including `resource_metadata` and `scope` | ✅ |
| Discovery | Protected resource metadata is served unauthenticated, with a canonical URI without a trailing slash | ✅ `resource` = `MCP_AUTH_RESOURCE_URL` |
| Discovery | The metadata `resource` and the audience required by the code are the same value | ✅ the resource URL is always an accepted audience |
| Discovery | `offline_access` doesn't appear in the advertised scopes | ✅ default (SEP-2207) |
| Validation | Signature algorithm is hard-coded (allow-list), never read from the token header | ✅ `MCP_AUTH_ALGORITHMS` |
| Validation | Signature checked against the directory's public keys, with caching and rotation | ✅ JWKS cache, refetch on new `kid` |
| Validation | Issuer and audience checked explicitly; a token for another service is refused, **and this is tested** | ✅ `invalid_audience` tests (Graph token) |
| Validation | Insufficient scope → 403 `insufficient_scope` with all missing scopes at once | ✅ `scope` = required ∪ granted |
| Validation | No token in the logs; the refusal reason is logged, not the token material | ✅ audit ring buffer, query redaction |
| Validation | Scopes are granular (read / write), not a single global right | ✅ `mcp.read` / `mcp.write` |
| Entra ID | `requestedAccessTokenVersion: 2` in the API manifest | ✅ generator, `ver == 2.0` enforced |
| Entra ID | Delegated scopes exposed, and MCP clients pre-authorized on them | ✅ VS Code and Visual Studio in the generated manifest |
| Entra ID | Client redirect URIs declared exactly, under the right platform type | ✅ documented; loopback and vscode.dev only by default |
| Entra ID | The flow has been tested end to end with **each** of the team's clients (Copilot and Claude Code behave differently) | ☐ your tenant; see [clients](clients.md) and the smoke-test prompt |
| Entra ID | If a directory limitation forces a facade, it comes from a proven implementation, not home-grown OAuth code | ⚠️ `entra-proxy` is built in and tested; prefer pre-authorized clients or an existing gateway where possible |

**In one sentence:** serve MCP **from** your API, publish **two HTTP responses** that say
where to authenticate, validate **the audience** of every token, and sharing becomes
just a URL.
