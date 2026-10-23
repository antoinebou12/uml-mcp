---
name: symbolator
description: >-
  Writes valid symbolator diagram source for uml-mcp (diagram_type=symbolator). Digital logic and schematic symbols Use when the user asks for symbolator or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# symbolator diagram (uml-mcp)

**`diagram_type`:** `symbolator`  
**Backend:** `symbolator`  
**Output formats:** svg

Digital logic and schematic symbols

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Input is a Verilog/SystemVerilog module; Symbolator draws the pin symbol.
- Group ports with `//# {{group|Title}}` before related ports (e.g. `clocks`, `ctrl`, `data`).
- Name clocks `clk` and active-low resets `rst_n` so wedges render; buses as `[7:0]`.
- Put inputs on the left groups and outputs on the right of the last group for a readable IC-style symbol.

## Styling

- Port groups color the symbol bands; naming drives clock/reset glyphs.
- No MCP `theme` param.

## Starter template

```symbolator
module counter (
  //# {{clocks|Clocking}}
  input  wire       clk,
  input  wire       rst_n,
  //# {{data|Data}}
  output reg  [7:0] count
);
endmodule
```

## Example

```symbolator
module uart_tx (
  //# {{clocks|Clocking}}
  input  wire       clk,
  input  wire       rst_n,
  //# {{ctrl|Control}}
  input  wire       valid,
  output wire       ready,
  //# {{data|Payload}}
  input  wire [7:0] data,
  output wire       tx
);
endmodule
```

## Render with uml-mcp

1. Set `diagram_type` to `symbolator` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
