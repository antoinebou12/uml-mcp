---
title: Enterprise auth architecture
description: "How UML-MCP validates tokens, separates 401/403/404, publishes RFC 9728 metadata and brokers Entra ID sign-in statelessly."
---

# Architecture

Enterprise auth is a small, **pure-ASGI layer** (`mcp_core/auth/`) in front of the
existing FastAPI app. It isn't FastMCP's built-in auth: that version cannot return
per-tool HTTP 403 responses, does not require `exp` or check `nbf`, ignores Entra
`roles`/`appid`, and its OAuth proxy needs shared storage.

## Components

```mermaid
flowchart LR
  subgraph Clients
    VSC[VS Code / Copilot]
    VS[Visual Studio]
    CC[Claude Code]
    CUR[Cursor]
  end
  subgraph Pod["uml-mcp pod (stateless, N replicas)"]
    direction TB
    MW["AuthMiddleware<br/>mcp_core/auth/mcp_auth.py"]
    PRM["/.well-known/oauth-protected-resource[/mcp]<br/>RFC 9728"]
    AS["/oauth/* + RFC 8414 metadata<br/>(entra-proxy only)"]
    MCP["FastMCP /mcp"]
    REST["REST /generate_diagram, /kroki_encode, /ag-ui/*"]
    ADM["/admin (read-only)"]
  end
  ENTRA[(Microsoft Entra ID)]
  KROKI[(Kroki)]
  Clients -->|HTTPS + Bearer| MW
  MW --> MCP & REST & ADM
  Clients --> PRM & AS
  MW -. "JWKS (cached)" .-> ENTRA
  AS -- "code + PKCE S256" --> ENTRA
  MCP --> KROKI
```

The request passes the middlewares in this order:
`RequestId/RateLimit → Accept → Origin → CORS → AuthMiddleware → router`.
Auth sits inside CORS, so 401/403 responses carry CORS headers and preflights never
need a token. It sits after the Origin (DNS-rebinding) check.

## Decision flow for a protected request

```mermaid
flowchart TD
  A[Request] --> B{Protected path?<br/>/mcp, /admin/api, protected REST}
  B -- no --> R[Router: 200 / 404 / 405]
  B -- yes --> C{OPTIONS?}
  C -- yes --> R
  C -- no --> D{Token in query / 2 headers?}
  D -- yes --> E400[400 invalid_request]
  D -- no --> F{Authorization: Bearer?}
  F -- no --> E401a[401 + resource_metadata + scope]
  F -- yes --> G{Token valid?<br/>alg, kid, sig, iss, aud, exp, tid, ver}
  G -- IdP down --> E503[503 Retry-After]
  G -- no --> E401b[401 error=invalid_token + reason]
  G -- yes --> H{Permission for method / tool?}
  H -- no --> E403[403 insufficient_scope + scope]
  H -- yes --> I[Strip Authorization, attach principal] --> R
```

## `jwt` mode: VS Code / Copilot with Entra ID

```mermaid
sequenceDiagram
  participant C as VS Code (Copilot)
  participant M as uml-mcp
  participant E as Entra ID
  C->>M: POST /mcp (no token)
  M-->>C: 401 WWW-Authenticate: Bearer resource_metadata=".../oauth-protected-resource/mcp", scope="api://app/mcp.read api://app/mcp.write"
  C->>M: GET /.well-known/oauth-protected-resource/mcp
  M-->>C: {resource, authorization_servers:[login.microsoftonline.com/<tid>/v2.0], scopes_supported}
  C->>E: Sign in (VS Code client aebc6443-…, pre-authorized) PKCE S256
  E-->>C: v2 access token (aud = API client ID, scp = "mcp.read mcp.write")
  C->>M: POST /mcp Authorization: Bearer …
  M->>E: GET JWKS (cached)
  M-->>C: 200 (Authorization stripped before FastMCP)
```

## `entra-proxy` mode: Claude Code, Cursor

```mermaid
sequenceDiagram
  participant C as Claude Code
  participant M as uml-mcp (AS facade)
  participant B as Browser
  participant E as Entra ID
  C->>M: POST /mcp → 401 (resource_metadata)
  C->>M: GET PRM → authorization_servers: [https://mcp.contoso.com]
  C->>M: GET /.well-known/oauth-authorization-server (S256 only, registration_endpoint)
  C->>M: POST /oauth/register {redirect_uris:[http://localhost:PORT/callback]}
  M-->>C: 201 {client_id: sealed}
  C->>B: open /oauth/authorize?code_challenge=…&code_challenge_method=S256&resource=…/mcp
  B->>M: consent page (CSRF-bound, frame-ancestors 'none')
  B->>E: authorize (our client ID, our PKCE S256, no resource param)
  E-->>B: redirect /oauth/callback?code
  B->>M: callback → seal {Entra code, our verifier}
  M-->>B: redirect http://localhost:PORT/callback?code=sealed&state&iss
  C->>M: POST /oauth/token (code_verifier)
  M->>E: redeem Entra code (secret / certificate / workload identity)
  E-->>M: access token (aud = API) + refresh token
  M-->>C: access token + sealed refresh token
  C->>M: POST /mcp Bearer → validated exactly like jwt mode
```

**Stateless by design.** Client IDs, transactions, authorization codes and refresh
tokens are AES-256-GCM sealed blobs:

- A per-purpose HKDF key and an AAD bound to purpose, key ID and issuer, so a client ID
  can never pass as a code.
- Keys come from `MCP_AUTH_PROXY_ENCRYPTION_KEYS` and rotate with the first key used to
  encrypt.
- Any replica can finish any flow. Single use of codes is enforced by Entra
  (AADSTS54005), not by a local cache.

## Token validation pipeline

Cheap local checks run before any network call, and nothing is accepted without
full verification:

1. size ≤ 16 KiB, three segments, JSON header and payload
2. `alg` in the allow-list (default `RS256`; `none` and `HS*` are impossible to configure);
   `jku`/`x5u`/`jwk`/`crit` headers are rejected
3. unverified `iss` ∈ trusted issuers, `aud` ∈ accepted audiences, `exp` present
   and not expired. This produces precise 401 reasons and costs no JWKS fetch.
4. key by `kid` from the JWKS cache: 1 h TTL, refetch on unknown `kid` at most once
   per 60 s, stale-if-error for 24 h
5. `jwt.decode` (signature, `exp`/`nbf` with 60 s leeway, `iss`, `aud`)
6. Entra rules:
   - `tid` is a GUID and matches `iss`
   - tenant allow-list
   - `ver == "2.0"` (v1 is opt-in)
   - signing-key issuer check
   - `azp`/`appid` allow-list
   - ID tokens (`nonce`) rejected
7. permissions from `scp` (delegated) or `roles` (app-only), per Microsoft guidance

## Permissions

| Permission | Delegated scope | App role | Needed for |
| --- | --- | --- | --- |
| read | `mcp.read` (or `mcp.write`) | MCP.Reader, MCP.Read.All | `tools/list`, resources, prompts, `validate_uml`, `list_diagram_types`, `/kroki_encode` |
| write | `mcp.write` | MCP.Writer, MCP.Write.All | `generate_uml`, `generate_uml_batch`, `generate_uml_image`, `/generate_diagram`, AG-UI; unknown tools/methods (fail safe) |
| admin | none | MCP.Admin | `/admin/api/*` |

Tool classes come from each tool's `readOnlyHint` annotation. Admins can override them
with `tool_permissions`.

## Standards map

| Standard | Where |
| --- | --- |
| RFC 6750 (Bearer) | `WWW-Authenticate`, `invalid_request` / `invalid_token` / `insufficient_scope`, header-only tokens |
| RFC 9728 (Protected Resource Metadata) | `/.well-known/oauth-protected-resource[/mcp]`, `resource_metadata` challenge |
| RFC 8414 (AS Metadata) | `/.well-known/oauth-authorization-server` (entra-proxy) |
| RFC 7591 (Dynamic Client Registration) | `POST /oauth/register` (entra-proxy) |
| RFC 7636 (PKCE) | S256 required; `plain` refused |
| RFC 8707 (Resource Indicators) | `resource` validated against the MCP URL; audience binding; never forwarded to Entra |
| RFC 8252 (Native apps) | Loopback redirects on any port |
| RFC 9207 (`iss` in responses) | Every authorization redirect |
| RFC 9068 (JWT access tokens) | Optional `typ` check (`MCP_AUTH_TOKEN_TYPE=at+jwt`) |
| MCP 2025-11-25 authorization, SEP-2207 | Discovery, step-up 403, no token passthrough, `offline_access` not advertised in the resource metadata |
