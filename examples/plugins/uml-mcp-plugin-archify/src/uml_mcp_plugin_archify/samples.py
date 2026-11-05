"""Examples exposed through ``uml://examples`` and ``uml://templates``."""

from __future__ import annotations

import json
from typing import Any


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2)


ARCHITECTURE = _dump(
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
                "icon": "shield",
            },
            {"id": "fe", "name": "Frontend", "style": "frontend", "icon": "browser"},
            {
                "id": "be",
                "name": "Backend Services",
                "style": "backend",
                "icon": "server",
            },
            {"id": "bus", "name": "Message Bus", "style": "bus", "icon": "queue"},
            {"id": "wk", "name": "Workers", "style": "workers", "icon": "gear"},
            {"id": "data", "name": "Database", "style": "database", "icon": "database"},
        ],
        "nodes": [
            {
                "id": "auth",
                "name": "Auth Service",
                "role": "OAuth2 / OIDC",
                "icon": "lock",
                "group": "sec",
            },
            {
                "id": "web",
                "name": "Web App",
                "role": "React / TypeScript",
                "icon": "browser",
                "group": "fe",
            },
            {
                "id": "api",
                "name": "API Service",
                "role": "REST / GraphQL",
                "icon": "api",
                "group": "be",
            },
            {"id": "users", "name": "User Service", "icon": "user", "group": "be"},
            {
                "id": "billing",
                "name": "Billing Service",
                "icon": "payments",
                "group": "be",
            },
            {
                "id": "events",
                "name": "Event Bus",
                "role": "RabbitMQ / Kafka",
                "icon": "queue",
                "group": "bus",
            },
            {"id": "mail", "name": "Email Worker", "icon": "mail", "group": "wk"},
            {"id": "report", "name": "Report Worker", "icon": "chart", "group": "wk"},
            {
                "id": "pg",
                "name": "PostgreSQL",
                "role": "primary database",
                "icon": "database",
                "group": "data",
            },
        ],
        "edges": [
            {"from": "web", "to": "api", "label": "HTTPS"},
            {"from": "auth", "to": "api", "label": "validate token", "style": "dashed"},
            {"from": "api", "to": "users"},
            {"from": "api", "to": "billing"},
            {"from": "api", "to": "events", "tone": "orange"},
            {"from": "events", "to": "mail", "tone": "orange"},
            {"from": "events", "to": "report", "tone": "orange"},
            {"from": "users", "to": "pg"},
            {"from": "billing", "to": "pg"},
        ],
    }
)

WORKFLOW = _dump(
    {
        "title": "Order fulfilment",
        "direction": "TB",
        "theme": "auto",
        "groups": [
            {"id": "intake", "name": "Intake", "style": "frontend", "icon": "browser"},
            {
                "id": "ship",
                "name": "Fulfilment",
                "style": "backend",
                "icon": "container",
            },
        ],
        "nodes": [
            {
                "id": "order",
                "name": "Place order",
                "role": "customer",
                "icon": "user",
                "group": "intake",
            },
            {
                "id": "pay",
                "name": "Take payment",
                "role": "stripe",
                "icon": "payments",
                "group": "intake",
            },
            {
                "id": "pick",
                "name": "Pick & pack",
                "role": "warehouse",
                "icon": "storage",
                "group": "ship",
            },
            {
                "id": "send",
                "name": "Ship",
                "role": "carrier",
                "icon": "container",
                "group": "ship",
            },
            {
                "id": "notify",
                "name": "Notify customer",
                "role": "email",
                "icon": "mail",
            },
        ],
        "edges": [
            {"from": "order", "to": "pay"},
            {"from": "pay", "to": "pick", "label": "paid"},
            {"from": "pick", "to": "send"},
            {"from": "send", "to": "notify", "label": "tracking link"},
            {"from": "pay", "to": "notify", "label": "receipt", "style": "dashed"},
        ],
    }
)

WORKFLOW_TEMPLATE = _dump(
    {
        "title": "My flow",
        "direction": "LR",
        "theme": "auto",
        "nodes": [
            {"id": "a", "name": "Step A", "icon": "user"},
            {"id": "b", "name": "Step B", "icon": "gear"},
            {"id": "c", "name": "Step C", "icon": "database"},
        ],
        "edges": [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c", "label": "result"},
        ],
    }
)

SEQUENCE = _dump(
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
                "tone": "blue",
            },
            {
                "id": "api",
                "name": "API",
                "role": "request handler",
                "icon": "api",
                "tone": "green",
            },
            {
                "id": "auth",
                "name": "Auth",
                "role": "JWT verify",
                "icon": "shield",
                "tone": "red",
            },
            {
                "id": "cache",
                "name": "Redis",
                "role": "cache",
                "icon": "cache",
                "tone": "orange",
            },
            {
                "id": "db",
                "name": "Postgres",
                "role": "source of truth",
                "icon": "database",
                "tone": "purple",
            },
        ],
        "messages": [
            {"from": "web", "to": "api", "label": "GET /dashboard"},
            {"from": "api", "to": "auth", "label": "verify JWT"},
            {"from": "auth", "to": "api", "label": "claims ok", "style": "dashed"},
            {"from": "api", "to": "cache", "label": "read cache"},
            {"from": "cache", "to": "api", "label": "miss", "style": "dashed"},
            {
                "from": "api",
                "to": "db",
                "label": "SELECT widgets",
                "note": "indexed by account",
            },
            {"from": "db", "to": "api", "label": "rows", "style": "dashed"},
            {"from": "api", "to": "cache", "label": "set cache", "tone": "orange"},
            {"from": "api", "to": "api", "label": "emit trace"},
            {"from": "api", "to": "web", "label": "200 OK", "style": "dashed"},
        ],
    }
)

SEQUENCE_TEMPLATE = _dump(
    {
        "title": "My sequence",
        "participants": [
            {"id": "client", "name": "Client", "icon": "user"},
            {"id": "server", "name": "Server", "icon": "server"},
        ],
        "messages": [
            {"from": "client", "to": "server", "label": "request"},
            {"from": "server", "to": "client", "label": "response", "style": "dashed"},
        ],
    }
)
