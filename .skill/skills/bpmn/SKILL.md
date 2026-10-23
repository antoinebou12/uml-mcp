---
name: bpmn
description: >-
  Writes valid bpmn diagram source for uml-mcp (diagram_type=bpmn). Business Process Model and Notation Use when the user asks for bpmn or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# bpmn diagram (uml-mcp)

**`diagram_type`:** `bpmn`  
**Backend:** `bpmn`  
**Output formats:** svg

Business Process Model and Notation

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Prefer executable BPMN 2.0 XML with start, tasks, gateways, end, and `sequenceFlow` (see tutorials/bpmn.md).
- Use `uml://templates` / `uml://examples` key `bpmn` as a starter.

## Styling

- BPMN XML has no Kroki theme switch; use clear task names and gateway labels.
- Prefer executable BPMN 2.0 with `sequenceFlow`.

## Starter template

```bpmn
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  id="Definitions_1"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="StartEvent_1"/>
    <bpmn:task id="Task_1" name="Process"/>
    <bpmn:endEvent id="EndEvent_1"/>
    <bpmn:sequenceFlow sourceRef="StartEvent_1" targetRef="Task_1"/>
    <bpmn:sequenceFlow sourceRef="Task_1" targetRef="EndEvent_1"/>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="_BPMNShape_StartEvent_2" bpmnElement="StartEvent_1">
        <dc:Bounds x="173" y="102" width="36" height="36"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="_BPMNShape_Task_1" bpmnElement="Task_1">
        <dc:Bounds x="260" y="80" width="100" height="80"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="_BPMNShape_EndEvent_2" bpmnElement="EndEvent_1">
        <dc:Bounds x="417" y="102" width="36" height="36"/>
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
```

## Example

```bpmn
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  id="Definitions_1"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="StartEvent_1"/>
    <bpmn:task id="Task_1" name="Process"/>
    <bpmn:endEvent id="EndEvent_1"/>
    <bpmn:sequenceFlow sourceRef="StartEvent_1" targetRef="Task_1"/>
    <bpmn:sequenceFlow sourceRef="Task_1" targetRef="EndEvent_1"/>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="_BPMNShape_StartEvent_2" bpmnElement="StartEvent_1">
        <dc:Bounds x="173" y="102" width="36" height="36"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="_BPMNShape_Task_1" bpmnElement="Task_1">
        <dc:Bounds x="260" y="80" width="100" height="80"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="_BPMNShape_EndEvent_2" bpmnElement="EndEvent_1">
        <dc:Bounds x="417" y="102" width="36" height="36"/>
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
```

## Render with uml-mcp

1. Set `diagram_type` to `bpmn` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
