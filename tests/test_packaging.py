"""Packaging contract: default distribution ships mcp_core + tools only (no ai_uml)."""

from pathlib import Path

import tomllib


def test_poetry_packages_exclude_ai_uml() -> None:
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    packages = data["tool"]["poetry"]["packages"]
    includes = {p["include"] for p in packages}
    assert "ai_uml" not in includes, (
        "ai_uml must not be listed in [tool.poetry] packages; "
        "keep it repository-only (see README / docs/ai_uml.md)."
    )
    assert {"mcp_core", "tools"}.issubset(includes)
