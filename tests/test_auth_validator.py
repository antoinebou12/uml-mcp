"""Token validation: Microsoft Entra v1/v2 rules, algorithm safety, JWKS behaviour."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from mcp_core.auth import errors
from mcp_core.auth.jwks import JwksCache, StaticKeySet, UnknownKeyError
from mcp_core.auth.validator import TokenValidator
from tests.fixtures_auth import (
    GRAPH,
    JWKS_URI,
    OTHER_TENANT,
    TENANT,
    VSCODE,
    entra_app_claims,
    entra_v1_claims,
    entra_v2_claims,
    jwk_for,
    mint,
    public_pem,
)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _compact(header, claims, sig: bytes | None) -> str:
    head = _b64(json.dumps(header).encode()) + "." + _b64(json.dumps(claims).encode())
    return head if sig is None else f"{head}.{_b64(sig)}"


def make_validator(settings, mock_idp):
    keys = JwksCache(JWKS_URI, http=mock_idp.client())
    return TokenValidator(settings, keys), keys


async def reason_of(validator, token):
    with pytest.raises(errors.AuthError) as exc:
        await validator.validate(token)
    return exc.value


async def test_valid_entra_v2_token(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(settings_factory(), mock_idp)
    p = await v.validate(mint(entra_v2_claims(), rsa_key))
    assert p.kind == "delegated"
    assert p.scopes == {"mcp.read", "mcp.write"}
    assert p.permissions == {"read", "write"}
    assert p.client_id == VSCODE and p.tenant_id == TENANT


async def test_audience_api_uri_and_prefixed_scopes(
    settings_factory, mock_idp, rsa_key
):
    v, _ = make_validator(settings_factory(), mock_idp)
    token = mint(
        entra_v2_claims(
            aud="api://aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", scp="mcp.read"
        ),
        rsa_key,
    )
    p = await v.validate(token)
    assert p.permissions == {"read"}


async def test_token_for_other_service_is_rejected(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(settings_factory(), mock_idp)
    err = await reason_of(v, mint(entra_v2_claims(aud=GRAPH), rsa_key))
    assert (err.status, err.reason) == (401, "invalid_audience")
    assert mock_idp.calls == {}  # rejected before any network call


async def test_v1_tokens_rejected_by_default(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(settings_factory(), mock_idp)
    err = await reason_of(v, mint(entra_v1_claims(), rsa_key))
    assert err.reason == "invalid_issuer"


async def test_v1_tokens_opt_in(settings_factory, mock_idp, rsa_key):
    s = settings_factory(MCP_AUTH_ENTRA_TOKEN_VERSIONS="1,2")
    v, _ = make_validator(s, mock_idp)
    p = await v.validate(mint(entra_v1_claims(), rsa_key))
    assert p.client_id == VSCODE and p.token_version == "1.0"


async def test_version_claim_must_be_two(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(settings_factory(), mock_idp)
    err = await reason_of(v, mint(entra_v2_claims(ver="1.0"), rsa_key))
    assert err.reason in ("token_version_not_allowed", "invalid_issuer")


async def test_cross_tenant_binding(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(settings_factory(), mock_idp)
    err = await reason_of(v, mint(entra_v2_claims(tid=OTHER_TENANT), rsa_key))
    assert err.reason == "tenant_not_allowed"


async def test_multi_tenant_allow_list(settings_factory, mock_idp, rsa_key):
    s = settings_factory(
        MCP_AUTH_ENTRA_TENANT_ID="organizations",
        MCP_AUTH_ALLOWED_TENANTS=f"{TENANT},{OTHER_TENANT}",
    )
    v, _ = make_validator(s, mock_idp)
    other_iss = f"https://login.microsoftonline.com/{OTHER_TENANT}/v2.0"
    await v.validate(mint(entra_v2_claims(tid=OTHER_TENANT, iss=other_iss), rsa_key))
    err = await reason_of(v, mint(entra_v2_claims(tid=OTHER_TENANT), rsa_key))
    assert err.reason == "invalid_issuer"  # iss/tid mismatch


@pytest.mark.parametrize(
    ("claims", "reason"),
    [
        ({"exp": int(time.time()) - 600}, "token_expired"),
        ({"nbf": int(time.time()) + 600}, "token_not_yet_valid"),
        ({"exp": None}, "missing_claim"),
        ({"nonce": "abc"}, "id_token_not_accepted"),
        ({"iss": "https://evil.example/"}, "invalid_issuer"),
    ],
)
async def test_claim_failures(settings_factory, mock_idp, rsa_key, claims, reason):
    v, _ = make_validator(settings_factory(), mock_idp)
    err = await reason_of(v, mint(entra_v2_claims(**claims), rsa_key))
    assert (err.status, err.reason) == (401, reason)


async def test_expired_within_leeway_is_ok(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(settings_factory(), mock_idp)
    await v.validate(mint(entra_v2_claims(exp=int(time.time()) - 30), rsa_key))


async def test_algorithm_attacks(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(settings_factory(), mock_idp)
    claims = entra_v2_claims()
    none_token = _compact({"alg": "none", "kid": "k1"}, claims, b"")
    assert (await reason_of(v, none_token)).reason == "unsupported_algorithm"
    # key confusion: HS256 "signed" with the RSA public key as the HMAC secret
    header = {"alg": "HS256", "kid": "k1", "typ": "JWT"}
    signing_input = _compact(header, claims, None)
    sig = hmac.new(
        public_pem(rsa_key).encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    confused = _compact(header, claims, sig)
    assert (await reason_of(v, confused)).reason == "unsupported_algorithm"
    jku = mint(claims, rsa_key, headers={"jku": "https://evil.example/keys"})
    assert (await reason_of(v, jku)).reason == "forbidden_header"


async def test_malformed_and_signature(settings_factory, mock_idp, rsa_key, rsa_key_2):
    v, _ = make_validator(settings_factory(), mock_idp)
    assert (await reason_of(v, "opaque-token")).reason == "malformed_token"
    assert (await reason_of(v, "a.b.c")).reason == "malformed_token"
    assert (await reason_of(v, "x" * 20000)).status == 400
    forged = mint(entra_v2_claims(), rsa_key_2)  # right kid, wrong key
    assert (await reason_of(v, forged)).reason == "invalid_signature"
    nokid = mint(entra_v2_claims(), rsa_key, kid=None)
    assert (await reason_of(v, nokid)).reason == "missing_kid"


async def test_unknown_kid_refetch_is_throttled(settings_factory, mock_idp, rsa_key):
    v, keys = make_validator(settings_factory(), mock_idp)
    await v.validate(mint(entra_v2_claims(), rsa_key))
    for i in range(5):
        err = await reason_of(v, mint(entra_v2_claims(), rsa_key, kid=f"rand{i}"))
        assert err.reason == "unknown_signing_key"
    assert keys.fetch_count <= 2  # initial + at most one forced refresh


async def test_key_rotation_picked_up(settings_factory, mock_idp, rsa_key, rsa_key_2):
    v, keys = make_validator(settings_factory(), mock_idp)
    await v.validate(mint(entra_v2_claims(), rsa_key))
    mock_idp.jwks["keys"].append(jwk_for(rsa_key_2, "k2"))
    keys._last_attempt = None  # rotation happened long ago
    p = await v.validate(mint(entra_v2_claims(), rsa_key_2, kid="k2"))
    assert p.subject


async def test_idp_outage_fails_closed_then_serves_stale(
    settings_factory, mock_idp, rsa_key
):
    v, keys = make_validator(settings_factory(), mock_idp)
    mock_idp.fail = True
    err = await reason_of(v, mint(entra_v2_claims(), rsa_key))
    assert (err.status, err.reason) == (503, "jwks_unavailable")
    mock_idp.fail = False
    await v.validate(mint(entra_v2_claims(), rsa_key))
    mock_idp.fail = True
    keys._fetched_at -= 7200  # TTL expired, IdP down => stale keys still serve
    await v.validate(mint(entra_v2_claims(), rsa_key))
    assert keys.health()["status"] == "degraded"


async def test_client_allow_list(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(
        settings_factory(MCP_AUTH_ALLOWED_CLIENT_IDS=VSCODE), mock_idp
    )
    await v.validate(mint(entra_v2_claims(), rsa_key))
    err = await reason_of(
        v, mint(entra_v2_claims(azp="12345678-1234-1234-1234-123456789012"), rsa_key)
    )
    assert err.reason == "client_not_allowed"


async def test_app_only_roles_and_user_roles(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(settings_factory(), mock_idp)
    p = await v.validate(mint(entra_app_claims(), rsa_key))
    assert p.kind == "app" and p.permissions == {"read", "write"}
    p = await v.validate(mint(entra_app_claims(roles=("MCP.Read.All",)), rsa_key))
    assert p.permissions == {"read"}
    p = await v.validate(mint(entra_v2_claims(roles=["MCP.Admin"]), rsa_key))
    assert "admin" in p.permissions
    strict, _ = make_validator(
        settings_factory(MCP_AUTH_REQUIRE_USER_ROLES="true"), mock_idp
    )
    p = await strict.validate(mint(entra_v2_claims(), rsa_key))
    assert p.permissions == set()
    p = await strict.validate(mint(entra_v2_claims(roles=["MCP.Reader"]), rsa_key))
    assert p.permissions == {"read"}


async def test_token_type_check(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(settings_factory(MCP_AUTH_TOKEN_TYPE="at+jwt"), mock_idp)
    err = await reason_of(v, mint(entra_v2_claims(), rsa_key))
    assert err.reason == "invalid_token_type"
    await v.validate(mint(entra_v2_claims(), rsa_key, headers={"typ": "at+jwt"}))


async def test_static_pem_and_ec(ec_key):
    from mcp_core.auth.settings import load_auth_settings

    s = load_auth_settings(
        {
            "MCP_AUTH_MODE": "jwt",
            "MCP_AUTH_RESOURCE_URL": "https://mcp.example/mcp",
            "MCP_AUTH_ISSUERS": "https://idp.example",
            "MCP_AUTH_PUBLIC_KEY": public_pem(ec_key),
            "MCP_AUTH_ALGORITHMS": "ES256",
        }
    )
    v = TokenValidator(s, StaticKeySet([s.public_key_pem or ""]))
    now = int(time.time())
    token = mint(
        {
            "iss": "https://idp.example",
            "aud": "https://mcp.example/mcp",
            "exp": now + 60,
            "sub": "u",
            "scope": "mcp.read",
        },
        ec_key,
        kid=None,
        alg="ES256",
    )
    p = await v.validate(token)
    assert p.permissions == {"read"}
    with pytest.raises(UnknownKeyError):
        await StaticKeySet([public_pem(ec_key)]).get_key(None, "RS256")


async def test_explain_never_returns_token(settings_factory, mock_idp, rsa_key):
    v, _ = make_validator(settings_factory(), mock_idp)
    token = mint(entra_v2_claims(), rsa_key)
    report = await v.explain(token)
    assert report[0].ok and token not in repr(report)
    bad = await v.explain(mint(entra_v2_claims(aud=GRAPH), rsa_key))
    assert bad[0].name == "invalid_audience" and not bad[0].ok


async def test_jwks_document_problems(mock_idp):
    keys = JwksCache(JWKS_URI, http=mock_idp.client())
    mock_idp.jwks = {"nope": []}
    from mcp_core.auth.jwks import KeyUnavailableError

    with pytest.raises(KeyUnavailableError):
        await keys.get_key("k1", "RS256")


async def test_jwks_alg_mismatch(mock_idp, rsa_key):
    mock_idp.jwks = {"keys": [jwk_for(rsa_key, "k1", use="enc")]}
    keys = JwksCache(JWKS_URI, http=mock_idp.client())
    with pytest.raises(UnknownKeyError):
        await keys.get_key("k1", "RS256")
    with pytest.raises(UnknownKeyError):
        await keys.get_key(None, "RS256")
