"""Packaging contract: published distribution ships mcp_core + tools only."""

from pathlib import Path

import tomli as tomllib


def test_poetry_packages_surface() -> None:
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    packages = data["tool"]["poetry"]["packages"]
    includes = {p["include"] for p in packages}
    assert includes == {"mcp_core", "tools"}
