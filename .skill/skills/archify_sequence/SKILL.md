---
name: archify_sequence
description: >-
  Writes valid archify_sequence JSON for uml-mcp (diagram_type=archify_sequence, bundled plugin archify). Use when the user asks for a sequence diagram of calls and replies between participants; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# archify_sequence diagram (uml-mcp plugin `archify`)

**`diagram_type`:** `archify_sequence`  
**Backend:** `plugin:archify` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

Sequence diagram: participants across the top, lifelines and ordered call and reply messages; dark, light or auto. JSON participants and messages; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/archify/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Sequence diagram of a cache-miss request through web, API, auth, Redis and Postgres.

## Notation tips

- `participants` (`id`, `name`, `role`, `icon`, `tone`) and ordered `messages` (`from`, `to`, `label`, `style`, `note`).
- `style: "dashed"` marks a reply; a message to the same participant draws a loop; `autonumber: true` numbers them.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Cache miss request sequence","subtitle":"A dashboard request that misses the cache and falls through to Postgres","theme":"auto","preset":"classic","participants":[{"id":"web","name":"Web App","role":"React UI","icon":"browser","tone":"blue"},{"id":"api","name":"API","role":"request handler","icon":"api","tone":"green"},{"id":"auth","name":"Auth","role":"JWT verify","icon":"shield","tone":"red"},{"id":"cache","name":"Redis","role":"cache","icon":"cache","tone":"orange"},{"id":"db","name":"Postgres","role":"source of truth","icon":"database","tone":"purple"}],"messages":[{"from":"web","to":"api","label":"GET /dashboard"},{"from":"api","to":"auth","label":"verify JWT"},{"from":"auth","to":"api","label":"claims ok","style":"dashed"},{"from":"api","to":"cache","label":"read cache"},{"from":"cache","to":"api","label":"miss","style":"dashed"},{"from":"api","to":"db","label":"SELECT widgets","note":"indexed by account"},{"from":"db","to":"api","label":"rows","style":"dashed"},{"from":"api","to":"cache","label":"set cache","tone":"orange"},{"from":"api","to":"api","label":"emit trace"},{"from":"api","to":"web","label":"200 OK","style":"dashed"}]}
```
