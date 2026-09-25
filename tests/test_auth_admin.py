"""Read-only admin console and generators (Entra manifest, Helm values, clients)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from mcp_core.auth.__main__ import main as cli_main
from mcp_core.auth.generators import GeneratorParams, entra_app_manifest, generate
from tests.fixtures_auth import build_auth_app, entra_v2_claims, mint


def admin_client(settings_factory, mock_idp):
    app = build_auth_app(settings_factory(MCP_ADMIN_UI="true"), http=mock_idp.client())
    return TestClient(app)


def test_admin_disabled_is_404(settings_factory, mock_idp):
    c = TestClient(build_auth_app(settings_factory(), http=mock_idp.client()))
    assert c.get("/admin").status_code == 404
    # /admin/api is still a protected namespace: authenticate first, then 404
    assert c.get("/admin/api/overview").status_code == 401


def test_admin_requires_role(settings_factory, mock_idp, rsa_key):
    c = admin_client(settings_factory, mock_idp)
    page = c.get("/admin")
    assert (
        page.status_code == 200
        and "script-src 'self'" in page.headers["content-security-policy"]
    )
    assert c.get("/admin/favicon.svg").status_code == 200
    assert c.get("/admin/api/overview").status_code == 401
    user = mint(entra_v2_claims(), rsa_key)
    r = c.get("/admin/api/overview", headers={"Authorization": f"Bearer {user}"})
    assert r.status_code == 403 and "MCP.Admin" in r.json()["error_description"]
    assert "scope" not in r.json()  # role-only denial carries no scope
    admin = mint(entra_v2_claims(roles=["MCP.Admin"]), rsa_key)
    h = {"Authorization": f"Bearer {admin}"}
    ov = c.get("/admin/api/overview", headers=h).json()
    assert ov["mode"] == "jwt" and ov["protected_resource_metadata"]["resource"]
    assert c.get("/admin/api/events", headers=h).status_code == 200
    check = c.post("/admin/api/token-check", headers=h, json={"token": user}).json()
    assert check["valid"] and check["principal"]["permissions"] == ["read", "write"]
    assert user not in json.dumps(check)
    bad = c.post("/admin/api/token-check", headers=h, json={"token": "a.b.c"}).json()
    assert bad["valid"] is False
    assert c.post("/admin/api/token-check", headers=h, json={}).status_code == 400
    gen = c.get("/admin/api/generate/entra-manifest", headers=h)
    assert json.loads(gen.text)["api"]["requestedAccessTokenVersion"] == 2
    assert c.get("/admin/api/generate/nope", headers=h).status_code == 404


def test_entra_manifest_follows_microsoft_guidance():
    m = entra_app_manifest(GeneratorParams(client_id="c1", mode="entra-proxy"))
    assert m["api"]["requestedAccessTokenVersion"] == 2
    assert m["identifierUris"] == ["api://c1"]
    scopes = {s["value"] for s in m["api"]["oauth2PermissionScopes"]}
    assert scopes == {"mcp.read", "mcp.write"}
    preauth = {p["appId"] for p in m["api"]["preAuthorizedApplications"]}
    assert "aebc6443-996d-45c2-90f0-388ff96faa56" in preauth  # VS Code
    assert "04f0c124-f2bc-4f59-8241-bf6df9866bbd" in preauth  # Visual Studio
    roles = {r["value"] for r in m["appRoles"]}
    assert {
        "MCP.Reader",
        "MCP.Writer",
        "MCP.Admin",
        "MCP.Read.All",
        "MCP.Write.All",
    } <= roles
    assert m["web"]["redirectUris"] == ["https://mcp.contoso.com/oauth/callback"]
    again = entra_app_manifest(GeneratorParams(client_id="c1", mode="entra-proxy"))
    assert again == m  # deterministic IDs


def test_generators_and_cli(capsys):
    p = GeneratorParams()
    for kind in ("vscode", "visual-studio", "cursor"):
        data = json.loads(generate(kind, p))
        assert "/mcp" in json.dumps(data)
    assert "--client-id" in generate("claude-code", p)
    assert generate("claude-code", GeneratorParams(mode="entra-proxy")).startswith(
        "claude mcp add"
    )
    assert "requestedAccessTokenVersion" in generate("az-script", p)
    assert "mode: jwt" in generate("helm-values", p)
    assert cli_main(["generate", "entra-manifest", "--client-id", "x"]) == 0
    assert json.loads(capsys.readouterr().out)["identifierUris"] == ["api://x"]
    assert cli_main(["keygen", "--kid", "k9"]) == 0
    assert capsys.readouterr().out.startswith("k9:")
