# uml-mcp-plugin-d3

Interactive [D3.js](https://d3js.org) diagrams for [UML-MCP](https://github.com/antoinebou12/uml-mcp).
Each type renders to a standalone **HTML** page (zoom, pan, drag, "Save HTML") or a static
**SVG**, locally, with no network calls beyond the pinned D3 script.

| Diagram type | What it draws |
| --- | --- |
| `d3_force` | A force-directed graph: drag and pin nodes, hover to highlight |
| `d3_architecture` | Boxes in nested groups with AWS, Azure, Google Cloud and Kubernetes style icons, input and output ports, and straight right-angled arrows routed around the boxes with A* (flows left to right) |
| `d3_topology` | The same engine flowing top to bottom, for deployments and networks |

It also adds one read-only tool, `d3_catalog`, listing the providers, service names and icon
kinds a diagram can use.

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-d3   # next to uml-mcp
uml-mcp plugins enable d3                              # enables the tool and the renderer
```

Then restart the server. Read the full guide in
[docs/plugins/d3.md](../../../docs/plugins/d3.md).

## Settings (`plugins.settings.d3` in `uml-mcp.yaml`)

| Key | Default | Meaning |
| --- | --- | --- |
| `d3_source` | `cdn` | `cdn` loads D3 7.9.0 from jsDelivr (pinned, with a Subresource Integrity hash); `inline` embeds the vendored copy so the page works offline (about 280 KB larger) |
| `max_nodes` | `400` | Refuse diagrams with more nodes (400 is the hard cap) |

## Licence

The plugin follows UML-MCP's licence. It bundles D3 7.9.0 (ISC, see
`src/uml_mcp_plugin_d3/assets/d3.LICENSE`). The icons are original line glyphs drawn for this
plugin in the colour of each node's category, with a provider badge, a monogram tile for popular
software, or a `logo` you give a node; they are not the vendors' own artwork.
