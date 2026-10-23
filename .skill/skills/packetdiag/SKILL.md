---
name: packetdiag
description: >-
  Writes valid packetdiag diagram source for uml-mcp (diagram_type=packetdiag). Network packet layout diagrams Use when the user asks for packetdiag or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# packetdiag diagram (uml-mcp)

**`diagram_type`:** `packetdiag`  
**Backend:** `packetdiag`  
**Output formats:** png, svg, pdf

Network packet layout diagrams

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Field lengths drive the layout; label every span.
- No MCP `theme` — use short field names for contrast.

## Starter template

```packetdiag
packetdiag {
  0-15: Source Port;
  16-31: Destination Port;
  32-63: Sequence Number;
  64-95: Acknowledgment Number;
}
```

## Example

```packetdiag
packetdiag {
  colwidth = 32;
  node_height = 72;
  0-15: Source Port;
  16-31: Destination Port;
  32-63: Sequence Number;
  64-95: Acknowledgment Number;
  96-99: Data Offset;
  100-105: Reserved;
  106: URG [rotate = 270];
  107: ACK [rotate = 270];
  108: PSH [rotate = 270];
  109: RST [rotate = 270];
  110: SYN [rotate = 270];
  111: FIN [rotate = 270];
  112-127: Window;
  128-143: Checksum;
  144-159: Urgent Pointer;
  160-191: (Options and Padding);
  192-223: data [colheight = 3];
}
```

## Render with uml-mcp

1. Set `diagram_type` to `packetdiag` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
