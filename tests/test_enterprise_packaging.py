"""Helm chart, Entra templates, client configs, Copilot agent/skill and SOUL.md."""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "deploy" / "helm" / "uml-mcp"


def _pyproject_version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def test_chart_metadata_and_defaults():
    chart = yaml.safe_load((CHART / "Chart.yaml").read_text())
    assert chart["apiVersion"] == "v2"
    assert chart["appVersion"] == _pyproject_version()
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    assert values["auth"]["mode"] == "none"  # open by default, like Vercel
    assert values["podSecurityContext"]["runAsNonRoot"] is True
    assert values["securityContext"]["readOnlyRootFilesystem"] is True
    assert values["auth"]["entra"]["tokenVersions"] == ["2"]
    schema = json.loads((CHART / "values.schema.json").read_text())
    assert schema["properties"]["auth"]["properties"]["mode"]["enum"] == [
        "none",
        "jwt",
        "entra-proxy",
    ]
    for ci in (CHART / "ci").glob("*-values.yaml"):
        assert yaml.safe_load(ci.read_text())["image"]["repository"]


@pytest.mark.skipif(
    shutil.which("helm") is None, reason="helm not installed (CI runs it)"
)
def test_chart_renders():
    out = subprocess.run(
        [
            "helm",
            "template",
            "t",
            str(CHART),
            "-f",
            str(CHART / "ci" / "jwt-values.yaml"),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "MCP_AUTH_CONFIG_FILE" in out and "auth.json" in out
    assert "UML_MCP_CONFIG" in out and "uml-mcp.yaml" in out


def test_chart_config_values_are_valid_uml_mcp_yaml():
    """``.Values.config`` becomes uml-mcp.yaml verbatim: it must pass the real loader."""
    from mcp_core.core.settings_file import parse_app_config

    values = yaml.safe_load((CHART / "values.yaml").read_text())
    assert values["config"] == {}  # opt-in
    schema = json.loads((CHART / "values.schema.json").read_text())
    allowed = set(schema["properties"]["config"]["properties"])
    assert "auth" not in allowed  # auth stays under .Values.auth
    for ci in (CHART / "ci").glob("*-values.yaml"):
        config = yaml.safe_load(ci.read_text()).get("config") or {}
        assert set(config) <= allowed
        parse_app_config(config, str(ci))


def test_entra_templates():
    manifest = json.loads((ROOT / "deploy/entra/app-registration.json").read_text())
    assert manifest["api"]["requestedAccessTokenVersion"] == 2
    example = json.loads((ROOT / "deploy/entra/auth.example.json").read_text())
    from mcp_core.auth.settings import load_auth_settings

    cfg = ROOT / "deploy/entra/auth.example.json"
    settings = load_auth_settings({"MCP_AUTH_CONFIG_FILE": str(cfg)})
    assert settings.mode == example["mode"] == "jwt"
    script = (ROOT / "deploy/entra/register-app.sh").read_text()
    assert (
        "requestedAccessTokenVersion" in script
        and "appRoleAssignmentRequired" in script
    )


def test_enterprise_client_configs():
    for name in (
        "vscode_mcp_enterprise.json",
        "visualstudio_mcp_enterprise.json",
        "cursor_http_enterprise.json",
    ):
        data = json.loads((ROOT / "config" / name).read_text())
        assert json.dumps(data).count("/mcp") >= 1


def test_compose_override_parses():
    data = yaml.safe_load((ROOT / "docker-compose.enterprise.yml").read_text())
    env = data["services"]["uml-mcp"]["environment"]
    assert any(e.startswith("MCP_AUTH_MODE=") for e in env)
    assert all("=" in e for e in env)


def test_copilot_agent_and_skill_mirror():
    text = (ROOT / ".github/agents/uml-mcp.agent.md").read_text()
    front = yaml.safe_load(text.split("---")[1])
    assert front["name"] == "uml-mcp" and front["description"]
    assert front["mcp-servers"]["uml-mcp"]["url"].endswith("/mcp")
    assert "uml-mcp/*" in front["tools"]
    assert len(text) < 30000
    canonical = (ROOT / ".skill/skills/uml-mcp-diagrams/SKILL.md").read_bytes()
    mirror = (ROOT / ".github/skills/uml-mcp-diagrams/SKILL.md").read_bytes()
    assert mirror == canonical
    assert (ROOT / "SOUL.md").read_text().startswith("# SOUL.md")
