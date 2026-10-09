"""Email + password sign-in for the hosted (Vercel) admin console.

The console in :mod:`mcp_core.admin` otherwise only admits loopback clients (local
mode) or Entra ``MCP.Admin`` users (enterprise mode). Neither exists on a plain
Vercel deployment, so this adds a third, **read-only** ``password`` mode.

Configuration (environment only; credentials never go in ``uml-mcp.yaml``):

==========================  ====================================================
``ADMIN_EMAIL``             sign-in email
``ADMIN_PASSWORD_HASH``     preferred: ``scrypt$N$r$p$salt_b64$hash_b64``
``ADMIN_PASSWORD``          plain fallback (a warning recommends the hash)
``ADMIN_SESSION_SECRET``    HMAC key for the session cookie, at least 32 chars
``ADMIN_SESSION_TTL_SECONDS``  session lifetime, default 3600, capped at 43200
==========================  ====================================================

The mode fails closed: unless the email, a password and a session secret are all
present, ``/admin`` stays a 404. Sessions are stateless (HMAC-signed cookie) because
serverless instances share no memory, and they are bound to the configured
credentials, so rotating the email or password signs everyone out.

Generate the values with ``python -m mcp_core.admin.password_auth hash`` and
``python -m mcp_core.admin.password_auth session-secret``.
"""

from __future__ import annotations

import asyncio
import base64
import functools
import getpass
import hashlib
import hmac
import logging
import os
import secrets
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .guards import Guards

logger = logging.getLogger(__name__)

EMAIL_ENV = "ADMIN_EMAIL"
PASSWORD_ENV = "ADMIN_PASSWORD"
PASSWORD_HASH_ENV = "ADMIN_PASSWORD_HASH"
SECRET_ENV = "ADMIN_SESSION_SECRET"
TTL_ENV = "ADMIN_SESSION_TTL_SECONDS"

COOKIE_NAME = "uml_admin_session"
LOGIN_PATH = "/admin/login"
ADMIN_HOME = "/admin/"
MIN_SECRET_LENGTH = 32
DEFAULT_TTL = 3600
MAX_TTL = 43200
MAX_PASSWORD_LENGTH = 1024
MAX_FORM_BYTES = 4096
MAX_FAILURES = 5
FAILURE_WINDOW_SECONDS = 900.0
#: Pause after a failed attempt (module-level so tests can zero it).
FAIL_DELAY_SECONDS = 0.5

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**15, 8, 1
_SCRYPT_MAXMEM = 128 * 1024 * 1024
_SCRYPT_LIMITS = (2**20, 16, 4)  # reject hostile parameters in a supplied hash
GENERIC_ERROR = "Invalid email or password."

PAGE_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
        "frame-ancestors 'none'; base-uri 'none'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
}


# --------------------------------------------------------------------------- passwords


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=32,
        maxmem=_SCRYPT_MAXMEM,
    )


def hash_password(password: str) -> str:
    """``scrypt$N$r$p$salt_b64$hash_b64`` for ``ADMIN_PASSWORD_HASH``."""
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return "$".join(
        (
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )
    )


@dataclass(frozen=True)
class _Verifier:
    """A scrypt verifier; plain ``ADMIN_PASSWORD`` is converted to one at load time."""

    n: int
    r: int
    p: int
    salt: bytes
    digest: bytes

    def check(self, password: str) -> bool:
        if len(password) > MAX_PASSWORD_LENGTH:
            # Still burn the same work so length cannot be probed cheaply.
            password = password[:MAX_PASSWORD_LENGTH]
            matched = False
        else:
            matched = True
        candidate = _scrypt(password, self.salt, self.n, self.r, self.p)
        return hmac.compare_digest(candidate, self.digest) and matched


def _parse_hash(value: str) -> _Verifier | None:
    parts = value.strip().split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return None
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        digest = base64.b64decode(parts[5], validate=True)
    except ValueError:
        return None
    max_n, max_r, max_p = _SCRYPT_LIMITS
    if not (
        2 <= n <= max_n and n & (n - 1) == 0 and 1 <= r <= max_r and 1 <= p <= max_p
    ):
        return None
    if (
        128 * n * r > _SCRYPT_MAXMEM
    ):  # would raise at sign-in time instead of failing closed
        return None
    if not salt or not digest:
        return None
    return _Verifier(n, r, p, salt, digest)


@functools.lru_cache(maxsize=4)
def _plain_verifier(password: str) -> _Verifier:
    salt = secrets.token_bytes(16)
    return _Verifier(
        _SCRYPT_N,
        _SCRYPT_R,
        _SCRYPT_P,
        salt,
        _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P),
    )


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


# ------------------------------------------------------------------------------ config


@dataclass(frozen=True)
class AdminLoginConfig:
    email: str  # normalised (stripped, casefolded)
    verifier: _Verifier
    session_key: bytes
    ttl: int


_warned: set[str] = set()


def _warn_once(key: str, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        logger.warning(message)


def _ttl() -> int:
    raw = os.environ.get(TTL_ENV, "").strip()
    try:
        value = int(raw) if raw else DEFAULT_TTL
    except ValueError:
        _warn_once("ttl", f"{TTL_ENV} is not an integer; using {DEFAULT_TTL}s.")
        return DEFAULT_TTL
    return max(60, min(value, MAX_TTL))


def load_config() -> AdminLoginConfig | None:
    """Return the password-mode config, or ``None`` (mode off) if anything is missing."""
    email = os.environ.get(EMAIL_ENV, "").strip()
    pw_hash = os.environ.get(PASSWORD_HASH_ENV, "").strip()
    pw_plain = os.environ.get(PASSWORD_ENV, "")
    secret = os.environ.get(SECRET_ENV, "")
    if not (email or pw_hash or pw_plain or secret):
        return None  # not configured at all: stay silent
    missing = [
        name
        for name, ok in (
            (EMAIL_ENV, bool(email)),
            (f"{PASSWORD_HASH_ENV} or {PASSWORD_ENV}", bool(pw_hash or pw_plain)),
            (SECRET_ENV, bool(secret)),
        )
        if not ok
    ]
    if missing:
        _warn_once(
            "missing:" + ",".join(missing),
            "Admin password login disabled; missing " + ", ".join(missing) + ".",
        )
        return None
    if len(secret) < MIN_SECRET_LENGTH:
        _warn_once(
            "secret",
            f"Admin password login disabled; {SECRET_ENV} must be at least "
            f"{MIN_SECRET_LENGTH} characters.",
        )
        return None

    if pw_hash:
        verifier = _parse_hash(pw_hash)
        if verifier is None:
            _warn_once(
                "hash",
                f"Admin password login disabled; {PASSWORD_HASH_ENV} is not a valid "
                "scrypt hash (generate one with `python -m mcp_core.admin.password_auth hash`).",
            )
            return None
        material = pw_hash
    else:
        _warn_once(
            "plain",
            f"{PASSWORD_ENV} holds a plain password; prefer {PASSWORD_HASH_ENV} "
            "(`python -m mcp_core.admin.password_auth hash`).",
        )
        verifier = _plain_verifier(pw_plain)
        material = "plain:" + hashlib.sha256(pw_plain.encode("utf-8")).hexdigest()

    normalised = email.casefold()
    # Binding the key to the credentials signs everyone out when they are rotated.
    session_key = hmac.new(
        secret.encode("utf-8"),
        f"uml-mcp-admin-session\0{normalised}\0{material}".encode(),
        hashlib.sha256,
    ).digest()
    return AdminLoginConfig(normalised, verifier, session_key, _ttl())


def enabled() -> bool:
    """True when password mode is fully configured."""
    return load_config() is not None


def verify_credentials(cfg: AdminLoginConfig, email: str, password: str) -> bool:
    """Constant-time check; the scrypt work is done even when the email is wrong."""
    email_ok = hmac.compare_digest(
        _digest(email.strip().casefold()), _digest(cfg.email)
    )
    password_ok = cfg.verifier.check(password)
    return email_ok & password_ok


# ------------------------------------------------------------------------ sessions


def _sign(key: bytes, message: str) -> str:
    mac = hmac.new(key, message.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode("ascii")


def issue_session(cfg: AdminLoginConfig, now: float | None = None) -> str:
    expires = int((time.time() if now is None else now) + cfg.ttl)
    message = f"v1.{expires}.{secrets.token_urlsafe(12)}"
    return f"{message}.{_sign(cfg.session_key, message)}"


def valid_session(
    cfg: AdminLoginConfig, token: str | None, now: float | None = None
) -> bool:
    if not token or len(token) > 256 or not token.isascii():
        return False
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "v1":
        return False
    message = ".".join(parts[:3])
    if not hmac.compare_digest(_sign(cfg.session_key, message), parts[3]):
        return False
    try:
        expires = int(parts[1])
    except ValueError:
        return False
    return (time.time() if now is None else now) < expires


# ------------------------------------------------------------------------- throttle


class FailureThrottle:
    """Lock a client out after ``max_failures`` failed sign-ins within ``window``.

    Per process (like the rest of the in-memory limiters): on serverless each
    instance counts separately, so add an edge rule on ``/admin/login`` as well.
    """

    def __init__(
        self,
        max_failures: int = MAX_FAILURES,
        window: float = FAILURE_WINDOW_SECONDS,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_failures
        self._window = window
        self._max_keys = max_keys
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int:
        """Seconds until ``key`` may try again (0 when it may try now)."""
        now = self._clock()
        with self._lock:
            queue = self._failures.get(key)
            if not queue:
                return 0
            while queue and now - queue[0] > self._window:
                queue.popleft()
            if len(queue) < self._max:
                return 0
            return max(1, int(self._window - (now - queue[0]) + 0.999))

    def record_failure(self, key: str) -> None:
        with self._lock:
            if len(self._failures) > self._max_keys:
                self._failures.clear()  # bounded memory under key-spraying
            self._failures.setdefault(key, deque()).append(self._clock())

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


THROTTLE = FailureThrottle()


def _client_ip(request: Request) -> str:
    """Vercel overwrites ``x-forwarded-for``/``x-real-ip`` at its edge, so they can be
    trusted there; elsewhere honour them only for configured trusted proxies."""
    if os.environ.get("VERCEL"):
        for header in ("x-real-ip", "x-forwarded-for"):
            value = request.headers.get(header)
            if value:
                return value.split(",")[0].strip()[:64] or "unknown"
    from ..core.settings_file import get_app_config
    from ..observability.ratelimit import client_ip

    peer = request.client.host if request.client else None
    return client_ip(
        peer,
        request.headers.get("x-forwarded-for"),
        get_app_config().rate_limit.trusted_proxies,
    )


# ----------------------------------------------------------------------- request checks


def _secure_cookie(request: Request) -> bool:
    return bool(os.environ.get("VERCEL")) or request.url.scheme == "https"


def _same_origin(request: Request) -> bool:
    """Reject cross-site form posts.

    ``Sec-Fetch-Site`` is set by the browser and cannot be forged by page script, so
    it decides when present. ``Origin`` is only the fallback for older clients: under
    ``Referrer-Policy: no-referrer`` browsers send ``Origin: null`` even on a
    same-origin form post, so it cannot be the primary signal. Non-browser clients
    (curl, the CI smoke script) send neither header and are allowed.
    """
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        return site in ("same-origin", "none")
    origin = request.headers.get("origin")
    if origin is None:
        return True
    host = (request.headers.get("host") or "").lower()
    return bool(host) and urlsplit(origin).netloc.lower() == host


def _wants_html(request: Request) -> bool:
    dest = request.headers.get("sec-fetch-dest")
    if dest is not None:
        return dest == "document"
    return "text/html" in (request.headers.get("accept") or "")


def _config_or_404() -> AdminLoginConfig:
    cfg = load_config()
    if cfg is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return cfg


def require_session(request: Request) -> None:
    """Guard: a valid session cookie, else redirect (pages) or 401 (everything else)."""
    cfg = _config_or_404()
    if valid_session(cfg, request.cookies.get(COOKIE_NAME)):
        return
    if _wants_html(request):
        raise HTTPException(
            status_code=303,
            detail="Sign in required",
            headers={"Location": LOGIN_PATH, "Cache-Control": "no-store"},
        )
    raise HTTPException(
        status_code=401,
        detail="Sign in required",
        headers={"Cache-Control": "no-store"},
    )


def _read_only(request: Request) -> None:
    require_session(request)
    raise HTTPException(
        status_code=403,
        detail="The hosted admin console is read-only; change settings through "
        "environment variables or uml-mcp.yaml.",
    )


def password_guards() -> Guards:
    return Guards(
        read=require_session, write=_read_only, stop=_read_only, mode="password"
    )


# ---------------------------------------------------------------------------- pages

_PAGE_CSS = """
:root{color-scheme:light dark;--bg:#f6f7f9;--card:#fff;--fg:#111827;--muted:#6b7280;
--border:#d1d5db;--accent:#2563eb;--danger:#b91c1c}
@media (prefers-color-scheme:dark){:root{--bg:#0b0f17;--card:#111827;--fg:#f3f4f6;
--muted:#9ca3af;--border:#374151;--accent:#60a5fa;--danger:#fca5a5}}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:1rem;
background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{width:100%;max-width:22rem;background:var(--card);border:1px solid var(--border);
border-radius:12px;padding:1.5rem}
h1{margin:0 0 .25rem;font-size:1.25rem}
p{margin:0 0 1rem;color:var(--muted);font-size:.9rem}
label{display:block;margin:.75rem 0 .25rem;font-size:.85rem;font-weight:600}
input{width:100%;padding:.55rem .65rem;border:1px solid var(--border);border-radius:8px;
background:transparent;color:inherit;font:inherit}
input:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button{width:100%;margin-top:1.25rem;padding:.6rem;border:0;border-radius:8px;
background:var(--accent);color:#fff;font:inherit;font-weight:600;cursor:pointer}
.error{margin:0 0 .75rem;padding:.5rem .65rem;border:1px solid var(--danger);
border-radius:8px;color:var(--danger);font-size:.875rem}
"""


def _page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        f"<title>{escape(title)}</title><style>{_PAGE_CSS}</style></head>"
        f"<body><main>{body}</main></body></html>"
    )


def login_html(error: str | None = None) -> str:
    notice = f'<div class="error" role="alert">{escape(error)}</div>' if error else ""
    return _page(
        "Sign in — UML-MCP admin",
        "<h1>UML-MCP admin</h1><p>Sign in to continue.</p>"
        f"{notice}"
        f'<form method="post" action="{LOGIN_PATH}">'
        '<label for="email">Email</label>'
        '<input id="email" name="email" type="email" autocomplete="username" '
        'required maxlength="320" autofocus>'
        '<label for="password">Password</label>'
        '<input id="password" name="password" type="password" '
        'autocomplete="current-password" required maxlength="1024">'
        '<button type="submit">Sign in</button></form>',
    )


def logout_html() -> str:
    return _page(
        "Sign out — UML-MCP admin",
        "<h1>Sign out?</h1><p>This ends your admin session on this device.</p>"
        '<form method="post" action="/admin/logout">'
        '<button type="submit">Sign out</button></form>',
    )


def _html(
    body: str, status: int = 200, headers: dict[str, str] | None = None
) -> HTMLResponse:
    return HTMLResponse(
        body, status_code=status, headers={**PAGE_HEADERS, **(headers or {})}
    )


def _set_session_cookie(
    response: Response, request: Request, token: str, ttl: int
) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=ttl,
        path="/admin",
        httponly=True,
        secure=_secure_cookie(request),
        samesite="strict",
    )


def _clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        path="/admin",
        httponly=True,
        secure=_secure_cookie(request),
        samesite="strict",
    )


async def _read_form(request: Request) -> dict[str, str] | None:
    declared = request.headers.get("content-length")
    if declared and (not declared.isdigit() or int(declared) > MAX_FORM_BYTES):
        return None
    body = await request.body()
    if len(body) > MAX_FORM_BYTES:
        return None
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError:
        return None
    return {key: values[0] for key, values in parsed.items() if values}


def add_login_routes(router: APIRouter) -> None:
    """``GET/POST /admin/login`` and ``GET/POST /admin/logout``."""

    @router.get(LOGIN_PATH, include_in_schema=False)
    async def login_form(request: Request) -> Response:
        cfg = _config_or_404()
        if valid_session(cfg, request.cookies.get(COOKIE_NAME)):
            return RedirectResponse(ADMIN_HOME, status_code=303, headers=PAGE_HEADERS)
        return _html(login_html())

    @router.post(LOGIN_PATH, include_in_schema=False)
    async def login_submit(request: Request) -> Response:
        cfg = _config_or_404()
        if not _same_origin(request):
            raise HTTPException(status_code=403, detail="Cross-site request refused")
        ip = _client_ip(request)
        wait = THROTTLE.retry_after(ip)
        if wait:
            logger.warning("admin login throttled ip=%s", ip)
            minutes = max(1, (wait + 59) // 60)
            return _html(
                login_html(f"Too many attempts. Try again in {minutes} min."),
                status=429,
                headers={"Retry-After": str(wait)},
            )
        form = await _read_form(request)
        if form is None:
            raise HTTPException(status_code=400, detail="Malformed form")
        if verify_credentials(cfg, form.get("email", ""), form.get("password", "")):
            THROTTLE.clear(ip)
            logger.info("admin login ok ip=%s", ip)
            response = RedirectResponse(
                ADMIN_HOME, status_code=303, headers=PAGE_HEADERS
            )
            _set_session_cookie(response, request, issue_session(cfg), cfg.ttl)
            return response
        THROTTLE.record_failure(ip)
        logger.warning("admin login failed ip=%s", ip)
        await asyncio.sleep(FAIL_DELAY_SECONDS)
        return _html(login_html(GENERIC_ERROR), status=401)

    @router.get("/admin/logout", include_in_schema=False)
    async def logout_form(request: Request) -> Response:
        _config_or_404()
        return _html(logout_html())

    @router.post("/admin/logout", include_in_schema=False)
    async def logout_submit(request: Request) -> Response:
        _config_or_404()
        if not _same_origin(request):
            raise HTTPException(status_code=403, detail="Cross-site request refused")
        response = RedirectResponse(LOGIN_PATH, status_code=303, headers=PAGE_HEADERS)
        _clear_session_cookie(response, request)
        return response


# ------------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["session-secret"]:
        print(secrets.token_urlsafe(48))
        return 0
    if args == ["hash"]:
        password = getpass.getpass("Admin password: ")
        if getpass.getpass("Repeat password: ") != password:
            print("Passwords do not match.", file=sys.stderr)
            return 1
        if len(password) < 12:
            print("Use at least 12 characters.", file=sys.stderr)
            return 1
        print(hash_password(password))
        return 0
    print(
        "usage: python -m mcp_core.admin.password_auth (hash | session-secret)",
        file=sys.stderr,
    )
    return 2


__all__ = [
    "COOKIE_NAME",
    "THROTTLE",
    "AdminLoginConfig",
    "FailureThrottle",
    "add_login_routes",
    "enabled",
    "hash_password",
    "issue_session",
    "load_config",
    "password_guards",
    "require_session",
    "valid_session",
    "verify_credentials",
]

if __name__ == "__main__":
    raise SystemExit(main())
