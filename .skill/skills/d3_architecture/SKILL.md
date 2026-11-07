---
name: d3_architecture
description: >-
  Writes valid d3_architecture JSON for uml-mcp (diagram_type=d3_architecture, bundled plugin d3). Use when the user asks for a cloud or system architecture with provider and brand logos; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# d3_architecture diagram (uml-mcp plugin `d3`)

**`diagram_type`:** `d3_architecture`  
**Backend:** `plugin:d3` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

System or cloud architecture (D3): boxes in nested groups with AWS, Azure, GCP and Kubernetes style icons, input/output ports, A*-routed straight arrows and draggable boxes. JSON; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/d3-plugins/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Our AI app: Cloudflare in front of a Vercel app, a LangChain agent calling Claude, OpenAI and Gemini, Postgres for data.

## Notation tips

- Node `service` keys draw real logos: `aws:s3`, `gcp:run`, `tech:claude`, `tech:github`, `tech:vercel`...
- `groups` nest (`region` > `vpc` > `subnet`); `provider` is a top-level field, never a node field.
- Call `d3_catalog` (when enabled) for every service key before writing source.
- The `service` kind sets the shape (database cylinder, queue pipe, function slant, gateway chamfer) and the docs link a click opens; `docs` overrides it with your own `https://` page.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Orders service on AWS","provider":"aws","groups":[{"id":"region","label":"eu-west-1","type":"region"},{"id":"vpc","label":"VPC 10.0.0.0/16","type":"vpc","parent":"region"},{"id":"private","label":"Private subnets","type":"subnet","parent":"vpc"}],"nodes":[{"id":"users","label":"Users","kind":"user"},{"id":"cdn","label":"CDN","service":"aws:cloudfront"},{"id":"api","label":"API","service":"aws:apigateway","group":"vpc","inputs":["https"],"outputs":["invoke"]},{"id":"orders","label":"Orders","service":"aws:lambda","group":"private","inputs":["invoke"],"outputs":["rows","events"]},{"id":"db","label":"Orders table","service":"aws:dynamodb","group":"private"},{"id":"queue","label":"Order events","service":"aws:sqs","group":"private"},{"id":"mail","label":"Notifier","service":"aws:lambda","group":"private"}],"links":[{"from":"users","to":"cdn","label":"HTTPS"},{"from":"cdn","to":"api:https"},{"from":"api:invoke","to":"orders:invoke"},{"from":"orders:rows","to":"db","label":"read / write"},{"from":"orders:events","to":"queue","style":"dashed"},{"from":"queue","to":"mail","style":"dashed"}]}
```
