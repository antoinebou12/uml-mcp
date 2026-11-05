---
name: stack_diagram
description: >-
  Writes valid stack_diagram JSON for uml-mcp (diagram_type=stack_diagram, bundled plugin stack-diagram). Use when the user asks for a stack or cloud diagram with icon tiles, nested vendor and region groups; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# stack_diagram diagram (uml-mcp plugin `stack-diagram`)

**`diagram_type`:** `stack_diagram`  
**Backend:** `plugin:stack-diagram` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

Stack or cloud architecture diagram: icon tiles, nested vendor/region groups and labelled orthogonal edges, auto-laid out left-right or top-down in dark or light. JSON nodes, groups and edges; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/stack-diagram/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Draw my stack: Next.js and Hono on Vercel, Neon Postgres, Clerk for auth, Stripe for payments, GitHub Actions deploys. Left to right.

## Notation tips

- `nodes` (`id`, `name`, `role`, `icon`, `group`, `tag`), `groups` (`id`, `name`, `parent`, `style`), `edges` (`from`, `to`, `label`, `style`, `step`).
- `icon` takes a brand (`github`, `vercel`, `aws`, `claude`...) for a real logo, or a glyph (`database`, `cache`, `queue`...).
- `direction`: `LR`, `RL`, `TB`, `BT`. Add `step` numbers to show a request path.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"SaaS stack","direction":"LR","theme":"dark","groups":[{"id":"vercel","name":"Vercel","style":"plain","icon":"vercel"},{"id":"github","name":"GitHub","style":"vendor","tone":"blue","icon":"github"}],"nodes":[{"id":"user","name":"User","role":"browser","icon":"user"},{"id":"web","name":"Next.js","role":"frontend","icon":"browser","group":"vercel"},{"id":"api","name":"Hono","role":"api routes","icon":"function","group":"vercel"},{"id":"db","name":"Neon","role":"serverless postgres","icon":"database"},{"id":"auth","name":"Clerk","role":"auth","icon":"lock"},{"id":"pay","name":"Stripe","role":"payments","icon":"payments"},{"id":"ci","name":"GitHub Actions","role":"ci","icon":"github","group":"github"}],"edges":[{"from":"user","to":"web","label":"HTTPS"},{"from":"web","to":"api","label":"RPC"},{"from":"api","to":"db","label":"SQL"},{"from":"api","to":"auth","label":"session","tone":"neutral"},{"from":"api","to":"pay","label":"checkout","tone":"neutral"},{"from":"ci","to":"web","label":"deploy","style":"dashed"}]}
```
