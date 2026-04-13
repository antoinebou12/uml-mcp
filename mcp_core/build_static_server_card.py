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

# Vercel build uses this in a separate process from serverless runtime.
os.environ["MOCK_FASTMCP"] = "true"

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.append(_REPO_ROOT)


def main() -> None:
    from mcp_core.core.server_card import build_server_card

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
                g.write(schema_content)
            print(f"Wrote {dest}")

    card = build_server_card(strict=True)
    if not card.get("tools"):
        print(
            "Skipping write: build_server_card returned no tools (missing deps?).",
            file=sys.stderr,
        )
        sys.exit(1)
    out_path = os.path.join(out_dir, "server-card.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(card, f, indent=2)
    print(f"Wrote {out_path}")
    public_path = os.path.join(public_dir, "server-card.json")
    with open(public_path, "w", encoding="utf-8") as f:
        json.dump(card, f, indent=2)
    print(f"Wrote {public_path}")


if __name__ == "__main__":
    main()
