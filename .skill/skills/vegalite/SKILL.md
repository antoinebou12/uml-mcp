---
name: vegalite
description: >-
  Writes valid vegalite diagram source for uml-mcp (diagram_type=vegalite). Vega-Lite visualization grammar Use when the user asks for vegalite or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# vegalite diagram (uml-mcp)

**`diagram_type`:** `vegalite`  
**Backend:** `vegalite`  
**Output formats:** png, svg, pdf

Vega-Lite visualization grammar

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Use `config` + `mark.color` / encoding colors; set explicit `width`/`height`.
- No MCP `theme` param.

## Starter template

```vegalite
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "title": "Signups",
  "data": {"values": [
    {"month": "Jan", "n": 40},
    {"month": "Feb", "n": 55},
    {"month": "Mar", "n": 70}
  ]},
  "mark": "bar",
  "encoding": {
    "x": {"field": "month", "type": "ordinal", "title": "Month"},
    "y": {"field": "n", "type": "quantitative", "title": "Users"}
  }
}
```

## Example

```vegalite
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "title": "Monthly active users",
  "width": 280,
  "height": 180,
  "data": {
    "values": [
      {"month": "Jan", "users": 120, "plan": "Free"},
      {"month": "Jan", "users": 80, "plan": "Pro"},
      {"month": "Feb", "users": 140, "plan": "Free"},
      {"month": "Feb", "users": 110, "plan": "Pro"},
      {"month": "Mar", "users": 160, "plan": "Free"},
      {"month": "Mar", "users": 150, "plan": "Pro"},
      {"month": "Apr", "users": 180, "plan": "Free"},
      {"month": "Apr", "users": 190, "plan": "Pro"}
    ]
  },
  "mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3},
  "encoding": {
    "x": {
      "field": "month",
      "type": "ordinal",
      "title": "Month",
      "sort": ["Jan", "Feb", "Mar", "Apr"],
      "axis": {"labelAngle": 0}
    },
    "y": {"field": "users", "type": "quantitative", "title": "Users"},
    "color": {
      "field": "plan",
      "type": "nominal",
      "title": "Plan",
      "scale": {"range": ["#94a3b8", "#0ea5e9"]}
    },
    "xOffset": {"field": "plan"}
  }
}
```

## Render with uml-mcp

1. Set `diagram_type` to `vegalite` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
