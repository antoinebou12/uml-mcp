# Stack diagram plugin

`uml-mcp-plugin-stack-diagram` draws stack and cloud architecture diagrams in the
"engineered paper" style: white icon tiles with a name and a mono role line, nested vendor
and region groups, and labelled right-angled edges on a grid. You describe nodes, groups and
edges; the plugin lays them out, so there are no coordinates to write.

```bash
uml-mcp plugins enable stack-diagram   # ships with uml-mcp; restart the server after
```

It adds one diagram type, `stack_diagram`, rendered as `html` or `svg`. The [archify
plugin](archify.md) reuses its layout engine.

## Source format

| Field | Notes |
| --- | --- |
| `title` | Shown in the page header and as the SVG title |
| `direction` | `LR` (default), `RL`, `TB` or `BT` |
| `theme` | `auto` (default: follows the system in HTML, dark in static output), `dark` or `light` |
| `nodes[]` | `id`, `name`, `role`, `icon`, `group`, `tone` |
| `groups[]` | `id`, `name`, `parent` (for nesting), `style`, `tone`, `icon` |
| `edges[]` | `from`, `to`, `label`, `style` (`solid` or `dashed`), `tone`. `source` and `target` also work |

* **Group styles:** `plain` (default), `vendor`, `aws` (square corners), `gcp`, `azure`, `dashed`.
* **Tones:** `blue`, `orange`, `green`, `purple`, `red`, `teal`, `yellow`, `gray`. Edges also take
  `accent` (the default for solid edges) and `neutral` (the default for dashed ones).
* **Limits:** 100 nodes (`plugins.settings.stack-diagram.max_nodes` can lower it), 40 groups, 240 edges.

## Layout

* A node's column (or row, when the flow is vertical) is its longest path from a source, so
  edges always run with the flow. Cycles are broken, and the edge that closes one is drawn
  around the outside.
* A group is packed as a unit. Units whose ranges do not overlap share a row, so a pipeline
  stays on a single line and branches stack. A group box encloses exactly its members and
  nested groups; ungrouped nodes are never inside one.
* Edges are orthogonal. The router tries a straight line, an elbow, then a detour lane around
  the outside and keeps the first route that does not cross another node.

## Icons

Icons are built-in line glyphs (`user`, `browser`, `server`, `database`, `cache`, `cloud`,
`queue`, `lock`, `shield`, `key`, `function`, `container`, `storage`, `cdn`, `git`, `payments`,
`ai`, `api`, `mail`, `search`, `gear`, `chart`, `bell`, `mobile`, `monitor`), plus aliases such
as `postgres`, `redis`, `s3` or `kafka`. A name that is not a glyph shows a monogram badge
built from the node's name.

**Real logos.** A brand name as `icon` (`github`, `vercel`, `cloudflare`, `aws`, `azure`,
`gcp`, `openai`, `claude`, `gemini`, `mistral`, `langchain`, `huggingface`, `mcp`...), or as a word
of the node's name when `icon` is empty ("GitHub Actions"), draws the real logo. The 28 logos are
the MIT-licensed LobeHub set bundled with the D3 plugin, checked for scripts and external
references and drawn without network access; archify backs them with a white tile on dark
cards. They remain trademarks of their owners.

For any other logo, pass the node's `icon` as a base64 image data URI (SVG, PNG, JPEG or WebP,
under 1 MB). SVGs are checked and rejected if they contain scripts, event handlers or external
references.

## Themes and the viewer

The HTML page has pan, zoom, fit and a light/dark toggle, with no network access, under a
hash-based Content-Security-Policy and no inline style attributes. The static SVG uses literal
colours in the chosen theme, so it also previews as PNG on the server. In the MCP App viewer
the theme picker re-renders the diagram: it writes `theme` into the source.
