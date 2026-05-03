---
title: Mermaid live examples
description: "Gallery of Mermaid diagrams plus prompts, optional Sequential Thinking, and server SVG; flowchart, sequence, class, state, Gantt, ER rendered live on the page."
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

## Prompts, Sequential Thinking, and server-rendered SVG

Use **natural-language prompts** first, then have the model produce Mermaid source and call **`generate_uml`** with **`"output_format": "svg"`** when you need a static asset, PDF pipeline, or shareable Kroki URL (unlike the in-page diagrams below, which rely on JavaScript).

**Optional Sequential Thinking MCP.** In clients such as Cursor you can enable a **Sequential Thinking** server alongside UML-MCP. It is a separate product: use its `sequentialthinking` tool to step through scope, diagram type, participants, edge cases, then finish with **`nextThoughtNeeded: false`** before invoking `generate_uml`. UML-MCP’s own **`uml_diagram_with_thinking`** prompt is different: it is fetched with `prompts/get` and only affects how the model plans inside the chat.

**Named prompts on UML-MCP** (see [MCP prompts](../reference/prompts.md)):

| Prompt | Use when |
| --- | --- |
| `mermaid_sequence_api` | HTTP-style `sequenceDiagram` with client, API, optional DB, `alt` / errors. |
| `mermaid_gantt` | `gantt` with sections, `dateFormat`, dependencies. |
| `convert_class_to_mermaid` | Turn class structure (PlantUML or prose) into `classDiagram`. |
| `uml_diagram_with_thinking` | Any Mermaid type with an explicit plan-then-code step. |

Example chat prompts:

```
Using the mermaid_sequence_api style, draw a sequenceDiagram for OAuth2 authorization code flow:
browser, auth server, resource API, and token storage. Include success and error alt branches.
```

```
Gantt chart for a two-sprint release: Sprint 1 backend, Sprint 2 frontend and QA, milestone release.
Use the mermaid_gantt conventions from uml-mcp prompts.
```

**Illustrative Sequential Thinking steps** before generating the flowchart in the next section:

1. Diagram type is **flowchart** (`flowchart LR`), not sequence.
2. Decision **Authenticated?** splits login vs dashboard paths.
3. Loop: submit credentials and re-check authentication.
4. Terminal **End** only after success path.
5. Call `validate_uml` then `generate_uml` with `diagram_type: "mermaid"` and `"output_format": "svg"`.

**Direct `tools/call`** for that flowchart (same source as the SVG asset below):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "generate_uml",
    "arguments": {
      "diagram_type": "mermaid",
      "output_format": "svg",
      "code": "flowchart LR\n    A([Start]) --> B{Authenticated?}\n    B -- yes --> C[Show dashboard]\n    B -- no  --> D[Show login form]\n    D --> E[Submit credentials]\n    E --> B\n    C --> F([End])"
    }
  }
}
```

**Example output** (SVG from UML-MCP `generate_uml` with the same `code` as the live diagram under [Flowchart](#flowchart)):

![Mermaid flowchart rendered as SVG via Kroki](../assets/tutorials/mermaid-tutorial.svg)

See also [Diagram Assistant](../diagram-assistant.md) for how prompts map to tools and `uml://` resources.

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
