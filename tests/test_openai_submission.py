"""OpenAI Apps submission: bundle in submission/openai and the domain challenge route."""

import importlib.util
import json
import os
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "true"

from app import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def _load_build_script():
    """Load scripts/build_openai_submission.py without putting scripts/ on sys.path."""
    spec = importlib.util.spec_from_file_location(
        "build_openai_submission", ROOT / "scripts" / "build_openai_submission.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _load_build_script()


def _bundle():
    return build.load_json("plugin.json"), build.load_json("mcp.json")


def test_checked_in_bundle_is_ready():
    plugin, mcp = _bundle()
    problems = build.check_bundle(
        plugin, mcp, build.known_tools(), build.pyproject_version()
    )
    assert problems == []


def test_check_flags_unknown_tool_and_foreign_host():
    plugin, mcp = _bundle()
    plugin = json.loads(json.dumps(plugin))
    openai = plugin["extensions"]["com.openai"]
    openai["review"]["test_cases"]["positive"][0]["tools_triggered"] = "send_email"
    openai["interface"]["privacyPolicyURL"] = "https://uml-mcp.vercel.app/privacy"
    mcp = {"mcpServers": {"fast-steel-xf470": {"type": "sse", "url": "http://x/mcp"}}}

    problems = build.check_bundle(plugin, mcp, {"generate_uml"}, "0.0.0")

    joined = "\n".join(problems)
    assert "unknown tool 'send_email'" in joined
    assert "privacyPolicyURL" in joined
    assert "exactly one server named 'uml-mcp'" in joined
    assert "streamable-http" in joined
    assert "version" in joined


def test_build_zip_is_reproducible_and_allowlisted(tmp_path):
    first = build.build_zip("9.9.9", tmp_path / "a")
    second = build.build_zip("9.9.9", tmp_path / "b")
    assert first.name == "uml-mcp-openai-9.9.9.zip"
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert sorted(archive.namelist()) == sorted(build.BUNDLE_FILES)
        assert json.loads(archive.read("plugin.json"))["name"] == "uml-mcp"


def test_main_check_only(capsys):
    assert build.main(["--check"]) == 0
    assert "ready" in capsys.readouterr().out


def test_openai_apps_challenge_unset_is_404(monkeypatch):
    monkeypatch.delenv("OPENAI_APPS_CHALLENGE_TOKEN", raising=False)
    response = client.get("/.well-known/openai-apps-challenge")
    assert response.status_code == 404


@pytest.mark.parametrize("token", ["  abc123-token\n", "tok_9f8e7d"])
def test_openai_apps_challenge_echoes_token(monkeypatch, token):
    monkeypatch.setenv("OPENAI_APPS_CHALLENGE_TOKEN", token)
    response = client.get("/.well-known/openai-apps-challenge")
    assert response.status_code == 200
    assert response.text == token.strip()
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["cache-control"] == "no-store"


def test_openai_apps_challenge_rejects_multiline_token(monkeypatch):
    monkeypatch.setenv("OPENAI_APPS_CHALLENGE_TOKEN", "abc\n<script>")
    assert client.get("/.well-known/openai-apps-challenge").status_code == 404


def test_terms_of_service_is_served():
    response = client.get("/.well-known/terms.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "Terms of Service" in response.text


def test_challenge_token_has_yaml_key():
    from mcp_core.core.settings_file import ENV_MAP

    assert (
        ENV_MAP[("server", "openai_apps_challenge_token")]
        == "OPENAI_APPS_CHALLENGE_TOKEN"
    )
