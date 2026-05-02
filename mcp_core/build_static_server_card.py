"""
Generate static MCP server-card.json for Vercel.

Served at .well-known/mcp/server-card.json (see public/.well-known/ copy).

Run from repo root:
  python -m mcp_core.build_static_server_card

This lives under mcp_core/ so Vercel buildCommand does not depend on scripts/
being present in the build workspace (path0).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# Vercel build uses this in a separate process from serverless runtime.
os.environ["MOCK_FASTMCP"] = "true"

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.append(_REPO_ROOT)

# Canonical origin for static linkset / OAuth metadata (preview deploys still serve these files).
_DEFAULT_PUBLIC_BASE = "https://uml-mcp.vercel.app"


def _dump_json(obj: Any, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def _write_discovery_artifacts(repo_root: str, public_base: str) -> None:
    """Emit RFC 9727 api-catalog, RFC 9728 oauth-protected-resource, agent-skills index."""
    from mcp_core.core.agent_discovery import (
        build_agent_skills_index,
        build_api_catalog,
        build_oauth_protected_resource,
    )

    catalog = build_api_catalog(public_base)
    oauth = build_oauth_protected_resource(public_base)
    skills_index = build_agent_skills_index(repo_root)

    roots = [
        os.path.join(repo_root, ".well-known"),
        os.path.join(repo_root, "public", ".well-known"),
    ]
    for wk in roots:
        os.makedirs(wk, exist_ok=True)
        api_cat_path = os.path.join(wk, "api-catalog")
        _dump_json(catalog, api_cat_path)
        print(f"Wrote {api_cat_path}")

        oauth_path = os.path.join(wk, "oauth-protected-resource")
        _dump_json(oauth, oauth_path)
        print(f"Wrote {oauth_path}")

        ask_dir = os.path.join(wk, "agent-skills")
        os.makedirs(ask_dir, exist_ok=True)
        idx_path = os.path.join(ask_dir, "index.json")
        _dump_json(skills_index, idx_path)
        print(f"Wrote {idx_path}")


def main() -> None:
    from mcp_core.core.server_card import build_server_card

    public_base = os.environ.get("AGENT_DISCOVERY_BASE_URL", _DEFAULT_PUBLIC_BASE)

    schema_src = os.path.join(_REPO_ROOT, "smithery-config-schema.json")
    out_dir = os.path.join(_REPO_ROOT, ".well-known", "mcp")
    public_dir = os.path.join(_REPO_ROOT, "public", ".well-known", "mcp")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(public_dir, exist_ok=True)
    if os.path.isfile(schema_src):
        for dest_dir in [out_dir, public_dir]:
            dest = os.path.join(dest_dir, "config-schema.json")
            with open(schema_src, encoding="utf-8") as f:
                schema_content = f.read()
            with open(dest, "w", encoding="utf-8") as g:
                g.write(schema_content.rstrip("\n") + "\n")
            print(f"Wrote {dest}")

    card = build_server_card(strict=True)
    if not card.get("tools"):
        print(
            "Skipping write: build_server_card returned no tools (missing deps?).",
            file=sys.stderr,
        )
        sys.exit(1)
    out_path = os.path.join(out_dir, "server-card.json")
    _dump_json(card, out_path)
    print(f"Wrote {out_path}")
    public_path = os.path.join(public_dir, "server-card.json")
    _dump_json(card, public_path)
    print(f"Wrote {public_path}")

    _write_discovery_artifacts(_REPO_ROOT, public_base)


if __name__ == "__main__":
    main()
