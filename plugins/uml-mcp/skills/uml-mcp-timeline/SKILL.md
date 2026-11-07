---
name: uml-mcp-timeline
description: Draw project timelines and product roadmaps with swimlanes, phases, milestones, releases and dependencies (timeline).
---

# Timelines and roadmaps

Follow `skill://uml-mcp-diagrams/SKILL.md`. Swimlanes of task bars with progress and status colour, phases as bands, milestone diamonds, release flags, dependency arrows and a today line. The page zooms between quarters, months, weeks and days, filters by lane, owner and status, and highlights a clicked item's dependency chain.

## Types

| Type | Use for | Example prompt |
| --- | --- | --- |
| `timeline` | a project timeline, product roadmap or Gantt-style plan with swimlanes, milestones and dependencies | Show our product roadmap for the next three quarters: platform, product and go-to-market lanes, the beta phase, launch milestones and the 2.0 release. |

## Steps

1. Check the live catalog (`list_diagram_types` or `uml://types`); the bundled plugins are on by default, but a server may turn them off with `plugins.bundled: false`.
2. Read the type's example from `uml://examples` and keep its field names.
3. Call `validate_uml`; an error names the field and, for a bad reference, lists the known ids, so fix it and validate again.
4. Render with `generate_uml_image` for a chat image, or `generate_uml` with `output_format: "html"` for the interactive page in the MCP App viewer. Clients without MCP Apps still get the PNG and SVG.
5. Pass `theme` (`auto`, `dark`, `light`) rather than editing colours.

## Example

```json
{"title":"Product roadmap 2026–27","today":"2026-11-07","lanes":[{"id":"platform","name":"Platform","color":"#6366f1"},{"id":"product","name":"Product","color":"#0ea5e9"},{"id":"gtm","name":"Go-to-market","color":"#f59e0b"}],"items":[{"id":"beta-phase","lane":"product","name":"Public beta","kind":"phase","start":"2026-11-02","end":"2027-01-29","status":"active","note":"Invite-only beta with weekly releases."},{"id":"auth","lane":"platform","name":"SSO and SCIM","start":"2026-09-01","end":"2026-10-23","status":"done","owner":"Priya","link":"https://example.com/roadmap/sso"},{"id":"api","lane":"platform","name":"Public API v2","start":"2026-10-12","end":"2026-12-11","status":"active","owner":"Marco","progress":55,"depends_on":["auth"],"note":"REST and webhooks; GraphQL follows."},{"id":"billing","lane":"platform","name":"Usage billing","start":"2026-11-16","end":"2027-01-22","status":"blocked","owner":"Marco","progress":10,"depends_on":["api"],"note":"Waiting on the payment provider contract."},{"id":"editor","lane":"product","name":"New editor","start":"2026-09-14","end":"2026-11-20","status":"active","owner":"Ada","progress":80},{"id":"beta","lane":"product","name":"Beta opens","kind":"milestone","start":"2026-11-02","status":"done","depends_on":["editor","auth"]},{"id":"mobile","lane":"product","name":"Mobile app","start":"2026-12-01","end":"2027-02-26","status":"at-risk","owner":"Ada","progress":15,"depends_on":["api"]},{"id":"ga","lane":"product","name":"v2.0 GA","kind":"release","start":"2027-03-01","status":"planned","depends_on":["billing","mobile"],"link":"https://example.com/releases/2.0"},{"id":"pricing","lane":"gtm","name":"Pricing study","start":"2026-10-05","end":"2026-11-27","status":"active","owner":"Lena","progress":60},{"id":"launch","lane":"gtm","name":"Launch campaign","start":"2027-01-11","end":"2027-03-12","status":"planned","owner":"Lena","depends_on":["pricing"]},{"id":"summit","lane":"gtm","name":"Customer summit","kind":"milestone","start":"2027-02-10","status":"planned"}]}
```
