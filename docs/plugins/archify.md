# Archify plugin

`uml-mcp-plugin-archify` draws architecture and workflow diagrams in the "archify" style:
dashed, colour-coded group containers (security, frontend, backend, message bus, workers,
database, cloud), glowing icon cards and labelled arrows, on a dot grid. It takes the same
JSON as the [stack-diagram plugin](stack-diagram.md) and shares its layout engine, so both
support `LR`, `RL`, `TB` and `BT` flows and `dark`, `light` and `auto` themes.

```bash
uml-mcp plugins enable archify   # ships with uml-mcp; restart the server after
```

| Type | Starts as | For |
| --- | --- | --- |
| `archify_architecture` | left to right | Systems, services and the groups they belong to |
| `archify_workflow` | top down | Steps and hand-offs, optionally grouped into stages |
| `archify_sequence` | participants across the top | Call and reply messages in order |

All three render to `html` or `svg`. This plugin implements architecture, workflow and sequence
diagrams only, not the other kinds the original archify project offers.

## Presets, theme and chrome

| Field | Values | Effect |
| --- | --- | --- |
| `preset` | `classic` (default), `blueprint`, `flow` | `blueprint` adds a line grid, corner brackets and dash-dot containers; `flow` adds a soft glow under every edge |
| `theme` | `auto` (default), `dark`, `light` | `auto` follows the system in the HTML page and is dark in static output |
| `direction` | `LR`, `RL`, `TB`, `BT` | Flow direction for architecture and workflow |
| `subtitle` | text | Shown under the title (static SVG header, page header) |
| node `tag` | up to 24 characters | A small coloured third line, e.g. an owning team |

Static SVGs get a title block, the preset's look and a **legend** with a node count per group
style. The HTML page has its own header with a preset picker, a **Live** toggle that animates the
edges (off for reduced motion), zoom and fit, and the theme toggle.

## Interacting with the page

* **Click a node** to focus it: everything not upstream or downstream of it dims, and a detail
  panel lists its role, group, reach counts and incoming and outgoing links (click one to jump).
* **Shift+click a second node** to show the shortest path between them.
* **Esc** or a click on empty space clears the focus.

## Sequence diagrams

```json
{
  "title": "Cache miss",
  "participants": [
    {"id": "web", "name": "Web App", "icon": "browser"},
    {"id": "api", "name": "API", "icon": "api"}
  ],
  "messages": [
    {"from": "web", "to": "api", "label": "GET /dashboard"},
    {"from": "api", "to": "api", "label": "emit trace"},
    {"from": "api", "to": "web", "label": "200 OK", "style": "dashed"}
  ]
}
```

`style: "dashed"` marks a reply; a message from a participant to itself draws a loop; `note`
adds a line under the label; `"autonumber": true` numbers every message. At most 12 participants and 100 messages.

## Group styles

A group's `style` sets its colour, and its nodes borrow it unless they set their own `tone`.

| Style | Tone | Typical use |
| --- | --- | --- |
| `default` | gray | Anything else |
| `security` | red | Identity, auth, secrets |
| `frontend` | teal | Web and mobile clients |
| `backend` | green | Services and APIs |
| `bus` | orange | Queues, event buses |
| `workers` | teal | Background jobs |
| `database` | purple | Data stores |
| `cloud` | yellow | Infrastructure |
| `external` | gray | Third parties |

## Example

```json
{
  "title": "Platform", "direction": "LR", "theme": "dark",
  "groups": [
    {"id": "sec", "name": "Security & Identity", "style": "security", "icon": "shield"},
    {"id": "be", "name": "Backend Services", "style": "backend", "icon": "server"}
  ],
  "nodes": [
    {"id": "auth", "name": "Auth Service", "role": "OAuth2 / OIDC", "icon": "lock", "group": "sec"},
    {"id": "api", "name": "API Service", "role": "REST / GraphQL", "icon": "api", "group": "be"}
  ],
  "edges": [{"from": "auth", "to": "api", "label": "validate token", "style": "dashed"}]
}
```

Nodes, edges, icons, limits and layout rules are the ones in the
[stack-diagram reference](stack-diagram.md#source-format).
