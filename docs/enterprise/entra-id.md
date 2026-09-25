---
title: Microsoft Entra ID setup
description: "Register UML-MCP in Entra ID: Expose an API, mcp.read / mcp.write / .default scopes, v2 tokens, app roles, pre-authorized VS Code and Visual Studio."
---

# Microsoft Entra ID setup

You create **one app registration** that represents the UML-MCP API. It exposes
scopes, issues **v2 access tokens**, and pre-authorizes VS Code and Visual Studio so
users are not asked to consent.

## Fastest path: generated script

```bash
# from a clone (uv) or any environment with uml-mcp installed
python -m mcp_core.auth generate az-script --mode jwt > register.sh      # or --mode entra-proxy
az login --tenant <tenant-id>
bash register.sh   # prints MCP_AUTH_ENTRA_CLIENT_ID / MCP_AUTH_ENTRA_TENANT_ID
```

The same content is committed as
[`deploy/entra/register-app.sh`](https://github.com/antoinebou12/uml-mcp/blob/main/deploy/entra/register-app.sh)
and the Graph body as
[`deploy/entra/app-registration.json`](https://github.com/antoinebou12/uml-mcp/blob/main/deploy/entra/app-registration.json).

## Portal steps (what the script does)

1. **App registrations → New registration**: name `UML-MCP`, *Accounts in this
   organizational directory only*.
2. **Manifest**: set `"requestedAccessTokenVersion": 2` (older manifest editor:
   `accessTokenAcceptedVersion: 2`). UML-MCP accepts **only v2 tokens** by default:
   the `ver` claim must be `2.0` and the issuer `https://login.microsoftonline.com/<tid>/v2.0`.
3. **Expose an API**:
    - Application ID URI: `api://<client-id>` (default).
    - Add scope `mcp.read`: *Read UML-MCP catalog and validate diagrams* (admins and users).
    - Add scope `mcp.write`: *Generate diagrams* (admins and users).
    - `.default`: clients may request `api://<client-id>/.default` to receive every
      consented scope. Set `MCP_AUTH_SCOPE_STRATEGY=default` to advertise it.
4. **Authorized client applications** (pre-authorization, no consent prompt).
   Select both scopes for each:

    | Client | Client ID |
    | --- | --- |
    | Visual Studio Code (GitHub Copilot) | `aebc6443-996d-45c2-90f0-388ff96faa56` |
    | Visual Studio | `04f0c124-f2bc-4f59-8241-bf6df9866bbd` |
    | Azure CLI (optional, admin tokens) | `04b07795-8ddb-461a-bbee-02f9e1bf7b46` |

5. **App roles** (for RBAC and app-only access):

    | Value | Allowed member types | Grants |
    | --- | --- | --- |
    | `MCP.Reader` | Users/Groups | read |
    | `MCP.Writer` | Users/Groups | read + write |
    | `MCP.Admin` | Users/Groups | admin console |
    | `MCP.Read.All` | Applications | read (client credentials) |
    | `MCP.Write.All` | Applications | read + write (client credentials) |

6. **Enterprise applications → UML-MCP → Properties → Assignment required = Yes**.
   Then assign users and groups to the roles. With `MCP_AUTH_REQUIRE_USER_ROLES=true`,
   a delegated token needs both the scope **and** a role.
7. **Token configuration → Add optional claim → Access → `idtyp`**. This lets the server
   distinguish app-only tokens.

## Redirect URIs

| Mode | Where | Redirect URI |
| --- | --- | --- |
| `jwt` | none needed for VS Code / Visual Studio | they use their own first-party registrations |
| `jwt` + your own public client (Claude Code `--client-id`) | *Mobile and desktop* platform | `http://localhost` and `http://127.0.0.1` (Entra ignores the loopback port, RFC 8252) |
| `entra-proxy` | *Web* platform on the API app | `https://mcp.contoso.com/oauth/callback` |

In `entra-proxy` mode the client-side redirect URIs are validated by UML-MCP, not by
Entra. By default it accepts:

- `https://vscode.dev/redirect` and `https://insiders.vscode.dev/redirect`
- `http://127.0.0.1`, `http://localhost` and `http://[::1]` on any port

Add others, such as `cursor://anysphere.cursor-mcp/oauth/callback`, with
`MCP_AUTH_PROXY_ALLOWED_REDIRECT_URIS`. Custom schemes are outside the MCP
"localhost or HTTPS" rule, so only add them deliberately.

## Credentials for `entra-proxy`

The proxy is a confidential client. In order of preference:

1. **AKS workload identity** (no secret): Helm `workloadIdentity.enabled=true`, plus a
   federated credential on the app for `system:serviceaccount:<ns>:<sa>`.
2. **Certificate** (`private_key_jwt`): `MCP_AUTH_ENTRA_CLIENT_CERTIFICATE[_FILE]` +
   `MCP_AUTH_ENTRA_CLIENT_PRIVATE_KEY[_FILE]`.
3. **Client secret**: `MCP_AUTH_ENTRA_CLIENT_SECRET[_FILE]` (rotate regularly).

Generate the sealing key with `python -m mcp_core.auth keygen --kid k1` and store it in
the Kubernetes secret (`proxy-encryption-keys`).

## Server configuration

```bash
MCP_AUTH_MODE=jwt                                 # or entra-proxy
MCP_AUTH_RESOURCE_URL=https://mcp.contoso.com/mcp
MCP_AUTH_ENTRA_TENANT_ID=<tenant-id>
MCP_AUTH_ENTRA_CLIENT_ID=<api-client-id>
# optional hardening
MCP_AUTH_ALLOWED_CLIENT_IDS=aebc6443-996d-45c2-90f0-388ff96faa56,04f0c124-f2bc-4f59-8241-bf6df9866bbd
```

Derived automatically:

- **Issuer:** `https://login.microsoftonline.com/<tid>/v2.0`
- **JWKS:** `…/<tid>/discovery/v2.0/keys`
- **Audiences:** `<client-id>` (v2 `aud`), `api://<client-id>`, and the resource URL
- **Scopes:** advertised as `api://<client-id>/mcp.read …`

## Sovereign clouds and multi-tenant apps

- `MCP_AUTH_ENTRA_CLOUD=usgov` (`login.microsoftonline.us`) or `china`
  (`login.chinacloudapi.cn`).
- Multi-tenant: set `MCP_AUTH_ENTRA_TENANT_ID=organizations` **and**
  `MCP_AUTH_ALLOWED_TENANTS=<tid1>,<tid2>`. Each token's issuer must match its own `tid`.
- Apps with custom signing keys (claims mapping): `MCP_AUTH_ENTRA_JWKS_APPID=true`.
