---
name: archify_workflow
description: >-
  Writes valid archify_workflow JSON for uml-mcp (diagram_type=archify_workflow, bundled plugin archify). Use when the user asks for a workflow or process with steps grouped into stages, top to bottom; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# archify_workflow diagram (uml-mcp plugin `archify`)

**`diagram_type`:** `archify_workflow`  
**Backend:** `plugin:archify` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

Workflow or process diagram: steps grouped into stages, hand-offs between them, flowing top-down by default; dark, light or auto. Same JSON as archify_architecture; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/archify/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Draw our order fulfilment workflow: place order, take payment, pick and pack, ship, notify the customer.

## Notation tips

- Same JSON as `archify_architecture`; flows top down by default.
- Use groups for stages and `step` numbers on edges for the order of hand-offs.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Order fulfilment","direction":"TB","theme":"auto","groups":[{"id":"intake","name":"Intake","style":"frontend","icon":"browser"},{"id":"ship","name":"Fulfilment","style":"backend","icon":"container"}],"nodes":[{"id":"order","name":"Place order","role":"customer","icon":"user","group":"intake"},{"id":"pay","name":"Take payment","role":"stripe","icon":"payments","group":"intake"},{"id":"pick","name":"Pick & pack","role":"warehouse","icon":"storage","group":"ship"},{"id":"send","name":"Ship","role":"carrier","icon":"container","group":"ship"},{"id":"notify","name":"Notify customer","role":"email","icon":"mail"}],"edges":[{"from":"order","to":"pay"},{"from":"pay","to":"pick","label":"paid"},{"from":"pick","to":"send"},{"from":"send","to":"notify","label":"tracking link"},{"from":"pay","to":"notify","label":"receipt","style":"dashed"}]}
```
