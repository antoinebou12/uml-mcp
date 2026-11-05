# uml-mcp-plugin-stack-diagram

Stack and cloud architecture diagrams for [UML-MCP](https://github.com/antoinebou12/uml-mcp), in
an "engineered paper" style: icon tiles, nested vendor and region groups, labelled right-angled
edges. Describe nodes, groups and edges; the plugin lays them out.

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-stack-diagram
uml-mcp plugins enable stack-diagram
```

Restart the server. The `stack_diagram` type renders to `html` (pan, zoom, fit, light/dark toggle)
or `svg`. It flows left to right (`LR`), right to left (`RL`), top down (`TB`) or bottom up (`BT`),
in `dark`, `light` or `auto`.

```json
{
  "title": "SaaS stack",
  "direction": "LR",
  "theme": "dark",
  "groups": [{"id": "vercel", "name": "Vercel"}],
  "nodes": [
    {"id": "user", "name": "User", "role": "browser", "icon": "user"},
    {"id": "web", "name": "Next.js", "role": "frontend", "icon": "browser", "group": "vercel"},
    {"id": "db", "name": "Neon", "role": "postgres", "icon": "database"}
  ],
  "edges": [
    {"from": "user", "to": "web", "label": "HTTPS"},
    {"from": "web", "to": "db", "label": "SQL"}
  ]
}
```

See [`docs/plugins/stack-diagram.md`](../../../docs/plugins/stack-diagram.md) for the source
reference, layout rules and icons. The [archify plugin](../uml-mcp-plugin-archify) builds on this
package's layout engine.

Brand logos are trademarks and are not bundled: use the built-in glyphs, or pass a logo as an
`icon` data URI.
