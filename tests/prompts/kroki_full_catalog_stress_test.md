# Kroki full-catalog MCP stress-test prompt

Use this prompt after connecting the UML MCP server at:

`https://uml-mcp.vercel.app/mcp`

This is intentionally much stricter than the basic smoke test. It verifies MCP tool discovery, MCP resources, catalog completeness, complex Mermaid rendering, complex PlantUML rendering, all currently exposed Kroki-backed diagram types, batching, stateless repeatability, validation failures, and returned artifacts.

## Expected catalog

The server currently exposes these 35 `diagram_type` values:

`class`, `sequence`, `activity`, `usecase`, `state`, `component`, `deployment`, `object`, `mermaid`, `d2`, `graphviz`, `erd`, `blockdiag`, `packetdiag`, `bpmn`, `c4plantuml`, `actdiag`, `bytefield`, `seqdiag`, `nwdiag`, `rackdiag`, `dbml`, `ditaa`, `excalidraw`, `nomnoml`, `pikchr`, `plantuml`, `structurizr`, `svgbob`, `symbolator`, `tikz`, `vega`, `vegalite`, `wavedrom`, `wireviz`.

If the live server exposes additional types, report them as catalog drift and test them too when `uml://examples` provides a non-empty example. If any expected type is missing, the test fails.

## Full stress-test prompt

Copy and paste the following into an MCP-enabled ChatGPT conversation:

```text
Use only the connected UML MCP server for every diagram operation in this test. Do not render diagrams yourself, do not substitute built-in diagram knowledge for MCP tool calls, and do not claim success unless a real MCP result is returned.

This is a multi-phase conformance/stress test. Keep a running result table and do not stop after the first successful diagram.

PHASE 1 - DISCOVERY AND MCP RESOURCES

1. Discover the available UML MCP tools and confirm these are callable:
   - list_diagram_types
   - validate_uml
   - generate_uml
   - generate_uml_batch

2. Read these MCP resources when the client supports MCP resources:
   - uml://types
   - uml://formats
   - uml://examples
   - uml://capabilities
   - uml://server-info

3. Call list_diagram_types as well, even if uml://types was readable.

4. Confirm that the live catalog contains at least these 35 diagram_type values:
   class, sequence, activity, usecase, state, component, deployment, object,
   mermaid, d2, graphviz, erd, blockdiag, packetdiag, bpmn, c4plantuml,
   actdiag, bytefield, seqdiag, nwdiag, rackdiag, dbml, ditaa, excalidraw,
   nomnoml, pikchr, plantuml, structurizr, svgbob, symbolator, tikz, vega,
   vegalite, wavedrom, wireviz.

5. If an expected type is missing, record it and continue the rest of the test, but the final result must be FAIL.

PHASE 2 - SUPER-COMPLEX MERMAID

Validate and render every Mermaid case below as SVG. Use validate_uml before generate_uml or generate_uml_batch. All cases must be rendered by the MCP server.

MERMAID CASE A - distributed architecture flowchart

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

MERMAID CASE B - concurrent OAuth and diagram-render sequence

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
  and Warm metadata
    Edge->>MCP: list_diagram_types
    MCP-->>Edge: catalog
  end
  Edge-->>Browser: workspace + capabilities
  User->>Browser: Generate architecture diagram
  Browser->>Edge: POST /diagram
  Edge->>MCP: validate_uml(...)
  MCP-->>Edge: valid
  Edge->>MCP: generate_uml(...)
  MCP->>Kroki: render Mermaid SVG
  alt Render succeeds
    Kroki-->>MCP: SVG
    MCP-->>Edge: URL/artifact
    Edge-->>Browser: 200 result
    Browser-->>User: Show diagram
  else Render fails
    Kroki-->>MCP: error
    MCP-->>Edge: structured error
    Edge-->>Browser: 502 render failure
  end

MERMAID CASE C - class model

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

MERMAID CASE D - state machine

stateDiagram-v2
  [*] --> Disconnected
  Disconnected --> Discovering: connect
  Discovering --> Ready: tools/resources discovered
  Discovering --> Failed: handshake error
  Ready --> Validating: validate_uml
  Validating --> Rendering: valid
  Validating --> Ready: invalid source
  Rendering --> Ready: result returned
  Rendering --> Failed: backend error
  Failed --> Discovering: retry
  Ready --> Disconnected: close

MERMAID CASE E - ER diagram

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

MERMAID CASE F - Gantt

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

MERMAID CASE G - mind map

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
    Resources
      types
      examples
      formats
      capabilities
    Backends
      Mermaid
      PlantUML
      Kroki catalog

Render all seven Mermaid cases. Prefer one generate_uml_batch call for the seven render operations after validation. Record success, returned format, and whether each result contains a usable artifact URL or returned payload.

PHASE 3 - SUPER-COMPLEX PLANTUML FAMILY

Validate and render these PlantUML-backed cases as SVG. Use the diagram_type shown for each case.

PLANTUML CASE A - class
Diagram type: class

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

PLANTUML CASE B - sequence
Diagram type: sequence

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

PLANTUML CASE C - activity
Diagram type: activity

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

PLANTUML CASE D - usecase
Diagram type: usecase

@startuml
left to right direction
actor Developer
actor "ChatGPT Client" as Client
actor Maintainer
rectangle "UML MCP" {
  usecase "Discover diagram types" as UC1
  usecase "Read examples/resources" as UC2
  usecase "Validate diagram" as UC3
  usecase "Render one diagram" as UC4
  usecase "Render batch" as UC5
  usecase "Run conformance suite" as UC6
}
Developer --> UC1
Developer --> UC2
Developer --> UC3
Client --> UC1
Client --> UC3
Client --> UC4
Client --> UC5
Maintainer --> UC6
UC4 .> UC3 : <<include>>
UC5 .> UC3 : <<include>>
@enduml

PLANTUML CASE E - state
Diagram type: state

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

PLANTUML CASE F - component
Diagram type: component

@startuml
package "Client" {
  [ChatGPT]
  [MCP Adapter]
}
package "UML MCP" {
  [FastMCP Server]
  [Tool Registry]
  [Resource Registry]
  [Diagram Service]
}
package "External" {
  [Kroki API]
}
database "Metadata Cache" as Cache
[ChatGPT] --> [MCP Adapter]
[MCP Adapter] --> [FastMCP Server] : MCP 2026 HTTP
[FastMCP Server] --> [Tool Registry]
[FastMCP Server] --> [Resource Registry]
[Tool Registry] --> [Diagram Service]
[Diagram Service] --> [Kroki API] : render
[Diagram Service] --> Cache
@enduml

PLANTUML CASE G - deployment
Diagram type: deployment

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
fn --> github : metadata/status
github --> fn : deployment trigger
@enduml

PLANTUML CASE H - object
Diagram type: object

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

PLANTUML CASE I - raw PlantUML mind map
Diagram type: plantuml

@startmindmap
* UML MCP full stress test
** MCP protocol
*** 2026-07-28
*** stateless HTTP
*** cache hints
** Discovery
*** tools
*** resources
*** diagram catalog
** Rendering
*** Mermaid
*** PlantUML
*** 35 catalog types
** Verification
*** validation
*** batches
*** artifacts
*** negative cases
@endmindmap

Render all nine PlantUML-family cases. Prefer a single generate_uml_batch call after validation. Record success and artifact information for each case.

PHASE 4 - FULL 35-TYPE CATALOG SWEEP

1. Use the live list_diagram_types result as the source of truth for backend and supported formats.
2. Read uml://examples. If resources are unavailable in the client, report that limitation and use uml://templates if available. If neither resource can be read, this phase fails because the test must not invent 35 backend-specific fixtures silently.
3. For every expected diagram type, obtain its non-empty example from uml://examples. If an example is empty, use the matching non-empty template from uml://templates and mark that row as TEMPLATE_FALLBACK.
4. Choose output_format = svg whenever the live catalog says svg is supported. Otherwise use the first supported format reported for that type.
5. Build exactly two generate_uml_batch calls because the server batch limit is 20:
   - batch 1: first 20 catalog entries
   - batch 2: remaining 15 catalog entries
6. Do not omit difficult formats such as bpmn, bytefield, excalidraw, symbolator, tikz, vega, vegalite, wavedrom, or wireviz.
7. For every result, verify all of the following:
   - the batch returned an entry for the requested index;
   - the entry did not contain an error;
   - a usable URL, content/result payload, saved artifact, or other explicit successful render artifact was returned;
   - the returned artifact corresponds to the requested diagram type and output format as far as the response metadata allows.
8. If the live server exposes additional catalog types beyond the expected 35 and uml://examples contains a non-empty example for them, render those too in one or more additional batches of at most 20 items.

PHASE 5 - STATELESS REPEATABILITY

1. Pick the complex Mermaid sequence case from Phase 2.
2. Call generate_uml twice with identical arguments.
3. Both calls must succeed independently without relying on a prior session-specific server state.
4. If URL generation is deterministic, note whether the URLs are identical. Different successful artifacts are acceptable, but both calls must independently return a valid result.

PHASE 6 - NEGATIVE TESTS

Run these and confirm they fail safely without breaking the MCP connection:

1. validate_uml with diagram_type=mermaid and malformed source `sequenceDiagram\nA->>`.
2. generate_uml with an invalid diagram_type such as `not-a-real-diagram-type`.
3. generate_uml_batch with an empty items array.
4. If safe to do so, send one mixed batch containing one valid Mermaid item and one invalid item and verify the valid result is preserved while the invalid item reports its own error.

PHASE 7 - FINAL REPORT

Return a compact table with one row per catalog diagram type and these columns:

- diagram_type
- backend
- source (EXAMPLE or TEMPLATE_FALLBACK)
- output_format
- render status
- artifact returned (yes/no)
- short error if any

Then report these aggregate counters:

- expected catalog types
- discovered catalog types
- catalog types rendered successfully
- catalog types failed
- complex Mermaid cases passed / total
- complex PlantUML-family cases passed / total
- negative tests passed / total
- MCP resources successfully read
- total generate_uml calls
- total generate_uml_batch calls

The overall result is PASS only if:

- all expected 35 diagram types are discovered;
- all 35 expected types render successfully;
- all 7 complex Mermaid cases render successfully;
- all 9 complex PlantUML-family cases render successfully;
- stateless repeatability succeeds twice;
- all negative tests fail safely as expected;
- no diagram is fabricated locally by the client.

Finish with exactly one of these lines:

MCP_KROKI_FULL_STRESS_TEST: PASS
MCP_KROKI_FULL_STRESS_TEST: FAIL - <short reason>
```

## What this test covers

- MCP 2026 tool discovery and real tool invocation.
- MCP resource discovery/read behavior.
- The server's complete 35-type diagram catalog.
- All eight PlantUML aliases plus raw PlantUML.
- Multiple complex Mermaid grammars instead of a single trivial sequence diagram.
- `generate_uml_batch` behavior across the server's 20-item batch limit.
- Dynamic use of `uml://examples` and `uml://templates` so every backend uses server-owned source fixtures.
- Stateless repeatability across independent requests.
- Error isolation and negative validation behavior.
- Real artifact return from the Kroki-backed rendering pipeline.

## Notes

The repository catalog is the contract for this test. Kroki itself may support additional engines that are not yet exposed by `uml-mcp`; those do not count as missing unless they are present in the live MCP catalog. If the catalog expands later, the test deliberately reports the drift so coverage can be extended rather than silently ignoring new engines.
