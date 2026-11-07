---
name: d3_force
description: >-
  Writes valid d3_force JSON for uml-mcp (diagram_type=d3_force, bundled plugin d3). Use when the user asks for a force-directed network or dependency graph; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# d3_force diagram (uml-mcp plugin `d3`)

**`diagram_type`:** `d3_force`  
**Backend:** `plugin:d3` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

Interactive force-directed graph (D3): drag and pin nodes, zoom, pan, hover to highlight. JSON nodes and links; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/d3-plugins/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Show our microservices as a force graph, grouped by team.

## Notation tips

- `nodes` (`id`, `label`, `group`, `service`, `docs`) and `links` (`source`, `target`, `label`).
- `service` (`postgres`, `kafka`, `aws:lambda`, `database`) draws an icon in the circle and links its docs.
- Keep it under a few hundred nodes; readers drag, pin, and click a node for its details.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Service dependencies","directed":true,"nodes":[{"id":"web","label":"Web app","group":"frontend","service":"react","size":1.4},{"id":"mobile","label":"Mobile app","group":"frontend","service":"mobile"},{"id":"gateway","label":"API gateway","group":"edge","service":"nginx","size":1.6},{"id":"auth","label":"Auth","group":"backend","service":"keycloak"},{"id":"orders","label":"Orders","group":"backend","service":"nodejs","size":1.3},{"id":"billing","label":"Billing","group":"backend","service":"python"},{"id":"db","label":"Postgres","group":"data","service":"postgres","size":1.4,"note":"primary + replica"},{"id":"queue","label":"Events","group":"data","service":"kafka"}],"links":[{"source":"web","target":"gateway"},{"source":"mobile","target":"gateway"},{"source":"gateway","target":"auth"},{"source":"gateway","target":"orders","label":"REST"},{"source":"orders","target":"db"},{"source":"orders","target":"queue","label":"publishes"},{"source":"billing","target":"queue","label":"consumes"},{"source":"billing","target":"db"}]}
```
