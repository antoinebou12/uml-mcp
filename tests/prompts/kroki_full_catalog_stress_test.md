# Tool-only Kroki full-catalog MCP smoke/stress test

Use this prompt in a ChatGPT conversation where the UML MCP app exposes these tools:

- `list_diagram_types`
- `validate_uml`
- `generate_uml`
- `generate_uml_batch`
- `generate_uml_image` (optional visual spot-check; not counted in the 28-call baseline)

Endpoint used by the project:

`https://uml-mcp.vercel.app/mcp`

This test is intentionally **tool-only**. It does not require MCP resource reads such as `uml://examples`.

## Execution rule

Copy and paste the prompt below into the MCP-enabled conversation. The assistant must execute it immediately with the tools that are available.

```text
EXECUTE THIS TEST NOW.

Use only these connected UML MCP tools:
- list_diagram_types
- validate_uml
- generate_uml
- generate_uml_batch
- generate_uml_image (optional spot-check only; do not count toward the 28-call baseline)

Do NOT require or attempt to read MCP resources such as uml://types, uml://examples, uml://templates, uml://formats, or uml://capabilities.
Do NOT stop and ask me to paste outputs.
Do NOT ask me which resources are available.
Do NOT explain that the test is too large.
Do NOT render diagrams locally or substitute built-in diagram rendering.
If a tool call fails, record the failure, continue when safe, and include it in the final report.

The purpose is to execute a real end-to-end UML MCP smoke/stress test in this conversation using only the four required tools (plus optional generate_uml_image).

PHASE 1 - TOOL DISCOVERY AND CATALOG

1. Call list_diagram_types now.
2. Confirm the returned catalog contains these 37 expected diagram_type values:

class, sequence, activity, usecase, state, component, deployment, object,
mermaid, d2, graphviz, erd, blockdiag, packetdiag, bpmn, c4plantuml,
actdiag, bytefield, seqdiag, nwdiag, rackdiag, dbml, ditaa, excalidraw,
goat, umlet, nomnoml, pikchr, plantuml, structurizr, svgbob, symbolator, tikz, vega,
vegalite, wavedrom, wireviz.

3. Record each type's backend and supported output formats from list_diagram_types.
4. If an expected type is missing, record it but continue. The final result must be FAIL.
5. If extra live types exist, report them as catalog drift. They are informational and do not block execution of the fixed 37-type test.

PHASE 2 - COMPLEX MERMAID SMOKE TESTS

For each Mermaid case below:
- call validate_uml with diagram_type="mermaid", output_format="svg", strict=true;
- if validation succeeds, include it in one generate_uml_batch call;
- if validation fails, record the validation error and continue with the other cases.

MERMAID A - distributed architecture

flowchart LR
  subgraph Client[Client Layer]
    Web[Web App]
    Mobile[Mobile App]
  end
  subgraph Edge[Edge Layer]
    CDN[CDN]
    WAF[WAF]
    Gateway[API Gateway]
  end
  subgraph Services[Service Mesh]
    Auth[Auth Service]
    Diagram[Diagram Service]
    Billing[Billing Service]
    Worker[Async Worker]
  end
  subgraph Data[Data Layer]
    PG[(PostgreSQL)]
    Redis[(Redis)]
    Queue[(Queue)]
  end
  subgraph External[External Systems]
    Kroki[Kroki]
    OAuth[OAuth Provider]
  end
  Web --> CDN
  Mobile --> CDN
  CDN --> WAF --> Gateway
  Gateway --> Auth
  Gateway --> Diagram
  Gateway --> Billing
  Auth --> OAuth
  Auth --> Redis
  Auth --> PG
  Diagram --> Kroki
  Diagram --> Queue
  Queue --> Worker
  Worker --> PG
  Billing --> PG
  Redis -. cache .-> Gateway

MERMAID B - concurrent OAuth and render sequence

sequenceDiagram
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
  par Authenticate
    Edge->>Auth: Validate session
    Auth->>DB: Load user + roles
    DB-->>Auth: user record
    Auth-->>Edge: authorized
  and Discover
    Edge->>MCP: list_diagram_types
    MCP-->>Edge: catalog
  end
  Edge-->>Browser: workspace + capabilities
  User->>Browser: Generate architecture diagram
  Browser->>Edge: POST /diagram
  Edge->>MCP: validate_uml(...)
  MCP-->>Edge: valid
  Edge->>MCP: generate_uml(...)
  MCP->>Kroki: Render Mermaid SVG
  alt Render succeeds
    Kroki-->>MCP: SVG
    MCP-->>Edge: artifact URL
    Edge-->>Browser: 200 result
    Browser-->>User: Show diagram
  else Render fails
    Kroki-->>MCP: error
    MCP-->>Edge: structured error
    Edge-->>Browser: 502
  end

MERMAID C - class model

classDiagram
  class MCPServer {
    +String name
    +String version
    +listTools()
    +callTool(name,args)
  }
  class DiagramService {
    +validate(request)
    +render(request)
  }
  class KrokiClient {
    +String baseUrl
    +render(type,format,code)
  }
  class CachePolicy {
    +int ttlSeconds
    +String scope
  }
  class DiagramRequest {
    +String diagramType
    +String outputFormat
    +String code
    +float scale
  }
  MCPServer --> DiagramService
  DiagramService --> KrokiClient
  DiagramService --> DiagramRequest
  MCPServer --> CachePolicy

MERMAID D - state machine

stateDiagram-v2
  [*] --> Disconnected
  Disconnected --> Discovering: connect
  Discovering --> Ready: tools discovered
  Discovering --> Failed: protocol error
  Ready --> Validating: validate_uml
  Validating --> Rendering: valid
  Validating --> Ready: invalid source
  Rendering --> Ready: artifact returned
  Rendering --> Failed: backend error
  Failed --> Discovering: retry
  Ready --> Disconnected: close

MERMAID E - ER model

erDiagram
  USER ||--o{ SESSION : owns
  USER ||--o{ DIAGRAM : creates
  DIAGRAM ||--o{ RENDER : has
  DIAGRAM }o--|| DIAGRAM_TYPE : uses
  RENDER }o--|| BACKEND : rendered_by
  USER {
    uuid id PK
    string email UK
    string display_name
  }
  SESSION {
    uuid id PK
    uuid user_id FK
    datetime expires_at
  }
  DIAGRAM {
    uuid id PK
    uuid user_id FK
    string source_hash
    string type
  }
  RENDER {
    uuid id PK
    uuid diagram_id FK
    string format
    string artifact_url
  }
  DIAGRAM_TYPE {
    string name PK
    string backend
  }
  BACKEND {
    string name PK
    string endpoint
  }

MERMAID F - Gantt

gantt
  title MCP 2026 migration and verification
  dateFormat YYYY-MM-DD
  axisFormat %b %d
  section Runtime
  Upgrade MCP SDK          :done, sdk, 2026-07-28, 2d
  Upgrade FastMCP          :done, fastmcp, after sdk, 3d
  Stateless transport      :done, stateless, after fastmcp, 2d
  section Verification
  Unit regression tests    :done, tests, after stateless, 2d
  Conformance suite        :active, conf, after tests, 3d
  Full Kroki stress test   :crit, stress, after conf, 3d
  section Release
  Vercel verification      :vercel, after stress, 2d
  Merge                    :milestone, merge, after vercel, 0d

MERMAID G - mind map

mindmap
  root((UML MCP))
    Protocol
      MCP 2026-07-28
      Stateless HTTP
      Cache hints
    Tools
      list_diagram_types
      validate_uml
      generate_uml
      generate_uml_batch
    Rendering
      Mermaid
      PlantUML
      Kroki catalog
    Verification
      batches
      artifacts
      negative tests

After validation, call generate_uml_batch exactly once for every Mermaid case that passed validation.
Use output_format="svg" and scale=1.0.
Record one result row per case.
On hosted Vercel, Mermaid-heavy batches may partially time out when falling back to mermaid.ink.
If any Mermaid batch item fails, recover with solo generate_uml for that case and mark the extra generate_uml calls as EXPLAIN in the tool-call ledger (expected baseline remains 3 unless recoveries are needed).

PHASE 3 - COMPLEX PLANTUML FAMILY SMOKE TESTS

For each case below:
- call validate_uml using the specified diagram_type, output_format="svg", strict=true;
- include every validation-success case in one generate_uml_batch call;
- record validation or render errors per case instead of stopping the test.

PLANTUML A
diagram_type=class

@startuml
skinparam classAttributeIconSize 0
package "MCP Runtime" {
  class MCPServer {
    +name: String
    +version: String
    +listTools(): Tool[]
    +callTool(name, args): Result
  }
  class CachePolicy {
    +ttlSeconds: int
    +scope: String
  }
}
package "Diagram Domain" {
  class DiagramService {
    +validate(request): ValidationResult
    +render(request): DiagramResult
  }
  class DiagramRequest {
    +diagramType: String
    +outputFormat: String
    +code: String
    +scale: float
  }
  interface Renderer {
    +render(request): DiagramResult
  }
  class KrokiRenderer
}
MCPServer *-- CachePolicy
MCPServer --> DiagramService
DiagramService --> DiagramRequest
DiagramService --> Renderer
Renderer <|.. KrokiRenderer
@enduml

PLANTUML B
diagram_type=sequence

@startuml
autonumber
actor User
participant ChatGPT
participant "UML MCP" as MCP
participant "Diagram Service" as DS
participant Kroki
database Cache
User -> ChatGPT: Generate architecture diagram
ChatGPT -> MCP: list_diagram_types
MCP --> ChatGPT: capabilities
ChatGPT -> MCP: validate_uml(source)
MCP -> DS: validate
DS --> MCP: valid
MCP --> ChatGPT: valid
ChatGPT -> MCP: generate_uml(source)
MCP -> DS: render
DS -> Cache: lookup(source hash)
alt cache hit
  Cache --> DS: artifact
else cache miss
  DS -> Kroki: POST/render
  Kroki --> DS: SVG
  DS -> Cache: store artifact metadata
end
DS --> MCP: diagram result
MCP --> ChatGPT: URL/artifact
ChatGPT --> User: Show result
@enduml

PLANTUML C
diagram_type=activity

@startuml
start
:Receive MCP tool request;
:Validate schema;
if (Request valid?) then (yes)
  :Resolve diagram backend;
  fork
    :Validate source syntax;
  fork again
    :Resolve output format;
  fork again
    :Apply runtime policy;
  end fork
  if (All checks pass?) then (yes)
    :Render through Kroki;
    if (Backend success?) then (yes)
      :Return artifact metadata;
    else (no)
      :Return structured render error;
    endif
  else (no)
    :Return validation error;
  endif
else (no)
  :Return schema error;
endif
stop
@enduml

PLANTUML D
diagram_type=usecase

@startuml
left to right direction
actor Developer
actor "ChatGPT Client" as Client
actor Maintainer
rectangle "UML MCP" {
  usecase "Discover diagram types" as UC1
  usecase "Validate diagram" as UC2
  usecase "Render one diagram" as UC3
  usecase "Render batch" as UC4
  usecase "Run conformance suite" as UC5
}
Developer --> UC1
Developer --> UC2
Client --> UC1
Client --> UC2
Client --> UC3
Client --> UC4
Maintainer --> UC5
UC3 .> UC2 : <<include>>
UC4 .> UC2 : <<include>>
@enduml

PLANTUML E
diagram_type=state

@startuml
[*] --> Offline
Offline --> Discovering : connect
Discovering --> Ready : discovery complete
Discovering --> Error : protocol failure
Ready --> Validating : validate_uml
Validating --> Ready : invalid
Validating --> Rendering : valid
Rendering --> Ready : artifact returned
Rendering --> Error : backend failure
Error --> Discovering : retry
Ready --> Offline : disconnect
state Rendering {
  [*] --> ResolveBackend
  ResolveBackend --> BuildRequest
  BuildRequest --> CallKroki
  CallKroki --> [*]
}
@enduml

PLANTUML F
diagram_type=component

@startuml
package "Client" {
  [ChatGPT]
  [MCP Adapter]
}
package "UML MCP" {
  [FastMCP Server]
  [Tool Registry]
  [Diagram Service]
}
package "External" {
  [Kroki API]
}
database "Metadata Cache" as Cache
[ChatGPT] --> [MCP Adapter]
[MCP Adapter] --> [FastMCP Server] : MCP 2026 HTTP
[FastMCP Server] --> [Tool Registry]
[Tool Registry] --> [Diagram Service]
[Diagram Service] --> [Kroki API] : render
[Diagram Service] --> Cache
@enduml

PLANTUML G
diagram_type=deployment

@startuml
node "Developer Device" as dev {
  artifact "ChatGPT Client"
}
cloud "Vercel" as vercel {
  node "Python Function" as fn {
    artifact "FastAPI"
    artifact "FastMCP 4"
  }
}
cloud "Kroki Public Service" as kroki
node "GitHub" as github {
  artifact "Repository"
  artifact "Actions"
}
dev --> fn : HTTPS /mcp
fn --> kroki : diagram render
fn --> github : deployment status
github --> fn : deployment trigger
@enduml

PLANTUML H
diagram_type=object

@startuml
object server {
  name = "uml_mcp"
  version = "1.3.0"
  stateless = true
}
object cachePolicy {
  ttlSeconds = 300
  scope = "public"
}
object request {
  diagramType = "mermaid"
  outputFormat = "svg"
  scale = 1.0
}
object result {
  success = true
  artifact = "kroki-url"
}
server --> cachePolicy : configured with
server --> request : receives
request --> result : produces
@enduml

PLANTUML I
diagram_type=plantuml

@startmindmap
* UML MCP full stress test
** MCP protocol
*** 2026-07-28
*** stateless HTTP
*** cache hints
** Discovery
*** tools
*** diagram catalog
** Rendering
*** Mermaid
*** PlantUML
*** 37 catalog types
** Verification
*** validation
*** batches
*** artifacts
*** negative cases
@endmindmap

After validation, call generate_uml_batch exactly once for every PlantUML-family case that passed validation.
Use output_format="svg" and scale=1.0.

PHASE 4 - TOOL-ONLY FULL 37-TYPE CATALOG SWEEP

Do not read any MCP resources for this phase.

Use list_diagram_types from Phase 1 to choose each output format:
- use "svg" if supported;
- otherwise use the first supported format returned by list_diagram_types.

Use these embedded fixtures exactly as the source inputs.

1. class
@startuml
class Account
class Customer
Customer "1" --> "*" Account : owns
@enduml

2. sequence
@startuml
participant Client
participant API
participant DB
Client -> API: GET /resource
API -> DB: query
DB --> API: result
API --> Client: 200
@enduml

3. activity
@startuml
start
:Receive order;
if (Valid?) then (yes)
  :Process order;
else (no)
  :Reject order;
endif
stop
@enduml

4. usecase
@startuml
left to right direction
actor User
rectangle System {
  usecase (View diagram)
  usecase (Generate diagram)
}
User --> (View diagram)
User --> (Generate diagram)
@enduml

5. state
@startuml
[*] --> Idle
Idle --> Running: start
Running --> Idle: stop
@enduml

6. component
@startuml
component [Web]
component [API]
database DB
[Web] --> [API]
[API] --> DB
@enduml

7. deployment
@startuml
node "App Server" {
  artifact "app"
}
node "Database Server" {
  database "PostgreSQL"
}
"App Server" --> "Database Server"
@enduml

8. object
@startuml
object user
object request
object result
user --> request
request --> result
@enduml

9. mermaid
flowchart LR
  Client --> MCP
  MCP --> Kroki
  Kroki --> MCP
  MCP --> Client

10. d2
User -> API: HTTP Request
API -> Database: Query
Database -> API: Result
API -> User: JSON Response

11. graphviz
digraph G {
  rankdir=LR;
  Client -> API [label="request"];
  API -> DB [label="query"];
  DB -> API [label="result"];
  API -> Client [label="response"];
}

12. erd
[Person]
*name
height
--
[Order]
*id
date
Person *-- Order

13. blockdiag
blockdiag {
  Client -> API -> Database;
  Database -> API -> Client;
}

14. packetdiag
packetdiag {
  colwidth = 32;
  0-15: Source Port;
  16-31: Destination Port;
  32-63: Sequence Number;
  64-95: Acknowledgment Number;
}

15. bpmn
<?xml version="1.0" encoding="UTF-8"?>
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
</bpmn:definitions>

16. c4plantuml
!include <C4/C4_Context>
title UML MCP Context
Person(user, "User")
System(mcp, "UML MCP")
System_Ext(kroki, "Kroki")
Rel(user, mcp, "Generates diagrams")
Rel(mcp, kroki, "Renders")

17. actdiag
actdiag {
  write -> validate -> render -> result
  lane user {
    label = "Client"
    write [label = "Write source"];
    result [label = "Receive result"];
  }
  lane server {
    label = "UML MCP"
    validate [label = "Validate"];
    render [label = "Render"];
  }
}

18. bytefield
(defattrs :bg-green {:fill "#a0ffa0"})
(draw-column-headers)
(draw-box 0x11 :bg-green)
(draw-box 0x872349ae [{:span 4} :bg-green])
(draw-box 0x10)
(draw-box 0x4702 [{:span 2}])

19. seqdiag
seqdiag {
  client -> mcp [label = "generate_uml"];
  mcp -> kroki [label = "render"];
  mcp <-- kroki [label = "SVG"];
  client <-- mcp [label = "result"];
}

20. nwdiag
nwdiag {
  network public {
    address = "10.0.0.0/24";
    client [address = "10.0.0.10"];
    gateway [address = "10.0.0.1"];
  }
  network service {
    address = "10.1.0.0/24";
    gateway [address = "10.1.0.1"];
    mcp [address = "10.1.0.10"];
  }
}

21. rackdiag
rackdiag {
  16U;
  1: UPS [2U];
  3: API Server [2U];
  5: MCP Server [2U];
  7: Switch [1U];
}

22. dbml
Table users {
  id int [pk, increment]
  email varchar [unique]
}
Table diagrams {
  id int [pk, increment]
  user_id int [ref: > users.id]
  type varchar
}

23. ditaa
+--------+      +---------+      +-------+
| Client | ---> | UML MCP | ---> | Kroki |
+--------+      +---------+      +-------+

24. excalidraw
{"type":"excalidraw","version":2,"source":"kroki","elements":[{"id":"rect","type":"rectangle","x":100,"y":100,"width":200,"height":100,"angle":0,"strokeColor":"#000000","backgroundColor":"#ffffff","fillStyle":"solid","strokeWidth":1,"strokeStyle":"solid","roughness":1,"opacity":100,"groupIds":[],"frameId":null,"roundness":null,"seed":1,"version":1,"versionNonce":1,"isDeleted":false,"boundElements":[],"updated":1,"link":null,"locked":false}],"appState":{"viewBackgroundColor":"#ffffff"},"files":{}}

25. goat
.---.     .-.       .-.
| A +--->| 1 |<--->| B |
'---'     '-'       '-'

26. umlet
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
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
</umlet_diagram>

27. nomnoml
[Client] -> [UML MCP]
[UML MCP] -> [Kroki]
[Kroki] -> [Artifact]

28. pikchr
box "Client" fit
arrow
box "UML MCP" fit
arrow
box "Kroki" fit

29. plantuml
@startuml
actor User
participant "UML MCP" as MCP
participant Kroki
User -> MCP: generate
MCP -> Kroki: render
Kroki --> MCP: SVG
MCP --> User: result
@enduml

30. structurizr
workspace "UML MCP" "Tool-only smoke test" {
  model {
    user = person "User"
    mcp = softwareSystem "UML MCP"
    kroki = softwareSystem "Kroki"
    user -> mcp "Uses"
    mcp -> kroki "Renders diagrams with"
  }
  views {
    systemLandscape "Landscape" {
      include *
      autoLayout
    }
  }
}

31. svgbob
    .--------.       .--------.
   /  Client  \---->| UML MCP |
   \__________/      \________/

32. symbolator
(symbol "RES" (pin_names (line (pin "1") (pin "2"))))

33. tikz
\documentclass[border=2pt]{standalone}
\usepackage{tikz}
\begin{document}
\begin{tikzpicture}
  \node[draw] (client) at (0,0) {Client};
  \node[draw] (mcp) at (3,0) {UML MCP};
  \node[draw] (kroki) at (6,0) {Kroki};
  \draw[->] (client) -- (mcp);
  \draw[->] (mcp) -- (kroki);
\end{tikzpicture}
\end{document}

34. vega
{"$schema":"https://vega.github.io/schema/vega/v5.json","width":240,"height":160,"data":[{"name":"table","values":[{"x":1,"y":2},{"x":2,"y":5},{"x":3,"y":3}]}],"scales":[{"name":"x","type":"linear","range":"width","domain":{"data":"table","field":"x"}},{"name":"y","type":"linear","range":"height","domain":{"data":"table","field":"y"}}],"marks":[{"type":"symbol","from":{"data":"table"},"encode":{"enter":{"x":{"scale":"x","field":"x"},"y":{"scale":"y","field":"y"},"size":{"value":100}}}}]}

35. vegalite
{"$schema":"https://vega.github.io/schema/vega-lite/v5.json","data":{"values":[{"engine":"Mermaid","count":7},{"engine":"PlantUML","count":9},{"engine":"Other","count":21}]},"mark":"bar","encoding":{"x":{"field":"engine","type":"nominal"},"y":{"field":"count","type":"quantitative"}}}

36. wavedrom
{"signal":[{"name":"clk","wave":"p......."},{"name":"request","wave":"01..0..."},{"name":"response","wave":"0...10.."}]}

37. wireviz
connectors:
  J1:
    type: Molex
    pinlabels: [GND, VCC, SDA, SCL]
  J2:
    type: Header
    pinlabels: [GND, VCC, SDA, SCL]
cables:
  W1:
    wirecount: 4
    length: 0.5
connections:
  -
    - J1: [1, 2, 3, 4]
    - W1: [1, 2, 3, 4]
    - J2: [1, 2, 3, 4]

Build exactly two generate_uml_batch calls from those fixtures:
- batch 1 = fixtures 1 through 20
- batch 2 = fixtures 21 through 37

Every item must include:
- diagram_type
- code
- output_format selected from live list_diagram_types
- scale=1.0

Do not silently omit a fixture. If one fixture fails, preserve the other batch results and record the individual error.

PHASE 5 - STATELESS REPEATABILITY

Use MERMAID B from Phase 2.

Call generate_uml twice with identical arguments:
- diagram_type="mermaid"
- output_format="svg"
- scale=1.0
- identical source code

Both calls must independently succeed.
Record whether the two returned URLs/artifacts are identical or different.
Either is acceptable; both calls must return successful artifacts.

PHASE 6 - NEGATIVE TESTS

Run all four negative tests.

NEGATIVE 1
Call validate_uml with:
- diagram_type="mermaid"
- output_format="svg"
- strict=true
- code="sequenceDiagram\nA->>"

Expected: controlled validation failure or invalid result.

NEGATIVE 2
Call generate_uml with:
- diagram_type="not-a-real-diagram-type"
- code="A"
- output_format="svg"

Expected: controlled error.

NEGATIVE 3
Call generate_uml_batch with:
- items=[]

Expected: controlled error containing or equivalent to "items must not be empty".

NEGATIVE 4
Call generate_uml_batch with exactly two items:
- one valid Mermaid item: graph TD; A-->B;
- one invalid diagram_type: not-a-real-diagram-type

Expected:
- valid item succeeds;
- invalid item has a per-index error;
- the batch call itself remains usable;
- after this call, call list_diagram_types one more time to prove the MCP connection is still healthy.

PHASE 7 - FINAL REPORT

Do not ask me for any additional input.

Return:
1. the exact MCP tools called;
2. catalog count and missing/extra types;
3. Mermaid results: passed/7;
4. PlantUML-family results: passed/9;
5. full catalog results: passed/37;
6. stateless repeatability: PASS/FAIL;
7. negative tests: passed/4;
8. total generate_uml calls;
9. total generate_uml_batch calls;
10. a table for all 37 catalog fixtures with:
   - diagram_type
   - backend
   - output_format
   - render status
   - artifact returned yes/no
   - short error if any

Overall PASS requires:
- all four MCP tools are available;
- all expected 37 types are discovered;
- all 7 Mermaid cases render;
- all 9 PlantUML-family cases render;
- all 37 catalog fixtures render;
- both stateless repeat renders succeed;
- all four negative tests behave safely;
- no diagram was locally fabricated;
- no MCP resource was required to complete the test.

Finish with exactly one line:

MCP_KROKI_TOOL_ONLY_STRESS_TEST: PASS

or

MCP_KROKI_TOOL_ONLY_STRESS_TEST: FAIL - <short reason>
```

## Why this version exists

Some ChatGPT MCP surfaces expose tools but do not expose arbitrary MCP resource reads to the assistant. This fixture deliberately treats the four UML tools as the complete execution surface and embeds the full catalog fixtures directly, so a client can run the test immediately instead of stopping on `uml://*` resource access.
