---
title: Mermaid live examples
description: "Gallery of Mermaid diagrams (flowchart, sequence, class, state, Gantt, ER), rendered live on the page."
tags:
  - mermaid
  - examples
---

# Mermaid live examples

Every code block on this page is a live Mermaid diagram rendered in your browser. Copy the source and pass it to `generate_uml` with `diagram_type: "mermaid"` to get a server-rendered SVG/PNG (and a Kroki URL you can share).

!!! tip "Quick call"

    ```json
    {
      "name": "generate_uml",
      "arguments": { "diagram_type": "mermaid", "code": "<paste source here>" }
    }
    ```

## Flowchart

```mermaid
flowchart LR
    A([Start]) --> B{Authenticated?}
    B -- yes --> C[Show dashboard]
    B -- no  --> D[Show login form]
    D --> E[Submit credentials]
    E --> B
    C --> F([End])
```

## Sequence (API call)

Same shape as the `mermaid_sequence_api` prompt and the `sequence_api` example under `uml://mermaid-examples`.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant A as API
    participant DB as Database
    C->>A: POST /login
    A->>DB: SELECT user WHERE email=?
    DB-->>A: user row
    alt valid password
        A-->>C: 200 + session cookie
    else invalid
        A-->>C: 401 Unauthorized
    end
```

## Class diagram

```mermaid
classDiagram
    class Account {
        +String id
        +String owner
        +deposit(amount) bool
        +withdraw(amount) bool
    }
    class Customer {
        +String name
        +String email
    }
    class Transaction {
        +String id
        +Date timestamp
        +float amount
    }
    Customer "1" --> "*" Account
    Account "1" --> "*" Transaction
```

## State diagram

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Processing: start
    Processing --> Completed: success
    Processing --> Failed: error
    Failed --> Idle: retry
    Completed --> [*]
```

## Gantt chart

Same shape as the `mermaid_gantt` prompt.

```mermaid
gantt
    title Project plan
    dateFormat  YYYY-MM-DD
    section Design
    Wireframes      :done, des1, 2025-01-05, 5d
    Visual design   :active, des2, after des1, 7d
    section Build
    API             :build1, after des2, 10d
    Frontend        :build2, after des2, 12d
    section Launch
    QA              :qa1, after build1, 4d
    Release         :milestone, m1, after qa1, 0d
```

## Entity-relationship

```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    PRODUCT ||--o{ LINE_ITEM : "ordered in"
    CUSTOMER {
        string id PK
        string email
    }
    ORDER {
        string id PK
        date created_at
    }
```

## Pie chart

```mermaid
pie showData
    title Diagram backends in use
    "Kroki" : 70
    "PlantUML server" : 20
    "Mermaid.ink" : 10
```

---

## Notes

!!! note "Server vs in-page rendering"

    The diagrams above use the **Mermaid runtime in your browser** (via `pymdownx.superfences`). `generate_uml` returns server-rendered SVG/PNG from Kroki, which suits static sites, PDFs, or any consumer that does not run JavaScript.

!!! tip "Validate first"

    Use `validate_uml(diagram_type="mermaid", code=..., strict=true)` to catch issues like missing `graph` directives or invalid sequence arrows before calling `generate_uml`.

See [Diagram Assistant](../diagram-assistant.md) for the matching named prompts (`mermaid_sequence_api`, `mermaid_gantt`, `convert_class_to_mermaid`).
