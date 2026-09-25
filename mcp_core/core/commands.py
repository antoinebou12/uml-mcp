"""Management subcommands: ``uml-mcp config|lint|client ...``.

The server itself keeps its historic flags (``uml-mcp --transport http``);
these subcommands only run when the first argument is one of them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from importlib import resources
from pathlib import Path
from typing import Any

SUBCOMMANDS = ("config", "lint", "client")
PROFILES = ("local", "docker", "enterprise")


def _template(profile: str) -> str:
    return (
        resources.files("mcp_core.config_templates")
        .joinpath(f"{profile}.yaml")
        .read_text(encoding="utf-8")
    )


def _default_user_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "uml-mcp" / "config.yaml"


def _effective(explicit: str | None) -> dict[str, Any]:
    from ..auth import auth_requested
    from .settings_file import ENV_MAP, load_config

    env = dict(os.environ)
    loaded = load_config(explicit, env)  # applies to a copy, never the real env
    sources = {
        env_name: {
            "value": env.get(env_name),
            "source": loaded.source_of(env_name, os.environ),
            "yaml": f"{section}.{key}",
        }
        for (section, key), env_name in ENV_MAP.items()
    }
    out: dict[str, Any] = {
        "config_file": str(loaded.path) if loaded.path else None,
        "sections": loaded.app.model_dump(mode="json", exclude={"auth"}),
        "env_mapped": sources,
    }
    try:
        if auth_requested():
            from ..auth.settings import get_auth_settings

            out["auth"] = get_auth_settings().redacted_dict()
        else:
            out["auth"] = {"mode": "none"}
    except Exception as exc:  # noqa: BLE001
        out["auth"] = {"error": str(exc)}
    return out


def cmd_config(args: argparse.Namespace) -> int:
    from .settings_file import ConfigFileError, find_config_path, load_config

    if args.action == "init":
        path = Path(args.path).expanduser() if args.path else _default_user_path()
        if path.exists() and not args.force:
            print(f"{path} already exists (use --force to overwrite)", file=sys.stderr)
            return 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_template(args.profile), encoding="utf-8")
        print(f"Wrote {args.profile} profile to {path}")
        print(f"Next: uml-mcp config validate --config {path}")
        return 0
    if args.action == "path":
        try:
            found = find_config_path(args.config)
        except ConfigFileError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(found or "(no config file found; using env vars and defaults)")
        return 0
    if args.action == "validate":
        try:
            loaded = load_config(args.config, dict(os.environ))
            if (loaded.data.get("auth") or {}).get("mode", "none") != "none":
                from ..auth.settings import load_auth_settings

                env = dict(os.environ)
                env.setdefault("MCP_AUTH_MODE", str(loaded.data["auth"]["mode"]))
                load_auth_settings(env, file_data=loaded.data["auth"])
        except Exception as exc:  # noqa: BLE001 - report every config error
            print(f"INVALID: {exc}", file=sys.stderr)
            return 1
        print(f"OK: {loaded.path or 'defaults + environment'}")
        return 0
    # show
    if args.config:
        os.environ["UML_MCP_CONFIG"] = args.config
    data = _effective(args.config)
    if not args.sources:
        data.pop("env_mapped", None)
    print(json.dumps(data, indent=2, default=str))
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    from ..quality.lint import exit_code, run_lint

    issues = run_lint()
    if args.format == "json":
        print(json.dumps([i.as_dict() for i in issues], indent=2))
    else:
        for i in issues:
            fix = f"  → {i.fix}" if i.fix else ""
            print(f"{i.severity.upper():7} {i.code} {i.target}: {i.message}{fix}")
        counts = {
            s: sum(1 for i in issues if i.severity == s)
            for s in ("error", "warning", "info")
        }
        print(
            f"{counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info"
        )
    return exit_code(issues, args.strict)


def cmd_client(args: argparse.Namespace) -> int:
    from .client_install import install

    try:
        text, path = install(args.client, scope=args.scope, dry_run=args.dry_run)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if path is None:
        print("Run this command to register UML-MCP with Claude Code:\n" + text)
    elif args.dry_run:
        print(f"# would write {path}\n{text}")
    else:
        print(f"Updated {path} (backup kept next to it). Restart the client.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uml-mcp")
    sub = parser.add_subparsers(dest="command", required=True)
    cfg = sub.add_parser("config", help="create, inspect and validate uml-mcp.yaml")
    cfg.add_argument("action", choices=("init", "show", "validate", "path"))
    cfg.add_argument("--profile", choices=PROFILES, default="local")
    cfg.add_argument(
        "--path", help="where 'init' writes (default ~/.config/uml-mcp/config.yaml)"
    )
    cfg.add_argument("--config", help="config file to read (show/validate/path)")
    cfg.add_argument(
        "--sources", action="store_true", help="show where each value comes from"
    )
    cfg.add_argument("--force", action="store_true")
    lint = sub.add_parser(
        "lint", help="lint tool/prompt/resource definitions and config"
    )
    lint.add_argument("--strict", action="store_true", help="fail on warnings")
    lint.add_argument("--format", choices=("text", "json"), default="text")
    client = sub.add_parser(
        "client", help="register the local stdio server in an MCP client"
    )
    client.add_argument("action", choices=("install",))
    client.add_argument(
        "--client",
        required=True,
        choices=("vscode", "cursor", "claude-desktop", "claude-code"),
    )
    client.add_argument("--scope", choices=("user", "workspace"), default="user")
    client.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return {"config": cmd_config, "lint": cmd_lint, "client": cmd_client}[args.command](
        args
    )


__all__ = ["PROFILES", "SUBCOMMANDS", "build_parser", "main"]
