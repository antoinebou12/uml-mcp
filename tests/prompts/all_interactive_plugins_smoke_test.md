# All interactive plugins smoke test

Use the connected UML-MCP server for these checks.

1. Call `list_diagram_types`. Confirm all 15 types below appear. Report missing
   types as FAIL and continue with the available types.
2. For each source below, call `validate_uml` with `output_format: svg`, then
   `generate_uml_image`. Check readable labels and visible colours in each image.
   Preserve the exact errors returned by the tools.
3. Call `generate_uml` with `output_format: html` for each source. In an MCP App,
   open every result and check labels, zoom and fit. Mark browser checks
   UNAVAILABLE when the client cannot inspect the viewer.
4. Repeat each type with `theme: light` and `theme: dark`. Verify the diagram's
   colours, including its background. Check the interactions listed below.
5. Export SVG, PNG and HTML from each plugin family. Open each download and
   verify its labels and colours. Reopen HTML offline and record any network
   dependencies that prevent verification.
6. Validate one deliberately invalid source and confirm a useful error. Then
   verify a valid source still renders.
7. Report one row per type: discovery | validation | PNG | SVG | HTML |
   interaction | exports. Use PASS, FAIL, UNVERIFIED or UNAVAILABLE for each
   stage. Tool success alone does not verify browser interactions or downloads.

## Interaction checks

| Plugin | Check in the HTML viewer |
| --- | --- |
| D3 | Drag and pin a force node; drag an architecture node and check routes; pan and fit topology. |
| Stack diagram | Check provider logos and numbered steps; change direction and fit. |
| Archify | Focus a node, trace a shortest path, change presets, and check sequence messages. |
| LLM visualizer | Inspect 2D layers; orbit the 3D scene and switch views. |
| Database schema | Search for a table or column and inspect relationship endpoints. |
| Dependency graphs | Collapse a branch, search a package and inspect its details. |
| Statechart | Fire an event, check the active state and log, then Undo. |
| Agent traces | Switch waterfall and flow views; inspect a step and token/cost totals. |
| C4 model | Open a system's containers, then a container's components; navigate back. |
| Timeline | Zoom the time scale and inspect milestones and dependency arrows. |

## Sources

### d3_force

```json
{
  "title": "Service dependencies",
  "directed": true,
  "nodes": [
    {
      "id": "web",
      "label": "Web app",
      "group": "frontend",
      "service": "react",
      "size": 1.4
    },
    {
      "id": "mobile",
      "label": "Mobile app",
      "group": "frontend",
      "service": "mobile"
    },
    {
      "id": "gateway",
      "label": "API gateway",
      "group": "edge",
      "service": "nginx",
      "size": 1.6
    },
    {
      "id": "auth",
      "label": "Auth",
      "group": "backend",
      "service": "keycloak"
    },
    {
      "id": "orders",
      "label": "Orders",
      "group": "backend",
      "service": "nodejs",
      "size": 1.3
    },
    {
      "id": "billing",
      "label": "Billing",
      "group": "backend",
      "service": "python"
    },
    {
      "id": "db",
      "label": "Postgres",
      "group": "data",
      "service": "postgres",
      "size": 1.4,
      "note": "primary + replica"
    },
    {
      "id": "queue",
      "label": "Events",
      "group": "data",
      "service": "kafka"
    }
  ],
  "links": [
    {
      "source": "web",
      "target": "gateway"
    },
    {
      "source": "mobile",
      "target": "gateway"
    },
    {
      "source": "gateway",
      "target": "auth"
    },
    {
      "source": "gateway",
      "target": "orders",
      "label": "REST"
    },
    {
      "source": "orders",
      "target": "db"
    },
    {
      "source": "orders",
      "target": "queue",
      "label": "publishes"
    },
    {
      "source": "billing",
      "target": "queue",
      "label": "consumes"
    },
    {
      "source": "billing",
      "target": "db"
    }
  ]
}
```

### d3_architecture

```json
{
  "title": "Orders service on AWS",
  "provider": "aws",
  "groups": [
    {
      "id": "region",
      "label": "eu-west-1",
      "type": "region"
    },
    {
      "id": "vpc",
      "label": "VPC 10.0.0.0/16",
      "type": "vpc",
      "parent": "region"
    },
    {
      "id": "private",
      "label": "Private subnets",
      "type": "subnet",
      "parent": "vpc"
    }
  ],
  "nodes": [
    {
      "id": "users",
      "label": "Users",
      "kind": "user"
    },
    {
      "id": "cdn",
      "label": "CDN",
      "service": "aws:cloudfront"
    },
    {
      "id": "api",
      "label": "API",
      "service": "aws:apigateway",
      "group": "vpc",
      "inputs": [
        "https"
      ],
      "outputs": [
        "invoke"
      ]
    },
    {
      "id": "orders",
      "label": "Orders",
      "service": "aws:lambda",
      "group": "private",
      "inputs": [
        "invoke"
      ],
      "outputs": [
        "rows",
        "events"
      ]
    },
    {
      "id": "db",
      "label": "Orders table",
      "service": "aws:dynamodb",
      "group": "private"
    },
    {
      "id": "queue",
      "label": "Order events",
      "service": "aws:sqs",
      "group": "private"
    },
    {
      "id": "mail",
      "label": "Notifier",
      "service": "aws:lambda",
      "group": "private"
    }
  ],
  "links": [
    {
      "from": "users",
      "to": "cdn",
      "label": "HTTPS"
    },
    {
      "from": "cdn",
      "to": "api:https"
    },
    {
      "from": "api:invoke",
      "to": "orders:invoke"
    },
    {
      "from": "orders:rows",
      "to": "db",
      "label": "read / write"
    },
    {
      "from": "orders:events",
      "to": "queue",
      "style": "dashed"
    },
    {
      "from": "queue",
      "to": "mail",
      "style": "dashed"
    }
  ]
}
```

### d3_topology

```json
{
  "title": "Web application deployment",
  "provider": "generic",
  "groups": [
    {
      "id": "dmz",
      "label": "DMZ",
      "type": "zone"
    },
    {
      "id": "prod",
      "label": "Production",
      "type": "env"
    },
    {
      "id": "app",
      "label": "App tier",
      "type": "system",
      "parent": "prod"
    },
    {
      "id": "data",
      "label": "Data tier",
      "type": "system",
      "parent": "prod"
    }
  ],
  "nodes": [
    {
      "id": "client",
      "label": "Browsers",
      "kind": "user"
    },
    {
      "id": "fw",
      "label": "Firewall",
      "kind": "firewall",
      "group": "dmz"
    },
    {
      "id": "lb",
      "label": "Load balancer",
      "kind": "loadbalancer",
      "group": "dmz"
    },
    {
      "id": "web1",
      "label": "web-1",
      "service": "kubernetes:pod",
      "group": "app"
    },
    {
      "id": "web2",
      "label": "web-2",
      "service": "kubernetes:pod",
      "group": "app"
    },
    {
      "id": "cache",
      "label": "Redis",
      "kind": "cache",
      "group": "data"
    },
    {
      "id": "db",
      "label": "PostgreSQL",
      "kind": "database",
      "group": "data"
    }
  ],
  "links": [
    {
      "from": "client",
      "to": "fw",
      "label": "443"
    },
    {
      "from": "fw",
      "to": "lb"
    },
    {
      "from": "lb",
      "to": "web1"
    },
    {
      "from": "lb",
      "to": "web2"
    },
    {
      "from": "web1",
      "to": "cache"
    },
    {
      "from": "web2",
      "to": "cache"
    },
    {
      "from": "web1",
      "to": "db",
      "label": "5432"
    },
    {
      "from": "web2",
      "to": "db"
    }
  ]
}
```

### stack_diagram

```json
{
  "title": "SaaS stack",
  "direction": "LR",
  "theme": "dark",
  "groups": [
    {
      "id": "vercel",
      "name": "Vercel",
      "style": "plain",
      "icon": "vercel"
    },
    {
      "id": "github",
      "name": "GitHub",
      "style": "vendor",
      "tone": "blue",
      "icon": "github"
    }
  ],
  "nodes": [
    {
      "id": "user",
      "name": "User",
      "role": "browser",
      "icon": "user"
    },
    {
      "id": "web",
      "name": "Next.js",
      "role": "frontend",
      "icon": "browser",
      "group": "vercel"
    },
    {
      "id": "api",
      "name": "Hono",
      "role": "api routes",
      "icon": "function",
      "group": "vercel"
    },
    {
      "id": "db",
      "name": "Neon",
      "role": "serverless postgres",
      "icon": "database"
    },
    {
      "id": "auth",
      "name": "Clerk",
      "role": "auth",
      "icon": "lock"
    },
    {
      "id": "pay",
      "name": "Stripe",
      "role": "payments",
      "icon": "payments"
    },
    {
      "id": "ci",
      "name": "GitHub Actions",
      "role": "ci",
      "icon": "github",
      "group": "github"
    }
  ],
  "edges": [
    {
      "from": "user",
      "to": "web",
      "label": "HTTPS"
    },
    {
      "from": "web",
      "to": "api",
      "label": "RPC"
    },
    {
      "from": "api",
      "to": "db",
      "label": "SQL"
    },
    {
      "from": "api",
      "to": "auth",
      "label": "session",
      "tone": "neutral"
    },
    {
      "from": "api",
      "to": "pay",
      "label": "checkout",
      "tone": "neutral"
    },
    {
      "from": "ci",
      "to": "web",
      "label": "deploy",
      "style": "dashed"
    }
  ]
}
```

### archify_architecture

```json
{
  "title": "Platform architecture",
  "subtitle": "Auth, API, bus and data, grouped by ownership",
  "preset": "classic",
  "direction": "LR",
  "theme": "auto",
  "groups": [
    {
      "id": "sec",
      "name": "Security & Identity",
      "style": "security",
      "icon": "shield"
    },
    {
      "id": "fe",
      "name": "Frontend",
      "style": "frontend",
      "icon": "browser"
    },
    {
      "id": "be",
      "name": "Backend Services",
      "style": "backend",
      "icon": "server"
    },
    {
      "id": "bus",
      "name": "Message Bus",
      "style": "bus",
      "icon": "queue"
    },
    {
      "id": "wk",
      "name": "Workers",
      "style": "workers",
      "icon": "gear"
    },
    {
      "id": "data",
      "name": "Database",
      "style": "database",
      "icon": "database"
    }
  ],
  "nodes": [
    {
      "id": "auth",
      "name": "Auth Service",
      "role": "OAuth2 / OIDC",
      "icon": "lock",
      "group": "sec"
    },
    {
      "id": "web",
      "name": "Web App",
      "role": "React / TypeScript",
      "icon": "browser",
      "group": "fe"
    },
    {
      "id": "api",
      "name": "API Service",
      "role": "REST / GraphQL",
      "icon": "api",
      "group": "be"
    },
    {
      "id": "users",
      "name": "User Service",
      "icon": "user",
      "group": "be"
    },
    {
      "id": "billing",
      "name": "Billing Service",
      "icon": "payments",
      "group": "be"
    },
    {
      "id": "events",
      "name": "Event Bus",
      "role": "RabbitMQ / Kafka",
      "icon": "queue",
      "group": "bus"
    },
    {
      "id": "mail",
      "name": "Email Worker",
      "icon": "mail",
      "group": "wk"
    },
    {
      "id": "report",
      "name": "Report Worker",
      "icon": "chart",
      "group": "wk"
    },
    {
      "id": "pg",
      "name": "PostgreSQL",
      "role": "primary database",
      "icon": "database",
      "group": "data"
    }
  ],
  "edges": [
    {
      "from": "web",
      "to": "api",
      "label": "HTTPS"
    },
    {
      "from": "auth",
      "to": "api",
      "label": "validate token",
      "style": "dashed"
    },
    {
      "from": "api",
      "to": "users"
    },
    {
      "from": "api",
      "to": "billing"
    },
    {
      "from": "api",
      "to": "events",
      "tone": "orange"
    },
    {
      "from": "events",
      "to": "mail",
      "tone": "orange"
    },
    {
      "from": "events",
      "to": "report",
      "tone": "orange"
    },
    {
      "from": "users",
      "to": "pg"
    },
    {
      "from": "billing",
      "to": "pg"
    }
  ]
}
```

### archify_workflow

```json
{
  "title": "Order fulfilment",
  "direction": "TB",
  "theme": "auto",
  "groups": [
    {
      "id": "intake",
      "name": "Intake",
      "style": "frontend",
      "icon": "browser"
    },
    {
      "id": "ship",
      "name": "Fulfilment",
      "style": "backend",
      "icon": "container"
    }
  ],
  "nodes": [
    {
      "id": "order",
      "name": "Place order",
      "role": "customer",
      "icon": "user",
      "group": "intake"
    },
    {
      "id": "pay",
      "name": "Take payment",
      "role": "stripe",
      "icon": "payments",
      "group": "intake"
    },
    {
      "id": "pick",
      "name": "Pick & pack",
      "role": "warehouse",
      "icon": "storage",
      "group": "ship"
    },
    {
      "id": "send",
      "name": "Ship",
      "role": "carrier",
      "icon": "container",
      "group": "ship"
    },
    {
      "id": "notify",
      "name": "Notify customer",
      "role": "email",
      "icon": "mail"
    }
  ],
  "edges": [
    {
      "from": "order",
      "to": "pay"
    },
    {
      "from": "pay",
      "to": "pick",
      "label": "paid"
    },
    {
      "from": "pick",
      "to": "send"
    },
    {
      "from": "send",
      "to": "notify",
      "label": "tracking link"
    },
    {
      "from": "pay",
      "to": "notify",
      "label": "receipt",
      "style": "dashed"
    }
  ]
}
```

### archify_sequence

```json
{
  "title": "Cache miss request sequence",
  "subtitle": "A dashboard request that misses the cache and falls through to Postgres",
  "theme": "auto",
  "preset": "classic",
  "participants": [
    {
      "id": "web",
      "name": "Web App",
      "role": "React UI",
      "icon": "browser",
      "tone": "blue"
    },
    {
      "id": "api",
      "name": "API",
      "role": "request handler",
      "icon": "api",
      "tone": "green"
    },
    {
      "id": "auth",
      "name": "Auth",
      "role": "JWT verify",
      "icon": "shield",
      "tone": "red"
    },
    {
      "id": "cache",
      "name": "Redis",
      "role": "cache",
      "icon": "cache",
      "tone": "orange"
    },
    {
      "id": "db",
      "name": "Postgres",
      "role": "source of truth",
      "icon": "database",
      "tone": "purple"
    }
  ],
  "messages": [
    {
      "from": "web",
      "to": "api",
      "label": "GET /dashboard"
    },
    {
      "from": "api",
      "to": "auth",
      "label": "verify JWT"
    },
    {
      "from": "auth",
      "to": "api",
      "label": "claims ok",
      "style": "dashed"
    },
    {
      "from": "api",
      "to": "cache",
      "label": "read cache"
    },
    {
      "from": "cache",
      "to": "api",
      "label": "miss",
      "style": "dashed"
    },
    {
      "from": "api",
      "to": "db",
      "label": "SELECT widgets",
      "note": "indexed by account"
    },
    {
      "from": "db",
      "to": "api",
      "label": "rows",
      "style": "dashed"
    },
    {
      "from": "api",
      "to": "cache",
      "label": "set cache",
      "tone": "orange"
    },
    {
      "from": "api",
      "to": "api",
      "label": "emit trace"
    },
    {
      "from": "api",
      "to": "web",
      "label": "200 OK",
      "style": "dashed"
    }
  ]
}
```

### llm_2d

```json
{
  "title": "Decoder-only transformer",
  "subtitle": "Grouped view of a 7B parameter language model",
  "theme": "dark",
  "layers": [
    {
      "id": "tokens",
      "label": "Token IDs",
      "kind": "input",
      "shape": [
        2048
      ],
      "note": "BPE token sequence"
    },
    {
      "id": "embed",
      "label": "Token embedding",
      "kind": "embedding",
      "shape": [
        2048,
        4096
      ]
    },
    {
      "id": "attn",
      "label": "Grouped-query attention",
      "kind": "attention",
      "shape": [
        32,
        128
      ],
      "repeat": 32,
      "note": "32 query heads, 8 key/value heads"
    },
    {
      "id": "ffn",
      "label": "SwiGLU feed-forward",
      "kind": "feedforward",
      "shape": [
        4096,
        11008
      ],
      "repeat": 32
    },
    {
      "id": "norm",
      "label": "RMSNorm",
      "kind": "normalization",
      "shape": [
        4096
      ]
    },
    {
      "id": "logits",
      "label": "Vocabulary logits",
      "kind": "output",
      "shape": [
        32000
      ]
    }
  ],
  "connections": [
    {
      "from": "tokens",
      "to": "embed"
    },
    {
      "from": "embed",
      "to": "attn",
      "label": "hidden states"
    },
    {
      "from": "attn",
      "to": "ffn",
      "label": "residual stream"
    },
    {
      "from": "ffn",
      "to": "norm"
    },
    {
      "from": "norm",
      "to": "logits"
    },
    {
      "from": "embed",
      "to": "norm",
      "label": "residual path",
      "style": "dashed"
    }
  ]
}
```

### llm_3d

```json
{
  "title": "Decoder-only transformer",
  "subtitle": "Grouped view of a 7B parameter language model",
  "theme": "dark",
  "layers": [
    {
      "id": "tokens",
      "label": "Token IDs",
      "kind": "input",
      "shape": [
        2048
      ],
      "note": "BPE token sequence"
    },
    {
      "id": "embed",
      "label": "Token embedding",
      "kind": "embedding",
      "shape": [
        2048,
        4096
      ]
    },
    {
      "id": "attn",
      "label": "Grouped-query attention",
      "kind": "attention",
      "shape": [
        32,
        128
      ],
      "repeat": 32,
      "note": "32 query heads, 8 key/value heads"
    },
    {
      "id": "ffn",
      "label": "SwiGLU feed-forward",
      "kind": "feedforward",
      "shape": [
        4096,
        11008
      ],
      "repeat": 32
    },
    {
      "id": "norm",
      "label": "RMSNorm",
      "kind": "normalization",
      "shape": [
        4096
      ]
    },
    {
      "id": "logits",
      "label": "Vocabulary logits",
      "kind": "output",
      "shape": [
        32000
      ]
    }
  ],
  "connections": [
    {
      "from": "tokens",
      "to": "embed"
    },
    {
      "from": "embed",
      "to": "attn",
      "label": "hidden states"
    },
    {
      "from": "attn",
      "to": "ffn",
      "label": "residual stream"
    },
    {
      "from": "ffn",
      "to": "norm"
    },
    {
      "from": "norm",
      "to": "logits"
    },
    {
      "from": "embed",
      "to": "norm",
      "label": "residual path",
      "style": "dashed"
    }
  ]
}
```

### db_schema

```json
{
  "title": "Blog",
  "tables": [
    {
      "name": "users",
      "group": "Accounts",
      "columns": [
        {
          "name": "id",
          "type": "uuid",
          "pk": true
        },
        {
          "name": "handle",
          "type": "text",
          "unique": true,
          "nullable": false
        },
        {
          "name": "bio",
          "type": "text"
        }
      ]
    },
    {
      "name": "posts",
      "note": "Published and draft posts",
      "columns": [
        {
          "name": "id",
          "type": "uuid",
          "pk": true
        },
        {
          "name": "author_id",
          "type": "uuid",
          "nullable": false,
          "fk": {
            "table": "users",
            "column": "id"
          }
        },
        {
          "name": "title",
          "type": "text",
          "nullable": false
        },
        {
          "name": "published_at",
          "type": "timestamptz"
        }
      ]
    },
    {
      "name": "tags",
      "columns": [
        {
          "name": "id",
          "type": "serial",
          "pk": true
        },
        {
          "name": "label",
          "type": "text",
          "unique": true
        }
      ]
    },
    {
      "name": "post_tags",
      "columns": [
        {
          "name": "post_id",
          "type": "uuid",
          "pk": true,
          "fk": "posts.id"
        },
        {
          "name": "tag_id",
          "type": "int",
          "pk": true,
          "fk": "tags.id"
        }
      ]
    }
  ]
}
```

### dependency_graph

```json
{
  "name": "storefront",
  "version": "2.4.0",
  "license": "MIT",
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "zod": "^3.23.8",
    "@tanstack/react-query": "^5.59.0"
  },
  "peerDependencies": {
    "typescript": ">=5.4"
  },
  "optionalDependencies": {
    "fsevents": "^2.3.3"
  },
  "devDependencies": {
    "vite": "^5.4.10",
    "vitest": "^2.1.4",
    "eslint": "^9.14.0"
  }
}
```

### state_machine

```json
{
  "id": "order",
  "title": "Order lifecycle",
  "initial": "cart",
  "context": {
    "items": 0,
    "total": 0
  },
  "states": {
    "cart": {
      "description": "The shopper is still adding items.",
      "on": {
        "ADD_ITEM": {
          "actions": [
            "addItem"
          ]
        },
        "CHECKOUT": {
          "target": "checkout",
          "guard": "hasItems"
        }
      }
    },
    "checkout": {
      "initial": "address",
      "entry": [
        "startTimer"
      ],
      "exit": [
        "stopTimer"
      ],
      "description": "Address, then payment. Help keeps your place.",
      "states": {
        "address": {
          "on": {
            "NEXT": "payment"
          }
        },
        "payment": {
          "on": {
            "BACK": "address",
            "PAY": [
              {
                "target": "#order.fulfilment",
                "guard": "cardOk",
                "actions": [
                  "charge"
                ]
              },
              {
                "target": "declined",
                "guard": "cardDeclined"
              }
            ]
          }
        },
        "declined": {
          "on": {
            "RETRY": "payment"
          }
        },
        "hist": {
          "type": "history"
        }
      },
      "on": {
        "HELP": "help",
        "CANCEL": "cancelled"
      }
    },
    "help": {
      "description": "A support chat; resuming returns to the same checkout step.",
      "on": {
        "RESUME": "checkout.hist"
      }
    },
    "fulfilment": {
      "type": "parallel",
      "description": "Packing and invoicing run at the same time.",
      "onDone": "delivered",
      "states": {
        "packing": {
          "initial": "picking",
          "states": {
            "picking": {
              "on": {
                "PACKED": "packed"
              }
            },
            "packed": {
              "type": "final"
            }
          }
        },
        "invoice": {
          "initial": "drafting",
          "states": {
            "drafting": {
              "on": {
                "SEND": "sent"
              }
            },
            "sent": {
              "type": "final"
            }
          }
        }
      },
      "on": {
        "CANCEL": {
          "target": "cancelled",
          "actions": [
            "refund"
          ]
        }
      }
    },
    "delivered": {
      "type": "final",
      "entry": [
        "notifyCustomer"
      ]
    },
    "cancelled": {
      "type": "final"
    }
  }
}
```

### agent_trace

```json
{
  "title": "Support agent: refund window question",
  "model": "gpt-4o",
  "steps": [
    {
      "id": "agent",
      "kind": "subagent",
      "name": "Support agent",
      "start_ms": 0,
      "end_ms": 4210
    },
    {
      "id": "ask",
      "parent": "agent",
      "kind": "user",
      "name": "What is the refund window for annual plans?",
      "start_ms": 0,
      "end_ms": 15,
      "input": "Hi! I bought the annual Pro plan three weeks ago. What is the refund window for annual plans, and can I still get my money back?"
    },
    {
      "id": "moderate",
      "parent": "agent",
      "kind": "guardrail",
      "name": "Input moderation",
      "tool": "omni-moderation",
      "start_ms": 15,
      "end_ms": 140,
      "output": "flagged: false"
    },
    {
      "id": "plan",
      "parent": "agent",
      "kind": "llm",
      "name": "Plan the answer",
      "model": "gpt-4o-mini",
      "start_ms": 140,
      "end_ms": 910,
      "tokens": {
        "in": 612,
        "out": 74,
        "cached": 512
      },
      "cost_usd": 0.00014,
      "output": "Call search_policies(\"refund annual plan\"), then get_customer_plan(customer_id), then calculate_refund."
    },
    {
      "id": "search",
      "parent": "agent",
      "kind": "retrieval",
      "name": "Search policy docs",
      "tool": "elasticsearch",
      "start_ms": 910,
      "end_ms": 1270,
      "input": "refund window annual plan",
      "docs": [
        {
          "title": "Refunds and cancellations",
          "score": 0.91,
          "source": "https://example.com/help/refunds"
        },
        {
          "title": "Annual plan terms",
          "score": 0.84,
          "source": "https://example.com/legal/annual-terms"
        },
        {
          "title": "Changing your plan",
          "score": 0.42,
          "source": "https://example.com/help/change-plan"
        }
      ]
    },
    {
      "id": "lookup",
      "parent": "agent",
      "kind": "tool",
      "name": "get_customer_plan",
      "tool": "postgres",
      "start_ms": 1270,
      "end_ms": 1730,
      "input": "{\"customer_id\": \"c_4821\"}",
      "status": "error",
      "note": "Connection timed out after 450 ms"
    },
    {
      "id": "lookup-retry",
      "parent": "agent",
      "kind": "tool",
      "name": "get_customer_plan",
      "tool": "postgres",
      "start_ms": 1730,
      "end_ms": 1980,
      "input": "{\"customer_id\": \"c_4821\"}",
      "output": "{\"plan\": \"pro-annual\", \"purchased\": \"2026-10-17\", \"paid_usd\": 240}",
      "status": "retry",
      "note": "Second attempt succeeded"
    },
    {
      "id": "refund",
      "parent": "agent",
      "kind": "tool",
      "name": "calculate_refund",
      "start_ms": 1980,
      "end_ms": 2140,
      "input": "{\"plan\": \"pro-annual\", \"days_since_purchase\": 21}",
      "output": "{\"eligible\": true, \"amount_usd\": 240, \"window_days\": 30}"
    },
    {
      "id": "answer",
      "parent": "agent",
      "kind": "llm",
      "name": "Compose the answer",
      "model": "gpt-4o",
      "start_ms": 2140,
      "end_ms": 4120,
      "tokens": {
        "in": 2310,
        "out": 186,
        "cached": 1024
      },
      "cost_usd": 0.0061,
      "input": "System: answer from the retrieved policy only.\nContext: Refunds and cancellations; Annual plan terms.\nCustomer plan: pro-annual, 21 days ago.",
      "output": "Annual plans can be refunded in full within 30 days of purchase. You bought yours 21 days ago, so you are still inside the window: I can refund the full $240 now."
    },
    {
      "id": "reply",
      "parent": "agent",
      "kind": "reply",
      "name": "Full refund available (21 of 30 days)",
      "start_ms": 4120,
      "end_ms": 4210,
      "output": "Annual plans can be refunded in full within 30 days of purchase. You bought yours 21 days ago, so you are still inside the window: I can refund the full $240 now."
    }
  ]
}
```

### c4_model

```json
{
  "title": "Internet banking system",
  "description": "Customers view balances and make payments online",
  "people": [
    {
      "id": "customer",
      "name": "Personal Banking Customer",
      "description": "A customer of the bank, with personal bank accounts"
    },
    {
      "id": "staff",
      "name": "Back Office Staff",
      "description": "Bank staff who handle customer support",
      "external": false
    }
  ],
  "systems": [
    {
      "id": "banking",
      "name": "Internet Banking System",
      "description": "Lets customers view their accounts and make payments",
      "containers": [
        {
          "id": "web",
          "name": "Web Application",
          "technology": "Java and Spring MVC",
          "kind": "app",
          "description": "Delivers the static content and the single-page app"
        },
        {
          "id": "spa",
          "name": "Single-Page App",
          "technology": "TypeScript and React",
          "kind": "web",
          "service": "react",
          "description": "All the internet banking features, in the browser"
        },
        {
          "id": "api",
          "name": "API Application",
          "technology": "Java and Spring Boot",
          "kind": "app",
          "description": "Internet banking features over a JSON/HTTPS API",
          "components": [
            {
              "id": "signin",
              "name": "Sign In Controller",
              "technology": "Spring MVC Rest Controller",
              "description": "Lets users sign in to the banking system"
            },
            {
              "id": "accounts",
              "name": "Accounts Summary Controller",
              "technology": "Spring MVC Rest Controller",
              "description": "Lists a customer's accounts and balances"
            },
            {
              "id": "security",
              "name": "Security Component",
              "technology": "Spring Bean",
              "description": "Signing in, changing passwords"
            },
            {
              "id": "facade",
              "name": "Mainframe Banking Facade",
              "technology": "Spring Bean",
              "description": "A facade onto the mainframe banking system"
            },
            {
              "id": "notifier",
              "name": "Notification Publisher",
              "technology": "Spring Bean",
              "description": "Publishes account events for e-mail delivery"
            }
          ]
        },
        {
          "id": "events",
          "name": "Account Events",
          "technology": "Amazon SQS",
          "kind": "queue",
          "service": "aws:sqs",
          "description": "Account changes waiting to be e-mailed"
        },
        {
          "id": "mailer",
          "name": "Mail Sender",
          "technology": "AWS Lambda",
          "kind": "function",
          "service": "aws:lambda",
          "description": "Turns account events into e-mails"
        },
        {
          "id": "db",
          "name": "Database",
          "technology": "PostgreSQL",
          "kind": "db",
          "service": "postgres",
          "description": "Users, hashed credentials and access logs"
        }
      ]
    },
    {
      "id": "mainframe",
      "name": "Mainframe Banking System",
      "description": "Core banking: customers, accounts, transactions",
      "external": true
    },
    {
      "id": "email",
      "name": "E-mail System",
      "description": "The internal Microsoft Exchange e-mail system",
      "external": true
    }
  ],
  "relations": [
    {
      "from": "customer",
      "to": "web",
      "label": "Visits",
      "technology": "HTTPS"
    },
    {
      "from": "customer",
      "to": "spa",
      "label": "Views balances, makes payments"
    },
    {
      "from": "web",
      "to": "spa",
      "label": "Delivers to the browser"
    },
    {
      "from": "spa",
      "to": "signin",
      "label": "Signs in",
      "technology": "JSON/HTTPS"
    },
    {
      "from": "spa",
      "to": "accounts",
      "label": "Reads accounts",
      "technology": "JSON/HTTPS"
    },
    {
      "from": "signin",
      "to": "security",
      "label": "Uses"
    },
    {
      "from": "accounts",
      "to": "facade",
      "label": "Uses"
    },
    {
      "from": "security",
      "to": "db",
      "label": "Reads and writes",
      "technology": "JDBC"
    },
    {
      "from": "facade",
      "to": "mainframe",
      "label": "Uses",
      "technology": "XML/HTTPS"
    },
    {
      "from": "accounts",
      "to": "notifier",
      "label": "Uses"
    },
    {
      "from": "notifier",
      "to": "events",
      "label": "Publishes account events",
      "technology": "SQS",
      "async": true
    },
    {
      "from": "mailer",
      "to": "events",
      "label": "Polls",
      "technology": "SQS",
      "async": true
    },
    {
      "from": "mailer",
      "to": "email",
      "label": "Sends e-mail",
      "technology": "SMTP"
    },
    {
      "from": "email",
      "to": "customer",
      "label": "Sends e-mails to"
    },
    {
      "from": "staff",
      "to": "mainframe",
      "label": "Uses"
    }
  ]
}
```

### timeline

```json
{
  "title": "Product roadmap 2026–27",
  "today": "2026-11-07",
  "lanes": [
    {
      "id": "platform",
      "name": "Platform",
      "color": "#6366f1"
    },
    {
      "id": "product",
      "name": "Product",
      "color": "#0ea5e9"
    },
    {
      "id": "gtm",
      "name": "Go-to-market",
      "color": "#f59e0b"
    }
  ],
  "items": [
    {
      "id": "beta-phase",
      "lane": "product",
      "name": "Public beta",
      "kind": "phase",
      "start": "2026-11-02",
      "end": "2027-01-29",
      "status": "active",
      "note": "Invite-only beta with weekly releases."
    },
    {
      "id": "auth",
      "lane": "platform",
      "name": "SSO and SCIM",
      "start": "2026-09-01",
      "end": "2026-10-23",
      "status": "done",
      "owner": "Priya",
      "link": "https://example.com/roadmap/sso"
    },
    {
      "id": "api",
      "lane": "platform",
      "name": "Public API v2",
      "start": "2026-10-12",
      "end": "2026-12-11",
      "status": "active",
      "owner": "Marco",
      "progress": 55,
      "depends_on": [
        "auth"
      ],
      "note": "REST and webhooks; GraphQL follows."
    },
    {
      "id": "billing",
      "lane": "platform",
      "name": "Usage billing",
      "start": "2026-11-16",
      "end": "2027-01-22",
      "status": "blocked",
      "owner": "Marco",
      "progress": 10,
      "depends_on": [
        "api"
      ],
      "note": "Waiting on the payment provider contract."
    },
    {
      "id": "editor",
      "lane": "product",
      "name": "New editor",
      "start": "2026-09-14",
      "end": "2026-11-20",
      "status": "active",
      "owner": "Ada",
      "progress": 80
    },
    {
      "id": "beta",
      "lane": "product",
      "name": "Beta opens",
      "kind": "milestone",
      "start": "2026-11-02",
      "status": "done",
      "depends_on": [
        "editor",
        "auth"
      ]
    },
    {
      "id": "mobile",
      "lane": "product",
      "name": "Mobile app",
      "start": "2026-12-01",
      "end": "2027-02-26",
      "status": "at-risk",
      "owner": "Ada",
      "progress": 15,
      "depends_on": [
        "api"
      ]
    },
    {
      "id": "ga",
      "lane": "product",
      "name": "v2.0 GA",
      "kind": "release",
      "start": "2027-03-01",
      "status": "planned",
      "depends_on": [
        "billing",
        "mobile"
      ],
      "link": "https://example.com/releases/2.0"
    },
    {
      "id": "pricing",
      "lane": "gtm",
      "name": "Pricing study",
      "start": "2026-10-05",
      "end": "2026-11-27",
      "status": "active",
      "owner": "Lena",
      "progress": 60
    },
    {
      "id": "launch",
      "lane": "gtm",
      "name": "Launch campaign",
      "start": "2027-01-11",
      "end": "2027-03-12",
      "status": "planned",
      "owner": "Lena",
      "depends_on": [
        "pricing"
      ]
    },
    {
      "id": "summit",
      "lane": "gtm",
      "name": "Customer summit",
      "kind": "milestone",
      "start": "2027-02-10",
      "status": "planned"
    }
  ]
}
```

## Verdict

End with exactly one of:

- `ALL_PLUGIN_SMOKE_TEST: PASS` when every applicable stage was verified.
- `ALL_PLUGIN_SMOKE_TEST: FAIL - <types and first failing stages>` for observed failures.
- `ALL_PLUGIN_SMOKE_TEST: UNVERIFIED - <stages the client could not inspect>` when checks remain unavailable.
