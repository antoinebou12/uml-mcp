---
name: archify_architecture
description: >-
  Writes valid archify_architecture JSON for uml-mcp (diagram_type=archify_architecture, bundled plugin archify). Use when the user asks for an architecture overview with colour-coded dashed groups, legend and presets; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# archify_architecture diagram (uml-mcp plugin `archify`)

**`diagram_type`:** `archify_architecture`  
**Backend:** `plugin:archify` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

Architecture diagram with dashed colour-coded groups (security, frontend, backend, bus, workers, database, cloud), icon cards, a legend and labelled arrows; auto-laid out left-right or top-down, dark, light or auto, in classic, blueprint or flow presets. JSON nodes, groups, edges; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/archify/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Show our platform as an archify architecture with security, frontend, backend, message bus and database groups, blueprint preset.

## Notation tips

- Group `style` sets the colour: `security`, `frontend`, `backend`, `bus`, `workers`, `database`, `cloud`, `external`.
- `preset`: `classic`, `blueprint`, `flow`; `subtitle` and node `tag` (an owning team) add context.
- Same `nodes`/`groups`/`edges` JSON as `stack_diagram`.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Platform architecture","subtitle":"Auth, API, bus and data, grouped by ownership","preset":"classic","direction":"LR","theme":"auto","groups":[{"id":"sec","name":"Security & Identity","style":"security","icon":"shield"},{"id":"fe","name":"Frontend","style":"frontend","icon":"browser"},{"id":"be","name":"Backend Services","style":"backend","icon":"server"},{"id":"bus","name":"Message Bus","style":"bus","icon":"queue"},{"id":"wk","name":"Workers","style":"workers","icon":"gear"},{"id":"data","name":"Database","style":"database","icon":"database"}],"nodes":[{"id":"auth","name":"Auth Service","role":"OAuth2 / OIDC","icon":"lock","group":"sec"},{"id":"web","name":"Web App","role":"React / TypeScript","icon":"browser","group":"fe"},{"id":"api","name":"API Service","role":"REST / GraphQL","icon":"api","group":"be"},{"id":"users","name":"User Service","icon":"user","group":"be"},{"id":"billing","name":"Billing Service","icon":"payments","group":"be"},{"id":"events","name":"Event Bus","role":"RabbitMQ / Kafka","icon":"queue","group":"bus"},{"id":"mail","name":"Email Worker","icon":"mail","group":"wk"},{"id":"report","name":"Report Worker","icon":"chart","group":"wk"},{"id":"pg","name":"PostgreSQL","role":"primary database","icon":"database","group":"data"}],"edges":[{"from":"web","to":"api","label":"HTTPS"},{"from":"auth","to":"api","label":"validate token","style":"dashed"},{"from":"api","to":"users"},{"from":"api","to":"billing"},{"from":"api","to":"events","tone":"orange"},{"from":"events","to":"mail","tone":"orange"},{"from":"events","to":"report","tone":"orange"},{"from":"users","to":"pg"},{"from":"billing","to":"pg"}]}
```
