# Changelog

All notable changes to UML-MCP are recorded here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/). Dates are the day the GitHub release was published.
No 1.1.x or 1.2.x versions were ever tagged: 1.0.1 was followed by 1.3.0.

## [Unreleased]

### Added

- C4 model plugin (`c4`, bundled and on by default) with the `c4_model` type: one JSON model of
  people, software systems, containers and components. The SVG draws the chosen level in C4
  notation (person shapes, grey external systems, containers inside the system boundary,
  database cylinders, queue pipes, labelled relations with their technology, a legend). The
  HTML page drills from context to containers to components with breadcrumbs back up, lifts
  relations to the level on screen and merges them, opens a detail card per element with
  **Open documentation** for its `service`, picks a top-down or left-right layout to fit the
  frame, and exports the current level as SVG, PNG or HTML. The Kroki `c4plantuml` type is
  unchanged.
- D3 plugin redesign. Boxes take the silhouette of their kind (database cylinders, queue pipes,
  slanted functions, chamfered gateways, security shields, user pills), the tile shows the
  service glyph or software logo, and the cloud provider is a corner logo badge (each logo written
  once and reused). Clicking a box or force node opens a detail card with its connections and
  **Open documentation**: a node's own `docs` link, or the official docs of its service (AWS,
  Azure, Google Cloud, Kubernetes, common software), opened through the host (`ui/open-link`)
  in the MCP App. Force nodes take a `service` for an icon in the circle. Pages open fitted to
  their frame and drop their own title and zoom box inside the viewer.
- LLM visualizer: the flow layout places each layer by its depth in the graph, so parallel
  branches share a column. A VAE's mean and log-variance heads now stack between the encoder
  and the sampled z, with curved edges fanning out and merging, in 2D, the static 3D SVG and the
  interactive 3D scene. A role in a layer's name (encoder, decoder, latent, mean μ, log σ²) wins
  over a vague `type` such as `dense`; small shapes carry their name underneath; edge labels have
  a halo; the default title is "Model architecture"; in a narrow chat frame the layer list hides
  and labels scale with the zoom.
- LLM visualizer cards carry a glyph for their kind (token chips, embedding matrix, causal
  attention mask, FFN, norm curve, ⊕, router diamond, experts, memory cylinder, logits bars),
  shared by the SVG and the interactive page; grid skip edges such as a residual path loop
  around the stack, and edge labels sit beside their arrows.
- LLM visualizer: encoders and decoders are funnels in 3D too, narrowing and widening along the
  flow in the interactive scene and in a new static oblique SVG with one label row. Sources may use
  `name`/`type` for `label`/`kind`, a missing kind is inferred from the layer's id and label, and a
  source with encoder, decoder, latent or vector layers gets the flow layout by default. The
  `llm_2d`/`llm_3d` skills and guide gained a recipes table (autoencoder, VAE, GAN, transformers).
- Optional MCP background tasks for `generate_uml`, `generate_uml_image` and
  `generate_uml_batch` (`uml-mcp[tasks]`, `tasks.enabled`, off by default). Supported clients get
  a task handle to poll; others still get foreground results. `uml-mcp lint` rejects tasks on
  Vercel and Redis backends without `FASTMCP_TASKS_ENCRYPTION_KEY`. With enterprise auth on, the
  verified caller (hashed key, no bearer token) becomes the task owner.
- An experimental `architecture` renderer, off by default: tiles at explicit positions, vendor
  groups and orthogonal edges with optional `via` corridors, exported as HTML or React TSX
  (`tsx` output format). Embedded SVG icons are checked for active content.

### Changed

- The MCP App view no longer requests nested frame domains: interactive plugin pages load in
  their sandboxed frame through `srcdoc` instead of a `blob:` URL, and `frameDomains` is gone
  from the view's CSP.
- `generate_uml_batch` advertises an explicit item schema (required `diagram_type` and `code`;
  optional `output_format`, `theme` and `scale` with their limits; no other fields) and the
  batch size, 1 to `MCP_BATCH_MAX_ITEMS`. Bad items still get a readable error at their index.
  The tool description states that inline previews share one 48k budget.
- `rerender_diagram` gives example values for `diagram_type` and `code`.

- Docs: a new MCP App viewer page (features, plugin pages, clients without MCP Apps,
  publishing readiness), shared options and example prompts on the plugins page, an updated docs
  home, and the compatibility page in the nav. The README is shorter and points to these pages.
- The README shows the MCP App recording as an animated GIF that links to the full video,
  because GitHub does not play videos referenced from repository files.

## [1.4.0] - 2026-11-05

Everything merged to `main` since 1.3.2, including the plugin work described below.

### Added

- **Interactive diagrams as plugins.** Four plugins add diagram types that render to a
  standalone HTML page (shown in the MCP App viewer) or a static SVG that also previews as PNG:
  - `d3`: `d3_force`, `d3_architecture`, `d3_topology` and the `d3_catalog` tool, with bounded
    physics, A\*-routed edges and grouped container tracing ([#362](https://github.com/antoinebou12/uml-mcp/pull/362)).
  - `stack-diagram`: `stack_diagram`, an auto-laid-out stack and cloud architecture diagram
    with nested vendor and region groups, 25 built-in glyphs, left-right, right-left, top-down
    and bottom-up flow, and `dark`, `light` and `auto` themes.
  - `archify`: `archify_architecture`, `archify_workflow` and `archify_sequence`, with dashed
    colour-coded containers, a legend, node tags, and `classic`, `blueprint` and `flow`
    presets. Pages support click-to-focus, shift-click shortest path, live edges and a preset
    picker. It reuses the stack-diagram layout engine.
  - `llm-visualizer`: `llm_2d` and `llm_3d` from one JSON source, with a rotatable perspective
    scene, autoencoder and GAN shapes (encoder and decoder trapezoids, bottleneck, vector,
    decision, token), left-right or top-down `flow` layouts, and grouped `N×` containers.
- **Custom diagrams.** Plugins follow one pattern (`uml_mcp.renderers` entry point, JSON source,
  `html` and `svg` outputs, an example and template per type) so you can add your own diagram
  type; see [Plugin author guide](docs/plugins/authoring.md). A plugin capability manifest and a
  common graph interchange model describe what each type can do.
- The d3, stack-diagram, archify and llm-visualizer plugins ship inside the `uml-mcp`
  package and are **on by default**: the new `plugins.bundled` setting (default `true`) loads
  these four renderers from the `uml-mcp` distribution without configuration. Plugin tools
  such as `d3_catalog` stay opt-in, and `bundled: false` restores a strict allow-list. The
  renderers add no connect-time tokens.
- stack-diagram and archify draw the same 28 real brand logos as D3, from an `icon` name or a
  word of the node's name.
- D3's A\* router adds a small cost for running in the lane next to a parallel arrow (in Python
  and in the page's JS router, which stay identical): on a dense 10-node graph, arrows running a
  lane apart fell from about 5,400 px to 630 px with no extra crossings.
- 32 more brand logos (60 in all: Qwen, OpenRouter, LangGraph, LangSmith, LlamaIndex, CrewAI,
  Snowflake, Claude Code, Codex, xAI...), each linked to its exact source file, checked on every
  test run and drawn offline. `tech:anthropic` now draws the Anthropic mark.
- stack-diagram and archify: numbered `step` badges on edges, `autonumber` for sequences, and
  errors that list the known ids for a bad reference.
- Skills: a per-type agent skill for all nine plugin diagram types (example prompt, notation
  tips, a validated example source) and three MCP guides (`stack-diagram`, `archify`,
  `llm-visualizer`) under `skill://uml-mcp-guides/{topic}/SKILL.md`, listed in the workflow skill.
- Smoke-test prompt for every bundled plugin (logos, steps, presets, autonumber, groups, theme,
  MCP App interactions); its sources are validated and rendered by the test suite.
- README rewritten: centred header, project stats, both hosted endpoints (primary and the
  `uml-mcp.antoineboucher.info` mirror), contents, contributing and licence sections.
- D3 draws real brand logos in a white tile on each card for 25 more services (Azure, GitHub,
  Copilot, Vercel, Cloudflare, Microsoft, Gemini, Mistral, DeepSeek, Meta and Llama, Ollama,
  Hugging Face, Groq, Cohere, Perplexity, Bedrock, Vertex AI, LangChain, n8n, MCP, Cursor,
  NVIDIA, Notion), from the MIT-licensed LobeHub icon set, plus a soft card shadow.
- The `ui://uml-mcp/diagram-viewer` resource also sends `_meta["openai/widgetDescription"]`
  on its read contents, which ChatGPT and the Manufact publishing checklist read as the view
  description. It is kept off `resources/list`, so connect-time tokens do not change.
- `architecture` renderer for positioned architecture tiles with vendor groups, as HTML or TSX.
- Interactive MCP App viewer: fit and pan, editable source, batch results with a gallery, theme
  and format re-render, bounded exports, and a self-hosted ChatGPT app submission path.
- MCP completions, resource templates, MRTR elicitation, progressive discovery with per-type
  skills, and the diagram workflow served through the Skills extension ([#366](https://github.com/antoinebou12/uml-mcp/pull/366)).
- `generate_uml_batch` reports progress and per-item logs to clients that ask for them.
- Hosted admin console sign-in with email and password ([#349](https://github.com/antoinebou12/uml-mcp/pull/349)).
- Self-hosted mermaid.ink, in-cluster renderers in the Helm chart, and Mermaid link
  verification in URL-only mode ([#351](https://github.com/antoinebou12/uml-mcp/pull/351), [#352](https://github.com/antoinebou12/uml-mcp/pull/352)).
- MCP Rig black-box test suites for the stdio server ([#341](https://github.com/antoinebou12/uml-mcp/pull/341)).
- Offline chat trace replay and a check that small diagram previews stay sharp.

### Changed

- **`theme` now reaches every plugin.** The MCP App viewer's theme picker and the `theme` tool
  argument are written into a plugin's JSON source, so they work for all plugins and offer
  `light`, `dark` and `auto`. PNG and PDF export are offered for every plugin that renders SVG.
- Connect-time surface cut from about 5,045 to about 4,118 tokens ([#358](https://github.com/antoinebou12/uml-mcp/pull/358)).
- Frontend builds with TypeScript 7 while ESLint stays on TypeScript 6 ([#359](https://github.com/antoinebou12/uml-mcp/pull/359)).
- Docker and CI cover Python 3.15 ([#360](https://github.com/antoinebou12/uml-mcp/pull/360), [#367](https://github.com/antoinebou12/uml-mcp/pull/367)).
- Dependency updates: fastmcp-slim 4.1.4, Pillow 13, python-dateutil 3, Node 26, Kroki 0.34,
  mermaid.ink 17 and others.

### Fixed

- Mermaid: common input mistakes are repaired and Kroki's real syntax errors are reported; a
  hung Kroki Mermaid renderer is skipped instead of waited on ([#357](https://github.com/antoinebou12/uml-mcp/pull/357), [#354](https://github.com/antoinebou12/uml-mcp/pull/354)).
- Viewer: initial payloads are bounded, HTTPS view domains are validated with clear errors,
  oversized previews fall back to safe links, and plugin HTML renders with working file exports.
- Rendering: fonts are bundled, labelled previews keep their resolution, and static SVG colours
  are resolved so raster previews match.
- HTTP: exploit probe paths are rejected before app dispatch.
- Excalidraw and Vega samples now render something ([#355](https://github.com/antoinebou12/uml-mcp/pull/355)).
- Stale `.well-known` discovery files are regenerated, with LF line endings and guard tests.

## [1.3.2] - 2026-09-03

### Added

- Claude Desktop MCPB bundle ([#324](https://github.com/antoinebou12/uml-mcp/pull/324)).
- OI OS intent manifest ([#326](https://github.com/antoinebou12/uml-mcp/pull/326)).
- Opt-in local PlantUML Docker Compose profile ([#325](https://github.com/antoinebou12/uml-mcp/pull/325)).
- Diagrams are returned as inline MCP image content blocks; AG-UI frontend streaming endpoints.
- Output schemas for tools.

### Changed

- Hardened result contracts, rendering, validation and HTTP security ([#316](https://github.com/antoinebou12/uml-mcp/pull/316)):
  CORS and origin validation, an output sandbox, and audit logging.
- Improved advertised tool schemas, with explicit empty `required` arrays ([#319](https://github.com/antoinebou12/uml-mcp/pull/319)).
- Playground links always appear in chat tool results, and Cursor, Copilot and Claude chat
  rendering improved.
- fastmcp-slim 4.0.0, typer 0.27.2, click 8.5.0, python-dotenv 1.2.3, charset-normalizer 3.5.1,
  and `astral-sh/setup-uv` v10.0.1.

### Fixed

- Real FastMCP HTTP startup restored ([#317](https://github.com/antoinebou12/uml-mcp/pull/317)).
- Vercel public Host headers accepted by the FastMCP guard ([#318](https://github.com/antoinebou12/uml-mcp/pull/318)).
- Three stale test assertions repaired ([#323](https://github.com/antoinebou12/uml-mcp/pull/323)).

## [1.3.1] - 2026-08-10

### Added

- Agent discovery for Vercel: robots, sitemap, `Link` headers, markdown and WebMCP ([#127](https://github.com/antoinebou12/uml-mcp/pull/127)).
- MCP 2026 stateless protocol support, cache hints and conformance CI ([#297](https://github.com/antoinebou12/uml-mcp/pull/297)).
- Full Kroki catalog MCP stress test ([#304](https://github.com/antoinebou12/uml-mcp/pull/304)).
- Service status endpoint, new prompts and resources for algorithm and paper explanations, and
  BPMN prompts with an SVG tutorial.
- Smoke tests of the hosted MCP in CD, and validation of the Cursor `mcp.json` in CI.

### Changed

- Python 3.12 and 3.14 in CI, Docker on 3.14 ([#126](https://github.com/antoinebou12/uml-mcp/pull/126)); coverage threshold enforced in test workflows.
- Consolidated dependency bumps ([#177](https://github.com/antoinebou12/uml-mcp/pull/177), [#269](https://github.com/antoinebou12/uml-mcp/pull/269)).
- Star History is now a repository-owned chart ([#307](https://github.com/antoinebou12/uml-mcp/pull/307)).

### Fixed

- Strict Mermaid validation and stress-test accounting ([#305](https://github.com/antoinebou12/uml-mcp/pull/305)).
- CD pipeline: removed a broken publish job and secrets in `if` conditions, and made the
  deploy smoke tests follow the `/mcp` redirect and parse SSE responses.

## [1.3.0] - 2026-04-23

### Added

- Batch diagram generation and a tool that lists supported diagram types.
- Custom Swagger UI and ReDoc endpoints with project branding.
- Strict validation checks for Mermaid and D2 diagrams, plus new settings for batch size and
  rate limits.
- GitHub stars badge and Star History section in the README.

### Changed

- Improved prompting and diagram skills; the `uml-skill` subproject was removed.
- MkDocs theme with consolidated light and dark modes and richer navigation.
- `uv`-driven dependency workflow, with `requirements.txt` checked for consistency in CI
  ([#74](https://github.com/antoinebou12/uml-mcp/pull/74), [#82](https://github.com/antoinebou12/uml-mcp/pull/82), [#99](https://github.com/antoinebou12/uml-mcp/pull/99)).
- Dependencies: cryptography 46.0.7, authlib 1.6.10, anyio 4.13.0, rich 14.3.4,
  cyclopts 4.10.2, certifi 2026.2.25 and others.

## [1.0.1] - 2026-04-14

### Added

- OpenAPI tags for the API documentation and a clearer API structure.
- Theme support in `kroki_encode`.

### Fixed

- TikZ handling: the preamble is stripped before rendering.

## [1.0.0] - 2026-04-13

First tagged release.

### Added

- Configurable `max_code_length` to prevent denial of service from huge diagrams (by @jannahopp,
  [#40](https://github.com/antoinebou12/uml-mcp/pull/40)).
- `MCP_READ_ONLY` mode that disables file-writing tools (by @jannahopp, [#39](https://github.com/antoinebou12/uml-mcp/pull/39)).

### Fixed

- FastMCP v3 compatibility, including the removal of `stateless_http` from the constructor, and
  a Dockerfile that was missing `pip install` ([#41](https://github.com/antoinebou12/uml-mcp/pull/41), [#43](https://github.com/antoinebou12/uml-mcp/pull/43)).
- The missing `read_only` field on `MCPSettings` (by @tangi-vass, [#46](https://github.com/antoinebou12/uml-mcp/pull/46)).
- Stdout pollution that broke the MCP stdio transport (by @tangi-vass, [#44](https://github.com/antoinebou12/uml-mcp/pull/44)).

### Changed

- GitHub Actions and Docker base images updated, and the docs deploy moved to
  `actions/deploy-pages` v5.

[Unreleased]: https://github.com/antoinebou12/uml-mcp/compare/v1.4.0...HEAD
[1.4.0]: https://github.com/antoinebou12/uml-mcp/compare/v1.3.2...v1.4.0
[1.3.2]: https://github.com/antoinebou12/uml-mcp/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/antoinebou12/uml-mcp/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/antoinebou12/uml-mcp/compare/v1.0.1...v1.3.0
[1.0.1]: https://github.com/antoinebou12/uml-mcp/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/antoinebou12/uml-mcp/releases/tag/v1.0.0
