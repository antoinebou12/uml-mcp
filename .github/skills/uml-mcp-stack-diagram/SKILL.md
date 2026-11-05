---
name: uml-mcp-stack-diagram
description: Draw auto-laid-out stack and cloud architecture diagrams with real logos (stack_diagram).
---

# Stack diagrams

Follow `skill://uml-mcp-diagrams/SKILL.md`. Icon tiles on engineered paper, nested vendor and region groups and labelled right-angled edges, laid out for you left to right, right to left, top down or bottom up.

## Types

| Type | Use for | Example prompt |
| --- | --- | --- |
| `stack_diagram` | a stack or cloud diagram with icon tiles, nested vendor and region groups | Draw my stack: Next.js and Hono on Vercel, Neon Postgres, Clerk for auth, Stripe for payments, GitHub Actions deploys. Left to right. |

## Steps

1. Check the live catalog (`list_diagram_types` or `uml://types`); the bundled plugins are on by default, but a server may turn them off with `plugins.bundled: false`.
2. Read the type's example from `uml://examples` and keep its field names.
3. Call `validate_uml`; an error names the field and, for a bad reference, lists the known ids, so fix it and validate again.
4. Render with `generate_uml_image` for a chat image, or `generate_uml` with `output_format: "html"` for the interactive page in the MCP App viewer. Clients without MCP Apps still get the PNG and SVG.
5. Pass `theme` (`auto`, `dark`, `light`) rather than editing colours.

## Example

```json
{"title":"SaaS stack","direction":"LR","theme":"dark","groups":[{"id":"vercel","name":"Vercel","style":"plain","icon":"vercel"},{"id":"github","name":"GitHub","style":"vendor","tone":"blue","icon":"github"}],"nodes":[{"id":"user","name":"User","role":"browser","icon":"user"},{"id":"web","name":"Next.js","role":"frontend","icon":"browser","group":"vercel"},{"id":"api","name":"Hono","role":"api routes","icon":"function","group":"vercel"},{"id":"db","name":"Neon","role":"serverless postgres","icon":"database"},{"id":"auth","name":"Clerk","role":"auth","icon":"lock"},{"id":"pay","name":"Stripe","role":"payments","icon":"payments"},{"id":"ci","name":"GitHub Actions","role":"ci","icon":"github","group":"github"}],"edges":[{"from":"user","to":"web","label":"HTTPS"},{"from":"web","to":"api","label":"RPC"},{"from":"api","to":"db","label":"SQL"},{"from":"api","to":"auth","label":"session","tone":"neutral"},{"from":"api","to":"pay","label":"checkout","tone":"neutral"},{"from":"ci","to":"web","label":"deploy","style":"dashed"}]}
```
