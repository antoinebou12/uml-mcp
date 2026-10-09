"""Email + password sign-in for the hosted admin console (read-only ``password`` mode)."""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_core.admin import password_auth as pa
from mcp_core.admin.api import build_password_admin_router

EMAIL = "admin@example.test"
PASSWORD = "correct horse battery staple"
SECRET = "s" * 48


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    """Cheap scrypt, no failure delay, clean env + counters for every test."""
    for name in (
        pa.EMAIL_ENV,
        pa.PASSWORD_ENV,
        pa.PASSWORD_HASH_ENV,
        pa.SECRET_ENV,
        pa.TTL_ENV,
        "VERCEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(pa, "_SCRYPT_N", 2**10)
    monkeypatch.setattr(pa, "FAIL_DELAY_SECONDS", 0)
    pa._plain_verifier.cache_clear()
    pa._warned.clear()
    pa.THROTTLE.reset()
    yield
    pa._plain_verifier.cache_clear()
    pa.THROTTLE.reset()


def _configure(monkeypatch, **overrides: str) -> None:
    values = {
        pa.EMAIL_ENV: EMAIL,
        pa.PASSWORD_ENV: PASSWORD,
        pa.SECRET_ENV: SECRET,
        **overrides,
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(build_password_admin_router())
    return TestClient(app, follow_redirects=False)


def _login(client: TestClient, email: str = EMAIL, password: str = PASSWORD, **headers):
    return client.post(
        "/admin/login", data={"email": email, "password": password}, headers=headers
    )


def _signed_in(client: TestClient) -> TestClient:
    response = _login(client)
    assert response.status_code == 303, response.text
    return client


# ---------------------------------------------------------------- fail closed


def test_unconfigured_admin_is_404(client):
    assert pa.enabled() is False
    for path in ("/admin", "/admin/login", "/admin/api/overview"):
        assert client.get(path).status_code == 404, path
    assert _login(client).status_code == 404


@pytest.mark.parametrize(
    "missing", [pa.EMAIL_ENV, pa.PASSWORD_ENV, pa.SECRET_ENV], ids=str
)
def test_partial_config_is_404_and_names_the_variable(
    client, monkeypatch, caplog, missing
):
    _configure(monkeypatch)
    monkeypatch.delenv(missing)
    with caplog.at_level(logging.WARNING):
        assert pa.enabled() is False
    assert missing in caplog.text
    assert client.get("/admin/login").status_code == 404


def test_short_session_secret_is_rejected(client, monkeypatch):
    _configure(monkeypatch, **{pa.SECRET_ENV: "too-short"})
    assert pa.enabled() is False
    assert client.get("/admin/login").status_code == 404


def test_invalid_hash_fails_closed(client, monkeypatch):
    _configure(monkeypatch, **{pa.PASSWORD_HASH_ENV: "not-a-hash"})
    assert pa.enabled() is False


# ---------------------------------------------------------------- sign-in flow


def test_wrong_email_and_wrong_password_look_identical(client, monkeypatch):
    _configure(monkeypatch)
    bad_email = _login(client, email="someone@else.test")
    bad_password = _login(client, password="nope")
    assert bad_email.status_code == bad_password.status_code == 401
    assert bad_email.text == bad_password.text
    assert pa.GENERIC_ERROR in bad_email.text
    assert pa.COOKIE_NAME not in bad_email.headers.get("set-cookie", "")


def test_login_sets_hardened_cookie_and_redirects(client, monkeypatch):
    _configure(monkeypatch)
    response = _login(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{pa.COOKIE_NAME}=")
    lowered = cookie.lower()
    assert "httponly" in lowered
    assert "samesite=strict" in lowered
    assert "path=/admin" in lowered
    assert "max-age=3600" in lowered


def test_cookie_is_secure_on_vercel(client, monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    assert "secure" in _login(client).headers["set-cookie"].lower()


def test_email_is_case_insensitive(client, monkeypatch):
    _configure(monkeypatch)
    assert _login(client, email=f"  {EMAIL.upper()} ").status_code == 303


def test_session_unlocks_shell_and_api(client, monkeypatch):
    _configure(monkeypatch)
    assert client.get("/admin/api/overview").status_code == 401
    _signed_in(client)
    shell = client.get("/admin/")
    assert shell.status_code == 200
    assert "text/html" in shell.headers["content-type"]
    overview = client.get("/admin/api/overview")
    assert overview.status_code == 200
    assert overview.json()["mode"] == "password"
    assert overview.json()["local"] is False
    assert overview.headers["cache-control"] == "no-store"


def test_navigation_without_session_redirects_to_login(client, monkeypatch):
    _configure(monkeypatch)
    for headers in ({"sec-fetch-dest": "document"}, {"accept": "text/html"}):
        response = client.get("/admin", headers=headers)
        assert response.status_code == 303, headers
        assert response.headers["location"] == "/admin/login"


def test_api_without_session_is_401_not_a_redirect(client, monkeypatch):
    _configure(monkeypatch)
    response = client.get("/admin/api/tools", headers={"accept": "application/json"})
    assert response.status_code == 401
    assert "location" not in response.headers


def test_login_page_security_headers(client, monkeypatch):
    _configure(monkeypatch)
    response = client.get("/admin/login")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "noindex" in response.headers["x-robots-tag"]
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "form-action 'self'" in csp
    assert "<script" not in response.text


def test_login_page_redirects_when_already_signed_in(client, monkeypatch):
    _configure(monkeypatch)
    _signed_in(client)
    response = client.get("/admin/login")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/"


def test_logout_clears_session(client, monkeypatch):
    _configure(monkeypatch)
    _signed_in(client)
    response = client.post("/admin/logout")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"
    assert "max-age=0" in response.headers["set-cookie"].lower()
    client.cookies.clear()
    assert client.get("/admin/api/overview").status_code == 401


# ------------------------------------------------------------ read-only by design


def test_writes_and_stop_are_refused_even_when_signed_in(client, monkeypatch):
    _configure(monkeypatch)
    _signed_in(client)
    saved = client.put("/admin/api/settings", json={"data": {}})
    stopped = client.post("/admin/api/server/stop")
    assert saved.status_code == 403
    assert stopped.status_code == 403
    assert "read-only" in saved.json()["detail"]


def test_writes_without_session_are_401(client, monkeypatch):
    _configure(monkeypatch)
    assert client.put("/admin/api/settings", json={"data": {}}).status_code == 401
    assert client.post("/admin/api/server/stop").status_code == 401


# --------------------------------------------------------------------------- CSRF


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://evil.example"},
        {"origin": "null"},
        {"sec-fetch-site": "cross-site"},
        {"sec-fetch-site": "same-site"},
    ],
    ids=str,
)
def test_cross_site_login_is_refused(client, monkeypatch, headers):
    _configure(monkeypatch)
    assert _login(client, **headers).status_code == 403


def test_cross_site_logout_is_refused(client, monkeypatch):
    _configure(monkeypatch)
    _signed_in(client)
    response = client.post("/admin/logout", headers={"origin": "https://evil.example"})
    assert response.status_code == 403
    assert client.get("/admin/api/overview").status_code == 200


def test_same_origin_browser_post_is_accepted(client, monkeypatch):
    _configure(monkeypatch)
    response = _login(
        client, origin="http://testserver", **{"sec-fetch-site": "same-origin"}
    )
    assert response.status_code == 303


def test_origin_null_on_same_origin_post_is_accepted(client, monkeypatch):
    """Regression: under ``Referrer-Policy: no-referrer`` (which the login page sets)
    Chromium sends ``Origin: null`` on same-origin form posts. Found in the browser."""
    _configure(monkeypatch)
    page = client.get("/admin/login")
    assert page.headers["referrer-policy"] == "no-referrer"
    response = _login(client, origin="null", **{"sec-fetch-site": "same-origin"})
    assert response.status_code == 303


def test_fetch_metadata_wins_over_a_matching_origin(client, monkeypatch):
    _configure(monkeypatch)
    response = _login(
        client, origin="http://testserver", **{"sec-fetch-site": "cross-site"}
    )
    assert response.status_code == 403


# ------------------------------------------------------------------ brute force


def test_sixth_failure_is_throttled_with_retry_after(client, monkeypatch):
    _configure(monkeypatch)
    for _ in range(pa.MAX_FAILURES):
        assert _login(client, password="wrong").status_code == 401
    blocked = _login(client, password="wrong")
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    # Even the right password is refused while locked out.
    assert _login(client).status_code == 429


def test_lockout_is_per_client_ip_on_vercel(client, monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    for _ in range(pa.MAX_FAILURES):
        _login(client, password="wrong", **{"x-real-ip": "203.0.113.7"})
    assert _login(client, **{"x-real-ip": "203.0.113.7"}).status_code == 429
    assert _login(client, **{"x-real-ip": "198.51.100.9"}).status_code == 303


def test_client_supplied_forwarded_for_is_ignored_off_vercel(client, monkeypatch):
    _configure(monkeypatch)
    for index in range(pa.MAX_FAILURES):
        _login(client, password="wrong", **{"x-forwarded-for": f"10.0.0.{index}"})
    response = _login(client, password="wrong", **{"x-forwarded-for": "10.9.9.9"})
    assert response.status_code == 429


def test_failure_throttle_window_and_clear():
    now = [0.0]
    throttle = pa.FailureThrottle(max_failures=3, window=60, clock=lambda: now[0])
    for _ in range(3):
        throttle.record_failure("ip")
    assert 0 < throttle.retry_after("ip") <= 60
    assert throttle.retry_after("other") == 0
    now[0] = 61.0
    assert throttle.retry_after("ip") == 0
    for _ in range(3):
        throttle.record_failure("ip")
    throttle.clear("ip")
    assert throttle.retry_after("ip") == 0


def test_oversized_login_body_is_rejected(client, monkeypatch):
    _configure(monkeypatch)
    response = client.post(
        "/admin/login",
        data={"email": EMAIL, "password": "x" * (pa.MAX_FORM_BYTES + 1)},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------- sessions


def _cfg(monkeypatch, **overrides: str) -> pa.AdminLoginConfig:
    _configure(monkeypatch, **overrides)
    cfg = pa.load_config()
    assert cfg is not None
    return cfg


def test_session_roundtrip_and_expiry(monkeypatch):
    cfg = _cfg(monkeypatch)
    token = pa.issue_session(cfg, now=1000.0)
    assert pa.valid_session(cfg, token, now=1000.0 + cfg.ttl - 1)
    assert not pa.valid_session(cfg, token, now=1000.0 + cfg.ttl + 1)


def test_tampered_sessions_are_rejected(monkeypatch):
    cfg = _cfg(monkeypatch)
    token = pa.issue_session(cfg, now=1000.0)
    version, expires, nonce, signature = token.split(".")
    forged_expiry = ".".join((version, str(int(expires) + 99999), nonce, signature))
    flipped = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    for bad in (
        forged_expiry,
        flipped,
        "",
        "garbage",
        "v1.1.2.3.4",
        "v2." + token[3:],
        "é" * 10,
        token + "x" * 400,
    ):
        assert not pa.valid_session(cfg, bad, now=1000.0), bad
    assert not pa.valid_session(cfg, None)


def test_session_from_another_secret_is_rejected(monkeypatch):
    token = pa.issue_session(_cfg(monkeypatch))
    other = _cfg(monkeypatch, **{pa.SECRET_ENV: "z" * 48})
    assert not pa.valid_session(other, token)


@pytest.mark.parametrize(
    "rotation",
    [{pa.PASSWORD_ENV: "a brand new password"}, {pa.EMAIL_ENV: "new@x.test"}],
)
def test_rotating_credentials_signs_everyone_out(monkeypatch, rotation):
    token = pa.issue_session(_cfg(monkeypatch))
    assert pa.valid_session(_cfg(monkeypatch), token)
    assert not pa.valid_session(_cfg(monkeypatch, **rotation), token)


def test_ttl_is_clamped(monkeypatch):
    assert _cfg(monkeypatch, **{pa.TTL_ENV: "999999"}).ttl == pa.MAX_TTL
    assert _cfg(monkeypatch, **{pa.TTL_ENV: "5"}).ttl == 60
    assert _cfg(monkeypatch, **{pa.TTL_ENV: "nonsense"}).ttl == pa.DEFAULT_TTL


# ---------------------------------------------------------------------- passwords


def test_scrypt_hash_roundtrip(client, monkeypatch):
    monkeypatch.setattr(pa, "_SCRYPT_N", 2**15)  # the production cost, once
    stored = pa.hash_password(PASSWORD)
    assert stored.startswith("scrypt$32768$8$1$")
    assert PASSWORD not in stored
    monkeypatch.setenv(pa.EMAIL_ENV, EMAIL)
    monkeypatch.setenv(pa.PASSWORD_HASH_ENV, stored)
    monkeypatch.setenv(pa.SECRET_ENV, SECRET)
    cfg = pa.load_config()
    assert cfg is not None
    assert pa.verify_credentials(cfg, EMAIL, PASSWORD)
    assert not pa.verify_credentials(cfg, EMAIL, PASSWORD + "x")
    assert not pa.verify_credentials(cfg, "other@x.test", PASSWORD)
    assert _login(client).status_code == 303


def test_hash_wins_over_plain_password(monkeypatch):
    _configure(monkeypatch, **{pa.PASSWORD_HASH_ENV: pa.hash_password("from the hash")})
    cfg = pa.load_config()
    assert cfg is not None
    assert pa.verify_credentials(cfg, EMAIL, "from the hash")
    assert not pa.verify_credentials(cfg, EMAIL, PASSWORD)


def test_plain_password_warns_once_to_prefer_hash(monkeypatch, caplog):
    _configure(monkeypatch)
    with caplog.at_level(logging.WARNING):
        pa.load_config()
        pa.load_config()
    assert caplog.text.count("holds a plain password") == 1


@pytest.mark.parametrize(
    "value",
    [
        "scrypt$3$8$1$c2FsdA==$ZGlnZXN0",  # n not a power of two
        "scrypt$1048576$16$1$c2FsdA==$ZGlnZXN0",  # would exceed the memory cap
        "scrypt$1024$8$99$c2FsdA==$ZGlnZXN0",  # p out of range
        "scrypt$1024$8$1$!!!$ZGlnZXN0",  # bad base64
        "bcrypt$1024$8$1$c2FsdA==$ZGlnZXN0",
        "scrypt$1024$8$1",
    ],
)
def test_hostile_or_malformed_hashes_are_rejected(value):
    assert pa._parse_hash(value) is None


def test_overlong_password_is_rejected_without_error(monkeypatch):
    cfg = _cfg(monkeypatch)
    assert not pa.verify_credentials(cfg, EMAIL, PASSWORD * 200)


# ------------------------------------------------------------------------ logging


def test_credentials_never_reach_the_logs(client, monkeypatch, caplog):
    _configure(monkeypatch, **{pa.PASSWORD_ENV: "Sup3r-secret-pw!"})
    with caplog.at_level(logging.DEBUG):
        _login(client, password="wrong-guess-123")
        _login(client, password="Sup3r-secret-pw!")
        client.get("/admin/api/overview")
    for needle in (EMAIL, "wrong-guess-123", "Sup3r-secret-pw!", SECRET):
        assert needle not in caplog.text


# ---------------------------------------------------------------------------- CLI


def test_cli_session_secret(capsys):
    assert pa.main(["session-secret"]) == 0
    assert len(capsys.readouterr().out.strip()) >= pa.MIN_SECRET_LENGTH


def test_cli_hash_prompts_and_validates(monkeypatch, capsys):
    answers = iter([PASSWORD, PASSWORD])
    monkeypatch.setattr(pa.getpass, "getpass", lambda _prompt="": next(answers))
    assert pa.main(["hash"]) == 0
    assert capsys.readouterr().out.startswith("scrypt$")

    answers = iter([PASSWORD, "different"])
    assert pa.main(["hash"]) == 1
    answers = iter(["short", "short"])
    assert pa.main(["hash"]) == 1
    assert pa.main(["bogus"]) == 2
