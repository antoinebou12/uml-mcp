---
title: Enterprise auth troubleshooting
description: "401/403 reason codes and common Microsoft Entra ID (AADSTS) errors with UML-MCP."
---

# Troubleshooting

## Reason codes

Every auth error body is JSON:
`{"error", "error_description", "reason", "status", "request_id", …}`.

| Status | `reason` | Meaning / fix |
| --- | --- | --- |
| 401 | `token_missing` | Send `Authorization: Bearer <token>` (see `missing` and `resource_metadata`) |
| 401 | `unsupported_auth_scheme` | Only `Bearer` is accepted |
| 400 | `token_in_query` | Tokens must never be in the URL |
| 400 | `multiple_authorization_headers`, `token_too_large` | Send exactly one header, under 16 KiB |
| 401 | `malformed_token` | Not a JWT (opaque tokens aren't supported) |
| 401 | `unsupported_algorithm` | `alg` is not in `MCP_AUTH_ALGORITHMS` |
| 401 | `forbidden_header` | The token carries `jku`/`x5u`/`jwk`/`crit` |
| 401 | `missing_kid`, `unknown_signing_key` | Key not in the JWKS (wrong tenant, or custom signing keys → `MCP_AUTH_ENTRA_JWKS_APPID`) |
| 401 | `invalid_signature` | Forged or corrupted token |
| 401 | `token_expired`, `token_not_yet_valid` | Check clocks (NTP); leeway is 60 s |
| 401 | `invalid_issuer` | Wrong tenant, v1 token (`sts.windows.net`), or iss/tid mismatch |
| 401 | `invalid_audience` | Token for another API (often Microsoft Graph); request `api://<client-id>/mcp.read` |
| 401 | `token_version_not_allowed` | Set `requestedAccessTokenVersion: 2` on the app |
| 401 | `tenant_not_allowed`, `client_not_allowed` | Allow-lists |
| 401 | `id_token_not_accepted` | Send the access token, not the ID token |
| 403 | `insufficient_scope` | Needs `mcp.write` (or an app role); the client should step up |
| 503 | `jwks_unavailable` | Egress to `login.microsoftonline.com` is blocked or the IdP is down |

## Common Entra errors

| Error | Cause | Fix |
| --- | --- | --- |
| AADSTS9010010 | The client sent RFC 8707 `resource` that differs from the scopes' resource | Use `entra-proxy`, or make the App ID URI equal to the MCP URL |
| AADSTS65001 | Consent missing | Pre-authorize the client, or grant admin consent |
| AADSTS50011 | Redirect URI mismatch | Add `/oauth/callback` (web) or loopback (desktop) to the app |
| AADSTS500011 | Resource principal not found | Wrong App ID URI or tenant |
| AADSTS700016 | Application not found in tenant | Wrong client ID or tenant |
| AADSTS54005 | Authorization code already redeemed | The client retried `/oauth/token`; sign in again |

## Checks

- `curl -i -X POST <resource>` must return **401** with `resource_metadata`. A 200
  means auth is off; a 421 means the host isn't allowed (set `MCP_ALLOWED_HOSTS`).
- `kubectl logs` shows `auth preflight …` lines at startup.
- The admin console's token tester shows exactly which check failed.
