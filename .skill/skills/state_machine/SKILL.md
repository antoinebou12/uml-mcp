---
name: state_machine
description: >-
  Writes valid state_machine JSON for uml-mcp (diagram_type=state_machine, bundled plugin statechart). Use when the user asks for a state machine or statechart (order lifecycle, traffic light, UI flow) to read or step through; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# state_machine diagram (uml-mcp plugin `statechart`)

**`diagram_type`:** `state_machine`  
**Backend:** `plugin:statechart` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

State machine (statechart) from XState-like JSON: compound and parallel states, initial, final and history states, guarded transitions with actions. html is a simulator (fire events, step log, undo); svg is a static image

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/statechart/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Model our order lifecycle as a state machine: checkout with address and payment steps, packing and invoicing in parallel, cancelled and delivered as final states.

## Notation tips

- XState-like JSON: `id`, `title`, `initial`, `context`, `states`. Each state: `on` (`EVENT: target` or `{target, guard, actions}`, or a list of guarded alternatives), `entry`, `exit`, `type` (`atomic`, `compound`, `parallel`, `final`, `history`), `initial`, `states`, `description`, `onDone`.
- Every compound state needs `initial`; a parallel state has none (all regions start).
- Targets: a sibling name, a dotted path (`checkout.payment`), `.child`, or `#id.path`. A transition with no target runs its actions and stays (drawn inside the state).
- `{"type": "history"}` in a compound remembers the last step; target it to resume (`"history": "deep"` for nested steps).
- Guards are labels: the simulator shows one button per guarded alternative.
- `direction`: `LR` (default) or `TB`. `validate_uml` warns about unreachable states.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"id":"order","title":"Order lifecycle","initial":"cart","context":{"items":0,"total":0},"states":{"cart":{"description":"The shopper is still adding items.","on":{"ADD_ITEM":{"actions":["addItem"]},"CHECKOUT":{"target":"checkout","guard":"hasItems"}}},"checkout":{"initial":"address","entry":["startTimer"],"exit":["stopTimer"],"description":"Address, then payment. Help keeps your place.","states":{"address":{"on":{"NEXT":"payment"}},"payment":{"on":{"BACK":"address","PAY":[{"target":"#order.fulfilment","guard":"cardOk","actions":["charge"]},{"target":"declined","guard":"cardDeclined"}]}},"declined":{"on":{"RETRY":"payment"}},"hist":{"type":"history"}},"on":{"HELP":"help","CANCEL":"cancelled"}},"help":{"description":"A support chat; resuming returns to the same checkout step.","on":{"RESUME":"checkout.hist"}},"fulfilment":{"type":"parallel","description":"Packing and invoicing run at the same time.","onDone":"delivered","states":{"packing":{"initial":"picking","states":{"picking":{"on":{"PACKED":"packed"}},"packed":{"type":"final"}}},"invoice":{"initial":"drafting","states":{"drafting":{"on":{"SEND":"sent"}},"sent":{"type":"final"}}}},"on":{"CANCEL":{"target":"cancelled","actions":["refund"]}}},"delivered":{"type":"final","entry":["notifyCustomer"]},"cancelled":{"type":"final"}}}
```
