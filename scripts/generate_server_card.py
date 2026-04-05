"""
Generate static MCP server-card.json for Vercel.
Vercel reserves /.well-known for SSL and does not allow rewrites to serverless
functions, so we serve the server card as a static file at .well-known/mcp/server-card.json.
Run from repo root: python scripts/generate_server_card.py
"""

import json
import os
import sys

# Vercel build uses this script in a separate process from serverless runtime.
# Use mock FastMCP here so we only need the @mcp_tool registry (no real fastmcp import).
# That avoids failures when fastmcp is missing or incompatible with the builder Python (e.g. 3.14).
os.environ["MOCK_FASTMCP"] = "true"

# Ensure project root is on path (append so venv site-packages take precedence)
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.append(repo_root)


def main():
    from mcp_core.core.server_card import build_server_card

    # Copy config schema first so it exists even if card build fails (e.g. missing deps)
    schema_src = os.path.join(repo_root, "smithery-config-schema.json")
    out_dir = os.path.join(repo_root, ".well-known", "mcp")
    public_dir = os.path.join(repo_root, "public", ".well-known", "mcp")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(public_dir, exist_ok=True)
    if os.path.isfile(schema_src):
        for dest_dir in [out_dir, public_dir]:
            dest = os.path.join(dest_dir, "config-schema.json")
            with open(schema_src, "r", encoding="utf-8") as f:
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
    # Write to .well-known/ (for local/dev)
    out_path = os.path.join(out_dir, "server-card.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(card, f, indent=2)
    print(f"Wrote {out_path}")
    # Write to public/ (Vercel serves this at root - required for Smithery)
    public_path = os.path.join(public_dir, "server-card.json")
    with open(public_path, "w", encoding="utf-8") as f:
        json.dump(card, f, indent=2)
    print(f"Wrote {public_path}")


if __name__ == "__main__":
    main()
