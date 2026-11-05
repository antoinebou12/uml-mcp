# LLM visualizer plugin

`uml-mcp-plugin-llm-visualizer` adds two diagram types that share one JSON source:

| Type | Output | Opens as |
| --- | --- | --- |
| `llm_2d` | `html`, `svg` | A layer and tensor-shape map |
| `llm_3d` | `html`, `svg` | A rotatable perspective scene (static isometric SVG) |

The HTML viewer has a 2D/3D switch, so either type can show both views. It runs locally
with no CDN or network access, in the sandboxed plugin frame, under a hash-based CSP.

```bash
uml-mcp plugins enable llm-visualizer   # ships with uml-mcp; restart the server after
```

## Source format

| Field | Notes |
| --- | --- |
| `title`, `subtitle`, `theme` | `theme` is `dark` (default), `light` or `auto` (static output is dark; the viewer has a toggle) |
| `layout` | `grid` (cards in columns) or `flow` (one row or column with shaped nodes; connections that skip layers arch over the row). Omitted, it is `flow` when any layer is an `encoder`, `decoder`, `bottleneck` or `vector`, else `grid` |
| `direction` | For `flow`: `LR` (default, left to right) or `TB` (top down). Shapes turn with the flow: an encoder narrows along it |
| `groups[]` | `id`, `label`, `repeat`, `color`. Layers join one with `"group": "<id>"`; it is drawn as a dashed container with an `N×` badge, and as a tinted slab on the floor in 3D |
| `layers[]` | `id` (required, unique), `label` (or `name`), `kind` (or `type`), `shape` (up to 4 integers), `repeat` (1 to 256), `color` (`#rrggbb`), `note` |
| `connections[]` | `from`, `to` (layer ids), `label`, `style` (`solid` or `dashed`); defaults to a chain in layer order |

`kind` is one of `input`, `embedding`, `attention`, `normalization`, `feedforward`,
`residual`, `router`, `expert`, `memory`, `output`, `encoder`, `decoder`, `bottleneck`,
`vector`, `decision`, `token`, `generic`. In the `flow` layout the last six get the
shapes used in autoencoder, VAE and GAN diagrams: `encoder` is a trapezoid that narrows,
`decoder` one that widens, `bottleneck` a small square, `vector` a tall bar, `decision` a
circle and `token` a chip. In 3D the encoder and decoder are frustums that narrow and widen
along the flow, so an autoencoder reads as a funnel in the interactive scene and the static SVG.

Without a `kind`, the layer's `type` is used when it names a kind or a common alias
(`tensor` is a `vector`, `latent` a `bottleneck`, `mlp` a `feedforward`...), and otherwise the
kind is inferred from the id and label: `Encoder qφ(z|x)` is an `encoder`, `Reconstruction x̂`
an `output`. An explicit `kind` always wins.
Limits: 64 layers
(`plugins.settings.llm-visualizer.max_layers` can lower it) and 160 connections.

## Controls

| Action | 2D | 3D |
| --- | --- | --- |
| Drag | Pan | Orbit (Shift+drag pans) |
| Wheel | Zoom | Zoom |
| Click | Inspect layer | Inspect layer |
| Arrow keys, `+`, `-`, `0` | Pan, zoom, reset | Orbit, zoom, reset |
