"""Guided management CLI (Typer + tqdm): ``uml-mcp setup | admin | plugins | kroki``.

``config``, ``lint`` and ``client`` keep their argparse implementation in
:mod:`mcp_core.core.commands`; ``uml-mcp`` dispatches here for the commands
listed in :data:`TYPER_COMMANDS`.
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer
from tqdm import tqdm

from ..core.features import FEATURES, PROFILES, build_config, default_features
from ..core.settings_file import write_config_file

TYPER_COMMANDS = ("setup", "admin", "plugins", "kroki")
CLIENTS = ("vscode", "cursor", "claude-desktop", "claude-code")

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="UML-MCP setup and administration.",
    rich_markup_mode=None,
)


def is_interactive() -> bool:
    return sys.stdin.isatty()


def _csv(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _default_path() -> Path:
    from ..core.commands import _default_user_path

    return _default_user_path()


def validate_config(data: dict[str, Any]) -> list[str]:
    """Return lint messages (errors raise); auth sections get the full auth check."""
    from ..core.settings_file import parse_app_config
    from ..quality.lint import lint_config

    app_config = parse_app_config(data, "setup")
    auth = None
    if (data.get("auth") or {}).get("mode", "none") != "none":
        from ..auth.settings import load_auth_settings

        env = dict(os.environ)
        env.setdefault("MCP_AUTH_MODE", str(data["auth"]["mode"]))
        auth = load_auth_settings(env, file_data=data["auth"])
    issues = lint_config(app_config, auth, {})
    return [f"{i.severity}: {i.code} {i.message}" for i in issues if i.code != "CFG007"]


def health_check() -> str:
    """Offline sanity check: validate a small diagram through the real tool."""
    from ..core.diagram_validation import validate_uml_inputs

    result = validate_uml_inputs("mermaid", "graph TD; A-->B")
    if not result.get("valid"):
        raise RuntimeError(f"sample diagram failed validation: {result.get('errors')}")
    return "sample diagram validated"


def _choose_features(
    profile: str, enable: list[str], disable: list[str], interactive: bool
) -> set[str]:
    chosen = default_features(profile)
    if interactive:
        typer.echo("\nFeatures (Enter keeps the recommended choice):")
        for feature in FEATURES:
            typer.echo(
                f"\n  {feature.title} [{feature.category}, applies {feature.apply}]"
            )
            typer.echo(f"    {feature.description}")
            on = typer.confirm("    Enable?", default=feature.key in chosen)
            chosen = (chosen | {feature.key}) if on else (chosen - {feature.key})
    for key in enable:
        chosen.add(key)
    for key in disable:
        chosen.discard(key)
    return chosen


@app.command()
def setup(
    profile: Annotated[
        str | None, typer.Option(help="local | docker | enterprise")
    ] = None,
    enable: Annotated[
        str | None, typer.Option(help="comma-separated feature keys")
    ] = None,
    disable: Annotated[
        str | None, typer.Option(help="comma-separated feature keys")
    ] = None,
    kroki_server: Annotated[str | None, typer.Option(help="Kroki URL")] = None,
    client: Annotated[
        list[str] | None, typer.Option(help="register in client(s)")
    ] = None,
    path: Annotated[
        Path | None, typer.Option(help="where to write uml-mcp.yaml")
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="no prompts")] = False,
    force: Annotated[bool, typer.Option(help="overwrite an existing file")] = False,
    dry_run: Annotated[
        bool, typer.Option(help="print the YAML, write nothing")
    ] = False,
    web: Annotated[bool, typer.Option(help="open the web setup form instead")] = False,
) -> None:
    """First-run wizard: choose a profile and features, write uml-mcp.yaml,
    register MCP clients and run a health check."""
    if web:
        admin(open_browser=True, page="setup")
        return
    interactive = not yes and is_interactive()
    from ..core.features import FEATURE_KEYS

    for key in [*_csv(enable), *_csv(disable)]:
        if key not in FEATURE_KEYS:
            raise typer.BadParameter(
                f"unknown feature {key!r}; choose from {', '.join(FEATURE_KEYS)}"
            )
    if profile is None:
        profile = (
            typer.prompt("Profile (local, docker, enterprise)", default="local")
            if interactive
            else "local"
        )
    if profile not in PROFILES:
        raise typer.BadParameter(f"profile must be one of {', '.join(PROFILES)}")
    chosen = _choose_features(profile, _csv(enable), _csv(disable), interactive)
    if interactive and kroki_server is None:
        kroki_server = typer.prompt("Kroki server", default="https://kroki.io")
    clients = list(client or [])
    if interactive and not clients and profile == "local":
        for name in CLIENTS:
            if typer.confirm(f"Register UML-MCP in {name}?", default=False):
                clients.append(name)
    bad = [c for c in clients if c not in CLIENTS]
    if bad:
        raise typer.BadParameter(
            f"unknown client(s) {bad}; choose from {', '.join(CLIENTS)}"
        )

    overrides: dict[str, Any] = {
        "setup": {
            "completed_at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
            "profile": profile,
            "features": sorted(chosen),
        },
    }
    if kroki_server:
        overrides["rendering"] = {"kroki_server": kroki_server}
    data = build_config(profile, chosen, overrides)
    target = (path or _default_path()).expanduser()

    if dry_run:
        import yaml

        typer.echo(yaml.safe_dump(data, sort_keys=False))
        return
    if (
        target.exists()
        and not force
        and not (
            interactive
            and typer.confirm(f"{target} exists. Overwrite (a backup is kept)?")
        )
    ):
        typer.echo(f"{target} already exists (use --force to overwrite)", err=True)
        raise typer.Exit(1)

    results: dict[str, str] = {}

    def step_validate() -> str:
        warnings = validate_config(data)
        return "valid" + (f" ({len(warnings)} note(s))" if warnings else "")

    def step_write() -> str:
        backup = write_config_file(target, data, force=True)
        return f"wrote {target}" + (f" (backup {backup.name})" if backup else "")

    def step_clients() -> str:
        from ..core.client_install import install

        done = []
        for name in clients:
            text, where = install(name)
            done.append(f"{name}: {where or text}")
        return "; ".join(done) or "skipped"

    steps: list[tuple[str, Callable[[], str]]] = [
        ("Validate configuration", step_validate),
        ("Write uml-mcp.yaml", step_write),
        ("Register clients", step_clients),
        ("Health check", health_check),
    ]
    with tqdm(
        total=len(steps), desc="Setting up", unit="step", file=sys.stderr, disable=None
    ) as bar:
        for label, fn in steps:
            bar.set_postfix_str(label)
            try:
                results[label] = fn()
            except Exception as exc:
                bar.close()
                typer.echo(f"✗ {label}: {exc}", err=True)
                raise typer.Exit(1) from exc
            bar.update(1)

    typer.echo("\nUML-MCP is configured:")
    for label, outcome in results.items():
        typer.echo(f"  ✓ {label}: {outcome}")
    typer.echo(
        f"\n  Profile: {profile}   Features: {', '.join(sorted(chosen)) or 'none'}"
    )
    typer.echo("\nNext steps:")
    typer.echo(
        '  • Restart your MCP client and ask: "Draw a sequence diagram of a login"'
    )
    typer.echo("  • Open the dashboard: uml-mcp admin")
    typer.echo(f"  • Change settings later: uml-mcp setup --force  (or edit {target})")


@app.command()
def admin(
    host: Annotated[
        str, typer.Option(help="bind address (loopback only)")
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8765,
    open_browser: Annotated[bool, typer.Option("--open/--no-open")] = True,
    page: Annotated[str, typer.Option(hidden=True)] = "overview",
) -> None:
    """Start the local admin console (setup form, settings, logs, charts)."""
    from ..admin.console import run_console

    run_console(host=host, port=port, open_browser=open_browser, page=page)


plugins_app = typer.Typer(
    help="List, enable and disable plugins.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
app.add_typer(plugins_app, name="plugins")


@plugins_app.command("list")
def plugins_list() -> None:
    """Installed plugins and whether uml-mcp.yaml enables them."""
    from ..core.settings_file import get_app_config
    from ..plugins.loader import discover

    found = discover()
    enabled = set(get_app_config().plugins.enabled)
    if not found and not enabled:
        typer.echo(
            "No plugins installed. See docs/plugins/index.md to add renderers/tools."
        )
        return
    for p in found:
        state = "enabled" if p.enabled else "available"
        dist = f"{p.distribution} {p.version}" if p.distribution else p.target
        typer.echo(f"{p.name:20} {p.group:9} {state:9} {dist}")
    for name in sorted(enabled - {p.name for p in found}):
        typer.echo(f"{name:20} {'?':9} {'MISSING':9} enabled but not installed")


def _toggle(name: str, enabled: bool) -> None:
    from ..admin.settings_service import set_plugin_enabled

    result = set_plugin_enabled(name, enabled, actor="cli")
    typer.echo(
        f"{'Enabled' if enabled else 'Disabled'} {name} in {result['saved']}. "
        "Restart the server to apply."
    )


@plugins_app.command("enable")
def plugins_enable(name: str) -> None:
    """Add a plugin to plugins.enabled."""
    _toggle(name, True)


@plugins_app.command("disable")
def plugins_disable(name: str) -> None:
    """Remove a plugin from plugins.enabled."""
    _toggle(name, False)


kroki_app = typer.Typer(
    help="Run a local Kroki (with every companion) in Docker and check it.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
app.add_typer(kroki_app, name="kroki")


def _print_health(report: dict[str, Any]) -> bool:
    from ..kroki.health import ready

    state = "reachable" if report["reachable"] else f"unreachable ({report['error']})"
    typer.echo(f"Kroki {report['version'] or ''} at {report['url']}: {state}")
    for dtype, check in report["companions"].items():
        typer.echo(f"  {'ok ' if check['ok'] else 'ERR'} {dtype:11} {check['detail']}")
    return ready(report)


def _use(url: str) -> None:
    from fastapi import HTTPException

    from ..admin.kroki_routes import use_kroki

    try:
        result = use_kroki(url, actor="cli")
    except HTTPException as exc:
        typer.echo(f"Not saved: {exc.detail}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"rendering.kroki_server = {url} saved in {result['saved']}.")


@kroki_app.command("up")
def kroki_up(
    port: Annotated[int, typer.Option(help="host port (loopback only)")] = 8001,
    use: Annotated[
        bool, typer.Option("--use", help="save it as rendering.kroki_server")
    ] = False,
    timeout: Annotated[
        float, typer.Option(help="seconds to wait for companions")
    ] = 300,
) -> None:
    """Start Kroki + mermaid, blockdiag, bpmn and excalidraw (pulls images once)."""
    from ..kroki import health, stack

    typer.echo(f"Starting Kroki with all companions ({stack.compose_path()})...")
    try:
        result = stack.up(port)
    except stack.StackError as exc:
        typer.echo(f"Could not start Kroki: {exc}", err=True)
        raise typer.Exit(1) from exc
    report = health.wait_until_ready(result["url"], timeout, trust_env=False)
    ok = _print_health(report)
    if use:
        _use(result["url"])
    if not ok:
        raise typer.Exit(1)


@kroki_app.command("down")
def kroki_down() -> None:
    """Stop and remove the local Kroki containers."""
    from ..kroki import stack

    try:
        result = stack.down()
    except stack.StackError as exc:
        typer.echo(f"Could not stop Kroki: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo("Stopped." if result["stopped"] else result["detail"])


@kroki_app.command("status")
def kroki_status(
    url: Annotated[
        str | None, typer.Option(help="Kroki URL (default: the configured one)")
    ] = None,
) -> None:
    """Check the configured (or given) Kroki and every companion renderer."""
    from ..core.config import MCP_SETTINGS
    from ..kroki import health, stack

    info = stack.status()
    typer.echo(f"Docker: {info['detail']}")
    for c in info["containers"]:
        typer.echo(f"  {c['service']:11} {c['state']:9} {c['status'] or ''}")
    if not _print_health(health.probe(url or MCP_SETTINGS.kroki_server)):
        raise typer.Exit(1)


@kroki_app.command("logs")
def kroki_logs(tail: Annotated[int, typer.Option()] = 100) -> None:
    """Recent logs of the local Kroki containers."""
    from ..kroki import stack

    try:
        typer.echo(stack.logs(tail))
    except stack.StackError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def main(argv: list[str]) -> int:
    try:
        # standalone_mode=False returns typer.Exit codes instead of raising them
        code = app(args=argv, prog_name="uml-mcp", standalone_mode=False)
        if isinstance(code, int):
            return code
    except typer.Exit as exc:
        return int(exc.exit_code or 0)
    except typer.Abort:
        return 1
    except Exception as exc:
        # Usage errors (Typer's vendored click): show them like the standalone CLI.
        show = getattr(exc, "show", None)
        code = getattr(exc, "exit_code", None)
        if callable(show) and isinstance(code, int):
            show()
            return code
        raise
    return 0


__all__ = ["TYPER_COMMANDS", "app", "main", "validate_config", "write_config_file"]
