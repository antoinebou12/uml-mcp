#!/usr/bin/env python3
"""UML-MCP installer. Needs only Python 3.12+, typer and tqdm.

    python install.py                 # uv tool > pipx > pip --user, then the setup wizard
    python install.py --dry-run       # show what would run
    uvx --with typer --with tqdm python install.py

It installs the ``uml-mcp`` command for the current user and then starts
``uml-mcp setup`` (use ``--no-setup`` to skip, ``--web`` for the browser form).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Annotated

try:
    import typer
    from tqdm import tqdm
except ImportError:  # pragma: no cover - guidance for bare interpreters
    sys.stderr.write(
        "This installer needs typer and tqdm:  python -m pip install typer tqdm\n"
    )
    raise SystemExit(1) from None

PACKAGE = "uml-mcp"
METHODS = ("uv", "pipx", "pip")

cli = typer.Typer(add_completion=False, rich_markup_mode=None)


def detect_method(which=shutil.which) -> str:
    if which("uv"):
        return "uv"
    if which("pipx"):
        return "pipx"
    return "pip"


def install_command(method: str, version: str | None, extras: str | None) -> list[str]:
    spec = (
        PACKAGE
        + (f"[{extras}]" if extras else "")
        + (f"=={version}" if version else "")
    )
    if method == "uv":
        return ["uv", "tool", "install", "--force", spec]
    if method == "pipx":
        return ["pipx", "install", "--force", spec]
    if method == "pip":
        return [sys.executable, "-m", "pip", "install", "--user", "--upgrade", spec]
    raise typer.BadParameter(f"method must be one of {', '.join(METHODS)}")


def plan(
    method: str, version: str | None, extras: str | None, setup: bool, web: bool
) -> list[list[str]]:
    steps = [install_command(method, version, extras)]
    if setup:
        steps.append(["uml-mcp", "setup", *(["--web"] if web else [])])
    return steps


@cli.command()
def main(
    method: Annotated[
        str | None, typer.Option(help="uv | pipx | pip (default: auto)")
    ] = None,
    version: Annotated[
        str | None, typer.Option(help="exact version, e.g. 1.4.0")
    ] = None,
    extras: Annotated[str | None, typer.Option(help="extras, e.g. otel")] = None,
    setup: Annotated[bool, typer.Option("--setup/--no-setup")] = True,
    web: Annotated[bool, typer.Option(help="run the browser setup form")] = False,
    dry_run: Annotated[bool, typer.Option(help="print commands only")] = False,
) -> None:
    """Install UML-MCP for this user and run the setup wizard."""
    if sys.version_info < (3, 12):  # noqa: UP036 - the installer may run on an old python
        typer.echo("UML-MCP needs Python 3.12 or newer.", err=True)
        raise typer.Exit(1)
    chosen = method or detect_method()
    steps = plan(chosen, version, extras, setup, web)
    if dry_run:
        for cmd in steps:
            typer.echo(" ".join(cmd))
        return
    with tqdm(total=len(steps), desc="Installing UML-MCP", unit="step") as bar:
        for cmd in steps:
            bar.set_postfix_str(cmd[0] if cmd[0] != sys.executable else "pip")
            if cmd[0] == "uml-mcp":
                bar.close()  # hand the terminal to the interactive wizard
                resolved = shutil.which("uml-mcp")
                if not resolved:
                    typer.echo(
                        "Installed. Open a new terminal, then run: uml-mcp setup"
                    )
                    return
                cmd = [resolved, *cmd[1:]]
            code = subprocess.call(cmd)
            if code != 0:
                typer.echo(f"Command failed ({code}): {' '.join(cmd)}", err=True)
                raise typer.Exit(code)
            if not bar.disable:
                bar.update(1)
    typer.echo("Done. Run `uml-mcp admin` to open the dashboard.")


if __name__ == "__main__":
    cli()
