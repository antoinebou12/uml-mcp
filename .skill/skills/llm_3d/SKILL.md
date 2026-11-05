---
name: llm_3d
description: >-
  Writes valid llm_3d JSON for uml-mcp (diagram_type=llm_3d, bundled plugin llm-visualizer). Use when the user asks for the same model as a rotatable 3D scene: layer panels, with encoder and decoder funnels; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# llm_3d diagram (uml-mcp plugin `llm-visualizer`)

**`diagram_type`:** `llm_3d`  
**Backend:** `plugin:llm-visualizer` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

LLM architecture as a rotatable perspective scene. JSON layers and connections; standalone interactive HTML or static isometric SVG

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/llm-visualizer/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Show the VAE as a 3D scene I can rotate, encoder narrowing to the latent and decoder widening back.

## Notation tips

- Same JSON as `llm_2d`; the page switches between 2D and 3D.
- `encoder` and `decoder` layers become frustums that narrow and widen along the flow; other kinds are glass panels, `repeat` stacks them and groups become tinted slabs on the floor.
- The static SVG/PNG is an oblique view with every label on one row under the solids.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Decoder-only transformer","subtitle":"Grouped view of a 7B parameter language model","theme":"dark","layers":[{"id":"tokens","label":"Token IDs","kind":"input","shape":[2048],"note":"BPE token sequence"},{"id":"embed","label":"Token embedding","kind":"embedding","shape":[2048,4096]},{"id":"attn","label":"Grouped-query attention","kind":"attention","shape":[32,128],"repeat":32,"note":"32 query heads, 8 key/value heads"},{"id":"ffn","label":"SwiGLU feed-forward","kind":"feedforward","shape":[4096,11008],"repeat":32},{"id":"norm","label":"RMSNorm","kind":"normalization","shape":[4096]},{"id":"logits","label":"Vocabulary logits","kind":"output","shape":[32000]}],"connections":[{"from":"tokens","to":"embed"},{"from":"embed","to":"attn","label":"hidden states"},{"from":"attn","to":"ffn","label":"residual stream"},{"from":"ffn","to":"norm"},{"from":"norm","to":"logits"},{"from":"embed","to":"norm","label":"residual path","style":"dashed"}]}
```
