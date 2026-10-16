---
title: Plugins
description: "Extend UML-MCP with extra MCP tools and diagram renderers from installed Python packages: discovery, allow-list, management and safety."
---

# Plugins

Plugins add capabilities without forking UML-MCP:

| Kind | Entry-point group | Adds |
| --- | --- | --- |
| **Tools** | `uml_mcp.tools` | New MCP tools, named `<plugin>_<tool>` |
| **Renderers** | `uml_mcp.renderers` | New diagram types, rendered locally before Kroki, as images or as an interactive HTML page |

Plugin tools get everything the built-in tools get:

- the audit trail, metrics and OpenTelemetry spans
- rate limits and `tools.enabled`/`disabled`
- `uml-mcp lint`
- enterprise read/write authorization, from `readOnlyHint`

Plugin diagram types appear in `list_diagram_types`, `uml://types`, validation and
the console.

## Install and enable

Plugins are ordinary Python packages installed in the same environment:

```bash
uv tool install uml-mcp --with uml-mcp-plugin-hello     # or: pip install uml-mcp-plugin-hello
uml-mcp plugins list
uml-mcp plugins enable hello        # the tool plugin
uml-mcp plugins enable ascii        # the renderer plugin
```

Then restart the server. Installed plugins are **not** loaded until they are listed in
`plugins.enabled`: an explicit allow-list. One name can serve both kinds: enabling `d3` loads its
tool and its renderer.

```yaml
# uml-mcp.yaml
plugins:
  enabled: [hello, ascii]
  settings:
    hello: {greeting: "Hi"}          # passed to the plugin
```

The console's **Tools & plugins** page lists installed plugins, their status, and any load
error, with an enable/disable switch.

## Plugins in this repository

Both live under `examples/plugins` and are installed from a checkout with
`uv pip install -e examples/plugins/<name>`.

| Plugin | Enable | Adds |
| --- | --- | --- |
| `uml-mcp-plugin-hello` | `hello`, `ascii` | The `hello_echo` tool and an `ascii` diagram type: the smallest complete example |
| `uml-mcp-plugin-d3` | `d3` | Interactive `d3_force`, `d3_architecture` and `d3_topology` diagrams (HTML or SVG), and the `d3_catalog` tool. See the [D3 diagrams plugin](d3.md) |

## Safety

- **Trusted code:** plugins run in the server process with its permissions. Install only
  packages you trust, and pin their versions.
- **Opt-in loading:** nothing loads unless allow-listed. A plugin that fails to load is
  marked with its error, and the server still starts.
- **Collisions:** built-in diagram types can't be overridden, and duplicate tool names
  are rejected.
- **Output formats:** a type accepts only the formats it declares. `html` is accepted by
  plugin types that list it and refused for every built-in type.
- **Cost:** every plugin tool and diagram type is part of what a client loads when it
  connects, in every conversation. The D3 plugin adds about 250 tokens (4,131 to 4,380 in
  `uml-mcp lint`), so enable only what you use. The CI token budget is checked without
  plugins.
- **Lint:** `uml-mcp lint` reports PLG001 for an enabled plugin that isn't installed, and
  PLG002 for one that failed to load.
- **Enterprise:** plugin tools without `readOnlyHint: true` need the **write** scope.

## Write one

Follow the [plugin author guide](authoring.md). A larger example, with an HTML renderer,
custom validation, settings and browser tests, is the [D3 diagrams plugin](d3.md). The smallest lives in
[`examples/plugins/uml-mcp-plugin-hello`](https://github.com/antoinebou12/uml-mcp/tree/main/examples/plugins/uml-mcp-plugin-hello).
