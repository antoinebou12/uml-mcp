---
name: d3_topology
description: >-
  Writes valid d3_topology JSON for uml-mcp (diagram_type=d3_topology, bundled plugin d3). Use when the user asks for a deployment or network topology flowing top to bottom; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# d3_topology diagram (uml-mcp plugin `d3`)

**`diagram_type`:** `d3_topology`  
**Backend:** `plugin:d3` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

Deployment or network topology (D3), flowing top to bottom, with zones, tiers and device icons; same engine and JSON as d3_architecture; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/d3-plugins/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Draw our Kubernetes deployment: ingress, two services, a database and a cache, top to bottom.

## Notation tips

- Same JSON as `d3_architecture`; the layout runs top to bottom.
- Use zones and tiers as groups; ports (`inputs`, `outputs`) pin where arrows attach.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Web application deployment","provider":"generic","groups":[{"id":"dmz","label":"DMZ","type":"zone"},{"id":"prod","label":"Production","type":"env"},{"id":"app","label":"App tier","type":"system","parent":"prod"},{"id":"data","label":"Data tier","type":"system","parent":"prod"}],"nodes":[{"id":"client","label":"Browsers","kind":"user"},{"id":"fw","label":"Firewall","kind":"firewall","group":"dmz"},{"id":"lb","label":"Load balancer","kind":"loadbalancer","group":"dmz"},{"id":"web1","label":"web-1","service":"kubernetes:pod","group":"app"},{"id":"web2","label":"web-2","service":"kubernetes:pod","group":"app"},{"id":"cache","label":"Redis","kind":"cache","group":"data"},{"id":"db","label":"PostgreSQL","kind":"database","group":"data"}],"links":[{"from":"client","to":"fw","label":"443"},{"from":"fw","to":"lb"},{"from":"lb","to":"web1"},{"from":"lb","to":"web2"},{"from":"web1","to":"cache"},{"from":"web2","to":"cache"},{"from":"web1","to":"db","label":"5432"},{"from":"web2","to":"db"}]}
```
