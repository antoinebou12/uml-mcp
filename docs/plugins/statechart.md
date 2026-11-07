# Statechart plugin

`uml-mcp-plugin-statechart` adds one diagram type, `state_machine`: a state machine written
as XState-like JSON, drawn as a statechart.

| Format | Opens as |
| --- | --- |
| `svg` | A static statechart (also the PNG preview for clients without MCP Apps) |
| `html` | A simulator: the same drawing, with the active states highlighted and a button for every event you can fire |

It ships with uml-mcp and is on by default (`plugins.bundled`). The page runs locally with no
CDN or network access, in the sandboxed plugin frame, under a hash-based CSP.

## Source format

```json
{
  "id": "order",
  "title": "Order lifecycle",
  "initial": "cart",
  "context": {"items": 0},
  "states": {
    "cart": {"on": {"ADD_ITEM": {"actions": ["addItem"]}, "CHECKOUT": {"target": "checkout", "guard": "hasItems"}}},
    "checkout": {
      "initial": "address",
      "entry": ["startTimer"],
      "states": {
        "address": {"on": {"NEXT": "payment"}},
        "payment": {"on": {"PAY": [
          {"target": "#order.fulfilment", "guard": "cardOk", "actions": ["charge"]},
          {"target": "declined", "guard": "cardDeclined"}]}},
        "declined": {"on": {"RETRY": "payment"}},
        "hist": {"type": "history"}
      },
      "on": {"HELP": "help", "CANCEL": "cancelled"}
    },
    "help": {"on": {"RESUME": "checkout.hist"}},
    "fulfilment": {
      "type": "parallel",
      "onDone": "delivered",
      "states": {
        "packing": {"initial": "picking", "states": {"picking": {"on": {"PACKED": "packed"}}, "packed": {"type": "final"}}},
        "invoice": {"initial": "drafting", "states": {"drafting": {"on": {"SEND": "sent"}}, "sent": {"type": "final"}}}
      }
    },
    "delivered": {"type": "final"},
    "cancelled": {"type": "final"}
  }
}
```

| Field | Notes |
| --- | --- |
| `id`, `title`, `description` | `id` names the machine for `#id.path` targets; `title` defaults to it |
| `initial`, `states` | The top-level states and the one the machine starts in. A top-level `"type": "parallel"` runs them all at once instead |
| `context` | Shown in the page's step log panel; the simulator does not evaluate it |
| `theme` | `auto` (default), `light` or `dark`. Static output for `auto` is dark |
| `direction` | `LR` (default, left to right) or `TB` (top down) |
| `on` (top level) | Events any state handles, listed under the title as **Any state** |

Each state may have:

| Field | Notes |
| --- | --- |
| `type` | `atomic`, `compound`, `parallel`, `final` or `history`. Omitted, it is `compound` when the state has `states`, else `atomic` |
| `initial` | Required on a compound state: the child it enters by default. A parallel state takes none |
| `states` | Child states (compound) or regions (parallel) |
| `on` | `EVENT: target`, `EVENT: {target, guard, actions}`, or a list of guarded alternatives. A transition with no `target` runs its actions and stays; it is drawn inside the state as `EVENT / action` |
| `entry`, `exit` | Action names (a name, a list, or `{"type": name}` objects) |
| `onDone` | On a compound or parallel state: the transition taken when it finishes (a final child is reached; for parallel, in every region) |
| `always`, `after` | Accepted and drawn as events (`always`, `after 1000ms`) that you fire by hand |
| `history`, `target` | On a history state: `shallow` (default) or `deep`, and the default child when there is no history yet |
| `description`, `label` | Shown in the detail card; `label` replaces the key on the drawing |

Targets are a sibling name (`"payment"`), a path from an ancestor's level (`"checkout.hist"`),
a child of the current state (`".payment"`), or an absolute `#machine.path` or `#id` of a state
with its own `id`. `guard` (or XState's older `cond`) is a label: nothing is evaluated.

### Validation

`validate_uml` reports every problem at once, each naming the state path: an unknown target
(with the closest names), a compound state without `initial` (with its children listed), an
`initial` that is not a child, a final state with transitions, an unknown `type` or key. States
nothing can reach are not errors: they come back under `warnings`. Limit: 300 states
(`plugins.settings.statechart.max_states` can lower it).

## The drawing

States are rounded boxes with their entry, exit and internal activities under a rule. Compound
states are containers around their children, with a dot for their initial state; parallel
states split their regions with dashed lines; final states are double circles and history
states an `H` (or `H*`) badge. Children are ranked from the initial state along the flow, and
every transition is routed with right angles around the states, labelled
`EVENT [guard] / actions` with the guard and actions in their own colours. A self-transition is
a loop on the corner.

## The simulator

| Action | Result |
| --- | --- |
| An event button, or a green transition label on the drawing | Fires it: the arrow animates and the highlight moves. An event with several guarded alternatives gets one button per guard, so you choose the outcome |
| Click a state | The detail card: kind, path, active or not, description, entry and exit actions, and its events (an enabled one fires, another shows its target) |
| **Undo** (Ctrl+Z), **Reset** | Step back one transition, or start over |
| Drag, wheel, **Fit**, **+**/**−** | Pan and zoom; the page fits the drawing on load and on resize |
| **Theme**, **Export** | Light or dark; save the drawing as SVG or PNG (with the current highlight), or the page as HTML |

Firing follows statechart rules: for each active atomic state the nearest state that handles
the event wins; the transition exits the states under its domain, runs its actions, and enters
its targets with their defaults (a compound's `initial`, every region of a parallel state, or
what a history state remembers). When a compound reaches a final child, or every region of a
parallel state does, its `onDone` fires by itself. The step log lists each event, the states it
reached and the actions it ran; the active states are listed above the drawing. In the chat's
MCP App viewer the page drops its own title and folds the log away in a narrow frame.
