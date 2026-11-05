# FastMCP feature adoption

Started 2026-11-03. Priority P1, size L. Requested by Antoine Boucher.

## Outcome

Audit the current FastMCP feature families and implement the applicable improvements to diagram workflows. Include background tasks, caller-model sampling, and the supplied Apps and client guides. Record deliberate exclusions and client or deployment limitations. Completion requires implementation evidence and repository quality checks, not only this audit.

## Initial source audit

The checkout pins `fastmcp-slim[server]==4.1.4`; the local runtime reports 4.1.4. The optional `fastmcp_tasks` module is absent.

| Feature family | Current evidence | Work remaining |
| --- | --- | --- |
| Tools, resources, templates, prompts | Registrations in `mcp_core/core/server.py` | Verify current wire contracts and discovery |
| Background tasks | No TasksExtension registration; synchronous render handlers | Optional package/configuration, async registration adapter, task lifecycle tests, deployment guidance |
| Caller-model sampling | No CreateMessageRequest implementation | Bounded, opt-in diagram repair with continuation validation and unsupported-client behavior |
| Elicitation | `mcp_core/tools/mrtr.py` | Verify modern and legacy capability handling, including multi-round continuation |
| Logging and progress | `mcp_core/tools/notifications.py` | Existing support; check task-context delivery and correct stale backlog claims |
| Custom HTML Apps | `mcp_core/apps/diagram_viewer.py` | Check current SDK lifecycle, visibility, CSP, host support and interaction tests |
| Generative UI / Prefab / FastMCPApp | No corresponding Python integration found | Evaluate useful diagram-specific interactions and sandbox/dependency costs before adoption |
| Client transports / ClientGroup | Client tooling exists; no ClientGroup integration found | Audit test/client workflows; federation is only applicable if a concrete workflow needs it |
| Completions / Skills / extensions | Existing registration and backlog entries | Verify current framework support and mirror invariants |
| Providers / composition / transforms | Plugin loader and schema compatibility transform exist | Audit applicability and avoid expanding the small tool catalog unnecessarily |
| Authentication / authorization | Existing enterprise auth modules | Verify task identity and access checks; auth must stay off on Vercel |
| Storage / sessions / lifespan | Needs focused inspection | Document process lifetime, persistence and replica requirements |
| Pagination / icons / versioning / fingerprints | Server icon registration confirmed | Inspect remaining discovery metadata and compatibility needs |
| Testing / telemetry / deployment | Existing quality tooling, OTEL and deployment files | Run relevant behavior tests and final quality gates |

## Implementation sequence

1. Add optional background execution for long render workflows. Preserve foreground calls. Verify polling, completion, failure, cancellation and progress. Determine safe deployment settings for persistent workers; an in-memory worker cannot outlive a serverless invocation.
2. Implement caller-model sampling through FastMCP 4 multi-round results. Validate model output before rendering, bound the workflow and retain useful diagnostics when unsupported or unsuccessful.
3. Audit all seven supplied guides against the viewer and client workflows. Implement justified interaction improvements and record why other capabilities do not fit this server.
4. Complete the remaining feature-family audit, configuration documentation and compatibility tests.
5. Run ruff check/format, ty, pytest with coverage at least 82%, strict application lint and strict MkDocs build. If workflows change, run the required local act check. Record limitations without claiming unverified deployment success.

## References

- [FastMCP documentation index](https://gofastmcp.com/llms.txt)
- [Background tasks](https://gofastmcp.com/servers/tasks)
- [Sampling](https://gofastmcp.com/servers/sampling)
- User attachments: Generative UI, Custom HTML Apps, FastMCPApp, Interactive Tools, Client Transports, Client Groups, Sampling.

## Progress

- Architecture scope added by the user: reproduce the supplied stack-diagram design as an `architecture` renderer plugin with HTML/TSX exports and MCP App display. Current code includes embedded SVG validation, basic elbow routing, and an MCP result-contract test. Full reference styling, editable TSX components/constants, custom routes, nested groups, icon manifest integration, and browser verification remain incomplete.
- Latest integration checks: 59 focused tests pass (architecture assets/plugin, tasks, authentication middleware, MCP Apps). Repository ruff check and format check pass; ty passes. Strict application lint reports A, 100/100, zero errors/warnings, with default plugins. Architecture-enabled lint and full pytest/coverage/docs validation are still required.
- The unmodified upstream logo helper is excluded from repository Ruff formatting/lint; its adjacent MIT license and provenance README are retained.

- Confirmed the checkout was clean at the start on `codex/viewer-trace-regressions`.
- Confirmed that FastMCP 4 supports tasks through its optional package and sampling through InputRequiredResult; the previous blanket skip entry was inaccurate.
- Found logging already implemented despite the backlog skip entry.
- `SOUL.md`, referenced by AGENTS.md, is absent from this checkout.
- Added the optional `tasks` dependency, configuration with environment overrides, guarded extension registration and async adapters for the three render tools.
- Added strict lint checks for unsupported task deployments and unencrypted Redis caller snapshots.
- Verified a real FastMCP client starts a background batch, polls it and receives the successful structured result (render backend stubbed).
- Focused configuration/registration/lint suite: 53 passed; background suite after the lifecycle addition: 5 passed. Type checking passes. Full quality gates remain pending.
- Next: expand task failure/cancellation/progress tests, audit task identity and multi-round handling, implement sampling, and complete Apps and remaining feature audits.
- 2026-11-04: bridged the verified enterprise principal into FastMCP's request user identity for task ownership. The bridge uses the existing hashed owner key and an empty token; incoming bearer credentials remain stripped. Authentication/task tests: 31 passed. Cross-caller task lifecycle integration remains to be verified.
- 2026-11-04: committed the tasks work and the architecture renderer (off by default) with readable errors for malformed architecture sources. The Manufact fixes landed separately (`ac68178`: no `frameDomains`, explicit batch item schema). Still open: sampling, cancellation/progress coverage, per-tool `timeout`, FastMCP `ErrorHandlingMiddleware` feeding the admin metrics.
