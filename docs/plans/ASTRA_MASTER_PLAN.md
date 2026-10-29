# Astra master plan — UML-MCP interactive diagram platform

**Goal:** Implement, test and safely deploy an extensible, interactive MCP diagramming platform in the existing repository. **Astra is the parent orchestrator; Luna is the interactive D3/SVG/MCP Apps specialist.** Agent configuration does not start an agent on its own.

**Sources:** [UML-MCP](https://github.com/antoinebou12/uml-mcp), [LLM2SVG](https://github.com/antoinebou12/LLM2SVG/tree/main/data/train), [GitDiagram](https://gitdiagram.com/), [IcePanel developer documentation](https://developer.icepanel.io/).

## Baseline and compatibility

The repository already has:
- MCP Apps resource `ui://uml-mcp/diagram-viewer` attached to `generate_uml`/`generate_uml_image` plus app-only `rerender_diagram`.
- D3 plugin in `examples/plugins/uml-mcp-plugin-d3`: `d3_force`, `d3_architecture`, `d3_topology`, drag/zoom/pan/fit/reset and AWS/Azure/GCP/Kubernetes service catalog.
- Kroki-backed D2, C4 PlantUML, Structurizr, Mermaid, Graphviz and other diagram types.
- Python plugin entry points `uml_mcp.tools` and `uml_mcp.renderers`, explicit enabled allowlist, FastMCP, React admin console, AG-UI.

**Extend these; do not create competing backends or duplicate existing notation.** Preserve `/mcp`, `/ag-ui`, model-facing tool budget, format fallbacks, auth, resource discovery, deployment contracts and existing tests.

## Execution model

1. Astra reads `.plan/DECISIONS.md`, local git state, open issues/PRs, CI and Manufact logs. Do not overwrite uncommitted user edits.
2. Astra assigns scoped UI work to Luna via Cursor's actual subagent mechanism, using `.cursor/agents/luna.md`. Luna owns viewer and D3 interaction/visual tests; Astra owns backend/plugin/packaging/security/deployment.
3. Never edit the same file simultaneously. Each task gets inputs, exact owner, dependency, acceptance criteria, code paths and verified test output.
4. Luna hands off commit/changed paths, screenshots, Playwright results and caveats. Astra reviews, integrates and reruns tests.
5. Track honest statuses in `docs/plans/IMPLEMENTATION_STATUS.md` and resume existing unfinished work after major features are stable.

## P0: Unified MCP Apps viewer

Work in `mcp_core/apps/diagram_viewer.py`, existing D3 `assets/common.js`, frontend and browser tests.

- Toolbar: zoom in/out, reset zoom **and** pan, fit content, center, percentage, accessible labels, theme, responsive layout and optional fullscreen when host supports it.
- Mouse wheel/trackpad zoom around pointer, drag-pan (without stealing draggable node interactions), keyboard `+`, `-`, `0`, `f`. Keep camera state consistent after resize/re-render.
- Render raster, sanitized SVG, static Kroki SVG and trusted D3/HTML plugin output. For HTML, use sandbox/allowlisted renderer behavior; never inject arbitrary plugin-provided executable HTML in parent DOM.
- Baseline explore/fit/export on *all* SVG-based diagram types. Semantic editing/drilldown only where a validated graph model exists; do not invent semantic IDs for static images.
- Clear errors, retryable tool-call failure, timeout handling, cancellation/teardown, visible focus, Unicode labels, safe link protocols, viewer CSP and postMessage source/origin validation.
- MCP Apps host lifecycle: initialize, initialized, tool input/results, host theme, app-only rerender through host; image/url fallback for clients without Apps.
- Browser tests: zoom/pan/fit/reset, Unicode SVG, unsafe href, malformed SVG, re-render failure/retry, mobile overflow, theme, exported content.

**Done:** host tests and screenshots demonstrate real interaction; no claim based on inspecting HTML alone.

## P0: Plugin contract, packaging and hardening

Keep `DiagramTypeSpec`, `RenderOutput` and entry-point API compatible. Add *optional* capability manifest: `diagram_types`, `source_schema`, `formats`, `interaction_features`, `examples`, `templates`, `version`, `security_profile`. Keep model-facing MCP tool list small via catalog/resources/skills.

- Ensure production image installs and explicitly enables required plugin packages (the D3 example is not guaranteed installed just because it lives in the repo).
- Validate per-type JSON, unique IDs and references, bounded graph sizes, safe HTML and SVG, URLs, payload size and rendering time; no arbitrary Python/plugin installation from chat input.
- Unified graph interchange where useful: nodes/ports/edges/groups, metadata/tags/flows/source refs and distinct view state. Adapt plugin-specific JSON, never force Kroki notation to migrate.
- Keep failure isolation, log/audit metrics, caching and deterministic diagram layout.

## P1: Diagram types and semantic interactions

### Architecture patterns — `uml-mcp-plugin-architecture`
- `iceberg_model`: events, patterns, systemic structures and mental models, waterline, expanding evidence and causality. This means *systems-thinking* Iceberg, not Apache Iceberg.
- Optional distinct `apache_iceberg_architecture`: snapshots, catalog, lake storage, query engine and lineage.
- `hexagonal_architecture`: driving/driven adapters, inbound/outbound ports, domain boundaries, technology/dependency directions.
- `ddd_context_map`: bounded contexts, upstream/downstream, ACL, conformist, customer-supplier, partnership and ownership (only when evidence exists).
- `ddd_domain_model`: aggregates, entities, value objects, events, services, invariants.
- `clean_architecture`, `onion_architecture`, `c4_interactive`: layered views, source-linked objects, C4 drilldown and breadcrumbs. Existing `c4plantuml`/Structurizr remain.
- D2 already exists: enhance viewer for `d2`, not a duplicate type.

### Cloud — `uml-mcp-plugin-cloud`
`aws_architecture`, `azure_architecture`, `gcp_architecture`, `multicloud_architecture`, `hybrid_cloud_architecture`. Reuse D3 icon/service catalog and nested regions/VPCs/subnets; allow provider, cost, security, region, ownership and environment overlays only with supplied values. Respect official icon licenses; generic fallbacks.

### AI — `uml-mcp-plugin-ai`
`ai_training_pipeline`, `neural_network_architecture`, `transformer_architecture`, `rag_pipeline`, `ai_agent_workflow`, `multi_agent_workflow`, `llm_inference_pipeline`, `mlops_pipeline`. Support step-by-step data flow, loops, tensor labels, checkpoints, gradients, handoffs and evaluation. Audit actual LLM2SVG `data/train` files for reusable *SVG primitives*, provenance and licensing. The README describes general text-to-SVG examples; don't assume an ML diagram dataset or add mandatory GPU model training.

### UI/DevOps — `uml-mcp-plugin-ui`, optional `uml-mcp-plugin-devops`
`ui_wireframe`, `ui_user_flow`, `ui_component_tree`, `ui_navigation_map`, `ui_state_diagram`, `ui_design_system`. Add CI/CD pipelines, event-driven systems, data lineage and trust-boundary visualizations only where existing Mermaid/D2/Kroki lack the needed semantic interactions.

## P1: GitDiagram-style repository maps — `uml-mcp-plugin-repomap`

Create local-first architecture extraction from authorized repo checkout or least-privilege GitHub connector. Parse repository tree, manifests/imports/routes, CI, Docker, Terraform/CloudFormation/Kubernetes. Build evidence-linked graph: repo > service > module > dependency. Mark discovered vs inferred relations, source path/line/commit and confidence. Avoid crawling unnecessary private code or posting it to third parties.

Types: `git_repository_map`, `git_dependency_graph`, `git_service_architecture`, `git_change_impact`. Click existing GitHub file at pinned commit, expand/collapse, filter language/service, trace impact, compare commits. Cache by repo + commit and cap very large graphs. Test against a public fixture and UML-MCP itself.

GitDiagram is inspiration, not a required hosted API dependency.

## P1: IcePanel-style interactive model (and optional API)

**Offline-first original implementation:** One canonical architecture JSON/YAML model; C4 context/container/component navigation; shared nodes, breadcrumbs, flow walkthroughs, data paths, tags, ownership, environment/status overlays, compare current/future states, dependency tracing. Do not copy proprietary UI branding/assets.

**Optional real IcePanel API:** Read/import landscape via documented API, map model/diagrams/flows, validate export; writes require explicit credentials, user approval, dry-run diff and stable IDs. No default destructive prune or unapproved sync. The offline interactive mode must work without an IcePanel account.

## Luna interaction modes

Capability-driven interaction, not promises that every format can do every operation:
1. Explore: pan, zoom, fit, search, filter and minimap.
2. Drilldown: navigate hierarchical groups/C4 levels with breadcrumb and back.
3. Trace: highlight data/dependency paths and adjacent nodes.
4. Story: replay flows with stepper/pause/resume.
5. Compare: Git commit diff, current vs future; distinguish added/deleted/changed.
6. Inspect: accessible side panel with metadata and evidence/source links.
7. Arrange: drag/pin/auto-layout/undo/reset; keep ephemeral view state separate.
8. Overlay: provider, risk, status, environment, ownership and cost where present.

## P0 validation and release gates

- Backend: pytest, Ruff, ty, `uml-mcp lint`, plugin schema/registration, MCP protocol discovery, real renderer fixtures; keep token budget and existing public API stable.
- Browser: Playwright actual MCP Apps host sandbox, SVG sanitizer injection checks, accessible keyboard/contrast, desktop/mobile, color themes, zoom/pan/fit/reset, exports and failures.
- Visual regression: cloud, iceberg, hexagonal, DDD, C4, D2, AI, UI, Git maps and non-Apps fallback. Fix clipping, dense labels, incorrect edges and bad layout instead of accepting snapshots blindly.
- Security: SVG/HTML XSS, dangerous URL protocols, origin/source, CSP, external resources, allowed plugin install/config, token leakage, large payload exhaustion and rendering timeouts.
- CI build must package plugins and frontend exactly as production uses them.

## Manufact deployment and previous local changes

**Existing server:** `uml-mcp`; production `main`; `https://fast-steel-xf470.run.mcp-use.com/mcp`. Before modifications, read **current** server config/status and latest runtime logs. User-supplied notes describe a prior failed startup caused by an incorrect `server:app` entry, despite local `app:app` working. Check current config; do not assume historical failure still applies.

Astra: preview deployment when available, run tests and publishing checklist against real endpoint (initialize, tools/list, resources/list/read, render ordinary and plugin diagram, MCP Apps capable-host test), inspect runtime logs and analytics, then promote to production only after authorization and passing gates; preserve rollback SHA. Running container alone does not equal verified app.

**Existing unfinished local changes:** User described uncommitted Smithery/Lulu promotional removal, metadata fixes, viewer security tests and deployment settings on Windows. These changes are *not* necessarily on GitHub. Reconcile with the user's checkout before re-implementing or overwriting. Remove unwanted promotional badges/docs while preserving actual user-facing integrations deliberately approved by the user. Never claim local edits were included if not committed/pushed.

## Required final report

Provide task ledger, actual changed paths/commit(s), test commands and outputs, screenshots, CI checks, Manufact environment URL/commit/checklist and deployment health, open defects/blockers and next task. Distinguish **implemented**, **tested locally**, **tested in preview**, **deployed**, and **verified in production**. Never mark optional integrations complete without real credentials or tests.
