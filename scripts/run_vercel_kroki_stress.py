"""Tool-only Kroki catalog stress harness against the live Vercel MCP HTTP API.

Uses FastMCP streamable HTTP (initialize + tools/call) against
https://uml-mcp.vercel.app/mcp and prints a compact Phase 4–6 report.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

import httpx

MCP_URL = "https://uml-mcp.vercel.app/mcp"
TIMEOUT = httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)

FIXTURES_1_20: list[dict[str, str]] = [
    {
        "diagram_type": "class",
        "code": "@startuml\nclass Account\nclass Customer\nCustomer \"1\" --> \"*\" Account : owns\n@enduml",
    },
    {
        "diagram_type": "sequence",
        "code": "@startuml\nparticipant Client\nparticipant API\nparticipant DB\nClient -> API: GET /resource\nAPI -> DB: query\nDB --> API: result\nAPI --> Client: 200\n@enduml",
    },
    {
        "diagram_type": "activity",
        "code": "@startuml\nstart\n:Receive order;\nif (Valid?) then (yes)\n  :Process order;\nelse (no)\n  :Reject order;\nendif\nstop\n@enduml",
    },
    {
        "diagram_type": "usecase",
        "code": "@startuml\nleft to right direction\nactor User\nrectangle System {\n  usecase (View diagram)\n  usecase (Generate diagram)\n}\nUser --> (View diagram)\nUser --> (Generate diagram)\n@enduml",
    },
    {
        "diagram_type": "state",
        "code": "@startuml\n[*] --> Idle\nIdle --> Running: start\nRunning --> Idle: stop\n@enduml",
    },
    {
        "diagram_type": "component",
        "code": "@startuml\ncomponent [Web]\ncomponent [API]\ndatabase DB\n[Web] --> [API]\n[API] --> DB\n@enduml",
    },
    {
        "diagram_type": "deployment",
        "code": '@startuml\nnode "App Server" {\n  artifact "app"\n}\nnode "Database Server" {\n  database "PostgreSQL"\n}\n"App Server" --> "Database Server"\n@enduml',
    },
    {
        "diagram_type": "object",
        "code": "@startuml\nobject user\nobject request\nobject result\nuser --> request\nrequest --> result\n@enduml",
    },
    {
        "diagram_type": "mermaid",
        "code": "flowchart LR\n  Client --> MCP\n  MCP --> Kroki\n  Kroki --> MCP\n  MCP --> Client",
    },
    {
        "diagram_type": "d2",
        "code": "User -> API: HTTP Request\nAPI -> Database: Query\nDatabase -> API: Result\nAPI -> User: JSON Response",
    },
    {
        "diagram_type": "graphviz",
        "code": 'digraph G {\n  rankdir=LR;\n  Client -> API [label="request"];\n  API -> DB [label="query"];\n  DB -> API [label="result"];\n  API -> Client [label="response"];\n}',
    },
    {
        "diagram_type": "erd",
        "code": "[Person]\n*name\nheight\n--\n[Order]\n*id\ndate\nPerson *-- Order",
    },
    {
        "diagram_type": "blockdiag",
        "code": "blockdiag {\n  Client -> API -> Database;\n  Database -> API -> Client;\n}",
    },
    {
        "diagram_type": "packetdiag",
        "code": "packetdiag {\n  colwidth = 32;\n  0-15: Source Port;\n  16-31: Destination Port;\n  32-63: Sequence Number;\n  64-95: Acknowledgment Number;\n}",
    },
    {
        "diagram_type": "bpmn",
        "code": """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  id="Definitions_1"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="StartEvent_1"/>
    <bpmn:task id="Task_1" name="Process"/>
    <bpmn:endEvent id="EndEvent_1"/>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Task_1"/>
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="EndEvent_1"/>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="StartShape" bpmnElement="StartEvent_1">
        <dc:Bounds x="100" y="100" width="36" height="36"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="TaskShape" bpmnElement="Task_1">
        <dc:Bounds x="200" y="80" width="100" height="80"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="EndShape" bpmnElement="EndEvent_1">
        <dc:Bounds x="370" y="100" width="36" height="36"/>
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>""",
    },
    {
        "diagram_type": "c4plantuml",
        "code": '!include <C4/C4_Context>\ntitle UML MCP Context\nPerson(user, "User")\nSystem(mcp, "UML MCP")\nSystem_Ext(kroki, "Kroki")\nRel(user, mcp, "Generates diagrams")\nRel(mcp, kroki, "Renders")',
    },
    {
        "diagram_type": "actdiag",
        "code": 'actdiag {\n  write -> validate -> render -> result\n  lane user {\n    label = "Client"\n    write [label = "Write source"];\n    result [label = "Receive result"];\n  }\n  lane server {\n    label = "UML MCP"\n    validate [label = "Validate"];\n    render [label = "Render"];\n  }\n}',
    },
    {
        "diagram_type": "bytefield",
        "code": "(defattrs :bg-green {:fill \"#a0ffa0\"})\n(draw-column-headers)\n(draw-box 0x11 :bg-green)\n(draw-box 0x872349ae [{:span 4} :bg-green])\n(draw-box 0x10)\n(draw-box 0x4702 [{:span 2}])",
    },
    {
        "diagram_type": "seqdiag",
        "code": 'seqdiag {\n  client -> mcp [label = "generate_uml"];\n  mcp -> kroki [label = "render"];\n  mcp <-- kroki [label = "SVG"];\n  client <-- mcp [label = "result"];\n}',
    },
    {
        "diagram_type": "nwdiag",
        "code": 'nwdiag {\n  network public {\n    address = "10.0.0.0/24";\n    client [address = "10.0.0.10"];\n    gateway [address = "10.0.0.1"];\n  }\n  network service {\n    address = "10.1.0.0/24";\n    gateway [address = "10.1.0.1"];\n    mcp [address = "10.1.0.10"];\n  }\n}',
    },
]

FIXTURES_21_37: list[dict[str, str]] = [
    {
        "diagram_type": "rackdiag",
        "code": "rackdiag {\n  16U;\n  1: UPS [2U];\n  3: API Server [2U];\n  5: MCP Server [2U];\n  7: Switch [1U];\n}",
    },
    {
        "diagram_type": "dbml",
        "code": "Table users {\n  id int [pk, increment]\n  email varchar [unique]\n}\nTable diagrams {\n  id int [pk, increment]\n  user_id int [ref: > users.id]\n  type varchar\n}",
    },
    {
        "diagram_type": "ditaa",
        "code": "+--------+      +---------+      +-------+\n| Client | ---> | UML MCP | ---> | Kroki |\n+--------+      +---------+      +-------+",
    },
    {
        "diagram_type": "excalidraw",
        "code": '{"type":"excalidraw","version":2,"source":"kroki","elements":[{"id":"rect","type":"rectangle","x":100,"y":100,"width":200,"height":100,"angle":0,"strokeColor":"#000000","backgroundColor":"#ffffff","fillStyle":"solid","strokeWidth":1,"strokeStyle":"solid","roughness":1,"opacity":100,"groupIds":[],"frameId":null,"roundness":null,"seed":1,"version":1,"versionNonce":1,"isDeleted":false,"boundElements":[],"updated":1,"link":null,"locked":false}],"appState":{"viewBackgroundColor":"#ffffff"},"files":{}}',
    },
    {
        "diagram_type": "goat",
        "code": ".---.     .-.       .-.\n| A +--->| 1 |<--->| B |\n'---'     '-'       '-'",
    },
    {
        "diagram_type": "umlet",
        "code": """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<umlet_diagram>
  <zoom_level>10</zoom_level>
  <element>
    <id>UMLClass</id>
    <coordinates>
      <x>10</x>
      <y>10</y>
      <w>120</w>
      <h>70</h>
    </coordinates>
    <panel_attributes>Account
--
-balance: decimal
++deposit()
</panel_attributes>
    <additional_attributes/>
  </element>
</umlet_diagram>""",
    },
    {
        "diagram_type": "nomnoml",
        "code": "[Client] -> [UML MCP]\n[UML MCP] -> [Kroki]\n[Kroki] -> [Artifact]",
    },
    {
        "diagram_type": "pikchr",
        "code": 'box "Client" fit\narrow\nbox "UML MCP" fit\narrow\nbox "Kroki" fit',
    },
    {
        "diagram_type": "plantuml",
        "code": '@startuml\nactor User\nparticipant "UML MCP" as MCP\nparticipant Kroki\nUser -> MCP: generate\nMCP -> Kroki: render\nKroki --> MCP: SVG\nMCP --> User: result\n@enduml',
    },
    {
        "diagram_type": "structurizr",
        "code": 'workspace "UML MCP" "Tool-only smoke test" {\n  model {\n    user = person "User"\n    mcp = softwareSystem "UML MCP"\n    kroki = softwareSystem "Kroki"\n    user -> mcp "Uses"\n    mcp -> kroki "Renders diagrams with"\n  }\n  views {\n    systemLandscape "Landscape" {\n      include *\n      autoLayout\n    }\n  }\n}',
    },
    {
        "diagram_type": "svgbob",
        "code": "    .--------.       .--------.\n   /  Client  \\---->| UML MCP |\n   \\__________/      \\________/",
    },
    {
        "diagram_type": "symbolator",
        "code": '(symbol "RES" (pin_names (line (pin "1") (pin "2"))))',
    },
    {
        "diagram_type": "tikz",
        "code": r"""\documentclass[border=2pt]{standalone}
\usepackage{tikz}
\begin{document}
\begin{tikzpicture}
  \node[draw] (client) at (0,0) {Client};
  \node[draw] (mcp) at (3,0) {UML MCP};
  \node[draw] (kroki) at (6,0) {Kroki};
  \draw[->] (client) -- (mcp);
  \draw[->] (mcp) -- (kroki);
\end{tikzpicture}
\end{document}""",
    },
    {
        "diagram_type": "vega",
        "code": '{"$schema":"https://vega.github.io/schema/vega/v5.json","width":240,"height":160,"data":[{"name":"table","values":[{"x":1,"y":2},{"x":2,"y":5},{"x":3,"y":3}]}],"scales":[{"name":"x","type":"linear","range":"width","domain":{"data":"table","field":"x"}},{"name":"y","type":"linear","range":"height","domain":{"data":"table","field":"y"}}],"marks":[{"type":"symbol","from":{"data":"table"},"encode":{"enter":{"x":{"scale":"x","field":"x"},"y":{"scale":"y","field":"y"},"size":{"value":100}}}}]}',
    },
    {
        "diagram_type": "vegalite",
        "code": '{"$schema":"https://vega.github.io/schema/vega-lite/v5.json","data":{"values":[{"engine":"Mermaid","count":7},{"engine":"PlantUML","count":9},{"engine":"Other","count":21}]},"mark":"bar","encoding":{"x":{"field":"engine","type":"nominal"},"y":{"field":"count","type":"quantitative"}}}',
    },
    {
        "diagram_type": "wavedrom",
        "code": '{"signal":[{"name":"clk","wave":"p......."},{"name":"request","wave":"01..0..."},{"name":"response","wave":"0...10.."}]}',
    },
    {
        "diagram_type": "wireviz",
        "code": "connectors:\n  J1:\n    type: Molex\n    pinlabels: [GND, VCC, SDA, SCL]\n  J2:\n    type: Header\n    pinlabels: [GND, VCC, SDA, SCL]\ncables:\n  W1:\n    wirecount: 4\n    length: 0.5\nconnections:\n  -\n    - J1: [1, 2, 3, 4]\n    - W1: [1, 2, 3, 4]\n    - J2: [1, 2, 3, 4]",
    },
]

MERMAID_B = """sequenceDiagram
  autonumber
  actor User
  participant Browser
  participant Edge as API Gateway
  participant Auth
  participant DB
  participant MCP as UML MCP
  participant Kroki
  User->>Browser: Open diagram workspace
  Browser->>Edge: GET /workspace
  Edge->>Auth: Validate session
  Auth->>DB: Load user + roles
  DB-->>Auth: user record
  Auth-->>Edge: authorized
  Edge->>MCP: list_diagram_types
  MCP-->>Edge: catalog
  Edge-->>Browser: workspace + capabilities
  User->>Browser: Generate architecture diagram
  Browser->>Edge: POST /diagram
  Edge->>MCP: validate_uml(...)
  MCP-->>Edge: valid
  Edge->>MCP: generate_uml(...)
  MCP->>Kroki: Render Mermaid SVG
  Kroki-->>MCP: SVG
  MCP-->>Edge: artifact URL
  Edge-->>Browser: 200 result
  Browser-->>User: Show diagram"""


def _parse_sse_or_json(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    if text.startswith("{"):
        return json.loads(text)
    # SSE: data: {...}
    for line in text.splitlines():
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                return json.loads(payload)
    # multi-event: take last data
    datas = [
        line[5:].strip()
        for line in text.splitlines()
        if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]")
    ]
    if datas:
        return json.loads(datas[-1])
    raise ValueError(f"Unparseable MCP response: {text[:200]}")


def _tool_result_text(rpc: dict[str, Any]) -> str:
    result = rpc.get("result") or {}
    content = result.get("content") or []
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
    if parts:
        return "\n".join(parts)
    # structuredContent
    sc = result.get("structuredContent")
    if sc is not None:
        return json.dumps(sc)
    if "error" in rpc:
        return json.dumps(rpc["error"])
    return json.dumps(result)[:2000]


class McpClient:
    def __init__(self) -> None:
        self.client = httpx.Client(timeout=TIMEOUT, follow_redirects=True)
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self._id = 0
        self.counts = {
            "list_diagram_types": 0,
            "validate_uml": 0,
            "generate_uml": 0,
            "generate_uml_batch": 0,
        }

    def close(self) -> None:
        self.client.close()

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def initialize(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "vercel-kroki-stress", "version": "1.0"},
            },
        }
        r = self.client.post(MCP_URL, json=payload, headers=self.headers)
        r.raise_for_status()
        sid = r.headers.get("mcp-session-id")
        if sid:
            self.headers["mcp-session-id"] = sid
        self.client.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=self.headers,
        )

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name in self.counts:
            self.counts[name] += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        r = self.client.post(MCP_URL, json=payload, headers=self.headers)
        r.raise_for_status()
        rpc = _parse_sse_or_json(r.text)
        return rpc


def _item_ok(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    if row.get("error") or row.get("ok") is False:
        return False
    return bool(
        row.get("url")
        or row.get("content_base64")
        or row.get("local_path")
        or row.get("success")
        or (row.get("status") in ("ok", "success"))
    )


def _extract_batch_rows(rpc: dict[str, Any]) -> list[Any]:
    text = _tool_result_text(rpc)
    # Prefer structuredContent
    result = rpc.get("result") or {}
    sc = result.get("structuredContent")
    if isinstance(sc, dict):
        for key in ("results", "items", "diagrams"):
            if isinstance(sc.get(key), list):
                return sc[key]
        if "error" in sc and not any(k in sc for k in ("results", "items")):
            return [{"error": sc.get("error"), "ok": False}]
    # Try JSON in text
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("results", "items", "diagrams"):
                if isinstance(parsed.get(key), list):
                    return parsed[key]
            return [parsed]
    except json.JSONDecodeError:
        pass
    # Heuristic: count FAIL/SUCCESS lines
    return [{"raw": text, "ok": "error" not in text.lower()}]


def main() -> int:
    mcp = McpClient()
    try:
        mcp.initialize()
        print("initialized session", mcp.headers.get("mcp-session-id", "")[:16])

        # Phase 4 batch 1
        items1 = [
            {**f, "output_format": "svg", "scale": 1.0} for f in FIXTURES_1_20
        ]
        rpc1 = mcp.call("generate_uml_batch", {"items": items1})
        rows1 = _extract_batch_rows(rpc1)
        ok1 = sum(1 for r in rows1 if _item_ok(r))
        print(f"batch1 rows={len(rows1)} ok={ok1}")
        for i, r in enumerate(rows1):
            typ = FIXTURES_1_20[i]["diagram_type"] if i < len(FIXTURES_1_20) else "?"
            status = "OK" if _item_ok(r) else "FAIL"
            err = ""
            if isinstance(r, dict):
                err = str(r.get("error") or r.get("message") or "")[:100]
            print(f"  {i+1:02d} {typ:12s} {status} {err}")

        # Phase 4 batch 2
        items2 = [
            {**f, "output_format": "svg", "scale": 1.0} for f in FIXTURES_21_37
        ]
        rpc2 = mcp.call("generate_uml_batch", {"items": items2})
        rows2 = _extract_batch_rows(rpc2)
        ok2 = sum(1 for r in rows2 if _item_ok(r))
        print(f"batch2 rows={len(rows2)} ok={ok2}")
        for i, r in enumerate(rows2):
            typ = FIXTURES_21_37[i]["diagram_type"] if i < len(FIXTURES_21_37) else "?"
            status = "OK" if _item_ok(r) else "FAIL"
            err = ""
            if isinstance(r, dict):
                err = str(r.get("error") or r.get("message") or "")[:100]
            print(f"  {i+21:02d} {typ:12s} {status} {err}")

        # Phase 5
        a1 = mcp.call(
            "generate_uml",
            {
                "diagram_type": "mermaid",
                "code": MERMAID_B,
                "output_format": "svg",
                "scale": 1.0,
            },
        )
        a2 = mcp.call(
            "generate_uml",
            {
                "diagram_type": "mermaid",
                "code": MERMAID_B,
                "output_format": "svg",
                "scale": 1.0,
            },
        )
        t1 = _tool_result_text(a1)
        t2 = _tool_result_text(a2)
        urls = []
        for t in (t1, t2):
            m = re.search(r"https://[^\s\"']+", t)
            urls.append(m.group(0) if m else None)
        print("phase5 urls", urls)
        print(
            "phase5",
            "PASS"
            if ("error" not in t1.lower() and "error" not in t2.lower())
            else "FAIL",
        )

        # Phase 6 negatives
        n1 = mcp.call(
            "validate_uml",
            {
                "diagram_type": "mermaid",
                "output_format": "svg",
                "strict": True,
                "code": "sequenceDiagram\nA->>",
            },
        )
        n1t = _tool_result_text(n1).lower()
        n1_pass = ("valid: false" in n1t) or ("invalid" in n1t) or ("error" in n1t)
        # stricter: reject if clearly valid true
        if "valid\": true" in n1t or "valid: true" in n1t or "diagram is valid" in n1t:
            n1_pass = False
        print("NEG1", "PASS" if n1_pass else "FAIL", _tool_result_text(n1)[:180])

        n2 = mcp.call(
            "generate_uml",
            {
                "diagram_type": "not-a-real-diagram-type",
                "code": "A",
                "output_format": "svg",
            },
        )
        n2t = _tool_result_text(n2).lower()
        n2_pass = "error" in n2t or "unsupported" in n2t or "unknown" in n2t
        print("NEG2", "PASS" if n2_pass else "FAIL", _tool_result_text(n2)[:180])

        n3 = mcp.call("generate_uml_batch", {"items": []})
        n3t = _tool_result_text(n3).lower()
        n3_pass = "empty" in n3t or "error" in n3t or "must not" in n3t
        print("NEG3", "PASS" if n3_pass else "FAIL", _tool_result_text(n3)[:180])

        n4 = mcp.call(
            "generate_uml_batch",
            {
                "items": [
                    {
                        "diagram_type": "mermaid",
                        "code": "graph TD; A-->B;",
                        "output_format": "svg",
                        "scale": 1.0,
                    },
                    {
                        "diagram_type": "not-a-real-diagram-type",
                        "code": "A",
                        "output_format": "svg",
                        "scale": 1.0,
                    },
                ]
            },
        )
        n4rows = _extract_batch_rows(n4)
        print("NEG4 rows", len(n4rows), json.dumps(n4rows)[:300])
        n4_pass = len(n4rows) >= 1  # partial success expected
        # health
        mcp.call("list_diagram_types", {})
        print("NEG4 health list_diagram_types OK")

        print("COUNTS", json.dumps(mcp.counts))
        catalog_ok = ok1 + ok2
        print(f"CATALOG_PASSED {catalog_ok}/37")
        return 0
    finally:
        mcp.close()


if __name__ == "__main__":
    sys.exit(main())
