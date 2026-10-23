---
name: nwdiag
description: >-
  Writes valid nwdiag diagram source for uml-mcp (diagram_type=nwdiag). Network diagrams (blockdiag family) Use when the user asks for nwdiag or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# nwdiag diagram (uml-mcp)

**`diagram_type`:** `nwdiag`  
**Backend:** `nwdiag`  
**Output formats:** png, svg, pdf

Network diagrams (blockdiag family)

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Declare `network name { address = "…"; node [address = "…"]; }` blocks.
- Reuse the same node id in two networks to draw a gateway between them.
- Prefer short node ids (`mcp`, `gateway`); put detail in `address` / `description`.
- Two networks (DMZ + internal) with a shared gateway is the clearest default layout.

## Styling

- Network bars + short node ids read best on dark Kroki backgrounds.
- No MCP `theme` — structure is the styling.

## Starter template

```nwdiag
nwdiag {
  network internet {
    address = "0.0.0.0/0"
  }
  network internal {
    address = "192.168.1.0/24"
    server [address = "192.168.1.1"];
  }
}
```

## Example

```nwdiag
nwdiag {
  network dmz {
    address = "210.x.x.x/24"
    web01 [address = "210.x.x.1"];
    web02 [address = "210.x.x.2"];
  }
  network internal {
    address = "172.x.x.x/24";
    web01 [address = "172.x.x.1"];
    web02 [address = "172.x.x.2"];
    db01;
    db02;
  }
}
```

## Render with uml-mcp

1. Set `diagram_type` to `nwdiag` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
