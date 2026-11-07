---
name: timeline
description: >-
  Writes valid timeline JSON for uml-mcp (diagram_type=timeline, bundled plugin timeline). Use when the user asks for a project timeline, product roadmap or Gantt-style plan with swimlanes, milestones and dependencies; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# timeline diagram (uml-mcp plugin `timeline`)

**`diagram_type`:** `timeline`  
**Backend:** `plugin:timeline` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

Project timeline or product roadmap: swimlanes, task bars with progress and status, phases, milestones, releases, dependency arrows and a today line. JSON lanes and items with ISO dates or quarters; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/timeline/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Show our product roadmap for the next three quarters: platform, product and go-to-market lanes, the beta phase, launch milestones and the 2.0 release.

## Notation tips

- `lanes` (`id`, `name`, `color`) and `items` (`id`, `lane`, `name`, `start`, `end`, `kind`, `status`, `owner`, `progress`, `depends_on`, `link`, `note`).
- Dates are `2026-11-07`, `2026-11` or `2026-Q3`; a month or quarter as `end` means its last day. `end` is inclusive.
- `kind`: `task` (bar), `phase` (translucent band behind the lane), `milestone` (diamond), `release` (flag). Milestones and releases take only `start`.
- `status`: `planned`, `active`, `done`, `blocked`, `at-risk`; `progress` is 0-100.
- `depends_on` lists item ids; arrows run from each dependency's end to the item's start. Cycles and unknown ids are rejected by name.
- Optional `today` pins the dashed today line; `scale` (`day`, `week`, `month`, `quarter`) sets the static SVG's zoom.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Product roadmap 2026–27","today":"2026-11-07","lanes":[{"id":"platform","name":"Platform","color":"#6366f1"},{"id":"product","name":"Product","color":"#0ea5e9"},{"id":"gtm","name":"Go-to-market","color":"#f59e0b"}],"items":[{"id":"beta-phase","lane":"product","name":"Public beta","kind":"phase","start":"2026-11-02","end":"2027-01-29","status":"active","note":"Invite-only beta with weekly releases."},{"id":"auth","lane":"platform","name":"SSO and SCIM","start":"2026-09-01","end":"2026-10-23","status":"done","owner":"Priya","link":"https://example.com/roadmap/sso"},{"id":"api","lane":"platform","name":"Public API v2","start":"2026-10-12","end":"2026-12-11","status":"active","owner":"Marco","progress":55,"depends_on":["auth"],"note":"REST and webhooks; GraphQL follows."},{"id":"billing","lane":"platform","name":"Usage billing","start":"2026-11-16","end":"2027-01-22","status":"blocked","owner":"Marco","progress":10,"depends_on":["api"],"note":"Waiting on the payment provider contract."},{"id":"editor","lane":"product","name":"New editor","start":"2026-09-14","end":"2026-11-20","status":"active","owner":"Ada","progress":80},{"id":"beta","lane":"product","name":"Beta opens","kind":"milestone","start":"2026-11-02","status":"done","depends_on":["editor","auth"]},{"id":"mobile","lane":"product","name":"Mobile app","start":"2026-12-01","end":"2027-02-26","status":"at-risk","owner":"Ada","progress":15,"depends_on":["api"]},{"id":"ga","lane":"product","name":"v2.0 GA","kind":"release","start":"2027-03-01","status":"planned","depends_on":["billing","mobile"],"link":"https://example.com/releases/2.0"},{"id":"pricing","lane":"gtm","name":"Pricing study","start":"2026-10-05","end":"2026-11-27","status":"active","owner":"Lena","progress":60},{"id":"launch","lane":"gtm","name":"Launch campaign","start":"2027-01-11","end":"2027-03-12","status":"planned","owner":"Lena","depends_on":["pricing"]},{"id":"summit","lane":"gtm","name":"Customer summit","kind":"milestone","start":"2027-02-10","status":"planned"}]}
```
