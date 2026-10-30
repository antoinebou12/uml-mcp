"""Packaging contract: published distribution includes the bundled D3 plugin."""

from pathlib import Path

import tomli as tomllib


def test_poetry_packages_surface() -> None:
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    packages = data["tool"]["poetry"]["packages"]
    includes = {p["include"] for p in packages}
    assert includes == {"mcp_core", "tools", "uml_mcp_plugin_d3"}


def test_hosted_build_contexts_include_declared_runtime_packages() -> None:
    import pathspec

    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    for ignore_file in (".dockerignore", ".vercelignore"):
        ignore = pathspec.PathSpec.from_lines(
            "gitignore", (root / ignore_file).read_text().splitlines()
        )
        for package in data["tool"]["poetry"]["packages"]:
            source = root / package.get("from", "") / package["include"]
            files = [
                p
                for p in source.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts
            ]
            assert files
            for path in files:
                relative = path.relative_to(root).as_posix()
                assert not ignore.match_file(relative), (
                    f"{ignore_file} excludes runtime file {relative}"
                )
