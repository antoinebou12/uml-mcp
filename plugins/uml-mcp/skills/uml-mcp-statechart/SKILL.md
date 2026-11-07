---
name: uml-mcp-statechart
description: Draw state machines as statecharts with a step-through simulator (state_machine).
---

# Statecharts

Follow `skill://uml-mcp-diagrams/SKILL.md`. Rounded states, compound containers, parallel regions split by dashed lines, initial, final and history pseudo-states and labelled orthogonal transitions. The HTML page is a simulator: it highlights the active states and offers a button for every enabled event, with a step log, Undo and Reset.

## Types

| Type | Use for | Example prompt |
| --- | --- | --- |
| `state_machine` | a state machine or statechart (order lifecycle, traffic light, UI flow) to read or step through | Model our order lifecycle as a state machine: checkout with address and payment steps, packing and invoicing in parallel, cancelled and delivered as final states. |

## Steps

1. Check the live catalog (`list_diagram_types` or `uml://types`); the bundled plugins are on by default, but a server may turn them off with `plugins.bundled: false`.
2. Read the type's example from `uml://examples` and keep its field names.
3. Call `validate_uml`; an error names the field and, for a bad reference, lists the known ids, so fix it and validate again.
4. Render with `generate_uml_image` for a chat image, or `generate_uml` with `output_format: "html"` for the interactive page in the MCP App viewer. Clients without MCP Apps still get the PNG and SVG.
5. Pass `theme` (`auto`, `dark`, `light`) rather than editing colours.

## Example

```json
{"id":"order","title":"Order lifecycle","initial":"cart","context":{"items":0,"total":0},"states":{"cart":{"description":"The shopper is still adding items.","on":{"ADD_ITEM":{"actions":["addItem"]},"CHECKOUT":{"target":"checkout","guard":"hasItems"}}},"checkout":{"initial":"address","entry":["startTimer"],"exit":["stopTimer"],"description":"Address, then payment. Help keeps your place.","states":{"address":{"on":{"NEXT":"payment"}},"payment":{"on":{"BACK":"address","PAY":[{"target":"#order.fulfilment","guard":"cardOk","actions":["charge"]},{"target":"declined","guard":"cardDeclined"}]}},"declined":{"on":{"RETRY":"payment"}},"hist":{"type":"history"}},"on":{"HELP":"help","CANCEL":"cancelled"}},"help":{"description":"A support chat; resuming returns to the same checkout step.","on":{"RESUME":"checkout.hist"}},"fulfilment":{"type":"parallel","description":"Packing and invoicing run at the same time.","onDone":"delivered","states":{"packing":{"initial":"picking","states":{"picking":{"on":{"PACKED":"packed"}},"packed":{"type":"final"}}},"invoice":{"initial":"drafting","states":{"drafting":{"on":{"SEND":"sent"}},"sent":{"type":"final"}}}},"on":{"CANCEL":{"target":"cancelled","actions":["refund"]}}},"delivered":{"type":"final","entry":["notifyCustomer"]},"cancelled":{"type":"final"}}}
```
