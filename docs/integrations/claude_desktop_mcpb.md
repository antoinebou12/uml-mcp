# Claude Desktop extension (.mcpb)

UML-MCP ships as an [MCP Bundle](https://github.com/modelcontextprotocol/mcpb) — a single
`.mcpb` file you drop into Claude Desktop. No clone, no `PYTHONPATH`, no hand-edited
`claude_desktop_config.json`.

If you would rather wire the server up manually, the JSON configuration is still documented
in [Claude Desktop integration](claude_desktop.md).

## Requirements

- Claude Desktop with extension support
- [`uv`](https://docs.astral.sh/uv/) on your `PATH` — Claude Desktop launches the bundle with
  `uv run`, and `uv` provisions Python 3.12+ and the dependencies on first start
- Network access to a Kroki server (the public `https://kroki.io` by default)

## Install

1. Get the bundle:
   - download `uml-mcp-<version>.mcpb` from the **Build MCPB Bundle** workflow artifacts, or
   - build it yourself (see below).
2. Open Claude Desktop → **Settings** → **Extensions**.
3. Drag the `.mcpb` file into the window, or use **Install extension** and pick the file.
4. Review the permissions and confirm.

The first launch takes a few seconds while `uv` creates the bundle's virtual environment.

## Settings

Claude Desktop shows three optional fields after install. All of them can stay empty.

| Setting | Effect when empty | Effect when set |
|---|---|---|
| **Diagram output directory** | Diagrams come back as a render URL plus inline image data; nothing is written to disk | Diagrams are also saved as files in that folder, and the folder becomes the write sandbox (`MCP_OUTPUT_DIR` + `MCP_OUTPUT_ROOT`) |
| **Kroki server URL** | `https://kroki.io` | Points rendering at your own Kroki instance, so diagram source never leaves your network |
| **PlantUML server URL** | `https://www.plantuml.com/plantuml` | PlantUML fallback used when Kroki cannot render a PlantUML-family diagram |

Setting an output directory is what makes Claude Desktop's **Save** action useful — without it
there is no local file to save. The directory doubles as the sandbox root, so the server will
refuse to write anywhere outside the folder you picked.

See [Configuration](../configuration.md) for the full environment-variable reference.

## Verify

Start a new conversation and ask:

```
Create a UML class diagram for a simple e-commerce system with Customer, Product and Order.
```

Claude should call `generate_uml` and return a rendered diagram. `list_diagram_types` tells you
what else is available; `validate_uml` checks syntax without rendering; `generate_uml_batch`
renders several diagrams in one call.

## Build the bundle yourself

```bash
uv sync --all-groups
uv run python scripts/build_mcpb.py
```

This produces `dist/uml-mcp-<version>.mcpb`. Useful flags:

| Flag | Purpose |
|---|---|
| `--skip-pack` | Stage and audit into `dist/mcpb-stage/` without invoking the `mcpb` CLI |
| `--no-lock` | Skip `uv lock`; the bundle then resolves dependencies on the user's machine |
| `--out DIR` | Write somewhere other than `dist/` |

The script assembles the bundle from an explicit allowlist — `server.py`, the `mcp_core` and
`tools` packages, `LICENSE`, a generated `pyproject.toml`, and `uv.lock`. Tests, documentation,
caches, logs, `.env` files and build output are never copied, and the build fails loudly if any
of them turn up in the staged tree.

The bundle's `pyproject.toml` is generated from the repository's own, copying `requires-python`
and `dependencies` verbatim, with `[tool.uv] package = false` so `uv` installs the dependencies
without building UML-MCP itself.

Smoke-test the staged bundle before shipping it:

```bash
uv run --directory dist/mcpb-stage python server.py --list-tools
```

All four tools — `generate_uml`, `generate_uml_batch`, `validate_uml`, `list_diagram_types` —
should be listed.

## Troubleshooting

**The extension fails to start.** Confirm `uv --version` works in a terminal. Claude Desktop
inherits your login shell's `PATH`; if `uv` was installed after Claude Desktop started, restart
the app.

**Diagrams render but nothing is saved.** No output directory is configured. Set one in the
extension settings.

**`output_dir must stay under configured output root`.** A tool call asked to write outside the
folder you configured. Either widen the setting or drop the explicit `output_dir` from the
request.

**Corporate network blocks kroki.io.** Run [Kroki locally](../deploy/docker.md) and point the
**Kroki server URL** setting at it.

## Attribution

Packaging by Antoine Boucher. The bundle format is
[MCPB](https://github.com/modelcontextprotocol/mcpb) `0.4`, built with
`@anthropic-ai/mcpb@2.1.2`.
