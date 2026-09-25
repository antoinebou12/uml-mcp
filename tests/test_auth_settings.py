"""Enterprise auth configuration: env + JSON precedence, validation, Entra presets."""

from __future__ import annotations

import json

import pytest

from mcp_core.auth import AuthConfigError, auth_mode_from_env, auth_requested
from mcp_core.auth.settings import load_auth_settings, reset_auth_settings_cache
from tests.fixtures_auth import API_CLIENT, ENC_KEY, RESOURCE, TENANT, auth_env


def test_default_mode_is_none():
    assert auth_mode_from_env({}) == "none"
    assert auth_requested({}) is False
    assert load_auth_settings({}).enabled is False


def test_unknown_mode_fails_closed():
    with pytest.raises(AuthConfigError, match="Unknown MCP_AUTH_MODE"):
        auth_mode_from_env({"MCP_AUTH_MODE": "maybe"})


def test_mode_can_come_from_json_file(tmp_path):
    cfg = tmp_path / "auth.json"
    cfg.write_text(json.dumps({"mode": "jwt"}))
    assert auth_mode_from_env({"MCP_AUTH_CONFIG_FILE": str(cfg)}) == "jwt"
    with pytest.raises(AuthConfigError):
        auth_mode_from_env({"MCP_AUTH_CONFIG_FILE": str(tmp_path / "missing.json")})
    bad = tmp_path / "bad.json"
    bad.write_text("[1]")
    with pytest.raises(AuthConfigError):
        auth_mode_from_env({"MCP_AUTH_CONFIG_FILE": str(bad)})


def test_entra_preset_derivations(settings_factory):
    s = settings_factory()
    assert s.effective_issuers == [f"https://login.microsoftonline.com/{TENANT}/v2.0"]
    assert s.effective_audiences == [API_CLIENT, f"api://{API_CLIENT}", RESOURCE]
    assert s.effective_jwks_uri.endswith(f"/{TENANT}/discovery/v2.0/keys")
    assert s.effective_scope_prefix == f"api://{API_CLIENT}/"
    assert (
        s.prm_url_mcp
        == "https://mcp.contoso.com/.well-known/oauth-protected-resource/mcp"
    )
    assert (
        s.prm_url_root == "https://mcp.contoso.com/.well-known/oauth-protected-resource"
    )
    assert s.effective_authorization_servers == [
        f"https://login.microsoftonline.com/{TENANT}/v2.0"
    ]


def test_v1_opt_in_and_sovereign_cloud(settings_factory):
    s = settings_factory(
        MCP_AUTH_ENTRA_TOKEN_VERSIONS="1,2", MCP_AUTH_ENTRA_CLOUD="usgov"
    )
    assert f"https://login.microsoftonline.us/{TENANT}/v2.0" in s.effective_issuers
    assert f"https://sts.windows.net/{TENANT}/" in s.effective_issuers


def test_json_file_then_env_precedence(tmp_path):
    cfg = tmp_path / "auth.json"
    cfg.write_text(
        json.dumps(
            {
                "mode": "jwt",
                "resource_url": "https://from-file.example/mcp",
                "read_scope": "file.read",
                "entra": {"tenant_id": TENANT, "client_id": API_CLIENT},
            }
        )
    )
    s = load_auth_settings(
        {"MCP_AUTH_CONFIG_FILE": str(cfg), "MCP_AUTH_RESOURCE_URL": RESOURCE}
    )
    assert s.resource_url == RESOURCE  # env wins
    assert s.read_scope == "file.read"  # file beats default


def test_secrets_are_rejected_in_json(tmp_path):
    cfg = tmp_path / "auth.json"
    cfg.write_text(json.dumps({"mode": "jwt", "proxy": {"client_secret": "x"}}))
    with pytest.raises(AuthConfigError, match="secrets must not be stored"):
        load_auth_settings({"MCP_AUTH_CONFIG_FILE": str(cfg)})


def test_secret_file_variants(tmp_path, settings_factory):
    secret = tmp_path / "secret"
    secret.write_text("s3cr3t\n")
    keys = tmp_path / "keys"
    keys.write_text(ENC_KEY)
    s = settings_factory(
        MCP_AUTH_MODE="entra-proxy",
        MCP_AUTH_ENTRA_CLIENT_SECRET_FILE=str(secret),
        MCP_AUTH_PROXY_ENCRYPTION_KEYS_FILE=str(keys),
    )
    assert s.proxy.client_secret.get_secret_value() == "s3cr3t"
    assert s.proxy.credential_kind == "secret"
    red = s.redacted_dict()
    assert red["proxy"]["client_secret"] == "***set***"
    assert "s3cr3t" not in json.dumps(red)
    assert s.effective_authorization_servers == ["https://mcp.contoso.com"]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"MCP_AUTH_ALGORITHMS": "HS256"}, "HMAC"),
        ({"MCP_AUTH_ALGORITHMS": "none"}, "never accepted"),
        ({"MCP_AUTH_RESOURCE_URL": "http://mcp.contoso.com/mcp"}, "https"),
        ({"MCP_AUTH_RESOURCE_URL": ""}, "resource_url is required"),
        ({"MCP_AUTH_ENTRA_TENANT_ID": "common"}, "allowed_tenants"),
        ({"MCP_AUTH_ENTRA_TENANT_ID": "not-a-guid"}, "GUID"),
        ({"MCP_AUTH_ENTRA_TOKEN_VERSIONS": "3"}, "token_versions"),
        ({"MCP_AUTH_MODE": "entra-proxy"}, "client credential"),
        ({"MCP_AUTH_LEEWAY_SECONDS": "abc"}, "invalid MCP_AUTH"),
        ({"MCP_AUTH_UNKNOWN": "x", "MCP_AUTH_LEEWAY_SECONDS": "9999"}, "leeway"),
    ],
)
def test_invalid_configs_fail_closed(settings_factory, overrides, message):
    with pytest.raises(AuthConfigError, match=message):
        settings_factory(**overrides)


def test_proxy_requires_valid_encryption_key(settings_factory):
    with pytest.raises(AuthConfigError, match="32 bytes"):
        settings_factory(
            MCP_AUTH_MODE="entra-proxy",
            MCP_AUTH_ENTRA_CLIENT_SECRET="x",
            MCP_AUTH_PROXY_ENCRYPTION_KEYS="k1:abcd",
        )


def test_loopback_http_allowed_for_dev(settings_factory):
    s = settings_factory(MCP_AUTH_RESOURCE_URL="http://127.0.0.1:8000/mcp")
    assert s.origin == "http://127.0.0.1:8000"


def test_generic_oidc_without_entra():
    s = load_auth_settings(
        {
            "MCP_AUTH_MODE": "jwt",
            "MCP_AUTH_RESOURCE_URL": RESOURCE,
            "MCP_AUTH_ISSUERS": '["https://idp.example/realms/acme"]',
            "MCP_AUTH_JWKS_URI": "https://idp.example/realms/acme/certs",
            "MCP_AUTH_ALGORITHMS": "RS256,ES256",
        }
    )
    assert s.effective_authorization_servers == ["https://idp.example/realms/acme"]
    assert s.effective_audiences == [RESOURCE]
    assert s.effective_scope_prefix == ""
    with pytest.raises(AuthConfigError, match="no key source"):
        load_auth_settings(
            {
                "MCP_AUTH_MODE": "jwt",
                "MCP_AUTH_RESOURCE_URL": RESOURCE,
                "MCP_AUTH_ISSUERS": "https://idp.example",
            }
        )


def test_cached_settings_reset(monkeypatch):
    from mcp_core.auth.settings import get_auth_settings

    for k, v in auth_env().items():
        monkeypatch.setenv(k, v)
    reset_auth_settings_cache()
    try:
        assert get_auth_settings().mode == "jwt"
    finally:
        reset_auth_settings_cache()
