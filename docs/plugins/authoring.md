---
title: Plugin author guide
description: "Write a UML-MCP plugin: entry points, PluginContext.tool for MCP tools, the Renderer protocol for diagram types, settings, testing and publishing."
---

# Plugin author guide

This guide builds the example plugin
[`uml-mcp-plugin-hello`](https://github.com/antoinebou12/uml-mcp/tree/main/examples/plugins/uml-mcp-plugin-hello)
step by step. It provides one tool (`hello_echo`) and one renderer (`ascii`).

For a larger plugin, with an interactive HTML renderer, custom validation, settings and tests that
drive a real server and a real browser, read the [D3 diagrams plugin](d3.md) and its
[source](https://github.com/antoinebou12/uml-mcp/tree/main/examples/plugins/uml-mcp-plugin-d3).

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
| `ctx.tool(name, description, *, annotations, output_schema, example, lint_ignore)` | Register an MCP tool named `<plugin>_<name>`. `lint_ignore={"rule": "reason"}` documents a deliberate exception to a `uml-mcp lint` rule; it is reported as suppressed |
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
                "Plain text / ASCII art rendered as SVG",
                ("svg",),
                example="+--------+\n|  UML   |\n|  MCP   |\n+--------+",
                template="+--+\n|  |\n+--+",
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
| `diagram_types` | `{type: DiagramTypeSpec(description, formats, example, template)}`; the types must be new (built-ins can't be replaced) |
| `render(diagram_type, code, output_format)` | Returns `RenderOutput(content: bytes, mime_type, url=None)`; raise to report an error |

`DiagramTypeSpec` fields:

| Field | Meaning |
| --- | --- |
| `description` | One line shown by `list_diagram_types`, `uml://types` and the console. Say what the source looks like |
| `formats` | The `output_format` values the type accepts, for example `("svg",)` or `("html", "svg")`. Other formats are refused before your code runs. `html` is accepted only by types that list it |
| `example` | A complete source that renders well, shown by `uml://examples` and the console |
| `template` | A minimal source to start from, shown by `uml://templates` |

!!! tip "Give every type an example"

    A model learns a custom source format from `uml://examples`. Without one the type shows an
    empty example. Keep them readable (a diagram with text in it, not a blank shape) and test
    that they render.

When a request targets a plugin type, `generate_uml` renders through your renderer
**instead of** Kroki. The bytes are returned as `content_base64` with the MIME type, and
the attempt is recorded as `{"backend": "plugin:<name>", "ok": true}`. Escape any user
input you embed in markup, as the example does. A message in the `ValueError` you raise reaches
the model as `plugin renderer <name> failed: <message>`, so make it say what to fix.

### Optional hooks

A renderer may define two more methods. Neither is part of the protocol check, so a plain
renderer needs neither.

| Method | Called | Use it to |
| --- | --- | --- |
| `validate(diagram_type, code) -> list[str]` | By `validate_uml`, without rendering | Return one message per problem in the source (empty when valid), so a model can fix a custom source in one round trip. A hook that raises is logged and ignored, so it can never turn a good diagram into an error |
| `configure(settings: dict) -> None` | Once at load, with `plugins.settings.<name>` | Read settings. Raise to refuse a bad value: the plugin then shows as failed with that message, and the server still starts |

### What the client receives

| `output_format` | Your `mime_type` | In the MCP result |
| --- | --- | --- |
| `svg`, `png`, `jpeg` | `image/svg+xml`, `image/png`, `image/jpeg` | An image block a chat can show, plus `content_base64` |
| `html`, `txt`, `pdf` | `text/html`, `text/plain`, `application/pdf` | The text summary and `content_base64`; nothing a chat can display |

With an `output_dir` (inside the server's `MCP_OUTPUT_ROOT`), the pipeline writes the file for
you, returns `local_path`, drops `content_base64`, and adds `Saved to: <path>` to the summary. If
the file cannot be written the content is returned instead. Return image formats for previews and
offer `html` for the full experience, as the D3 plugin does. Keep pages small: they travel as
base64 in the result when no folder is given.

### Renderers that produce HTML

The source of a diagram comes from a model or a user, so a page you generate must treat it as
untrusted:

- **Escape everything** you put in markup, and send data to scripts as JSON in a
  `<script type="application/json">` block with `<`, `>` and `&` escaped. Set text with
  `textContent`, never `innerHTML`.
- **Ship a Content-Security-Policy** as a `<meta http-equiv>` tag: `default-src 'none'`, then allow
  your own scripts and style by SHA-256 hash, plus any single pinned CDN script (with an
  `integrity` attribute). Use no inline `style=` attributes or `on...=` handlers: the policy
  blocks them.
- **Make no network calls** from the page, and none from the renderer.
- **Bound the work.** Cap node counts and label lengths so one request cannot ask for an
  unbounded layout.
- **Offer an offline mode** that inlines scripts you vendor (with their licence file), for air-gapped
  installs.

[`html.py`](https://github.com/antoinebou12/uml-mcp/blob/main/examples/plugins/uml-mcp-plugin-d3/src/uml_mcp_plugin_d3/html.py)
in the D3 plugin is a working example of all of these.

## 4. Try it

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-hello
uml-mcp plugins enable hello && uml-mcp plugins enable ascii
uml-mcp admin          # Tools & plugins shows both as loaded
uml-mcp lint --strict  # your tool must keep the grade at A
```

## 5. Test it

Test at three levels. Each catches things the others cannot.

**Unit tests.** Call the renderer and your tool directly. Check the output (parse the SVG, look
for the escaped text), the error messages, and that every `example` and `template` renders
something readable.

**Loader tests.** Point the loader at your entry points and allow-list them in a temporary config.
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

**Real-server tests.** The unit suite runs on a mock FastMCP, so also run the real server in a
subprocess with your plugin enabled and call it as a client does. Use the real client
(`fastmcp.Client`) and the `/mcp` HTTP route, then assert on what came back: the advertised tools,
`uml://types` and `uml://examples`, an image block for `svg`, the error text a model gets for a bad
source. The D3 plugin's
[`tests/fixtures_d3.py`](https://github.com/antoinebou12/uml-mcp/blob/main/tests/fixtures_d3.py)
and
[`tests/test_plugin_d3_mcp.py`](https://github.com/antoinebou12/uml-mcp/blob/main/tests/test_plugin_d3_mcp.py)
are a template. For an HTML renderer, add
[browser tests with Playwright](https://github.com/antoinebou12/uml-mcp/blob/main/tests/test_plugin_d3_browser.py)
that open the pages the server returned, and check that the Content-Security-Policy really blocks
an injected script. A test that cannot fail proves nothing: make each browser check fail by
breaking the code once.

## 6. Publish

- Name the package `uml-mcp-plugin-<name>` so people can find it, and depend on
  `uml-mcp>=1.4.0`.
- Document the entry-point names and settings in your README.
- Ship the files your code loads. With hatchling, `packages = ["src/<package>"]` includes
  everything under the package; read assets with `importlib.resources`, not a relative path. A
  test that lists the files in the package catches a missing one.
- Vendored third-party code needs its licence file next to it, and a pinned version and hash.
- Only `mcp_core.plugins` (`PluginContext`, `Renderer`, `DiagramTypeSpec`, `RenderOutput`)
  is the stable API. Don't import other `mcp_core` internals.
