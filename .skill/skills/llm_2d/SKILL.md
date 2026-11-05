---
name: llm_2d
description: >-
  Writes valid llm_2d JSON for uml-mcp (diagram_type=llm_2d, bundled plugin llm-visualizer). Use when the user asks for a neural network or LLM architecture as a 2D map, or an autoencoder, VAE or GAN; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# llm_2d diagram (uml-mcp plugin `llm-visualizer`)

**`diagram_type`:** `llm_2d`  
**Backend:** `plugin:llm-visualizer` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

LLM architecture as a 2D layer and tensor map. JSON layers and connections; standalone interactive HTML or static SVG

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/llm-visualizer/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Draw a VAE: input image, encoder, 2D latent z, decoder, reconstruction.

## Notation tips

- Each layer: `id`, `label`, `kind`, optional `shape` (e.g. `[784]`), `repeat`, `note`, `group`. `connections`: `from`, `to`, `label`, `style` (`solid`, `dashed`); omit them for a straight chain.
- Set `kind` on every layer. Encoders are `encoder` (a trapezoid that narrows), decoders `decoder` (one that widens), a latent code `vector` (a bar) or `bottleneck` (a square), a sampler or classifier `decision` (a circle).
- With an encoder, decoder, vector or bottleneck the layout switches to `flow` (shapes left to right); set `layout: "grid"` for cards, `direction: "TB"` for top down.
- Give `shape` so each layer shows its size; label the encoder-to-latent edge (`"μ, σ → sample z"`).
- `groups` (`id`, `label`, `repeat`) draw `N×` containers around repeated blocks.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Decoder-only transformer","subtitle":"Grouped view of a 7B parameter language model","theme":"dark","layers":[{"id":"tokens","label":"Token IDs","kind":"input","shape":[2048],"note":"BPE token sequence"},{"id":"embed","label":"Token embedding","kind":"embedding","shape":[2048,4096]},{"id":"attn","label":"Grouped-query attention","kind":"attention","shape":[32,128],"repeat":32,"note":"32 query heads, 8 key/value heads"},{"id":"ffn","label":"SwiGLU feed-forward","kind":"feedforward","shape":[4096,11008],"repeat":32},{"id":"norm","label":"RMSNorm","kind":"normalization","shape":[4096]},{"id":"logits","label":"Vocabulary logits","kind":"output","shape":[32000]}],"connections":[{"from":"tokens","to":"embed"},{"from":"embed","to":"attn","label":"hidden states"},{"from":"attn","to":"ffn","label":"residual stream"},{"from":"ffn","to":"norm"},{"from":"norm","to":"logits"},{"from":"embed","to":"norm","label":"residual path","style":"dashed"}]}
```
