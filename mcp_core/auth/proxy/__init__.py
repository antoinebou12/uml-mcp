"""``entra-proxy``: a stateless OAuth 2.1 authorization-server facade over Entra ID.

Why: Entra ID has no Dynamic Client Registration (RFC 7591), does not advertise
``code_challenge_methods_supported`` (MCP clients must then refuse it) and
rejects the RFC 8707 ``resource`` value MCP clients send. This facade exposes
RFC 8414 metadata + RFC 7591 registration, **requires PKCE S256**, validates
``resource`` locally and brokers the login to Entra with its own confidential
credential. All state is sealed (see :mod:`mcp_core.auth.sealing`).
"""

from __future__ import annotations

import hmac
import html
import secrets
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ..errors import AuthError
from ..sealing import SealError
from .redirects import is_loopback, redirect_allowed, redirect_matches
from .upstream import UpstreamError, pkce_challenge

if TYPE_CHECKING:  # pragma: no cover
    from ..integration import AuthRuntime

ADMIN_CLIENT_ID = "uml-mcp-admin"
_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}
_ERROR_CODES = frozenset(
    {
        "invalid_request",
        "access_denied",
        "unsupported_response_type",
        "invalid_scope",
        "server_error",
        "temporarily_unavailable",
        "invalid_target",
        "login_required",
        "consent_required",
        "interaction_required",
    }
)
CLIENT_TTL = 365 * 86400


def _oauth_error(error: str, description: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        {"error": error, "error_description": description},
        status_code=status,
        headers=_NO_STORE,
    )


def _page_headers(runtime: AuthRuntime, authority_origin: str = "") -> dict[str, str]:
    form_action = "'self'" + (f" {authority_origin}" if authority_origin else "")
    return {
        **_NO_STORE,
        "Content-Security-Policy": (
            "default-src 'none'; style-src 'unsafe-inline'; "
            f"form-action {form_action}; frame-ancestors 'none'; base-uri 'none'"
        ),
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }


def _html_page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>"
        "body{font-family:system-ui,sans-serif;max-width:560px;margin:3rem auto;"
        "padding:0 1rem;line-height:1.5;color:#1f2328}"
        ".card{border:1px solid #d0d7de;border-radius:12px;padding:1.5rem}"
        ".warn{background:#fff8c5;padding:.5rem .75rem;border-radius:8px}"
        "button{font-size:1rem;padding:.5rem 1.25rem;margin-right:.5rem;border-radius:8px;"
        "border:1px solid #d0d7de;cursor:pointer}.primary{background:#1f6feb;color:#fff}"
        "code{background:#f6f8fa;padding:0 .25rem;border-radius:4px}"
        "@media (prefers-color-scheme:dark){body{background:#0d1117;color:#e6edf3}"
        ".card{border-color:#30363d}code{background:#161b22}.warn{background:#3b2e00}}"
        f"</style></head><body><div class='card'>{body}</div></body></html>"
    )


def _error_page(runtime: AuthRuntime, message: str, status: int = 400) -> HTMLResponse:
    body = (
        "<h1>Authorization request rejected</h1>"
        f"<p>{html.escape(message)}</p>"
        "<p>The request was not redirected back to the client because the client "
        "or its redirect URI could not be verified.</p>"
    )
    return HTMLResponse(
        _html_page("Authorization error", body),
        status_code=status,
        headers=_page_headers(runtime),
    )


def _redirect_to_client(
    redirect_uri: str, params: dict[str, Any], iss: str
) -> RedirectResponse:
    clean = {k: str(v) for k, v in params.items() if v is not None}
    clean["iss"] = iss  # RFC 9207 on success *and* error
    sep = "&" if urlsplit(redirect_uri).query else "?"
    return RedirectResponse(
        f"{redirect_uri}{sep}{urlencode(clean)}", status_code=303, headers=_NO_STORE
    )


def build_proxy_router(runtime: AuthRuntime) -> APIRouter:
    router = APIRouter(include_in_schema=False)
    settings = runtime.settings
    sealer = runtime.sealer
    upstream = runtime.upstream
    assert sealer is not None and upstream is not None
    issuer = settings.origin
    short_read, short_write = settings.read_scope, settings.write_scope
    supported_short = [short_read, short_write]
    prefixes = [
        p
        for p in {settings.upstream_scope_prefix, settings.effective_scope_prefix}
        if p
    ]
    allowed_resources = {
        settings.resource_url.rstrip("/"),
        settings.origin,
        settings.root_resource,
    }
    extra_redirects = tuple(settings.proxy.allowed_redirect_uris)
    secure_cookie = urlsplit(settings.origin).scheme == "https"

    def lookup_client(client_id: str) -> dict[str, Any] | None:
        if client_id == ADMIN_CLIENT_ID and settings.admin_ui:
            return {
                "client_name": "UML-MCP admin console",
                "redirect_uris": [f"{issuer}/admin/"],
            }
        try:
            return sealer.unseal("client", client_id)
        except SealError:
            return None

    def normalize_scopes(raw: str | None) -> list[str] | None:
        if not raw:
            return list(supported_short)
        out: list[str] = []
        for item in raw.split():
            if item in ("offline_access", "openid", "profile", "email"):
                continue
            for prefix in prefixes:
                if item.startswith(prefix):
                    item = item[len(prefix) :]
                    break
            if item == ".default":
                return list(supported_short)
            if item not in supported_short:
                return None
            if item not in out:
                out.append(item)
        if short_write in out and short_read not in out:
            out.insert(0, short_read)
        return out or list(supported_short)

    def cookie_kwargs() -> dict[str, Any]:
        return {"httponly": True, "secure": secure_cookie, "path": "/"}

    cookie_tx = "__Host-uml_tx" if secure_cookie else "uml_tx"
    cookie_cb = "__Host-uml_cb" if secure_cookie else "uml_cb"

    # ----------------------------------------------------------- RFC 7591 DCR
    @router.post("/oauth/register")
    async def register(request: Request) -> Response:
        if "application/json" not in request.headers.get("content-type", ""):
            return _oauth_error(
                "invalid_client_metadata", "Content-Type must be application/json"
            )
        try:
            meta = await request.json()
        except ValueError:
            return _oauth_error("invalid_client_metadata", "body is not JSON")
        if not isinstance(meta, dict):
            return _oauth_error("invalid_client_metadata", "body must be a JSON object")
        uris = meta.get("redirect_uris")
        if not isinstance(uris, list) or not uris or len(uris) > 10:
            return _oauth_error(
                "invalid_redirect_uri", "redirect_uris must be a non-empty list"
            )
        bad = [u for u in uris if not redirect_allowed(u, extra_redirects)]
        if bad:
            return _oauth_error(
                "invalid_redirect_uri",
                "redirect URIs must be loopback (http://127.0.0.1, http://localhost, "
                "http://[::1] on any port), https://vscode.dev/redirect, or an "
                f"admin-approved URI; rejected: {str(bad[0])[:200]}",
            )
        method = meta.get("token_endpoint_auth_method", "none")
        if method != "none":
            return _oauth_error(
                "invalid_client_metadata",
                "only public clients (token_endpoint_auth_method=none) with PKCE are supported",
            )
        grants = meta.get("grant_types", ["authorization_code"])
        allowed_grants = {"authorization_code", "refresh_token"}
        if not isinstance(grants, list) or not set(grants) <= allowed_grants:
            return _oauth_error("invalid_client_metadata", "unsupported grant_types")
        rtypes = meta.get("response_types", ["code"])
        if rtypes != ["code"]:
            return _oauth_error(
                "invalid_client_metadata", "response_types must be ['code']"
            )
        name = str(meta.get("client_name") or "MCP client")[:120]
        now = int(time.time())
        client_id = sealer.seal(
            "client",
            {"client_name": name, "redirect_uris": uris, "iat": now},
            CLIENT_TTL,
        )
        body = {
            "client_id": client_id,
            "client_id_issued_at": now,
            "client_name": name,
            "redirect_uris": uris,
            "grant_types": grants,
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }
        return JSONResponse(body, status_code=201, headers=_NO_STORE)

    # ------------------------------------------------------------- authorize
    @router.get("/oauth/authorize")
    async def authorize(request: Request) -> Response:
        q = request.query_params
        client_id = q.get("client_id", "")
        redirect_uri = q.get("redirect_uri", "")
        client = lookup_client(client_id) if client_id else None
        if client is None:
            return _error_page(runtime, "Unknown or invalid client_id.")
        registered = client.get("redirect_uris") or []
        if not redirect_uri and len(registered) == 1:
            redirect_uri = registered[0]
        if not any(redirect_matches(redirect_uri, r) for r in registered):
            return _error_page(
                runtime, "redirect_uri is not registered for this client."
            )
        if client_id != ADMIN_CLIENT_ID and not redirect_allowed(
            redirect_uri, extra_redirects
        ):
            return _error_page(runtime, "redirect_uri is not allowed by this server.")
        state = q.get("state")

        def fail(error: str, desc: str) -> Response:
            return _redirect_to_client(
                redirect_uri,
                {"error": error, "error_description": desc, "state": state},
                issuer,
            )

        if q.get("request") or q.get("request_uri"):
            return fail("request_not_supported", "request objects are not supported")
        if q.get("response_type") != "code":
            return fail("unsupported_response_type", "response_type must be 'code'")
        challenge = q.get("code_challenge")
        method = q.get("code_challenge_method")
        if not challenge:
            return fail(
                "invalid_request", "PKCE is required: send code_challenge (S256)"
            )
        if method != "S256":
            return fail(
                "invalid_request",
                "Only code_challenge_method=S256 is supported (plain is refused)",
            )
        if len(challenge) != 43 or any(
            c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            for c in challenge
        ):
            return fail(
                "invalid_request", "code_challenge must be a base64url SHA-256 value"
            )
        resource = q.get("resource")
        if resource and resource.rstrip("/") not in {
            r.rstrip("/") for r in allowed_resources
        }:
            return fail("invalid_target", f"resource must be {settings.resource_url}")
        scopes = normalize_scopes(q.get("scope"))
        if scopes is None:
            return fail(
                "invalid_scope", f"supported scopes: {' '.join(supported_short)}"
            )
        nonce = secrets.token_urlsafe(24)
        txn = sealer.seal(
            "consent",
            {
                "client_id": client_id,
                "client_name": client.get("client_name"),
                "redirect_uri": redirect_uri,
                "challenge": challenge,
                "state": state,
                "scopes": scopes,
                "resource": resource or settings.resource_url,
                "nonce": nonce,
            },
            settings.proxy.transaction_ttl_seconds,
        )
        host = urlsplit(redirect_uri).netloc or redirect_uri
        warn = (
            ""
            if is_loopback(redirect_uri) or client_id == ADMIN_CLIENT_ID
            else "<p class='warn'>This client is not a local application. Continue only "
            "if you trust it.</p>"
        )
        perm_items = "".join(f"<li><code>{html.escape(s)}</code></li>" for s in scopes)
        body = (
            f"<h1>Allow access to {html.escape(settings.resource_name)}?</h1>"
            f"<p><strong>{html.escape(str(client.get('client_name')))}</strong> "
            f"(returns to <code>{html.escape(host)}</code>) is requesting:</p>"
            f"<ul>{perm_items}</ul>{warn}"
            f"<p>You will sign in with your organization account next.</p>"
            f"<form method='post' action='/oauth/authorize'>"
            f"<input type='hidden' name='txn' value='{html.escape(txn)}'>"
            "<button class='primary' name='action' value='approve'>Allow</button>"
            "<button name='action' value='deny'>Deny</button></form>"
        )
        resp = HTMLResponse(
            _html_page("Authorize access", body),
            headers=_page_headers(runtime, upstream.authority_origin),
        )
        resp.set_cookie(
            cookie_tx,
            nonce,
            max_age=settings.proxy.transaction_ttl_seconds,
            samesite="strict",
            **cookie_kwargs(),
        )
        return resp

    @router.post("/oauth/authorize")
    async def consent(request: Request) -> Response:
        fetch_site = request.headers.get("sec-fetch-site")
        origin = request.headers.get("origin")
        if (fetch_site and fetch_site not in ("same-origin", "none")) or (
            origin and origin.rstrip("/") != issuer
        ):
            return _error_page(runtime, "Cross-site consent submission refused.", 403)
        form = await request.form()
        try:
            txn = sealer.unseal("consent", str(form.get("txn", "")))
        except SealError:
            return _error_page(
                runtime, "The consent request expired or is invalid.", 403
            )
        cookie = request.cookies.get(cookie_tx, "")
        if not hmac.compare_digest(cookie.encode(), str(txn["nonce"]).encode()):
            return _error_page(runtime, "Consent could not be verified (CSRF).", 403)
        if form.get("action") != "approve":
            return _redirect_to_client(
                txn["redirect_uri"],
                {
                    "error": "access_denied",
                    "error_description": "user denied consent",
                    "state": txn.get("state"),
                },
                issuer,
            )
        verifier = secrets.token_urlsafe(48)
        cb_nonce = secrets.token_urlsafe(24)
        state = sealer.seal(
            "state",
            {
                **{k: v for k, v in txn.items() if k != "exp"},
                "verifier": verifier,
                "cb_nonce": cb_nonce,
            },
            settings.proxy.transaction_ttl_seconds,
        )
        resp = RedirectResponse(
            upstream.authorize_url(
                state=state, verifier=verifier, scopes=txn["scopes"]
            ),
            status_code=303,
            headers=_NO_STORE,
        )
        resp.delete_cookie(cookie_tx, path="/")
        resp.set_cookie(
            cookie_cb,
            cb_nonce,
            max_age=settings.proxy.transaction_ttl_seconds,
            samesite="lax",
            **cookie_kwargs(),
        )
        return resp

    # -------------------------------------------------------------- callback
    @router.get("/oauth/callback")
    async def callback(request: Request) -> Response:
        q = request.query_params
        try:
            st = sealer.unseal("state", q.get("state", ""))
        except SealError:
            return _error_page(runtime, "The sign-in state expired or is invalid.")
        cookie = request.cookies.get(cookie_cb, "")
        if not hmac.compare_digest(cookie.encode(), str(st["cb_nonce"]).encode()):
            return _error_page(runtime, "Sign-in could not be bound to this browser.")
        if q.get("error"):
            err = q.get("error", "server_error")
            resp = _redirect_to_client(
                st["redirect_uri"],
                {
                    "error": err if err in _ERROR_CODES else "server_error",
                    "error_description": (q.get("error_description") or "")[:200].split(
                        "\r\n"
                    )[0],
                    "state": st.get("state"),
                },
                issuer,
            )
        elif not q.get("code"):
            resp = _redirect_to_client(
                st["redirect_uri"],
                {
                    "error": "server_error",
                    "error_description": "no code from IdP",
                    "state": st.get("state"),
                },
                issuer,
            )
        else:
            code = sealer.seal(
                "code",
                {
                    "upstream_code": q["code"],
                    "verifier": st["verifier"],
                    "client_id": st["client_id"],
                    "redirect_uri": st["redirect_uri"],
                    "challenge": st["challenge"],
                    "scopes": st["scopes"],
                    "resource": st["resource"],
                },
                settings.proxy.code_ttl_seconds,
            )
            resp = _redirect_to_client(
                st["redirect_uri"], {"code": code, "state": st.get("state")}, issuer
            )
        resp.delete_cookie(cookie_cb, path="/")
        return resp

    # ----------------------------------------------------------------- token
    async def _finish(
        tokens: dict[str, Any],
        client_id: str,
        scopes: list[str],
        rt_expires_at: int | None,
    ) -> Response:
        try:
            principal = await runtime.validator.validate(str(tokens["access_token"]))
        except AuthError as exc:
            return _oauth_error(
                "invalid_grant",
                f"upstream token rejected by this server: {exc.description}",
            )
        body: dict[str, Any] = {
            "access_token": tokens["access_token"],
            "token_type": "Bearer",
            "expires_in": int(tokens.get("expires_in", 3600)),
            "scope": " ".join(
                s
                for s in (settings.read_scope, settings.write_scope)
                if s in principal.scopes
            )
            or " ".join(scopes),
        }
        upstream_rt = tokens.get("refresh_token")
        if settings.proxy.refresh_tokens and upstream_rt:
            max_age = settings.proxy.refresh_token_max_age_days * 86400
            expires_at = rt_expires_at or int(time.time()) + max_age
            ttl = max(1, expires_at - int(time.time()))
            body["refresh_token"] = sealer.seal(
                "refresh",
                {
                    "rt": upstream_rt,
                    "client_id": client_id,
                    "scopes": scopes,
                    "abs_exp": expires_at,
                },
                ttl,
            )
        return JSONResponse(body, headers=_NO_STORE)

    @router.post("/oauth/token")
    async def token(request: Request) -> Response:
        if "application/x-www-form-urlencoded" not in request.headers.get(
            "content-type", ""
        ):
            return _oauth_error(
                "invalid_request", "use application/x-www-form-urlencoded"
            )
        form = await request.form()
        grant = form.get("grant_type")
        client_id = str(form.get("client_id") or "")
        if form.get("client_secret") or request.headers.get("authorization"):
            return _oauth_error(
                "invalid_client", "public clients must not authenticate", 401
            )
        resource = form.get("resource")
        if resource and str(resource).rstrip("/") not in {
            r.rstrip("/") for r in allowed_resources
        }:
            return _oauth_error(
                "invalid_target", f"resource must be {settings.resource_url}"
            )
        try:
            if grant == "authorization_code":
                try:
                    data = sealer.unseal("code", str(form.get("code") or ""))
                except SealError:
                    return _oauth_error(
                        "invalid_grant", "authorization code invalid or expired"
                    )
                if not hmac.compare_digest(
                    client_id.encode(), str(data["client_id"]).encode()
                ):
                    return _oauth_error("invalid_grant", "client_id mismatch")
                if str(form.get("redirect_uri") or "") != data["redirect_uri"]:
                    return _oauth_error("invalid_grant", "redirect_uri mismatch")
                verifier = str(form.get("code_verifier") or "")
                if not (43 <= len(verifier) <= 128):
                    return _oauth_error(
                        "invalid_request", "code_verifier (PKCE S256) is required"
                    )
                if not hmac.compare_digest(
                    pkce_challenge(verifier).encode(), str(data["challenge"]).encode()
                ):
                    return _oauth_error("invalid_grant", "PKCE verification failed")
                tokens = await upstream.exchange_code(
                    data["upstream_code"], data["verifier"], data["scopes"]
                )
                return await _finish(tokens, client_id, data["scopes"], None)
            if grant == "refresh_token":
                if not settings.proxy.refresh_tokens:
                    return _oauth_error(
                        "unsupported_grant_type", "refresh tokens are disabled"
                    )
                try:
                    data = sealer.unseal(
                        "refresh", str(form.get("refresh_token") or "")
                    )
                except SealError:
                    return _oauth_error(
                        "invalid_grant", "refresh token invalid or expired"
                    )
                if not hmac.compare_digest(
                    client_id.encode(), str(data["client_id"]).encode()
                ):
                    return _oauth_error("invalid_grant", "client_id mismatch")
                tokens = await upstream.refresh(data["rt"], data["scopes"])
                return await _finish(
                    tokens, client_id, data["scopes"], int(data["abs_exp"])
                )
        except UpstreamError as exc:
            return _oauth_error(exc.error, exc.description, exc.status)
        return _oauth_error(
            "unsupported_grant_type",
            "grant_type must be authorization_code or refresh_token",
        )

    return router


__all__ = ["ADMIN_CLIENT_ID", "build_proxy_router"]
