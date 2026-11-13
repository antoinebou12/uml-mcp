#!/usr/bin/env python
"""Check and zip the OpenAI Apps submission bundle in ``submission/openai``.

The bundle (``plugin.json``, ``mcp.json``, ``assets/``) follows the
agent-plugins.org 1.0.0 layout that the OpenAI Apps submission form accepts.
This script stamps the pyproject version, checks the manifests against the
live tool registry and the production host, and writes a deterministic zip.

Usage::

    python scripts/build_openai_submission.py            # check + zip into dist/
    python scripts/build_openai_submission.py --check    # check only
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "submission" / "openai"
DIST_DIR = ROOT / "dist"
PRODUCTION_HOST = "uml-mcp.antoineboucher.info"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Files that go into the archive, relative to BUNDLE_DIR. The demo video is
# uploaded separately (demo_recording_url), so it never travels in the zip.
BUNDLE_FILES = ("plugin.json", "mcp.json", "assets/logo.png")


def load_json(name: str) -> dict[str, Any]:
    return json.loads((BUNDLE_DIR / name).read_text(encoding="utf-8"))


def pyproject_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def known_tools() -> set[str]:
    """Tool names registered by the server (import side effect of diagram_tools)."""
    sys.path.insert(0, str(ROOT))
    import mcp_core.tools.diagram_tools  # noqa: F401
    from mcp_core.tools.tool_decorator import get_tool_registry

    return set(get_tool_registry())


def _https_on_host(url: str, host: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == host


def check_bundle(
    plugin: dict[str, Any],
    mcp: dict[str, Any],
    tools: set[str],
    version: str,
    bundle_dir: Path = BUNDLE_DIR,
) -> list[str]:
    """Return human-readable problems; an empty list means the bundle is ready."""
    problems: list[str] = []
    if plugin.get("name") != "uml-mcp":
        problems.append("plugin.json name must be 'uml-mcp'")
    if plugin.get("version") != version:
        problems.append(
            f"plugin.json version {plugin.get('version')!r} != pyproject {version!r}"
        )

    servers = mcp.get("mcpServers") or {}
    if list(servers) != ["uml-mcp"]:
        problems.append("mcp.json must declare exactly one server named 'uml-mcp'")
    for name, server in servers.items():
        url = str(server.get("url", ""))
        if server.get("type") != "streamable-http":
            problems.append(f"mcp.json {name}: type must be streamable-http")
        if not _https_on_host(url, PRODUCTION_HOST) or not url.endswith("/mcp"):
            problems.append(
                f"mcp.json {name}: url must be https://{PRODUCTION_HOST}/mcp"
            )

    openai = (plugin.get("extensions") or {}).get("com.openai") or {}
    interface = openai.get("interface") or {}
    for key in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL"):
        if not _https_on_host(str(interface.get(key, "")), PRODUCTION_HOST):
            problems.append(f"interface.{key} must be https on {PRODUCTION_HOST}")
    for key in ("logo", "composerIcon"):
        rel = str(interface.get(key, ""))
        path = (bundle_dir / rel).resolve()
        if not rel.startswith("./") or bundle_dir.resolve() not in path.parents:
            problems.append(f"interface.{key} must be a ./ path inside the bundle")
        elif not path.is_file() or path.read_bytes()[:8] != PNG_MAGIC:
            problems.append(f"interface.{key} {rel} is not a PNG file")
    if len(interface.get("shortDescription", "")) > 60:
        problems.append("interface.shortDescription is longer than 60 characters")

    cases = (openai.get("review") or {}).get("test_cases") or {}
    if not cases.get("positive") or not cases.get("negative"):
        problems.append("review.test_cases needs positive and negative cases")
    for case in cases.get("positive") or []:
        tool = case.get("tools_triggered")
        if tool not in tools:
            problems.append(f"positive case uses unknown tool {tool!r}")
    for case in cases.get("negative") or []:
        if case.get("tools_triggered"):
            problems.append("negative cases must not trigger a tool")
    return problems


def build_zip(version: str, dist_dir: Path = DIST_DIR) -> Path:
    """Write ``uml-mcp-openai-<version>.zip`` with fixed timestamps (reproducible)."""
    dist_dir.mkdir(parents=True, exist_ok=True)
    target = dist_dir / f"uml-mcp-openai-{version}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for rel in BUNDLE_FILES:
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (BUNDLE_DIR / rel).read_bytes())
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="check only, no zip")
    args = parser.parse_args(argv)

    version = pyproject_version()
    problems = check_bundle(
        load_json("plugin.json"), load_json("mcp.json"), known_tools(), version
    )
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1
    if args.check:
        print(f"submission/openai is ready (version {version})")
        return 0
    print(build_zip(version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
