"""CLI: ``python -m mcp_core.auth generate <kind> ...`` and ``keygen``."""

from __future__ import annotations

import argparse
import sys

from .generators import KINDS, GeneratorParams, generate
from .sealing import generate_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mcp_core.auth")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="print an Entra/Helm/client artifact")
    gen.add_argument("kind", choices=KINDS)
    gen.add_argument("--resource-url", default="https://mcp.contoso.com/mcp")
    gen.add_argument("--tenant-id", default="<tenant-id>")
    gen.add_argument("--client-id", default="<api-client-id>")
    gen.add_argument("--mode", choices=("jwt", "entra-proxy"), default="jwt")
    gen.add_argument("--app-name", default="UML-MCP")
    gen.add_argument("--preauthorize-azure-cli", action="store_true")
    key = sub.add_parser(
        "keygen", help="print a new MCP_AUTH_PROXY_ENCRYPTION_KEYS entry"
    )
    key.add_argument("--kid", default="k1")
    args = parser.parse_args(argv)
    if args.command == "keygen":
        print(generate_key(args.kid))
        return 0
    params = GeneratorParams(
        resource_url=args.resource_url,
        tenant_id=args.tenant_id,
        client_id=args.client_id,
        mode=args.mode,
        app_name=args.app_name,
        preauthorize_azure_cli=args.preauthorize_azure_cli,
    )
    sys.stdout.write(generate(args.kind, params).rstrip("\n") + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
