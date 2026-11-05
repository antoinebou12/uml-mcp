"""Examples exposed through ``uml://examples`` and ``uml://templates``."""

from __future__ import annotations

import json
from typing import Any


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2)


EXAMPLE = _dump(
    {
        "title": "SaaS stack",
        "direction": "LR",
        "theme": "dark",
        "groups": [
            {"id": "vercel", "name": "Vercel", "style": "plain"},
            {"id": "github", "name": "GitHub", "style": "vendor", "tone": "blue"},
        ],
        "nodes": [
            {"id": "user", "name": "User", "role": "browser", "icon": "user"},
            {
                "id": "web",
                "name": "Next.js",
                "role": "frontend",
                "icon": "browser",
                "group": "vercel",
            },
            {
                "id": "api",
                "name": "Hono",
                "role": "api routes",
                "icon": "function",
                "group": "vercel",
            },
            {
                "id": "db",
                "name": "Neon",
                "role": "serverless postgres",
                "icon": "database",
            },
            {"id": "auth", "name": "Clerk", "role": "auth", "icon": "lock"},
            {"id": "pay", "name": "Stripe", "role": "payments", "icon": "payments"},
            {
                "id": "ci",
                "name": "GitHub Actions",
                "role": "ci",
                "icon": "git",
                "group": "github",
            },
        ],
        "edges": [
            {"from": "user", "to": "web", "label": "HTTPS"},
            {"from": "web", "to": "api", "label": "RPC"},
            {"from": "api", "to": "db", "label": "SQL"},
            {"from": "api", "to": "auth", "label": "session", "tone": "neutral"},
            {"from": "api", "to": "pay", "label": "checkout", "tone": "neutral"},
            {"from": "ci", "to": "web", "label": "deploy", "style": "dashed"},
        ],
    }
)

CLOUD_EXAMPLE = _dump(
    {
        "title": "Cloud architecture",
        "direction": "LR",
        "theme": "dark",
        "groups": [
            {"id": "cloud", "name": "Microsoft Azure", "style": "azure"},
            {
                "id": "region",
                "name": "Region Japan East",
                "style": "plain",
                "parent": "cloud",
            },
            {
                "id": "vnet",
                "name": "Virtual network",
                "style": "azure",
                "parent": "region",
            },
        ],
        "nodes": [
            {"id": "user", "name": "User", "role": "browser", "icon": "user"},
            {
                "id": "edge",
                "name": "Front Door",
                "role": "cdn",
                "icon": "cdn",
                "group": "cloud",
            },
            {
                "id": "app",
                "name": "App Service",
                "role": "api",
                "icon": "server",
                "group": "region",
            },
            {
                "id": "blob",
                "name": "Blob Storage",
                "role": "static assets",
                "icon": "storage",
                "group": "region",
            },
            {
                "id": "sql",
                "name": "SQL Database",
                "role": "private endpoint",
                "icon": "database",
                "group": "vnet",
            },
            {
                "id": "redis",
                "name": "Managed Redis",
                "role": "private endpoint",
                "icon": "cache",
                "group": "vnet",
            },
        ],
        "edges": [
            {"from": "user", "to": "edge", "label": "HTTPS"},
            {"from": "edge", "to": "app", "label": "/api/*"},
            {"from": "edge", "to": "blob", "label": "/*"},
            {"from": "app", "to": "sql", "label": "SQL"},
            {"from": "app", "to": "redis", "label": "cache", "tone": "neutral"},
        ],
    }
)

TEMPLATE = _dump(
    {
        "title": "My stack",
        "direction": "LR",
        "theme": "dark",
        "nodes": [
            {"id": "client", "name": "Client", "role": "browser", "icon": "browser"},
            {"id": "api", "name": "API", "role": "service", "icon": "server"},
            {"id": "db", "name": "Database", "role": "postgres", "icon": "database"},
        ],
        "edges": [
            {"from": "client", "to": "api", "label": "HTTPS"},
            {"from": "api", "to": "db", "label": "SQL"},
        ],
    }
)
