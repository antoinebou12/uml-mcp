---
name: uml-mcp-archify
description: Draw archify architecture, workflow and sequence diagrams with colour-coded groups.
---

# Archify diagrams

Follow `skill://uml-mcp-diagrams/SKILL.md`. Dashed, colour-coded containers, icon cards, a legend and three presets. The page lets readers click a node to focus it and shift-click another for the shortest path.

## Types

| Type | Use for | Example prompt |
| --- | --- | --- |
| `archify_architecture` | an architecture overview with colour-coded dashed groups, legend and presets | Show our platform as an archify architecture with security, frontend, backend, message bus and database groups, blueprint preset. |
| `archify_workflow` | a workflow or process with steps grouped into stages, top to bottom | Draw our order fulfilment workflow: place order, take payment, pick and pack, ship, notify the customer. |
| `archify_sequence` | a sequence diagram of calls and replies between participants | Sequence diagram of a cache-miss request through web, API, auth, Redis and Postgres. |

## Steps

1. Check the live catalog (`list_diagram_types` or `uml://types`); the bundled plugins are on by default, but a server may turn them off with `plugins.bundled: false`.
2. Read the type's example from `uml://examples` and keep its field names.
3. Call `validate_uml`; an error names the field and, for a bad reference, lists the known ids, so fix it and validate again.
4. Render with `generate_uml_image` for a chat image, or `generate_uml` with `output_format: "html"` for the interactive page in the MCP App viewer. Clients without MCP Apps still get the PNG and SVG.
5. Pass `theme` (`auto`, `dark`, `light`) rather than editing colours.

## Example

```json
{"title":"Platform architecture","subtitle":"Auth, API, bus and data, grouped by ownership","preset":"classic","direction":"LR","theme":"auto","groups":[{"id":"sec","name":"Security & Identity","style":"security","icon":"shield"},{"id":"fe","name":"Frontend","style":"frontend","icon":"browser"},{"id":"be","name":"Backend Services","style":"backend","icon":"server"},{"id":"bus","name":"Message Bus","style":"bus","icon":"queue"},{"id":"wk","name":"Workers","style":"workers","icon":"gear"},{"id":"data","name":"Database","style":"database","icon":"database"}],"nodes":[{"id":"auth","name":"Auth Service","role":"OAuth2 / OIDC","icon":"lock","group":"sec"},{"id":"web","name":"Web App","role":"React / TypeScript","icon":"browser","group":"fe"},{"id":"api","name":"API Service","role":"REST / GraphQL","icon":"api","group":"be"},{"id":"users","name":"User Service","icon":"user","group":"be"},{"id":"billing","name":"Billing Service","icon":"payments","group":"be"},{"id":"events","name":"Event Bus","role":"RabbitMQ / Kafka","icon":"queue","group":"bus"},{"id":"mail","name":"Email Worker","icon":"mail","group":"wk"},{"id":"report","name":"Report Worker","icon":"chart","group":"wk"},{"id":"pg","name":"PostgreSQL","role":"primary database","icon":"database","group":"data"}],"edges":[{"from":"web","to":"api","label":"HTTPS"},{"from":"auth","to":"api","label":"validate token","style":"dashed"},{"from":"api","to":"users"},{"from":"api","to":"billing"},{"from":"api","to":"events","tone":"orange"},{"from":"events","to":"mail","tone":"orange"},{"from":"events","to":"report","tone":"orange"},{"from":"users","to":"pg"},{"from":"billing","to":"pg"}]}
```
