# uml-mcp-plugin-archify

Architecture and workflow diagrams for [UML-MCP](https://github.com/antoinebou12/uml-mcp) with
dashed, colour-coded group containers (security, frontend, backend, bus, workers, database,
cloud) and glowing icon cards. It shares the layout engine, JSON format, directions
(`LR` `RL` `TB` `BT`) and themes (`dark` `light` `auto`) of
[`uml-mcp-plugin-stack-diagram`](../uml-mcp-plugin-stack-diagram), which it depends on.

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-stack-diagram
uv pip install -e examples/plugins/uml-mcp-plugin-archify
uml-mcp plugins enable archify
```

| Type | Starts as |
| --- | --- |
| `archify_architecture` | left to right |
| `archify_workflow` | top down |
| `archify_sequence` | participants across the top |

Group `style` picks the colour (`security`, `frontend`, `backend`, `bus`, `workers`, `database`,
`cloud`, `external`, `default`); nodes inherit it. See
[`docs/plugins/archify.md`](../../../docs/plugins/archify.md).

Presets `classic`, `blueprint` and `flow`, a legend, node tags, and an HTML page with click-to-focus and
shift-click shortest path come with it. Only architecture, workflow and sequence diagrams are implemented, not the other kinds the original
archify project offers.
