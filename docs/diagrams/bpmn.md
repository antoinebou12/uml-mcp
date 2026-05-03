---
title: BPMN (Kroki XML)
description: Minimal BPMN 2.0 XML for generate_uml and Kroki; links to the full BPMN guide.
tags:
  - reference
  - diagrams
---

# BPMN (Kroki XML)

For BPMN concepts, flow rules, and the same content as `uml://bpmn-guide`, see the **[BPMN guide](../tutorials/bpmn.md)**. This page shows a minimal BPMN 2.0 XML snippet you can pass to `generate_uml` with `diagram_type: bpmn` for rendering through Kroki.

## Example

```xml
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:process id="Approval" isExecutable="true">
    <bpmn:startEvent id="Start"/>
    <bpmn:task id="Submit" name="Submit request"/>
    <bpmn:endEvent id="End"/>
    <bpmn:sequenceFlow sourceRef="Start" targetRef="Submit"/>
    <bpmn:sequenceFlow sourceRef="Submit" targetRef="End"/>
  </bpmn:process>
</bpmn:definitions>
```

## Parameters

| Property | Value |
| --- | --- |
| `diagram_type` | `bpmn` |
| Backend | BPMN (via Kroki) |
| Output formats | `svg` |

## See also

- [BPMN guide](../tutorials/bpmn.md)
- [More diagram backends](general.md)
- [Diagram catalog](index.md)
