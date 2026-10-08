---
title: Hosted admin login (Vercel)
description: "Email + password sign-in for the read-only admin console on a hosted deployment such as Vercel."
---

# Hosted admin login (Vercel)

The [admin console](index.md) normally admits only loopback clients (local mode) or Entra
`MCP.Admin` users (enterprise mode). Neither exists on a plain Vercel deployment, so a third
**password** mode serves the same console at `/admin` behind an email + password sign-in.

It is **read-only**: saving settings and Stop always return 403. Change settings through
environment variables or `uml-mcp.yaml`.

## Environment variables

Set these in the **Vercel project** (Settings → Environment Variables, or
`vercel env add <NAME> production`), then redeploy.

| Variable | Notes |
| --- | --- |
| `ADMIN_EMAIL` | Sign-in email (case-insensitive) |
| `ADMIN_PASSWORD_HASH` | Preferred. `scrypt$N$r$p$salt$hash` from `python -m mcp_core.admin.password_auth hash` |
| `ADMIN_PASSWORD` | Plain fallback; logs a warning. Ignored when the hash is set |
| `ADMIN_SESSION_SECRET` | Required, at least 32 characters. `python -m mcp_core.admin.password_auth session-secret` |
| `ADMIN_SESSION_TTL_SECONDS` | Optional. Default `3600`, between `60` and `43200` |

!!! warning "GitHub secrets do not reach Vercel"
    Vercel deploys through its Git integration, so repository secrets are only visible to
    GitHub Actions. The same values must also be added to the Vercel project.

If the email, a password or a valid session secret is missing, `/admin` returns **404**
(fail closed). The server log names the missing variable, never a value.

## What protects it

- Passwords are checked with scrypt in constant time; a wrong email and a wrong password are
  indistinguishable.
- Sessions are stateless HMAC-signed cookies (`HttpOnly`, `Secure` on Vercel,
  `SameSite=Strict`, `Path=/admin`). Rotating the email or password signs everyone out.
- Cross-site form posts are refused using `Sec-Fetch-Site`, with `Origin` as a fallback.
- Five failed sign-ins within 15 minutes lock that client out (HTTP 429, `Retry-After`).
  Vercel overwrites `x-forwarded-for` / `x-real-ip`, so those identify the client there.
  The counter is **per process**: on serverless each instance counts separately, so also add a
  Vercel WAF rate-limit rule on `POST /admin/login`.
- The login page has no JavaScript and a strict CSP; every admin response is `no-store`.

## Rotating credentials

1. Generate a new hash and session secret with the commands above.
2. Update the Vercel variables and redeploy. Existing sessions stop working immediately.
