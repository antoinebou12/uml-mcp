# Changelog

All notable changes to UML-MCP are recorded here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/). Dates are the day the GitHub release was published.
No 1.1.x or 1.2.x versions were ever tagged: 1.0.1 was followed by 1.3.0.

## [Unreleased] (1.4.0)

Everything merged to `main` since 1.3.2, plus the plugin work described below.

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

[Unreleased]: https://github.com/antoinebou12/uml-mcp/compare/v1.3.2...HEAD
[1.3.2]: https://github.com/antoinebou12/uml-mcp/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/antoinebou12/uml-mcp/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/antoinebou12/uml-mcp/compare/v1.0.1...v1.3.0
[1.0.1]: https://github.com/antoinebou12/uml-mcp/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/antoinebou12/uml-mcp/releases/tag/v1.0.0
