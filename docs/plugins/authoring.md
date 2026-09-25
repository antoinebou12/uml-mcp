---
title: Plugin author guide
description: "Write a UML-MCP plugin: entry points, PluginContext.tool for MCP tools, the Renderer protocol for diagram types, settings, testing and publishing."
---

# Plugin author guide

This guide builds the example plugin
[`uml-mcp-plugin-hello`](https://github.com/antoinebou12/uml-mcp/tree/main/examples/plugins/uml-mcp-plugin-hello)
step by step. It provides one tool (`hello_echo`) and one renderer (`ascii`).

## 1. Package layout

```text
uml-mcp-plugin-hello/
├── pyproject.toml
└── src/uml_mcp_plugin_hello/__init__.py
```

```toml
[project]
name = "uml-mcp-plugin-hello"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["uml-mcp>=1.4.0"]

[project.entry-points."uml_mcp.tools"]
hello = "uml_mcp_plugin_hello:register"          # callable(ctx: PluginContext)

[project.entry-points."uml_mcp.renderers"]
ascii = "uml_mcp_plugin_hello:AsciiRenderer"     # Renderer class (or instance)
```

The entry-point **name** (`hello`, `ascii`) is what users put in `plugins.enabled`.

## 2. A tool

```python
from mcp_core.plugins import PluginContext


def register(ctx: PluginContext) -> None:
    greeting = str(ctx.settings.get("greeting", "Hello"))  # plugins.settings.hello

    @ctx.tool(
        "echo",  # exposed as hello_echo
        "Echo a message back with the configured greeting. Useful to verify that "
        "plugins are installed and enabled.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        output_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        example="hello_echo(text='world')",
    )
    def echo(text: str) -> dict[str, str]:
        """Echo text.

        Args:
            text: what to echo back
        """
        return {"message": f"{greeting}, {text}!"}
```

`PluginContext` gives you:

| Member | Purpose |
| --- | --- |
| `ctx.tool(name, description, *, annotations, output_schema, example)` | Register an MCP tool named `<plugin>_<name>` |
| `ctx.settings` | The plugin's `plugins.settings.<name>` mapping |
| `ctx.logger` | Logger `uml_mcp.plugins.<name>` (shows on the console's Logs page) |

Guidelines. `uml-mcp lint` enforces most of these:

- **Description:** 40+ characters saying what the tool does, when to use it and what it returns.
- **Annotations:** set all four hints. `readOnlyHint: True` means the tool needs only
  **read** permission in enterprise mode.
- **Typing:** type every parameter and document it under `Args:`.
- **Results:** return a `dict` that matches `output_schema`. To signal a failure, return
  `{"error": "..."}`; it becomes an MCP tool error and is audited as an error.

## 3. A renderer

```python
from html import escape

from mcp_core.plugins import DiagramTypeSpec, RenderOutput


class AsciiRenderer:
    name = "ascii"

    def __init__(self) -> None:
        self.diagram_types = {
            "ascii": DiagramTypeSpec(
                "Plain text / ASCII art rendered as SVG", ("svg",)
            ),
        }

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if output_format != "svg":
            raise ValueError("ascii renders svg only")
        lines = code.splitlines() or [""]
        body = "".join(
            f'<text x="12" y="{24 + i * 18}">{escape(line)}</text>'
            for i, line in enumerate(lines)
        )
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" font-family="monospace">{body}</svg>'
        return RenderOutput(svg.encode(), "image/svg+xml")
```

| Protocol member | Meaning |
| --- | --- |
| `name` | Shown as the result's `source` (`plugin:<name>`) |
| `diagram_types` | `{type: DiagramTypeSpec(description, formats)}`; the types must be new (built-ins can't be replaced) |
| `render(diagram_type, code, output_format)` | Returns `RenderOutput(content: bytes, mime_type, url=None)`; raise to report an error |

When a request targets a plugin type, `generate_uml` renders through your renderer
**instead of** Kroki. The bytes are returned as `content_base64` with the MIME type, and
the attempt is recorded as `{"backend": "plugin:<name>", "ok": true}`. Escape any user
input you embed in markup, as the example does.

## 4. Try it

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-hello
uml-mcp plugins enable hello && uml-mcp plugins enable ascii
uml-mcp admin          # Tools & plugins shows both as loaded
uml-mcp lint --strict  # your tool must keep the grade at A
```

## 5. Test it

Point the loader at your entry points and allow-list them in a temporary config.
[`tests/test_plugins.py`](https://github.com/antoinebou12/uml-mcp/blob/main/tests/test_plugins.py)
shows the pattern:

```python
import importlib.metadata as md
from mcp_core.plugins import loader


def test_my_plugin(monkeypatch, tmp_path):
    eps = {
        "uml_mcp.tools": [
            md.EntryPoint("hello", "uml_mcp_plugin_hello:register", "uml_mcp.tools")
        ]
    }
    monkeypatch.setattr(loader, "entry_points", lambda group: eps.get(group, []))
    cfg = tmp_path / "uml-mcp.yaml"
    cfg.write_text("plugins: {enabled: [hello]}\n")
    monkeypatch.setenv("UML_MCP_CONFIG", str(cfg))
    from mcp_core.core.settings_file import reset_config_cache

    reset_config_cache()
    status = {s.name: s for s in loader.load_plugins()}
    assert status["hello"].loaded and status["hello"].tools == ["hello_echo"]
```

## 6. Publish

- Name the package `uml-mcp-plugin-<name>` so people can find it, and depend on
  `uml-mcp>=1.4.0`.
- Document the entry-point names and settings in your README.
- Only `mcp_core.plugins` (`PluginContext`, `Renderer`, `DiagramTypeSpec`, `RenderOutput`)
  is the stable API. Don't import other `mcp_core` internals.
