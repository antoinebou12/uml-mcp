---
title: Installation
description: "Install UML-MCP in minutes: the one-file installer, the uml-mcp setup wizard, the web setup form, or a manual configuration. Also covers development installs and local renderers."
---

# Installation

| Path | Best for | Command |
| --- | --- | --- |
| **Installer** | Anyone; needs only Python 3.12+, typer and tqdm | `python scripts/install.py` |
| **Setup wizard** | Terminal users | `uv tool install uml-mcp && uml-mcp setup` |
| **Web setup** | A guided form in the browser | `uml-mcp setup --web` |
| **Hosted** | No install at all | `https://uml-mcp.vercel.app/mcp` in your MCP client |
| **Server / Kubernetes** | Teams | [Docker](deploy/docker.md) · [Helm + SSO](enterprise/enterprise-guide.md) |

## 1. Quick install

```bash
python scripts/install.py            # or: uvx --with typer --with tqdm python scripts/install.py
```

The installer picks **uv** (`uv tool install`), then **pipx**, then **pip --user**,
shows progress and then starts the setup wizard.

| Option | Meaning |
| --- | --- |
| `--method uv\|pipx\|pip` | Force an installer |
| `--version 1.4.0` | Pin a version |
| `--extras otel` | Optional extras (`otel` = OpenTelemetry) |
| `--web` | Run the browser setup form instead of the terminal wizard |
| `--no-setup` | Install only |
| `--dry-run` | Print the commands, change nothing |

Prefer doing it yourself? `uv tool install uml-mcp` (or `pipx install uml-mcp`).

## 2. Setup wizard (`uml-mcp setup`)

```bash
uml-mcp setup
```

The wizard asks for:

- a **profile** (`local`, `docker` or `enterprise`)
- which **features** to turn on (each one is explained, with whether it applies live or needs a restart)
- a Kroki server
- which **MCP clients** to register

It then runs, with a progress bar:

1. validate the configuration
2. write `~/.config/uml-mcp/config.yaml` (mode `0600`, with a backup of any previous file)
3. register the clients
4. run a health check

| Feature key | What it does | Applies |
| --- | --- | --- |
| `memory_only` | Keep diagrams in memory; return URLs/bytes, no files | restart |
| `diagram_fallback` | Retry with PlantUML server or mermaid.ink when Kroki fails | restart |
| `audit` | MXCP-style audit trail of every call (redacted) | live |
| `json_logs` | One JSON object per log line | live |
| `metrics_endpoint` | Prometheus `/metrics` | restart |
| `otel` | OpenTelemetry traces (needs `uml-mcp[otel]`) | live |
| `rate_limit` | Token-bucket limits per client/user, route and tool | live |
| `local_dashboard` | Admin console on `127.0.0.1` without SSO | restart |

Non-interactive, for scripts and CI:

```bash
uml-mcp setup --profile docker --enable otel --disable rate_limit \
  --kroki-server http://kroki:8000 --client cursor --path ./uml-mcp.yaml --yes
uml-mcp setup --profile enterprise --dry-run      # print the YAML only
```

## 3. Web setup and the console

```bash
uml-mcp setup --web        # opens the Setup page
uml-mcp admin              # opens the console (Overview)
```

This starts a local server with the MCP endpoint (`http://127.0.0.1:8765/mcp`) and
the [admin console](admin/index.md). The terminal prints a **one-time setup token**,
which the browser link carries in its URL fragment. The console needs the token
to save settings, register clients or stop the server. Only loopback clients can
reach it.

The **Setup** page walks through the same steps as the wizard: profile → features →
clients → YAML review → Save. Change anything later on the **Settings** page.

## 4. Manual configuration

```bash
uml-mcp config init --profile local        # commented template
uml-mcp config validate
uml-mcp client install --client vscode     # or cursor, claude-desktop, claude-code
```

- **Settings file:** every setting is described in the [uml-mcp.yaml reference](configuration/uml-mcp-yaml.md). Environment variables ([Configuration](configuration.md)) always win over the file.
- **Client registration:** `client install` merges a stdio entry into the client's config, keeps a backup and supports `--dry-run`. For Claude Code it prints the `claude mcp add` command instead of writing a file.

| Client | File written (user scope) |
| --- | --- |
| VS Code | `~/.config/Code/User/mcp.json` (macOS `~/Library/Application Support/Code/User`, Windows `%APPDATA%\Code\User`) |
| Cursor | `~/.cursor/mcp.json` |
| Claude Desktop | `claude_desktop_config.json` in the Claude app config folder |
| Claude Code | none: run the printed `claude mcp add --scope user uml-mcp -- uml-mcp --transport stdio` |

## 5. Extend with plugins

Install a plugin package next to UML-MCP, then enable it:

```bash
uml-mcp plugins list
uml-mcp plugins enable hello
```

See [Plugins](plugins/index.md).

## Development install (from a clone)

```bash
git clone https://github.com/antoinebou12/uml-mcp.git && cd uml-mcp
uv sync --all-groups              # tests, lint, docs, OTel, Playwright
uv run python server.py           # stdio; add --transport http --port 8000 for HTTP
uv run uvicorn app:app --port 8000   # full HTTP app (REST, AG-UI, console)
uv run python server.py --list-tools
```

To work on the console, see [Frontend](developers/frontend.md). Poetry
(`poetry install --with dev`) and pip (`pip install -e .`) also work.

## Local diagram servers (optional)

For offline use or to keep diagram source inside your network:

```bash
docker run -d -p 8000:8000 yuzutech/kroki
docker run -d -p 8080:8080 plantuml/plantuml-server
```

Then set `rendering.kroki_server` / `rendering.plantuml_server`, either in the
Settings page or `uml-mcp.yaml`, or with `KROKI_SERVER` / `PLANTUML_SERVER`.

## Uninstall

```bash
uv tool uninstall uml-mcp          # or: pipx uninstall uml-mcp
rm -rf ~/.config/uml-mcp ~/.local/state/uml-mcp
```

Then remove the `uml-mcp` entry from your client's MCP config. A backup of the
previous config is kept next to it.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `uml-mcp: command not found` | Open a new terminal, or run `uv tool update-shell` or `pipx ensurepath` |
| Setup page says "Enter the setup token" | Use the token printed by `uml-mcp admin`, or set `UML_MCP_ADMIN_TOKEN` |
| Diagrams fail to render | Check `rendering.kroki_server` reachability; enable `diagram_fallback` |
| Settings are read-only | The file is mounted read-only (e.g. Kubernetes); use **Download YAML** and apply it through your deployment |
| `uml-mcp lint` reports CFG010 | `pip install "uml-mcp[otel]"` or turn OpenTelemetry off |
