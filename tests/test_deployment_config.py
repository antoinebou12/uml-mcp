import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_pyproject_is_canonical_mcp_2026_manifest() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    project = pyproject["project"]
    dependencies = project["dependencies"]

    assert "fastmcp[tasks]==4.0.0b1" in dependencies
    assert "mcp>=2.0.0,<3.0.0" in dependencies
    assert project["requires-python"] == ">=3.12,<3.15"

    # Runtime dependencies belong to PEP 621. Keeping a second Poetry dependency
    # table would let package managers resolve different MCP stacks.
    assert "dependencies" not in pyproject.get("tool", {}).get("poetry", {})


def test_transitive_overrides_match_consolidated_dependency_updates() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    overrides = set(pyproject["tool"]["uv"]["override-dependencies"])

    assert "virtualenv==21.7.3" in overrides
    assert "cryptography==49.0.0" in overrides
    assert "opentelemetry-api==1.44.0" in overrides
    assert "cyclopts==4.22.5" in overrides
    assert "griffelib==2.1.0" in overrides
    assert "joserfc==1.7.4" in overrides


def test_vercel_uses_native_fastapi_routing_and_stateless_storage() -> None:
    config = _load_json("vercel.json")

    assert "rewrites" not in config
    assert "routes" not in config
    assert "installCommand" not in config
    assert config["buildCommand"] == "python -m mcp_core.build_static_server_card"

    env = config["env"]
    assert env["FASTMCP_STATELESS_HTTP"] == "true"
    assert env["MCP_MEMORY_ONLY"] == "true"
    assert env["MCP_URL_ONLY"] == "true"
    assert env["MCP_OUTPUT_DIR"] == "/tmp/diagrams"
    assert env["VERCEL_OUTPUT_DIR"] == "/tmp/diagrams"


def test_renovate_tracks_pep621_instead_of_generated_snapshots() -> None:
    renovate = _load_json("renovate.json")

    assert renovate["pep621"]["enabled"] is True
    assert renovate["poetry"]["enabled"] is False
    assert "postUpgradeTasks" not in renovate
