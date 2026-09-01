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
