"""Test that version is consistent across package metadata."""
from pathlib import Path


def test_version_consistency():
    # Load pyproject
    import tomllib
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    version = pyproject["project"]["version"]

    # Check MCPSettings default
    from mcp_core.core.config import MCPSettings
    # Create a fresh settings instance to avoid env overrides affecting version
    s = MCPSettings()
    assert s.version == version, f"Config version {s.version} != pyproject {version}"

    # Check README badge contains version range (basic)
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    # Badge should reflect >=3.12,<3.15
    assert ">=3.12" in readme


def test_version_consistency_across_manifests():
    import json
    import tomllib

    import yaml

    root = Path(__file__).parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    chart = yaml.safe_load((root / "deploy/helm/uml-mcp/Chart.yaml").read_text())
    assert chart["appVersion"] == version
    plugin = json.loads((root / "plugins/uml-mcp/.claude-plugin/plugin.json").read_text())
    assert plugin["version"] == version
    assert f'version: "{version}"' in (root / "smithery.yaml").read_text() or (
        f"version: {version}" in (root / "smithery.yaml").read_text()
    )
