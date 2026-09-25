---
title: Enterprise auth configuration
description: "All MCP_AUTH_* environment variables and the JSON config file (MCP_AUTH_CONFIG_FILE)."
---

# Configuration reference

Settings come from **defaults**, then the **JSON file** (`MCP_AUTH_CONFIG_FILE`, for
example a Kubernetes ConfigMap), then **environment variables**. Each layer
overrides the previous one.

- Lists accept a JSON array or CSV.
- Secrets are only accepted from env vars or `*_FILE` paths. A secret value inside
  the JSON file is rejected.
- An invalid configuration **stops the process** (fail closed).

## Core

| Variable | JSON key | Default | Description |
| --- | --- | --- | --- |
| `MCP_AUTH_MODE` | `mode` | `none` | `none`, `jwt` or `entra-proxy` |
| `MCP_AUTH_CONFIG_FILE` | – | – | Path to the JSON file |
| `MCP_AUTH_RESOURCE_URL` | `resource_url` | – | **Required.** The exact URL clients use, for example `https://mcp.contoso.com/mcp`. HTTPS is required; `http://127.0.0.1`/`localhost` is allowed for development. |
| `MCP_AUTH_PROTECT_REST` | `protect_rest` | `true` | Also protect `/generate_diagram`, `/kroki_encode` and `/ag-ui/*` |
| `MCP_AUTH_PREFLIGHT` | `preflight` | `warn` | Startup check of IdP metadata (PKCE S256) and JWKS: `warn`, `strict` (fail startup) or `off` |
| `MCP_ADMIN_UI` | `admin_ui` | `false` | Read-only console at `/admin` |

## Tokens

| Variable | JSON key | Default | Description |
| --- | --- | --- | --- |
| `MCP_AUTH_ALGORITHMS` | `algorithms` | `RS256` | Allowed JWS algorithms: RS/PS/ES 256/384/512 or EdDSA. `none`/HS* are rejected |
| `MCP_AUTH_ISSUERS` | `issuers` | Entra-derived | Trusted `iss` values (generic OIDC) |
| `MCP_AUTH_AUDIENCES` | `audiences` | Entra-derived + resource URL | Accepted `aud` values |
| `MCP_AUTH_JWKS_URI` | `jwks_uri` | Entra-derived | JWKS endpoint (HTTPS) |
| `MCP_AUTH_PUBLIC_KEY[_FILE]` | `public_key_file` | – | Static PEM key instead of JWKS |
| `MCP_AUTH_AUTHORIZATION_SERVERS` | `authorization_servers` | Entra v2 authority / first issuer | Advertised in the resource metadata |
| `MCP_AUTH_LEEWAY_SECONDS` | `leeway_seconds` | `60` | Clock skew (max 300) |
| `MCP_AUTH_JWKS_CACHE_SECONDS` | `jwks_cache_seconds` | `3600` | JWKS TTL |
| `MCP_AUTH_TOKEN_TYPE` | `token_type` | – | Require a JWT `typ` value, for example `at+jwt` (RFC 9068) |
| `MCP_AUTH_ALLOWED_CLIENT_IDS` | `allowed_client_ids` | any | Allow-list for `azp` / `appid` |
| `MCP_AUTH_ALLOWED_TENANTS` | `allowed_tenants` | the tenant | Multi-tenant allow-list |
| `MCP_AUTH_MAX_BODY_BYTES` | `max_body_bytes` | `max(1 MiB, 3×MCP_MAX_CODE_LENGTH)` | Body limit when classifying requests from read-only callers |

## Scopes and roles

| Variable | JSON key | Default | Description |
| --- | --- | --- | --- |
| `MCP_AUTH_READ_SCOPE` / `MCP_AUTH_WRITE_SCOPE` | `read_scope` / `write_scope` | `mcp.read` / `mcp.write` | Scope names |
| `MCP_AUTH_SCOPE_PREFIX` | `scope_prefix` | `api://<client-id>/` (Entra, `jwt`) | Prefix used when advertising scopes |
| `MCP_AUTH_SCOPE_STRATEGY` | `scope_strategy` | `granular` | `default` advertises `api://<client-id>/.default` |
| `MCP_AUTH_ADVERTISE_OFFLINE_ACCESS` | `advertise_offline_access` | `false` | SEP-2207: `offline_access` belongs to the authorization server; enable only for legacy clients |
| `MCP_AUTH_ROLES_CLAIM` | `roles_claim` | `roles` | Claim that carries roles |
| `MCP_AUTH_READER_ROLES` / `…_WRITER_ROLES` / `…_ADMIN_ROLES` | `reader_roles` … | see [architecture](architecture.md#permissions) | Role → permission mapping |
| `MCP_AUTH_REQUIRE_USER_ROLES` | `require_user_roles` | `false` | Delegated tokens also need a matching role (per-group RBAC) |
| `MCP_AUTH_TOOL_PERMISSIONS` | `tool_permissions` | from `readOnlyHint` | JSON map, for example `{"validate_uml": "read"}` |
| `MCP_AUTH_METHOD_PERMISSIONS` | `method_permissions` | built-in list | JSON map for JSON-RPC methods |

## Entra ID

| Variable | JSON key (`entra.*`) | Default |
| --- | --- | --- |
| `MCP_AUTH_ENTRA_TENANT_ID` | `tenant_id` | – |
| `MCP_AUTH_ENTRA_CLIENT_ID` | `client_id` | – |
| `MCP_AUTH_ENTRA_APP_ID_URI` | `app_id_uri` | `api://<client-id>` |
| `MCP_AUTH_ENTRA_CLOUD` | `cloud` | `public` (`usgov`, `china`) |
| `MCP_AUTH_ENTRA_TOKEN_VERSIONS` | `token_versions` | `2` (use `1,2` to also accept v1) |
| `MCP_AUTH_ENTRA_JWKS_APPID` | `jwks_appid` | `false` |

## entra-proxy

| Variable | JSON key (`proxy.*`) | Default |
| --- | --- | --- |
| `MCP_AUTH_ENTRA_CLIENT_SECRET[_FILE]` | `client_secret_file` | – |
| `MCP_AUTH_ENTRA_CLIENT_CERTIFICATE[_FILE]` + `MCP_AUTH_ENTRA_CLIENT_PRIVATE_KEY[_FILE]` | `client_certificate_file`, `client_private_key_file` | – |
| `AZURE_FEDERATED_TOKEN_FILE` | – | set by AKS workload identity |
| `MCP_AUTH_PROXY_ENCRYPTION_KEYS[_FILE]` | `encryption_keys_file` | – (`kid:base64url32`, comma separated, newest first) |
| `MCP_AUTH_PROXY_ALLOWED_REDIRECT_URIS` | `allowed_redirect_uris` | vscode.dev and loopback built in |
| `MCP_AUTH_PROXY_REFRESH_TOKENS` | `refresh_tokens` | `true` |
| `MCP_AUTH_PROXY_REFRESH_TOKEN_MAX_AGE_DAYS` | `refresh_token_max_age_days` | `7` |
| `MCP_AUTH_PROXY_CODE_TTL_SECONDS` | `code_ttl_seconds` | `60` |

## Example JSON file

```json
{
  "mode": "jwt",
  "resource_url": "https://mcp.contoso.com/mcp",
  "algorithms": ["RS256"],
  "entra": {"tenant_id": "<tenant-id>", "client_id": "<api-client-id>", "token_versions": ["2"]},
  "allowed_client_ids": ["aebc6443-996d-45c2-90f0-388ff96faa56", "04f0c124-f2bc-4f59-8241-bf6df9866bbd"],
  "scope_strategy": "granular",
  "tool_permissions": {"validate_uml": "read"}
}
```

A generic OIDC provider (Keycloak) needs no `entra` block:

```bash
MCP_AUTH_MODE=jwt
MCP_AUTH_RESOURCE_URL=https://mcp.example.com/mcp
MCP_AUTH_ISSUERS=https://sso.example.com/realms/acme
MCP_AUTH_JWKS_URI=https://sso.example.com/realms/acme/protocol/openid-connect/certs
MCP_AUTH_AUDIENCES=https://mcp.example.com/mcp
```

!!! warning "Run the ASGI app"
    Enterprise auth lives in `app.py`. Use `uvicorn app:app` (the Docker image and Helm
    chart do).
    - `python server.py --transport http` refuses to start when `MCP_AUTH_MODE` is set.
    - `fastmcp run … --transport http` bypasses `app.py` and must **not** be used for
      protected deployments.
    - Vercel refuses too, because its static metadata would shadow the live document.
