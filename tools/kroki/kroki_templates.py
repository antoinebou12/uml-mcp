"""
Templates and examples for various diagram formats supported by Kroki.
"""


class DiagramExamples:
    """
    Provides complete examples for different diagram formats supported by Kroki.
    """

    @staticmethod
    def get_example(diagram_type: str) -> str:
        """
        Get a comprehensive example for the specified diagram type.

        Args:
            diagram_type: The type of diagram (plantuml, mermaid, etc.)

        Returns:
            A comprehensive example for the diagram type
        """
        examples = {
            # PlantUML example with more detailed sequence diagram
            "plantuml": """@startuml
skinparam ranksep 20
skinparam dpi 125
skinparam packageTitleAlignment left
rectangle "Main" {
  (main.view)
  (singleton)
}
rectangle "Base" {
  (base.component)
  (component)
  (model)
}
rectangle "<b>main.ts</b>" as main_ts
(component) ..> (base.component)
main_ts ==> (main.view)
(main.view) --> (component)
(main.view) ...> (singleton)
(singleton) ---> (model)
@enduml""",
            # UML diagram type examples (PlantUML) for MCP diagram_type keys
            "class": """@startuml
class Account {
  - balance: decimal
  - accountNumber: string
  + deposit(amount: decimal): void
  + withdraw(amount: decimal): boolean
}
class Customer {
  - name: string
  - id: string
  + getAccounts(): List<Account>
}
class Transaction {
  - amount: decimal
  - date: DateTime
}
Customer "1" --> "*" Account : owns
Account "1" --> "*" Transaction : contains
@enduml""",
            "sequence": """@startuml
participant Client
participant API
participant Database

Client -> API: GET /resource
activate API
API -> Database: query
activate Database
Database --> API: result
deactivate Database
API --> Client: 200 JSON
deactivate API

alt Error
  API --> Client: 500
end
@enduml""",
            "activity": """@startuml
start
:Receive order;
:Validate order;
if (Valid?) then (yes)
  :Process payment;
  if (Payment OK?) then (yes)
    :Ship order;
    stop
  else (no)
    :Notify customer;
    stop
  endif
else (no)
  :Reject order;
  stop
endif
@enduml""",
            "usecase": """@startuml
left to right direction
actor Customer
actor Admin
rectangle "Banking System" {
  usecase (View balance) as UC1
  usecase (Transfer funds) as UC2
  usecase (Manage users) as UC3
}
Customer --> UC1
Customer --> UC2
Admin --> UC1
Admin --> UC2
Admin --> UC3
@enduml""",
            "state": """@startuml
[*] --> Idle
Idle --> Running: start
Running --> Paused: pause
Paused --> Running: resume
Running --> Idle: stop
Idle : entry / init
Idle : exit / cleanup
@enduml""",
            "component": """@startuml
component [Web Server] as WS
component [API Gateway] as GW
component [User Service] as US
component [Database] as DB
WS --> GW
GW --> US
US --> DB
@enduml""",
            "deployment": """@startuml
node "Load Balancer" {
  artifact "nginx"
}
node "App Server 1" {
  artifact "app.war"
}
node "App Server 2" {
  artifact "app.war"
}
node "Database Server" {
  database "MySQL"
}
"Load Balancer" --> "App Server 1"
"Load Balancer" --> "App Server 2"
"App Server 1" --> "Database Server"
"App Server 2" --> "Database Server"
@enduml""",
            "object": """@startuml
object order1 as "Order #1"
object item1 as "Item A"
object item2 as "Item B"
object customer as "Customer"
order1 --> item1: contains
order1 --> item2: contains
order1 --> customer: placed by
@enduml""",
            # Mermaid example with sequence diagram
            "mermaid": """sequenceDiagram
    participant Browser
    participant Webserver
    participant Processor

    Browser->>Webserver: GET /diagram/svg/base64
    Webserver->>Processor: Convert text to image
    Processor-->>Webserver: Return image
    Webserver-->>Browser: Deliver SVG image

    note over Browser,Webserver: HTTP Request
    note over Webserver,Processor: Internal Processing""",
            # Mermaid API call sequence example
            "mermaid_api": """sequenceDiagram
    participant Client
    participant API
    participant Auth
    participant DB

    Client->>+API: GET /resource
    API->>+Auth: Validate token
    Auth-->>-API: OK
    API->>+DB: Query data
    DB-->>-API: Result set
    API-->>-Client: 200 JSON

    alt Invalid token
        Auth-->>API: 401
        API-->>Client: Unauthorized
    end""",
            # Mermaid Gantt chart example
            "mermaid_gantt": """gantt
    title Project timeline
    dateFormat  YYYY-MM-DD
    section Design
    Requirements    :req, 2024-01-01, 7d
    UI mockups      :mock, after req, 5d
    section Development
    Backend API     :api, after mock, 14d
    Frontend        :fe, after mock, 14d
    section QA
    Testing         :crit, after api, 7d""",
            # BlockDiag example
            "blockdiag": """blockdiag {
  Kroki -> generates -> "Block diagrams";
  Kroki -> is -> "very easy!";
  Kroki [color = "greenyellow"];
  "Block diagrams" [color = "pink"];
  "very easy!" [color = "orange"];
}""",
            # SeqDiag example
            "seqdiag": """seqdiag {
  browser  -> webserver [label = "GET /seqdiag/svg/base64"];
  webserver  -> processor [label = "Convert text to image"];
  webserver <-- processor;
  browser <-- webserver;
}""",
            # ActDiag example
            "actdiag": """actdiag {
  write -> convert -> image
  lane user {
    label = "User"
    write [label = "Writing text"];
    image [label = "Get diagram image"];
  }
  lane Kroki {
    convert [label = "Convert text to image"];
  }
}""",
            # NwDiag example
            "nwdiag": """nwdiag {
  network dmz {
    address = "210.x.x.x/24"
    web01 [address = "210.x.x.1"];
    web02 [address = "210.x.x.2"];
  }
  network internal {
    address = "172.x.x.x/24";
    web01 [address = "172.x.x.1"];
    web02 [address = "172.x.x.2"];
    db01;
    db02;
  }
}""",
            # PacketDiag example
            "packetdiag": """packetdiag {
  colwidth = 32;
  node_height = 72;
  0-15: Source Port;
  16-31: Destination Port;
  32-63: Sequence Number;
  64-95: Acknowledgment Number;
  96-99: Data Offset;
  100-105: Reserved;
  106: URG [rotate = 270];
  107: ACK [rotate = 270];
  108: PSH [rotate = 270];
  109: RST [rotate = 270];
  110: SYN [rotate = 270];
  111: FIN [rotate = 270];
  112-127: Window;
  128-143: Checksum;
  144-159: Urgent Pointer;
  160-191: (Options and Padding);
  192-223: data [colheight = 3];
}""",
            # RackDiag example
            "rackdiag": """rackdiag {
  16U;
  1: UPS [2U];
  3: DB Server;
  4: Web Server;
  5: Web Server;
  6: Web Server;
  7: Load Balancer;
  8: L3 Switch;
}""",
            # C4 diagram (PlantUML extension) example
            "c4plantuml": """!include <C4/C4_Context>
title System Context diagram for Internet Banking System
Person(customer, "Banking Customer", "A customer of the bank, with personal bank accounts.")
System(banking_system, "Internet Banking System", "Allows customers to check their accounts.")
System_Ext(mail_system, "E-mail system", "The internal Microsoft Exchange e-mail system.")
System_Ext(mainframe, "Mainframe Banking System", "Stores all of the core banking information.")
Rel(customer, banking_system, "Uses")
Rel_Back(customer, mail_system, "Sends e-mails to")
Rel_Neighbor(banking_system, mail_system, "Sends e-mails", "SMTP")
Rel(banking_system, mainframe, "Uses")""",
            # Bytefield example
            "bytefield": """(defattrs :bg-green {:fill "#a0ffa0"})
(defattrs :bg-yellow {:fill "#ffffa0"})
(defattrs :bg-pink {:fill "#ffb0a0"})
(defattrs :bg-cyan {:fill "#a0fafa"})
(defattrs :bg-purple {:fill "#e4b5f7"})
(defn draw-group-label-header
  [span label]
  (draw-box (text label [:math {:font-size 12}]) {:span span :borders #{} :height 14}))
(defn draw-remotedb-header
  [kind args]
  (draw-column-headers)
  (draw-group-label-header 5 "start")
  (draw-group-label-header 5 "TxID")
  (draw-group-label-header 3 "type")
  (draw-group-label-header 2 "args")
  (draw-group-label-header 1 "tags")
  (next-row 18)
  (draw-box 0x11 :bg-green)
  (draw-box 0x872349ae [{:span 4} :bg-green])
  (draw-box 0x11 :bg-yellow)
  (draw-box (text "TxID" :math) [{:span 4} :bg-yellow])
  (draw-box 0x10 :bg-pink)
  (draw-box (hex-text kind 4 :bold) [{:span 2} :bg-pink])
  (draw-box 0x0f :bg-cyan)
  (draw-box (hex-text args 2 :bold) :bg-cyan)
  (draw-box 0x14 :bg-purple)
  (draw-box (text "0000000c" :hex [[:plain {:font-weight "light" :font-size 16}] " (12)"]) [{:span 4} :bg-purple])
  (draw-box (hex-text 6 2 :bold) [:box-first :bg-purple])
  (doseq [val [6 6 3 6 6 6 6 3]]
    (draw-box (hex-text val 2 :bold) [:box-related :bg-purple]))
  (doseq [val [0 0]]
    (draw-box val [:box-related :bg-purple]))
  (draw-box 0 [:box-last :bg-purple]))
(draw-remotedb-header 0x4702 9)""",
            # D2 example
            "d2": """title: Request flow
User -> API: HTTP Request
API -> Database: Query
Database -> API: Result
API -> User: JSON Response""",
            # Graphviz example
            "graphviz": """digraph G {
    rankdir=LR;
    node [shape=box];
    Client -> API [label="request"];
    API -> DB [label="query"];
    DB -> API [label="result"];
    API -> Client [label="response"];
}""",
            # DBML example
            "dbml": """Table users {
  id int [pk, increment]
  name varchar
  email varchar [unique]
}

Table orders {
  id int [pk, increment]
  user_id int [ref: > users.id]
  amount decimal
}""",
            # Ditaa example (ASCII art)
            "ditaa": """+--------+   +-------+   +----------+
| Client |   |  API  |   | Database |
+----+---+   +---+---+   +----+-----+
     |            |              |
     |  request   |   query      |
     +----------->+------------->
     |            |              |
     |  response  |   result     |
     <------------+<-------------+
     |            |              |""",
            # Excalidraw example (JSON)
            "excalidraw": """{"type":"excalidraw","version":2,"source":"kroki","elements":[{"id":"rect","type":"rectangle","x":100,"y":100,"width":200,"height":100,"angle":0,"strokeColor":"#000","backgroundColor":"#fff","fillStyle":"solid"},{"id":"text","type":"text","x":150,"y":130,"text":"Hello","fontSize":20}],"appState":{"viewBackgroundColor":"#fff"},"files":{}}""",
            # Nomnoml example
            "nomnoml": """[User] -> [API]
[API] -> [Database]
[User] - [Cache]""",
            # Pikchr example
            "pikchr": """box "Service" fit
arrow
box "Database" fit""",
            # Structurizr example
            "structurizr": """workspace "Example" "Description" {
    model {
        user = person "User"
        app = softwareSystem "App" "A sample system"
        user -> app "Uses"
    }
    views {
        systemContext app "Context" {
            include *
        }
    }
}""",
            # Svgbob example (ASCII)
            "svgbob": """    .--------.
   /  Hello  \\
  |   World   |
   \\________/""",
            # Symbolator example (minimal netlist)
            "symbolator": """(symbol "RES" (pin_names (line (pin "1") (pin "2"))))""",
            # TikZ example (flowchart + graph + geometry)
            "tikz": """\\documentclass[border=2pt]{standalone}
\\usepackage{tikz}
\\usetikzlibrary{shapes,arrows,positioning}
\\begin{document}
\\begin{tikzpicture}[node distance=1.8cm, auto]
  \\node[rectangle, draw] (start) {Start};
  \\node[diamond, draw, aspect=2, below of=start] (dec) {OK?};
  \\node[rectangle, draw, below left=1.2cm and 1cm of dec] (yes) {Yes};
  \\node[rectangle, draw, below right=1.2cm and 1cm of dec] (no) {No};
  \\draw[->] (start) -- (dec);
  \\draw[->] (dec) -- node[near start, left] {Y} (yes);
  \\draw[->] (dec) -- node[near start, right] {N} (no);
\\end{tikzpicture}
\\qquad
\\begin{tikzpicture}
  \\node[circle, draw] (a) at (0,0) {1};
  \\node[circle, draw] (b) at (2,0) {2};
  \\node[circle, draw] (c) at (1,1.5) {3};
  \\draw (a) -- (b) -- (c) -- (a);
\\end{tikzpicture}
\\qquad
\\begin{tikzpicture}[scale=0.7]
  \\draw[step=1, gray, thin] (-1,-1) grid (1,1);
  \\draw[thick, ->] (-1.2,0) -- (1.2,0) node[right] {$x$};
  \\draw[thick, ->] (0,-1.2) -- (0,1.2) node[above] {$y$};
  \\fill (0,0) circle (2pt);
\\end{tikzpicture}
\\end{document}""",
            # Vega example
            "vega": """{"$schema":"https://vega.github.io/schema/vega/v5.json","width":200,"height":200,"data":[{"name":"table","values":[{"x":1,"y":2},{"x":2,"y":4}]}],"scales":[{"name":"x","type":"linear","range":"width","domain":{"data":"table","field":"x"}},{"name":"y","type":"linear","range":"height","domain":{"data":"table","field":"y"}}],"marks":[{"type":"symbol","from":{"data":"table"},"encode":{"enter":{"x":{"scale":"x","field":"x"},"y":{"scale":"y","field":"y"},"size":{"value":50}}}}]}""",
            # Vega-Lite example
            "vegalite": """{"$schema":"https://vega.github.io/schema/vega-lite/v5.json","data":{"values":[{"a":1,"b":2},{"a":2,"b":4}]},"mark":"point","encoding":{"x":{"field":"a","type":"quantitative"},"y":{"field":"b","type":"quantitative"}}}""",
            # WaveDrom example
            "wavedrom": """{ "signal": [
  { "name": "clk", "wave": "p...." },
  { "name": "data", "wave": "x.345.", "data": ["head", "body", "tail"] }
]}""",
            # WireViz example (YAML)
            "wireviz": """connector: J1
  pin: 1: GND
  pin: 2: VCC
  pin: 3: SDA
  pin: 4: SCL
cable: C1
  gauge: 28
  length: 0.5
  color: black
  connector: [J1, J1]""",
            # ERD example
            "erd": """[Person]
*name
height
weight
--
[Order]
*id
date
Person *-- Order""",
            # BPMN example (minimal XML)
            "bpmn": """<?xml version="1.0" encoding="UTF-8"?>
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
</bpmn:definitions>""",
        }

        # Get the example or return a message if not found
        return examples.get(
            diagram_type.lower(),
            "# No specific example available for this diagram type.\n"
            "# Please refer to the documentation for " + diagram_type,
        )


class DiagramTemplates:
    """
    Provides starter templates for different diagram formats.
    """

    @staticmethod
    def get_template(diagram_type: str) -> str:
        """
        Get a starter template for the specified diagram type.

        Args:
            diagram_type: The type of diagram (plantuml, mermaid, etc.)

        Returns:
            A starter template for the diagram type
        """
        templates = {
            # Basic sequence diagram for PlantUML
            "plantuml": """@startuml
participant User
participant System

User -> System: Request
System --> User: Response
@enduml""",
            # UML diagram type templates (PlantUML) for MCP diagram_type keys
            "class": """@startuml
class Car {
  - brand: string
  - speed: int
  + drive(): void
}
class Engine {
  - horsepower: int
  + start(): void
}
Car --> Engine
@enduml""",
            "sequence": """@startuml
participant User
participant System

User -> System: Request
System --> User: Response
@enduml""",
            "activity": """@startuml
start
:Do something;
if (OK?) then (yes)
  :Continue;
else (no)
  :Handle error;
endif
stop
@enduml""",
            "usecase": """@startuml
left to right direction
actor User
rectangle System {
  usecase (Use case one)
  usecase (Use case two)
}
User --> (Use case one)
@enduml""",
            "state": """@startuml
[*] --> Idle
Idle --> Running: start
Running --> Idle: stop
@enduml""",
            "component": """@startuml
component [Component A]
component [Component B]
[Component A] --> [Component B]
@enduml""",
            "deployment": """@startuml
node "Server" {
  artifact "app.war"
}
@enduml""",
            "object": """@startuml
object user1 as "User"
object sys1 as "System"
user1 --> sys1: uses
@enduml""",
            # Basic sequence diagram for Mermaid (default)
            "mermaid": """sequenceDiagram
    participant User
    participant System

    User->>System: Request
    System-->>User: Response""",
            # Mermaid Gantt starter template
            "mermaid_gantt": """gantt
    title My project
    dateFormat  YYYY-MM-DD
    section Section A
    Task A1    :a1, 2024-01-01, 7d
    Task A2    :a2, after a1, 5d
    section Section B
    Task B1    :b1, 2024-01-01, 14d""",
            # Algorithm explainer starter: Mermaid flowchart with complexity labels,
            # base case vs recursive call shapes, and a layout direction to reduce
            # crossings. Use diagram_type "mermaid" with generate_uml.
            "algorithm_flowchart": """flowchart TD
    Start([Start: sort(arr)])
    Check{len(arr) <= 1?}
    Base([Return arr<br/><i>O(1)</i>])
    Pick["Pick pivot<br/><i>O(1)</i>"]
    Partition["Partition around pivot<br/><i>O(n)</i>"]
    Left[[Recurse on left half<br/><i>T(n/2)</i>]]
    Right[[Recurse on right half<br/><i>T(n/2)</i>]]
    Combine["Concat left + pivot + right<br/><i>O(n)</i>"]
    Done([Return sorted arr])

    Start --> Check
    Check -- yes --> Base
    Check -- no --> Pick --> Partition
    Partition --> Left
    Partition --> Right
    Left --> Combine
    Right --> Combine
    Combine --> Done

    %% Aggregate complexity: T(n) = 2T(n/2) + O(n) = O(n log n)
""",
            # Paper-concept starter: Mermaid flowchart with citation labels and one
            # clickable arXiv link. Use diagram_type "mermaid" with generate_uml and
            # output_format svg so the link survives the render.
            "paper_concept": """flowchart LR
    Input[/"Tokens"/]
    Embed["Embedding<br/>[Mikolov+ 2013]"]
    Attn["Self-Attention<br/>[Vaswani+ 2017]"]
    FFN["Feed-Forward<br/>[Vaswani+ 2017]"]
    Out[/"Logits"/]

    Input --> Embed --> Attn --> FFN --> Out

    click Attn "https://arxiv.org/abs/1706.03762" "Attention Is All You Need" _blank
    click Embed "https://arxiv.org/abs/1301.3781" "Efficient Estimation of Word Representations" _blank
""",
            # Basic diagram for D2
            "d2": """User -> System: Request
System -> User: Response""",
            # Basic diagram for Graphviz
            "graphviz": """digraph G {
    User -> System [label="Request"];
    System -> User [label="Response"];
}""",
            # Basic diagram for BlockDiag
            "blockdiag": """blockdiag {
  User -> System -> Database;
  System -> User;
}""",
            # Basic diagram for PacketDiag
            "packetdiag": """packetdiag {
  0-15: Source Port;
  16-31: Destination Port;
  32-63: Sequence Number;
  64-95: Acknowledgment Number;
}""",
            # ERD example
            "erd": """[Person]
*name
height
weight
--
[Order]
*id
date
Person *-- Order""",
            # BPMN example (minimal XML)
            "bpmn": """<?xml version="1.0" encoding="UTF-8"?>
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
</bpmn:definitions>""",
            # C4 PlantUML template
            "c4plantuml": """!include <C4/C4_Context>
title System Context
Person(user, "User")
System(system, "My System")
Rel(user, system, "Uses")""",
            # Basic diagram for Bytefield
            "bytefield": """(defattrs :bg-green {:fill "#a0ffa0"})
(defattrs :bg-yellow {:fill "#ffffa0"})
(defattrs :bg-pink {:fill "#ffb0a0"})
(defattrs :bg-cyan {:fill "#a0fafa"})
(defattrs :bg-purple {:fill "#e4b5f7"})

(def row-height 40)
(def row-header-width 50)
(def box-width 30)

(defn draw-packet-header
  []
  (draw-column-headers)
  (draw-box 0 0 8)
  (draw-box 0 1 8)
  (draw-gap "Payload")
  (draw-bottom))

(draw-packet-header)""",
            # SeqDiag template
            "seqdiag": """seqdiag {
  client -> server [label = "Request"];
  server <-- client [label = "Response"];
}""",
            # ActDiag template
            "actdiag": """actdiag {
  input -> process -> output
  lane user {
    input [label = "Input"];
    output [label = "Output"];
  }
  lane system {
    process [label = "Process"];
  }
}""",
            # NwDiag template
            "nwdiag": """nwdiag {
  network internet {
    address = "0.0.0.0/0"
  }
  network internal {
    address = "192.168.1.0/24"
    server [address = "192.168.1.1"];
  }
}""",
            # RackDiag template
            "rackdiag": """rackdiag {
  16U;
  1: Server 1;
  2: Server 2;
  3: Switch;
}""",
            # Ditaa template
            "ditaa": """+------+     +------+
|  A   +---->+  B   |
+------+     +------+""",
            # DBML template
            "dbml": """Table users {
  id int [pk]
  name varchar
}

Table posts {
  id int [pk]
  user_id int [ref: > users.id]
}""",
            # Excalidraw template (minimal JSON)
            "excalidraw": """{"type":"excalidraw","version":2,"source":"kroki","elements":[{"id":"r1","type":"rectangle","x":50,"y":50,"width":150,"height":80,"angle":0,"strokeColor":"#000","backgroundColor":"#fff","fillStyle":"solid"}],"appState":{"viewBackgroundColor":"#fff"},"files":{}}""",
            # Nomnoml template
            "nomnoml": """[A] -> [B]
[B] -> [C]""",
            # Pikchr template
            "pikchr": """box "A" fit
arrow
box "B" fit""",
            # Structurizr template
            "structurizr": """workspace "My Workspace" "Description" {
    model {
        user = person "User"
        system = softwareSystem "System" "Description"
        user -> system "Uses"
    }
    views {
        systemContext system "Context" { include * }
    }
}""",
            # Svgbob template
            "svgbob": """  +---+
  | A |
  +---+
    |
    v
  +---+""",
            # Symbolator template
            "symbolator": """(symbol "RES" (pin_names (line (pin "1") (pin "2"))))""",
            # TikZ template (flowchart starter with positioning)
            "tikz": """\\documentclass[border=2pt]{standalone}
\\usepackage{tikz}
\\usetikzlibrary{shapes,arrows,positioning}
\\begin{document}
\\begin{tikzpicture}[node distance=2cm, auto]
  \\node[rectangle, draw] (start) {Start};
  \\node[diamond, draw, below of=start, aspect=2] (decision) {Decision?};
  \\node[rectangle, draw, below left=1.2cm and 1cm of decision] (yes) {Yes};
  \\node[rectangle, draw, below right=1.2cm and 1cm of decision] (no) {No};
  \\draw[->] (start) -- (decision);
  \\draw[->] (decision) -- node[near start, left] {Y} (yes);
  \\draw[->] (decision) -- node[near start, right] {N} (no);
\\end{tikzpicture}
\\end{document}""",
            # Vega template
            "vega": """{"$schema":"https://vega.github.io/schema/vega/v5.json","width":200,"height":200,"data":[{"name":"d","values":[{"v":1},{"v":2}]}],"marks":[{"type":"rect","from":{"data":"d"},"encode":{"enter":{"x":{"value":0},"y":{"scale":"y","field":"v"},"width":{"value":20},"height":{"scale":"y","band":1}}}}],"scales":[{"name":"y","type":"band","range":"height","domain":{"data":"d","field":"v"}}]}""",
            # Vega-Lite template
            "vegalite": """{"$schema":"https://vega.github.io/schema/vega-lite/v5.json","data":{"values":[{"a":1},{"a":2}]},"mark":"bar","encoding":{"x":{"field":"a","type":"quantitative"}}}""",
            # WaveDrom template
            "wavedrom": """{ "signal": [
  { "name": "clk", "wave": "p...." },
  { "name": "sig", "wave": "01.0." }
]}""",
            # WireViz template
            "wireviz": """connector: P1
  pin: 1: GND
  pin: 2: VCC
cable: C1
  gauge: 24
  length: 1
  color: red
  connector: [P1, P1]""",
        }

        # Try to get a specific template, fall back to a generic one
        return templates.get(
            diagram_type.lower(),
            "# No specific template available for this diagram type.\n"
            "# Please refer to the documentation for this diagram type.",
        )
