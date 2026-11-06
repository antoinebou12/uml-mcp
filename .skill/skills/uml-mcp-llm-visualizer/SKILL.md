---
name: uml-mcp-llm-visualizer
description: Draw LLM and neural-network architectures in 2D and 3D (llm_2d, llm_3d).
---

# LLM visualizer

Follow `skill://uml-mcp-diagrams/SKILL.md`. Layer maps, autoencoder and GAN shapes, grouped N× blocks, and a rotatable 3D scene from one JSON source.

## Types

| Type | Use for | Example prompt |
| --- | --- | --- |
| `llm_2d` | a neural network or LLM architecture as a 2D map, or an autoencoder, VAE or GAN | Draw a VAE: input image, encoder, 2D latent z, decoder, reconstruction. |
| `llm_3d` | the same model as a rotatable 3D scene: layer panels, with encoder and decoder funnels | Show the VAE as a 3D scene I can rotate, encoder narrowing to the latent and decoder widening back. |

## Steps

1. Check the live catalog (`list_diagram_types` or `uml://types`); the bundled plugins are on by default, but a server may turn them off with `plugins.bundled: false`.
2. Read the type's example from `uml://examples` and keep its field names.
3. Call `validate_uml`; an error names the field and, for a bad reference, lists the known ids, so fix it and validate again.
4. Render with `generate_uml_image` for a chat image, or `generate_uml` with `output_format: "html"` for the interactive page in the MCP App viewer. Clients without MCP Apps still get the PNG and SVG.
5. Pass `theme` (`auto`, `dark`, `light`) rather than editing colours.

## Recipes

| Model | Layers (`kind`) |
| --- | --- |
| Autoencoder | `input` → `encoder` → `bottleneck` → `decoder` → `output` |
| VAE | `input` → `encoder` → two `vector` heads (μ, log σ²) → `bottleneck` (z = μ + σ ⊙ ε) → `decoder` → `output` |
| GAN | `token` (noise) → `decoder` (generator) → `vector` (fake sample) → `decision` (discriminator); a `dashed` edge for real data |
| Decoder-only LLM | `input` → `embedding` → `attention` and `feedforward` (`repeat: 32`) → `normalization` → `output`; a `dashed` residual edge |
| Encoder-decoder transformer | two `groups` with `repeat: 6`: `encoder` and `decoder` layers inside, a cross-attention edge between them |

Use `label` and `kind`. The parser also accepts `name` and `type` and infers a missing kind from the id and label (`encoder`, `decoder`, `latent`, `input`, `output`...), but explicit kinds give the shapes you expect. Give a `title` (the default is "Model architecture").

```json
{"title":"Variational autoencoder","layers":[{"id":"x","label":"Input x","kind":"input","shape":[784]},{"id":"enc","label":"Encoder qφ(z|x)","kind":"encoder","shape":[256]},{"id":"mu","label":"Mean μ","kind":"vector","shape":[2]},{"id":"logvar","label":"Log variance log σ²","kind":"vector","shape":[2]},{"id":"z","label":"z = μ + σ ⊙ ε","kind":"bottleneck","shape":[2]},{"id":"dec","label":"Decoder pθ(x|z)","kind":"decoder","shape":[256]},{"id":"xr","label":"Reconstruction x̂","kind":"output","shape":[784]}],"connections":[{"from":"x","to":"enc"},{"from":"enc","to":"mu","label":"predict μ"},{"from":"enc","to":"logvar","label":"predict log σ²"},{"from":"mu","to":"z","label":"reparameterize"},{"from":"logvar","to":"z","label":"σ = exp(½ log σ²)"},{"from":"z","to":"dec"},{"from":"dec","to":"xr"}]}
```

## Example

```json
{"title":"Decoder-only transformer","subtitle":"Grouped view of a 7B parameter language model","theme":"dark","layers":[{"id":"tokens","label":"Token IDs","kind":"input","shape":[2048],"note":"BPE token sequence"},{"id":"embed","label":"Token embedding","kind":"embedding","shape":[2048,4096]},{"id":"attn","label":"Grouped-query attention","kind":"attention","shape":[32,128],"repeat":32,"note":"32 query heads, 8 key/value heads"},{"id":"ffn","label":"SwiGLU feed-forward","kind":"feedforward","shape":[4096,11008],"repeat":32},{"id":"norm","label":"RMSNorm","kind":"normalization","shape":[4096]},{"id":"logits","label":"Vocabulary logits","kind":"output","shape":[32000]}],"connections":[{"from":"tokens","to":"embed"},{"from":"embed","to":"attn","label":"hidden states"},{"from":"attn","to":"ffn","label":"residual stream"},{"from":"ffn","to":"norm"},{"from":"norm","to":"logits"},{"from":"embed","to":"norm","label":"residual path","style":"dashed"}]}
```
