"""entra-proxy facade: RFC 7591 DCR, PKCE S256 only, consent/CSRF, callback, token."""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from mcp_core.auth.proxy.redirects import redirect_allowed, redirect_matches
from mcp_core.auth.sealing import Sealer, SealError, generate_key, parse_keys
from tests.fixtures_auth import RESOURCE, build_auth_app, entra_v2_claims, mint
from tests.test_auth_metadata import proxy_settings

LOOPBACK = "http://127.0.0.1:33418/callback"


def s256(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )


@pytest.fixture
def proxy(mock_idp):
    app = build_auth_app(proxy_settings(), http=mock_idp.client())
    return TestClient(app, base_url="https://mcp.contoso.com"), mock_idp


def register(client, uris=(LOOPBACK,), **extra):
    return client.post(
        "/oauth/register",
        json={"redirect_uris": list(uris), "client_name": "Claude Code", **extra},
    )


def authorize_params(client_id, verifier, **extra):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": LOOPBACK,
        "code_challenge": s256(verifier),
        "code_challenge_method": "S256",
        "state": "client-state",
        "scope": "mcp.read mcp.write",
        "resource": RESOURCE,
    }
    params.update(extra)
    return {k: v for k, v in params.items() if v is not None}


def test_sealing_roundtrip_and_attacks():
    keys = parse_keys(generate_key("k2") + "," + generate_key("k1"))
    sealer = Sealer(keys, "https://mcp.contoso.com")
    blob = sealer.seal("code", {"a": 1}, 60)
    assert sealer.unseal("code", blob)["a"] == 1
    with pytest.raises(SealError):
        sealer.unseal("client", blob)  # purpose binding
    with pytest.raises(SealError):
        sealer.unseal("code", blob[:-4] + "AAAA")
    with pytest.raises(SealError):
        Sealer(keys, "https://other.example").unseal("code", blob)  # issuer binding
    old = Sealer([keys[1]], "https://mcp.contoso.com").seal("code", {"a": 2}, 60)
    assert sealer.unseal("code", old)["a"] == 2  # rotation: old key still decrypts
    expired = Sealer(keys, "https://mcp.contoso.com", clock=lambda: 0).seal(
        "code", {}, 1
    )
    with pytest.raises(SealError, match="expired"):
        sealer.unseal("code", expired)
    for bad in ("", "v2.k1.xx", "v1.zz.AAAA", "v1.k1.!!"):
        with pytest.raises(SealError):
            sealer.unseal("code", bad)


def test_redirect_policy():
    assert redirect_allowed("https://vscode.dev/redirect")
    assert redirect_allowed("http://localhost:5555/callback")
    assert redirect_allowed("http://[::1]:1/cb")
    assert not redirect_allowed("https://evil.example/cb")
    assert not redirect_allowed("http://127.0.0.1/cb#frag")
    assert not redirect_allowed("cursor://anysphere.cursor-mcp/oauth/callback")
    assert redirect_allowed(
        "cursor://anysphere.cursor-mcp/oauth/callback",
        ["cursor://anysphere.cursor-mcp/oauth/callback"],
    )
    assert redirect_matches("http://127.0.0.1:9999/callback", LOOPBACK)  # port ignored
    assert not redirect_matches("http://127.0.0.1:9999/other", LOOPBACK)


def test_registration(proxy):
    client, _ = proxy
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["token_endpoint_auth_method"] == "none"
    assert r.headers["cache-control"] == "no-store"
    assert (
        register(client, uris=["https://evil.example/cb"]).json()["error"]
        == "invalid_redirect_uri"
    )
    assert (
        register(client, token_endpoint_auth_method="client_secret_basic").status_code
        == 400
    )
    assert register(client, grant_types=["password"]).status_code == 400
    assert (
        client.post(
            "/oauth/register", content=b"x", headers={"content-type": "text/plain"}
        ).status_code
        == 400
    )
    assert client.get("/oauth/register").status_code == 405


def test_authorize_rejects_bad_client_without_redirect(proxy):
    client, _ = proxy
    r = client.get(
        "/oauth/authorize",
        params={"client_id": "junk", "redirect_uri": LOOPBACK},
        follow_redirects=False,
    )
    assert r.status_code == 400 and "location" not in r.headers
    cid = register(client).json()["client_id"]
    r = client.get(
        "/oauth/authorize",
        params={"client_id": cid, "redirect_uri": "http://127.0.0.1:1/elsewhere"},
        follow_redirects=False,
    )
    assert r.status_code == 400


@pytest.mark.parametrize(
    ("extra", "error"),
    [
        ({"code_challenge": None}, "invalid_request"),
        ({"code_challenge_method": "plain"}, "invalid_request"),
        ({"code_challenge": "short"}, "invalid_request"),
        ({"response_type": "token"}, "unsupported_response_type"),
        ({"resource": "https://other.example/mcp"}, "invalid_target"),
        ({"scope": "admin.everything"}, "invalid_scope"),
    ],
)
def test_authorize_errors_redirect_with_iss(proxy, extra, error):
    client, _ = proxy
    cid = register(client).json()["client_id"]
    r = client.get(
        "/oauth/authorize",
        params=authorize_params(cid, "v" * 43, **extra),
        follow_redirects=False,
    )
    assert r.status_code == 303
    q = parse_qs(urlsplit(r.headers["location"]).query)
    assert q["error"] == [error]
    assert q["iss"] == ["https://mcp.contoso.com"] and q["state"] == ["client-state"]


def full_flow(client, idp, rsa_key, verifier=None):
    verifier = verifier or secrets.token_urlsafe(48)
    cid = register(client).json()["client_id"]
    r = client.get("/oauth/authorize", params=authorize_params(cid, verifier))
    assert r.status_code == 200
    assert r.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert "Claude Code" in r.text
    txn = r.text.split("name='txn' value='")[1].split("'")[0]
    r = client.post(
        "/oauth/authorize",
        data={"txn": txn, "action": "approve"},
        headers={"origin": "https://mcp.contoso.com"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    up = urlsplit(r.headers["location"])
    upq = parse_qs(up.query)
    assert up.netloc == "login.microsoftonline.com"
    assert upq["code_challenge_method"] == ["S256"]
    assert "resource" not in upq  # never forwarded to Entra (AADSTS9010010)
    assert "offline_access" in upq["scope"][0] and "/mcp.write" in upq["scope"][0]
    r = client.get(
        "/oauth/callback",
        params={"code": "entra-code", "state": upq["state"][0]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    cb = parse_qs(urlsplit(r.headers["location"]).query)
    assert cb["state"] == ["client-state"] and cb["iss"] == ["https://mcp.contoso.com"]
    idp.token_responses.append(
        (
            200,
            {
                "access_token": mint(entra_v2_claims(), rsa_key),
                "expires_in": 3599,
                "refresh_token": "entra-rt",
                "token_type": "Bearer",
            },
        )
    )
    return cid, verifier, cb["code"][0]


def test_full_authorization_code_flow(proxy, rsa_key):
    client, idp = proxy
    cid, verifier, code = full_flow(client, idp, rsa_key)
    r = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": cid,
            "redirect_uri": LOOPBACK,
            "code_verifier": verifier,
            "resource": RESOURCE,
        },
    )
    assert r.status_code == 200, r.text
    tok = r.json()
    assert tok["token_type"] == "Bearer" and tok["scope"] == "mcp.read mcp.write"
    assert r.headers["cache-control"] == "no-store"
    sent = idp.token_requests[-1]
    assert sent["code"] == "entra-code" and sent["client_secret"] == "secret"
    assert "code_verifier" in sent
    # the returned Entra token is accepted by /mcp
    assert (
        client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {tok['access_token']}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        ).status_code
        == 200
    )
    # refresh with rotation
    idp.token_responses.append(
        (
            200,
            {
                "access_token": mint(entra_v2_claims(), rsa_key),
                "refresh_token": "entra-rt-2",
            },
        )
    )
    r = client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tok["refresh_token"],
            "client_id": cid,
        },
    )
    assert (
        r.status_code == 200 and idp.token_requests[-1]["refresh_token"] == "entra-rt"
    )
    r = client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tok["refresh_token"],
            "client_id": "someone-else",
        },
    )
    assert r.json()["error"] == "invalid_grant"


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("code_verifier", "x" * 43, "invalid_grant"),
        ("code_verifier", "short", "invalid_request"),
        ("redirect_uri", "http://127.0.0.1:1/other", "invalid_grant"),
        ("client_id", "other", "invalid_grant"),
        ("code", "v1.k1.garbage", "invalid_grant"),
        ("resource", "https://other.example/mcp", "invalid_target"),
        ("grant_type", "password", "unsupported_grant_type"),
    ],
)
def test_token_errors(proxy, rsa_key, field, value, error):
    client, idp = proxy
    cid, verifier, code = full_flow(client, idp, rsa_key)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": cid,
        "redirect_uri": LOOPBACK,
        "code_verifier": verifier,
        field: value,
    }
    r = client.post("/oauth/token", data=data)
    assert r.status_code == 400 and r.json()["error"] == error


def test_upstream_code_reuse_and_outage(proxy, rsa_key):
    client, idp = proxy
    cid, verifier, code = full_flow(client, idp, rsa_key)
    idp.token_responses[-1] = (
        400,
        {
            "error": "invalid_grant",
            "error_description": "AADSTS54005: code already redeemed",
        },
    )
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": cid,
        "redirect_uri": LOOPBACK,
        "code_verifier": verifier,
    }
    assert client.post("/oauth/token", data=data).json()["error"] == "invalid_grant"
    idp.token_responses.append((500, {}))
    assert client.post("/oauth/token", data=data).status_code == 503


def test_foreign_upstream_token_is_rejected(proxy, rsa_key):
    client, idp = proxy
    cid, verifier, code = full_flow(client, idp, rsa_key)
    idp.token_responses[-1] = (
        200,
        {"access_token": mint(entra_v2_claims(aud="other"), rsa_key)},
    )
    r = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": cid,
            "redirect_uri": LOOPBACK,
            "code_verifier": verifier,
        },
    )
    assert r.json()["error"] == "invalid_grant"


def test_consent_csrf_and_deny(proxy):
    client, _ = proxy
    cid = register(client).json()["client_id"]
    r = client.get("/oauth/authorize", params=authorize_params(cid, "v" * 43))
    txn = r.text.split("name='txn' value='")[1].split("'")[0]
    cross = client.post(
        "/oauth/authorize",
        data={"txn": txn, "action": "approve"},
        headers={"origin": "https://evil.example"},
    )
    assert cross.status_code == 403
    client.cookies.clear()
    nocookie = client.post("/oauth/authorize", data={"txn": txn, "action": "approve"})
    assert nocookie.status_code == 403
    r = client.get("/oauth/authorize", params=authorize_params(cid, "v" * 43))
    txn = r.text.split("name='txn' value='")[1].split("'")[0]
    deny = client.post(
        "/oauth/authorize", data={"txn": txn, "action": "deny"}, follow_redirects=False
    )
    assert parse_qs(urlsplit(deny.headers["location"]).query)["error"] == [
        "access_denied"
    ]


def test_callback_binding_and_idp_error(proxy):
    client, _ = proxy
    assert client.get("/oauth/callback", params={"state": "junk"}).status_code == 400
    cid = register(client).json()["client_id"]
    r = client.get("/oauth/authorize", params=authorize_params(cid, "v" * 43))
    txn = r.text.split("name='txn' value='")[1].split("'")[0]
    r = client.post(
        "/oauth/authorize",
        data={"txn": txn, "action": "approve"},
        follow_redirects=False,
    )
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    r = client.get(
        "/oauth/callback",
        params={"error": "access_denied", "state": state},
        follow_redirects=False,
    )
    assert parse_qs(urlsplit(r.headers["location"]).query)["error"] == ["access_denied"]
    client.cookies.clear()
    assert (
        client.get("/oauth/callback", params={"code": "c", "state": state}).status_code
        == 400
    )


def test_client_credentials_variants(tmp_path, rsa_key):
    from datetime import UTC, datetime, timedelta

    import jwt
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import NameOID

    from mcp_core.auth.proxy.upstream import UpstreamClient

    fed = tmp_path / "token"
    fed.write_text("federated-assertion\n")
    up = UpstreamClient(
        proxy_settings(
            MCP_AUTH_ENTRA_CLIENT_SECRET="", AZURE_FEDERATED_TOKEN_FILE=str(fed)
        )
    )
    assert up.client_auth()["client_assertion"] == "federated-assertion"

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "uml-mcp")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(rsa_key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .sign(rsa_key, hashes.SHA256())
    )
    key_pem = rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    up = UpstreamClient(
        proxy_settings(
            MCP_AUTH_ENTRA_CLIENT_SECRET="",
            MCP_AUTH_ENTRA_CLIENT_CERTIFICATE=cert.public_bytes(
                serialization.Encoding.PEM
            ).decode(),
            MCP_AUTH_ENTRA_CLIENT_PRIVATE_KEY=key_pem,
        )
    )
    assertion = up.client_auth()["client_assertion"]
    header = jwt.get_unverified_header(assertion)
    assert "x5t#S256" in header
    claims = jwt.decode(
        assertion,
        rsa_key.public_key(),
        algorithms=["PS256"],
        audience=up.token_endpoint,
    )
    assert claims["iss"] == claims["sub"]


def test_admin_builtin_client_only_when_admin_enabled(mock_idp):
    app = build_auth_app(proxy_settings(MCP_ADMIN_UI="true"), http=mock_idp.client())
    c = TestClient(app, base_url="https://mcp.contoso.com")
    params = {
        "response_type": "code",
        "client_id": "uml-mcp-admin",
        "redirect_uri": "https://mcp.contoso.com/admin/",
        "code_challenge": s256("v" * 43),
        "code_challenge_method": "S256",
    }
    assert c.get("/oauth/authorize", params=params).status_code == 200
    app2 = build_auth_app(proxy_settings(), http=mock_idp.client())
    c2 = TestClient(app2, base_url="https://mcp.contoso.com")
    assert c2.get("/oauth/authorize", params=params).status_code == 400
