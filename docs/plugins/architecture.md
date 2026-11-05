# Architecture diagrams (experimental)

The `architecture` type draws tiles at the positions you give, for diagrams that must
match a reference layout exactly. It ships inside `uml-mcp` but is off by default; for
auto-laid-out diagrams use [stack diagrams](stack-diagram.md) instead. Enable it in
`uml-mcp.yaml`:

```yaml
plugins:
  enabled: [architecture]
```

Call `generate_uml` with `diagram_type: architecture`, `output_format: html`,
and a JSON string in `code`. Hosts supporting MCP Apps receive HTML in the
diagram viewer's sandboxed frame. TSX is an export for application source code;
choose `output_format: tsx` for that output.

```json
{
  "title": "Application",
  "theme": "dark",
  "width": 1000,
  "height": 540,
  "nodes": [
    {"id": "web", "name": "Frontend", "role": "browser", "cx": 220, "top": 120},
    {"id": "api", "name": "API", "role": "service", "cx": 600, "top": 350}
  ],
  "edges": [{"source": "web", "target": "api", "label": "HTTPS"}]
}
```

Nodes have 60px tiles and 132px-wide label boxes. Leave at least 140px between
centers on one row and between tile tops on successive rows. An optional `icon`
is a base64 image data URI. Embedded SVGs are checked for active content and
external references; accepted images retain their bytes and colors.

Groups use `{"name": "Hosting", "nodes": ["web", "api"]}`. Their padding is
computed from their members and must fit within the canvas.

Edges default to accent-colored solid arrows. Set `neutral: true` for neutral
edges or `dashed: true` for deployment paths. Straight and elbow routes are
computed from endpoint positions. For crowded diagrams, supply `via` as a list
of `[x, y]` intermediate points. Every segment must be horizontal or vertical,
stay inside the canvas, and avoid tiles and labels. Invalid routes return an
error so their geometry can be corrected before rendering.

Malformed sources (not JSON, missing coordinates, unknown group members or edge ends)
return a readable validation error. Logo preparation commands and upstream attribution
are in `scripts/architecture/README.md`. Nested groups and the complete reference styling
are not done yet.
