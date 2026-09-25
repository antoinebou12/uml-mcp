"""RFC 9728 protected resource metadata, RFC 8414 AS metadata and preflight."""

from __future__ import annotations

from fastapi.testclient import TestClient
from mcp.shared.auth import OAuthMetadata, ProtectedResourceMetadata

from mcp_core.auth.integration import build_auth_runtime
from mcp_core.auth.preflight import metadata_urls, run_preflight
from mcp_core.auth.settings import load_auth_settings
from tests.fixtures_auth import API_CLIENT, ENC_KEY, RESOURCE, TENANT, build_auth_app


def test_prm_documents(settings_factory, mock_idp):
    c = TestClient(build_auth_app(settings_factory(), http=mock_idp.client()))
    r = c.get(
        "/.well-known/oauth-protected-resource/mcp", headers={"Host": "evil.example"}
    )
    assert r.status_code == 200
    doc = r.json()
    ProtectedResourceMetadata.model_validate(doc)
    assert doc["resource"] == RESOURCE  # never derived from the Host header
    assert doc["authorization_servers"] == [
        f"https://login.microsoftonline.com/{TENANT}/v2.0"
    ]
    assert doc["scopes_supported"] == [
        f"api://{API_CLIENT}/mcp.read",
        f"api://{API_CLIENT}/mcp.write",
    ]
    assert "offline_access" not in doc["scopes_supported"]  # SEP-2207 default
    assert doc["bearer_methods_supported"] == ["header"]
    assert r.headers["access-control-allow-origin"] == "*"
    root = c.get("/.well-known/oauth-protected-resource").json()
    assert root["resource"] == "https://mcp.contoso.com/"
    assert c.head("/.well-known/oauth-protected-resource/mcp").status_code == 200
    assert c.post("/.well-known/oauth-protected-resource/mcp").status_code == 405
    assert c.get("/.well-known/oauth-protected-resource/other").status_code == 404
    assert c.get("/.well-known/oauth-authorization-server").status_code == 404
    assert c.get("/.well-known/openid-configuration").status_code == 404
    assert c.get("/oauth/register").status_code == 404
    assert c.get("/admin").status_code == 404


def proxy_settings(**extra):
    env = {
        "MCP_AUTH_MODE": "entra-proxy",
        "MCP_AUTH_RESOURCE_URL": RESOURCE,
        "MCP_AUTH_ENTRA_TENANT_ID": TENANT,
        "MCP_AUTH_ENTRA_CLIENT_ID": API_CLIENT,
        "MCP_AUTH_ENTRA_CLIENT_SECRET": "secret",
        "MCP_AUTH_PROXY_ENCRYPTION_KEYS": ENC_KEY,
        "MCP_AUTH_PREFLIGHT": "off",
    }
    env.update(extra)
    return load_auth_settings(env)


def test_proxy_as_metadata(mock_idp):
    c = TestClient(build_auth_app(proxy_settings(), http=mock_idp.client()))
    prm = c.get("/.well-known/oauth-protected-resource/mcp").json()
    assert prm["authorization_servers"] == ["https://mcp.contoso.com"]
    assert prm["scopes_supported"] == ["mcp.read", "mcp.write"]
    doc = c.get("/.well-known/oauth-authorization-server").json()
    OAuthMetadata.model_validate(doc)
    assert doc["issuer"] == "https://mcp.contoso.com"
    assert doc["code_challenge_methods_supported"] == ["S256"]
    assert doc["token_endpoint_auth_methods_supported"] == ["none"]
    assert doc["registration_endpoint"] == "https://mcp.contoso.com/oauth/register"
    assert doc["authorization_response_iss_parameter_supported"] is True
    assert "offline_access" in doc["scopes_supported"]


def test_metadata_discovery_order():
    assert metadata_urls("https://idp.example/tenant1") == [
        "https://idp.example/.well-known/oauth-authorization-server/tenant1",
        "https://idp.example/.well-known/openid-configuration/tenant1",
        "https://idp.example/tenant1/.well-known/openid-configuration",
    ]
    assert metadata_urls("https://idp.example")[0].endswith(
        "oauth-authorization-server"
    )


async def test_preflight_entra_warning_and_generic_s256(settings_factory, mock_idp):
    rt = build_auth_runtime(
        settings_factory(), http=mock_idp.client(), tool_registry={}
    )
    report = await run_preflight(rt)
    assert report.checks[0]["status"] == "warning"
    assert "entra-proxy" in report.checks[0]["detail"]

    generic = load_auth_settings(
        {
            "MCP_AUTH_MODE": "jwt",
            "MCP_AUTH_RESOURCE_URL": RESOURCE,
            "MCP_AUTH_ISSUERS": "https://idp.example",
            "MCP_AUTH_JWKS_URI": "https://idp.example/keys",
        }
    )
    rt = build_auth_runtime(generic, http=mock_idp.client(), tool_registry={})
    mock_idp.metadata["https://idp.example/.well-known/oauth-authorization-server"] = {
        "issuer": "https://idp.example",
        "code_challenge_methods_supported": ["plain"],
    }
    report = await run_preflight(rt)
    assert report.status == "degraded"
    mock_idp.metadata["https://idp.example/.well-known/oauth-authorization-server"][
        "code_challenge_methods_supported"
    ] = ["S256"]
    assert (await run_preflight(rt)).status == "ok"
    mock_idp.metadata.clear()
    assert (await run_preflight(rt)).status == "degraded"


async def test_strict_preflight_fails_startup(mock_idp):
    import pytest

    from mcp_core.auth.integration import compose_lifespan

    generic = load_auth_settings(
        {
            "MCP_AUTH_MODE": "jwt",
            "MCP_AUTH_RESOURCE_URL": RESOURCE,
            "MCP_AUTH_ISSUERS": "https://idp.example",
            "MCP_AUTH_JWKS_URI": "https://idp.example/keys",
            "MCP_AUTH_PREFLIGHT": "strict",
        }
    )
    rt = build_auth_runtime(generic, http=mock_idp.client(), tool_registry={})
    with pytest.raises(RuntimeError, match="preflight failed"):
        async with compose_lifespan(None, rt)(None):
            pass
