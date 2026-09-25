"""HTTP contract: 400 / 401 / 403 / 404 / 405 / 503 separation and challenges."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from mcp_core.auth.errors import AuthError, build_www_authenticate, sanitize_description
from mcp_core.auth.policy import Policy, parse_jsonrpc_body
from tests.fixtures_auth import (
    API_CLIENT,
    FAKE_TOOLS,
    GRAPH,
    build_auth_app,
    entra_app_claims,
    entra_v2_claims,
    mint,
    rpc,
)

PRM_MCP = "https://mcp.contoso.com/.well-known/oauth-protected-resource/mcp"
READ = f"api://{API_CLIENT}/mcp.read"
WRITE = f"api://{API_CLIENT}/mcp.write"


@pytest.fixture
def client(settings_factory, mock_idp):
    app = build_auth_app(settings_factory(), http=mock_idp.client())
    return TestClient(app)


@pytest.fixture
def tokens(rsa_key):
    return {
        "rw": mint(entra_v2_claims(), rsa_key),
        "read": mint(entra_v2_claims(scp="mcp.read"), rsa_key),
        "graph": mint(entra_v2_claims(aud=GRAPH), rsa_key),
        "admin": mint(entra_v2_claims(roles=["MCP.Admin"]), rsa_key),
        "app_read": mint(entra_app_claims(roles=("MCP.Read.All",)), rsa_key),
    }


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_missing_token_401_says_what_is_missing(client):
    r = client.post("/mcp", json=rpc("tools/list"))
    assert r.status_code == 401
    www = r.headers["www-authenticate"]
    assert www.startswith('Bearer realm="uml-mcp"')
    assert "error=" not in www  # RFC 6750 §3.1: no error when no credentials
    assert f'resource_metadata="{PRM_MCP}"' in www
    assert f'scope="{READ} {WRITE}"' in www
    body = r.json()
    assert body["reason"] == "token_missing"
    assert body["missing"] == ["Authorization: Bearer <access_token>"]
    assert r.headers["cache-control"] == "no-store"


def test_unauthenticated_get_and_subpaths_also_challenge(client):
    for method, path in (
        ("GET", "/mcp"),
        ("DELETE", "/mcp/"),
        ("PUT", "/mcp"),
        ("POST", "/mcp/x"),
    ):
        assert client.request(method, path).status_code == 401, (method, path)


def test_unrelated_paths_never_challenge(client):
    assert client.get("/mcpx").status_code == 404
    assert "www-authenticate" not in client.get("/mcpx").headers
    assert client.get("/nope").status_code == 404
    assert client.get("/health").status_code == 200
    assert client.get("/generate_diagram").status_code == 405  # REST GET not protected


def test_unsupported_scheme(client):
    r = client.post("/mcp", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert r.status_code == 401 and r.json()["reason"] == "unsupported_auth_scheme"


def test_token_in_query_is_400(client, tokens):
    r = client.post(f"/mcp?access_token={tokens['rw']}", json=rpc("ping"))
    assert r.status_code == 400
    assert 'error="invalid_request"' in r.headers["www-authenticate"]
    assert tokens["rw"] not in r.text


def test_invalid_token_401(client, tokens):
    r = client.post("/mcp", headers=bearer(tokens["graph"]), json=rpc("ping"))
    assert r.status_code == 401
    www = r.headers["www-authenticate"]
    assert 'error="invalid_token"' in www and "error_description=" in www
    assert r.json()["reason"] == "invalid_audience"


def test_read_token_can_list_but_not_generate(client, tokens):
    ok = client.post("/mcp", headers=bearer(tokens["read"]), json=rpc("tools/list"))
    assert ok.status_code == 200
    ok = client.post(
        "/mcp",
        headers=bearer(tokens["read"]),
        json=rpc("tools/call", name="validate_uml", arguments={}),
    )
    assert ok.status_code == 200
    r = client.post(
        "/mcp",
        headers=bearer(tokens["read"]),
        json=rpc("tools/call", name="generate_uml", arguments={}),
    )
    assert r.status_code == 403
    www = r.headers["www-authenticate"]
    assert 'error="insufficient_scope"' in www
    assert f'scope="{READ} {WRITE}"' in www
    assert f'resource_metadata="{PRM_MCP}"' in www
    body = r.json()
    assert body["required"] == "write" and body["granted"] == ["read"]
    assert "generate_uml" in body["error_description"]


def test_unknown_tool_and_method_require_write(client, tokens):
    for payload in (rpc("tools/call", name="mystery"), rpc("custom/method")):
        r = client.post("/mcp", headers=bearer(tokens["read"]), json=payload)
        assert r.status_code == 403


def test_batch_takes_highest_permission(client, tokens):
    batch = [rpc("tools/list"), rpc("tools/call", name="generate_uml")]
    r = client.post("/mcp", headers=bearer(tokens["read"]), json=batch)
    assert r.status_code == 403


def test_write_token_passes_and_token_is_stripped(client, tokens):
    body = json.dumps(
        rpc("tools/call", name="generate_uml", arguments={"code": "a->b"})
    )
    r = client.post(
        "/mcp",
        headers={**bearer(tokens["rw"]), "content-type": "application/json"},
        content=body,
    )
    assert r.status_code == 200
    seen = client.app.state.fake_mcp.seen[-1]
    assert seen["body"] == body.encode()  # replayed intact
    assert "authorization" not in seen["headers"]  # no token passthrough
    assert seen["path"] == "/"  # /mcp rewritten to the mount root, no 307
    assert seen["principal"].permissions == {"read", "write"}


def test_read_caller_body_parsing_is_strict(client, tokens):
    h = {**bearer(tokens["read"]), "content-type": "text/plain"}
    dup = '{"jsonrpc":"2.0","id":1,"method":"tools/list","method":"tools/call"}'
    assert client.post("/mcp", headers=h, content=dup).status_code == 400
    # parsed regardless of content-type: a text/plain tools/call is still checked
    sneaky = json.dumps(rpc("tools/call", name="generate_uml"))
    assert client.post("/mcp", headers=h, content=sneaky).status_code == 403
    gz = {**bearer(tokens["read"]), "content-encoding": "gzip"}
    assert client.post("/mcp", headers=gz, content=b"x").status_code == 415
    assert client.post("/mcp", headers=h, content=b"\xef\xbb\xbf{}").status_code == 400
    assert client.post("/mcp", headers=h, content=b"[]").status_code == 400
    mismatch = {**h, "mcp-method": "tools/list"}
    assert client.post("/mcp", headers=mismatch, content=sneaky).status_code == 400


def test_body_limit(settings_factory, mock_idp, tokens):
    app = build_auth_app(
        settings_factory(MCP_AUTH_MAX_BODY_BYTES="100"), http=mock_idp.client()
    )
    c = TestClient(app)
    r = c.post("/mcp", headers=bearer(tokens["read"]), content=b"x" * 500)
    assert r.status_code == 413


def test_authenticated_unknown_subpath_and_method(client, tokens):
    assert client.post("/mcp/x", headers=bearer(tokens["rw"])).status_code == 404
    assert client.put("/mcp", headers=bearer(tokens["rw"])).status_code == 405


def test_options_preflight_not_authenticated(client):
    r = client.options(
        "/mcp",
        headers={
            "Origin": "https://app.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200


def test_cors_exposes_www_authenticate(client):
    r = client.post("/mcp", headers={"Origin": "https://app.example"})
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers.get("access-control-expose-headers", "")


def test_rest_endpoints_protected(client, tokens):
    r = client.post("/generate_diagram", json={})
    assert r.status_code == 401
    assert 'oauth-protected-resource"' in r.headers["www-authenticate"]  # root PRM
    assert (
        client.post("/generate_diagram", headers=bearer(tokens["read"])).status_code
        == 403
    )
    r = client.post("/generate_diagram", headers=bearer(tokens["rw"]))
    assert r.status_code == 200 and r.json()["auth"] is False
    assert (
        client.post("/kroki_encode", headers=bearer(tokens["read"])).status_code == 200
    )


def test_rest_protection_can_be_disabled(settings_factory, mock_idp):
    c = TestClient(
        build_auth_app(
            settings_factory(MCP_AUTH_PROTECT_REST="false"), http=mock_idp.client()
        )
    )
    assert c.post("/generate_diagram").status_code == 200


def test_app_only_role_denial_names_role(client, tokens):
    r = client.post(
        "/mcp",
        headers=bearer(tokens["app_read"]),
        json=rpc("tools/call", name="generate_uml"),
    )
    assert r.status_code == 403 and "MCP.Write" in r.json()["error_description"]


def test_idp_down_is_503(client, tokens, mock_idp):
    mock_idp.fail = True
    r = client.post("/mcp", headers=bearer(tokens["rw"]), json=rpc("ping"))
    assert r.status_code == 503 and r.headers["retry-after"] == "30"
    assert "www-authenticate" not in r.headers


def test_denials_are_audited_without_tokens(client, tokens):
    client.post("/mcp", headers=bearer(tokens["graph"]))
    events = client.app.state.runtime.audit.snapshot()
    assert events[0]["reason"] == "invalid_audience"
    assert tokens["graph"] not in json.dumps(events)


def test_multiple_authorization_headers(client, tokens):
    headers = [
        ("authorization", f"Bearer {tokens['rw']}"),
        ("authorization", "Bearer x"),
    ]
    r = client.post("/mcp", headers=headers)
    assert r.status_code == 400


def test_default_scope_strategy(settings_factory, mock_idp):
    c = TestClient(
        build_auth_app(
            settings_factory(MCP_AUTH_SCOPE_STRATEGY="default"), http=mock_idp.client()
        )
    )
    www = c.post("/mcp").headers["www-authenticate"]
    assert f'scope="api://{API_CLIENT}/.default"' in www


def test_challenge_builder_and_sanitizer():
    value = build_www_authenticate(
        None, resource_metadata="https://x/r", scope=["a", "b"]
    )
    assert (
        value == 'Bearer realm="uml-mcp", scope="a b", resource_metadata="https://x/r"'
    )
    cleaned = sanitize_description(
        'bad "quote" \\ eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxIn0.sig'
    )
    assert '"' not in cleaned and "\\" not in cleaned and "eyJ" not in cleaned


def test_policy_and_jsonrpc_parsing(settings_factory):
    s = settings_factory(
        MCP_AUTH_TOOL_PERMISSIONS='{"generate_uml": "read"}',
        MCP_AUTH_ADVERTISE_OFFLINE_ACCESS="true",
    )
    policy = Policy(s, FAKE_TOOLS)
    assert policy.tool_permission("generate_uml") == "read"
    assert policy.tool_permission("generate_uml_image") == "write"
    assert (
        policy.required_for_message({"method": "notifications/initialized"}) == "read"
    )
    assert policy.required_for_message({"result": {}}) == "read"
    assert policy.advertised_scopes()[-1] == "offline_access"
    assert parse_jsonrpc_body(b"  ") is None
    with pytest.raises(AuthError):
        parse_jsonrpc_body(b'{"method": 3}')
    with pytest.raises(AuthError):
        parse_jsonrpc_body(b'{"method": "tools/call", "params": {}}')
    with pytest.raises(AuthError):
        parse_jsonrpc_body(b"[1]")
    assert policy.required_for_rest("HEAD", "/ag-ui/events/abc") == "read"
