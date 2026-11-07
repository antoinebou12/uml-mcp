# Timeline plugin

`uml-mcp-plugin-timeline` adds one diagram type, `timeline`, for project timelines and product
roadmaps: swimlanes of task bars with progress and status colour, phases as translucent bands,
milestone diamonds, release flags, dependency arrows, a dashed today line and a legend.

| Type | Output | Opens as |
| --- | --- | --- |
| `timeline` | `html`, `svg` | An interactive page that zooms between quarters, months, weeks and days |

It ships with uml-mcp and is on by default (`plugins.bundled`). The page runs locally with no
CDN or network access, in the sandboxed plugin frame, under a hash-based CSP.

```bash
uml-mcp plugins enable timeline   # only needed with plugins.bundled: false
```

## Source format

| Field | Notes |
| --- | --- |
| `title`, `subtitle` | The subtitle defaults to the date range and item count |
| `today` | Pins the today line (`2026-11-07`). Omitted, the page uses the reader's date and the SVG the server's |
| `scale` | `day`, `week`, `month` or `quarter`: the zoom of the static SVG. Omitted, the SVG is about 1000 px wide; the page always opens fitted |
| `theme` | `auto` (default), `light` or `dark`. Static output is dark for `auto`; the page follows the system and has a toggle |
| `lanes[]` | `id` (required, unique), `name`, `color` (`#rrggbb`; a palette colour by default) |
| `items[]` | `id` (required, unique), `lane`, `name`, `start` (required), `end`, `kind`, `status`, `owner`, `progress`, `depends_on`, `link`, `note` |

Item fields:

| Field | Values |
| --- | --- |
| `start`, `end` | `2026-11-07`, `2026-11` or `2026-Q3`. A month or quarter as `start` is its first day, as `end` its last day. `end` is inclusive; a task without one lasts one day, or the whole month or quarter it names |
| `kind` | `task` (default, a rounded bar), `phase` (a band behind the lane's items), `milestone` (a diamond), `release` (a flag). Milestones and releases take only `start` |
| `status` | `planned` (default), `active`, `done`, `blocked` (dashed outline), `at-risk` |
| `progress` | 0 to 100, drawn as a fill inside the bar; defaults to 100 for `done`, else 0 |
| `depends_on` | Item ids. Each arrow runs from the dependency's end to the item's start, looping back when the item starts first |
| `lane` | May be left out when there is only one lane |
| `link` | An `https://` URL, opened by the detail card's **Open link** button |
| `owner`, `note` | Free text shown in the detail card; owners feed the owner filter |

`validate_uml` reports every problem at once, naming the item: a date that is not real, an
`end` before its `start`, a lane or dependency that does not exist (with the known ids), a
dependency cycle (`dependency cycle: a → c → b → a`), an unknown field (with the right name
when it is a common alias such as `dependencies` or `end_date`). Limits: 40 lanes and 400 items
(`plugins.settings.timeline.max_items` can lower it).

## Example

```json
{
  "title": "Product roadmap 2026–27",
  "today": "2026-11-07",
  "lanes": [
    {"id": "platform", "name": "Platform", "color": "#6366f1"},
    {"id": "product", "name": "Product", "color": "#0ea5e9"},
    {"id": "gtm", "name": "Go-to-market", "color": "#f59e0b"}
  ],
  "items": [
    {"id": "beta-phase", "lane": "product", "name": "Public beta", "kind": "phase",
     "start": "2026-11-02", "end": "2027-01-29", "status": "active"},
    {"id": "auth", "lane": "platform", "name": "SSO and SCIM", "start": "2026-09-01",
     "end": "2026-10-23", "status": "done", "owner": "Priya"},
    {"id": "api", "lane": "platform", "name": "Public API v2", "start": "2026-10-12",
     "end": "2026-12-11", "status": "active", "owner": "Marco", "progress": 55,
     "depends_on": ["auth"]},
    {"id": "billing", "lane": "platform", "name": "Usage billing", "start": "2026-11-16",
     "end": "2027-01-22", "status": "blocked", "owner": "Marco", "depends_on": ["api"],
     "note": "Waiting on the payment provider contract."},
    {"id": "beta", "lane": "product", "name": "Beta opens", "kind": "milestone",
     "start": "2026-11-02", "status": "done", "depends_on": ["auth"]},
    {"id": "ga", "lane": "product", "name": "v2.0 GA", "kind": "release",
     "start": "2027-03-01", "depends_on": ["billing"], "link": "https://example.com/releases/2.0"},
    {"id": "launch", "lane": "gtm", "name": "Launch campaign", "start": "2027-01-11",
     "end": "2027-03-12", "owner": "Lena"}
  ]
}
```

The full example, with eleven items, is the type's entry in `uml://examples`.

## Page controls

| Action | Result |
| --- | --- |
| **Quarters**, **Months**, **Weeks**, **Days**, **−**, **+** | Zoom to a named scale or step; the axis ticks follow |
| Wheel or trackpad pinch, two-finger pinch on touch | Zoom around the pointer |
| Drag, Shift+wheel, arrow keys | Pan in time, and up and down through many lanes |
| **Now** | Centre the today line |
| **Fit**, `0` | Show the whole timeline (the page opens fitted) |
| Lane, owner and status menus | Show only matching items; phases stay visible under an owner filter |
| Click an item | Detail card: dates, duration, owner, progress, what it depends on and what it blocks, the note and **Open link**. Its whole dependency chain stays bright and the rest dims |
| Esc | Close the card |
| **Dark** / **Light** | Switch theme |
| **Export** | SVG or PNG of the whole timeline at the current zoom and filters, or the page as HTML |

Inside the MCP App viewer the page drops its own title, links open through the host
(`ui/open-link`) and the viewer's export buttons drive the page's exports. In a narrow frame
the toolbar scrolls sideways on one row and the detail card becomes a bottom sheet.
