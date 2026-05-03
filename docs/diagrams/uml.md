---
title: UML (PlantUML)
description: PlantUML-based UML diagram types (class, sequence, activity, use case, state, component, deployment, object).
tags:
  - uml
  - plantuml
---

# UML (PlantUML)

UML-MCP supports the eight standard UML diagram types through the PlantUML backend on Kroki, plus a raw `plantuml` type for arbitrary `@startuml` source.

| `diagram_type` | Use it for |
| --- | --- |
| `class` | Static structure: classes, attributes, methods, relationships |
| `sequence` | Object interactions over time |
| `activity` | Workflows and business processes |
| `usecase` | Actors and system functionality |
| `state` | Object lifecycle states |
| `component` | Components and dependencies |
| `deployment` | Physical architecture |
| `object` | Class instances and their relationships |
| `plantuml` | Raw PlantUML (any kind) |

!!! tip "Plan before you generate"

    The default `uml_diagram_with_thinking` prompt produces a brief plan (purpose, elements, relationships) before the code, which dramatically improves first-shot diagram quality.

## Class Diagrams

Class diagrams show the static structure of a system:

```plantuml
@startuml
class Car {
  -color: String
  -model: String
  +start(): void
  +accelerate(speed: int): void
}

class Driver {
  -name: String
  -license: String
  +drive(): void
}

Car -- Driver
@enduml
```

## Sequence Diagrams

Sequence diagrams show object interactions arranged in time sequence:

```plantuml
@startuml
participant User
participant System
participant Database

User -> System: Login Request
System -> Database: Validate Credentials
Database --> System: Validation Result
alt successful case
    System --> User: Login Success
else failed case
    System --> User: Login Failed
end
@enduml
```

## Activity Diagrams

Activity diagrams show workflows or business processes:

```plantuml
@startuml
start
:Check Authentication;
if (Authenticated?) then (yes)
  :Show Dashboard;
else (no)
  :Show Login Form;
endif
stop
@enduml
```

## Use Case Diagrams

Use case diagrams show system functionality and actors:

```plantuml
@startuml
left to right direction
actor Customer
actor Clerk
rectangle Checkout {
  Customer -- (Checkout)
  (Checkout) .> (Payment) : include
  (Help) .> (Checkout) : extend
  (Checkout) -- Clerk
}
@enduml
```

## State Diagrams

State diagrams show states of an object during its lifecycle:

```plantuml
@startuml
[*] --> Idle
Idle --> Processing: Start
Processing --> Completed: Success
Processing --> Failed: Error
Completed --> [*]
Failed --> Idle: Retry
@enduml
```

## Component Diagrams

Component diagrams show components and dependencies:

```plantuml
@startuml
package "Frontend" {
  [Web UI]
  [API Client]
}
package "Backend" {
  [API Gateway]
  [Authentication]
  [Business Logic]
  database "Database"
}

[Web UI] --> [API Client]
[API Client] --> [API Gateway]
[API Gateway] --> [Authentication]
[API Gateway] --> [Business Logic]
[Business Logic] --> [Database]
@enduml
```

## Tips for UML Diagrams

1. Use PlantUML preprocessor for advanced features:
   ```plantuml
   !include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml
   ```

2. Apply themes for better visuals:
   ```plantuml
   @startuml
   !theme cerulean
   class Example
   @enduml
   ```

3. Use notes for additional information:
   ```plantuml
   @startuml
   class User
   note right of User: This class represents system users
   @enduml
   ```

---

## Related

- [Diagram catalog](index.md): all supported types with output formats.
- [Mermaid](mermaid.md): alternative syntax if you prefer Mermaid.
- [Tutorials, Getting started](../tutorials/getting-started.md): step-by-step generation walkthrough.
- [MCP tools reference](../api/tools.md).
