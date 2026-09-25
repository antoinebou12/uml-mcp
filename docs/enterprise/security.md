---
title: Enterprise auth security model
description: "Threat model, guarantees and known limitations of UML-MCP enterprise authentication."
---

# Security model

## Guarantees

- **No token passthrough.** The `Authorization` header is removed before the request
  reaches FastMCP or the REST handlers. Kroki and PlantUML never see client tokens.
- **Audience binding (RFC 8707).** A token must be issued for this API (client ID,
  App ID URI or resource URL). Tokens for Microsoft Graph or other APIs get 401
  `invalid_audience`.
- **Algorithm safety.** An explicit asymmetric allow-list (default RS256). `alg=none`,
  HS\* key confusion and `jku`/`x5u`/`jwk`/`crit` headers are rejected, and the key
  type must match the algorithm.
- **Entra rules:**
  - v2 tokens only by default
  - `tid`/`iss` binding
  - tenant allow-list
  - signing-key issuer check
  - optional client (`azp`) allow-list
  - ID tokens (`nonce`) rejected
- **Fail closed.**
  - Invalid configuration stops the process.
  - An unreachable IdP returns 503.
  - `server.py --transport http` and Vercel refuse to run with auth.
- **Header-only bearer tokens.** A token in the query string gets 400. Access-log query
  strings are redacted, and the Helm chart disables access logs.
- **Step-up, not over-grant.** Read-only tools need `mcp.read` and generation needs
  `mcp.write`. Unknown tools and methods default to write.
- **Proxy hardening:**
  - PKCE **S256 only**
  - exact redirect URI allow-list (vscode.dev and loopback by default)
  - invalid client or redirect → error page, never an open redirect
  - consent on every authorization, with CSRF protection (cookie, sealed token and
    Origin checks) and `frame-ancestors 'none'`
  - a callback binding cookie
  - `iss` in every response (RFC 9207)
  - the `resource` value validated and never forwarded

## Limitations

- **Refresh-token reuse is not detectable.** Sealed refresh tokens are stateless.
  They are bound to the client, have an absolute lifetime (default 7 days), and Entra
  re-evaluates Conditional Access on every refresh. Set
  `MCP_AUTH_PROXY_REFRESH_TOKENS=false` to disable them.
- **Some state is per replica:** the audit log, the rate limiter and the AG-UI
  start/events run store. Prefer `POST /ag-ui/generate` behind a load balancer.
- **Per-tool, not per-list.** `tools/list` shows every tool; a disallowed call gets 403.
- **Not implemented:** Client ID Metadata Documents and RFC 7662 introspection of
  opaque tokens.
