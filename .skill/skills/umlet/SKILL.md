---
name: umlet
description: >-
  Writes valid umlet diagram source for uml-mcp (diagram_type=umlet). UMLet UML diagrams from UXF XML source Use when the user asks for umlet or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# umlet diagram (uml-mcp)

**`diagram_type`:** `umlet`  
**Backend:** `umlet`  
**Output formats:** png, svg, jpeg

UMLet UML diagrams from UXF XML source

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Source is UMLet UXF XML (`<umlet_diagram>` + `<element>` with `panel_attributes`).
- Class boxes: name, `--`, then attributes/methods. Visibility is a **single** `+` / `-` / `#` (never `++` — UMLet treats `++` as invalid and clips).
- Size `<w>` ≥ ~8× longest line length (zoom 10) or labels clip at the box edge.

## Styling

- UXF has no theme switch; sizing and `+`/`-`/`#` visibility are the polish.
- No MCP `theme` param.

## Starter template

```umlet
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<umlet_diagram>
  <zoom_level>10</zoom_level>
  <element>
    <id>UMLClass</id>
    <coordinates>
      <x>10</x>
      <y>10</y>
      <w>160</w>
      <h>80</h>
    </coordinates>
    <panel_attributes>Hello
--
+world()
</panel_attributes>
    <additional_attributes/>
  </element>
</umlet_diagram>
```

## Example

```umlet
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<umlet_diagram>
  <zoom_level>10</zoom_level>
  <element>
    <id>UMLClass</id>
    <coordinates>
      <x>10</x>
      <y>10</y>
      <w>180</w>
      <h>90</h>
    </coordinates>
    <panel_attributes>Account
--
-balance: decimal
+deposit()
</panel_attributes>
    <additional_attributes/>
  </element>
</umlet_diagram>
```

## Render with uml-mcp

1. Set `diagram_type` to `umlet` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
