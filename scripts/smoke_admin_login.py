#!/usr/bin/env python3
"""Smoke-test the hosted admin email + password login on a deployed server.

Credentials come from the environment only (``ADMIN_EMAIL`` and ``ADMIN_PASSWORD``,
the same names as the GitHub secrets), never from the command line, so they cannot
leak through process listings. With either one unset the check is skipped (exit 0).

    ADMIN_EMAIL=... ADMIN_PASSWORD=... python scripts/smoke_admin_login.py \
        --url https://uml-mcp.vercel.app

Checks: the console is closed without a session, a wrong password is refused with a
generic error, the right one sets a hardened cookie, and the cookie opens the API.
It never calls a write endpoint.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import urllib.parse


def _request(
    base: str,
    method: str,
    path: str,
    *,
    body: dict[str, str] | None = None,
    cookie: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    parts = urllib.parse.urlsplit(base)
    cls = (
        http.client.HTTPSConnection
        if parts.scheme == "https"
        else http.client.HTTPConnection
    )
    conn = cls(parts.netloc, timeout=20)
    headers = {"Accept": "application/json", "User-Agent": "uml-mcp-admin-smoke"}
    payload = None
    if body is not None:
        payload = urllib.parse.urlencode(body)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if cookie:
        headers["Cookie"] = cookie
    try:
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, data
    finally:
        conn.close()


def _expect(ok: bool, message: str, failures: list[str]) -> None:
    print(("  ok   " if ok else "  FAIL ") + message)
    if not ok:
        failures.append(message)


def run(base: str, email: str, password: str, require_enabled: bool = False) -> int:
    base = base.rstrip("/")
    failures: list[str] = []

    status, _, _ = _request(base, "GET", "/admin/api/overview")
    if status == 404:
        hint = (
            "Admin login is not enabled on this deployment (404). Set ADMIN_EMAIL, "
            "ADMIN_PASSWORD_HASH or ADMIN_PASSWORD, and ADMIN_SESSION_SECRET in the "
            "Vercel project and redeploy."
        )
        if require_enabled:
            print(hint)
            return 1
        # Not blocking by default: the deploy job also publishes to Smithery, and the
        # GitHub secrets can exist before the Vercel variables do.
        print(f"::warning::{hint}")
        return 0
    _expect(status == 401, f"no session -> 401 (got {status})", failures)

    status, headers, _ = _request(
        base,
        "POST",
        "/admin/login",
        body={"email": email, "password": "wrong-" + password},
    )
    _expect(status == 401, f"wrong password -> 401 (got {status})", failures)
    _expect("set-cookie" not in headers, "wrong password sets no cookie", failures)

    status, headers, _ = _request(
        base, "POST", "/admin/login", body={"email": email, "password": password}
    )
    _expect(status == 303, f"login -> 303 (got {status})", failures)
    cookie_header = headers.get("set-cookie", "")
    lowered = cookie_header.lower()
    secure_expected = base.startswith("https://")
    _expect("httponly" in lowered, "cookie is HttpOnly", failures)
    _expect("samesite=strict" in lowered, "cookie is SameSite=Strict", failures)
    _expect("path=/admin" in lowered, "cookie is scoped to /admin", failures)
    if secure_expected:
        _expect("secure" in lowered, "cookie is Secure", failures)

    session = cookie_header.split(";", 1)[0]
    if session:
        status, _, data = _request(base, "GET", "/admin/api/overview", cookie=session)
        _expect(status == 200, f"session opens the API -> 200 (got {status})", failures)
        try:
            mode = json.loads(data).get("mode")
        except ValueError:
            mode = None
        _expect(
            mode == "password",
            f"overview reports mode=password (got {mode!r})",
            failures,
        )

    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1
    print("\nAdmin login smoke test OK.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--url",
        default=os.environ.get("VERCEL_URL", "https://uml-mcp.vercel.app"),
        help="deployment root URL (default: $VERCEL_URL)",
    )
    parser.add_argument(
        "--require-enabled",
        action="store_true",
        help="fail (instead of warning) when /admin is still 404",
    )
    args = parser.parse_args()
    email = os.environ.get("ADMIN_EMAIL", "")
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        print(
            "ADMIN_EMAIL / ADMIN_PASSWORD not set; skipping the admin login smoke test."
        )
        return 0
    return run(args.url, email, password, args.require_enabled)


if __name__ == "__main__":
    sys.exit(main())
