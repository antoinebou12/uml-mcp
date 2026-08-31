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

    # Pinned exactly (Renovate bumps the patch); the major must stay on FastMCP 4.
    assert any(
        dependency.startswith("fastmcp-slim[server]==4.") for dependency in dependencies
    )
    assert all(not dependency.startswith("fastmcp[tasks]") for dependency in dependencies)
    assert "mcp>=2.0.0,<3.0.0" in dependencies
    assert "fastapi>=0.141.1,<0.200.0" in dependencies
    assert "starlette>=1.6.0,<2.0.0" in dependencies
    assert project["requires-python"] == ">=3.12,<3.15"

    # Runtime dependencies belong to PEP 621. Keeping a second Poetry dependency
    # table would let package managers resolve different MCP stacks.
    assert "dependencies" not in pyproject.get("tool", {}).get("poetry", {})


def test_pyproject_does_not_override_transitive_constraints() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    # Transitive versions belong to their owning packages. In particular this
    # keeps FastMCP 4 / MCP 2 free to resolve a mutually compatible graph on
    # Vercel instead of bypassing upstream constraints with uv overrides.
    uv_config = pyproject.get("tool", {}).get("uv", {})
    assert "override-dependencies" not in uv_config


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
