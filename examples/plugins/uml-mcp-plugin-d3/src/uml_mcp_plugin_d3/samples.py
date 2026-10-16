"""A full example and a minimal template for each diagram type.

They are what ``uml://examples`` and ``uml://templates`` show, so they are how a model
learns the source format. Every one of them is rendered by the tests.
"""

from __future__ import annotations

import json
from typing import Any


def _dump(spec: dict[str, Any]) -> str:
    return json.dumps(spec, indent=2)


FORCE_EXAMPLE = _dump(
    {
        "title": "Service dependencies",
        "directed": True,
        "nodes": [
            {"id": "web", "label": "Web app", "group": "frontend", "size": 1.4},
            {"id": "mobile", "label": "Mobile app", "group": "frontend"},
            {"id": "gateway", "label": "API gateway", "group": "edge", "size": 1.6},
            {"id": "auth", "label": "Auth", "group": "backend"},
            {"id": "orders", "label": "Orders", "group": "backend", "size": 1.3},
            {"id": "billing", "label": "Billing", "group": "backend"},
            {
                "id": "db",
                "label": "Postgres",
                "group": "data",
                "size": 1.4,
                "note": "primary + replica",
            },
            {"id": "queue", "label": "Events", "group": "data"},
        ],
        "links": [
            {"source": "web", "target": "gateway"},
            {"source": "mobile", "target": "gateway"},
            {"source": "gateway", "target": "auth"},
            {"source": "gateway", "target": "orders", "label": "REST"},
            {"source": "orders", "target": "db"},
            {"source": "orders", "target": "queue", "label": "publishes"},
            {"source": "billing", "target": "queue", "label": "consumes"},
            {"source": "billing", "target": "db"},
        ],
    }
)

FORCE_TEMPLATE = _dump(
    {
        "nodes": [
            {"id": "a", "group": "x"},
            {"id": "b", "group": "x"},
            {"id": "c", "group": "y"},
        ],
        "links": [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}],
    }
)

ARCHITECTURE_EXAMPLE = _dump(
    {
        "title": "Orders service on AWS",
        "provider": "aws",
        "groups": [
            {"id": "region", "label": "eu-west-1", "type": "region"},
            {
                "id": "vpc",
                "label": "VPC 10.0.0.0/16",
                "type": "vpc",
                "parent": "region",
            },
            {
                "id": "private",
                "label": "Private subnets",
                "type": "subnet",
                "parent": "vpc",
            },
        ],
        "nodes": [
            {"id": "users", "label": "Users", "kind": "user"},
            {"id": "cdn", "label": "CDN", "service": "aws:cloudfront"},
            {
                "id": "api",
                "label": "API",
                "service": "aws:apigateway",
                "group": "vpc",
                "inputs": ["https"],
                "outputs": ["invoke"],
            },
            {
                "id": "orders",
                "label": "Orders",
                "service": "aws:lambda",
                "group": "private",
                "inputs": ["invoke"],
                "outputs": ["rows", "events"],
            },
            {
                "id": "db",
                "label": "Orders table",
                "service": "aws:dynamodb",
                "group": "private",
            },
            {
                "id": "queue",
                "label": "Order events",
                "service": "aws:sqs",
                "group": "private",
            },
            {
                "id": "mail",
                "label": "Notifier",
                "service": "aws:lambda",
                "group": "private",
            },
        ],
        "links": [
            {"from": "users", "to": "cdn", "label": "HTTPS"},
            {"from": "cdn", "to": "api:https"},
            {"from": "api:invoke", "to": "orders:invoke"},
            {"from": "orders:rows", "to": "db", "label": "read / write"},
            {"from": "orders:events", "to": "queue", "style": "dashed"},
            {"from": "queue", "to": "mail", "style": "dashed"},
        ],
    }
)

ARCHITECTURE_TEMPLATE = _dump(
    {
        "title": "System",
        "provider": "generic",
        "nodes": [
            {"id": "client", "label": "Client", "kind": "user"},
            {
                "id": "api",
                "label": "API",
                "kind": "gateway",
                "inputs": ["http"],
                "outputs": ["sql"],
            },
            {"id": "db", "label": "Database", "kind": "database"},
        ],
        "links": [
            {"from": "client", "to": "api:http"},
            {"from": "api:sql", "to": "db"},
        ],
    }
)

TOPOLOGY_EXAMPLE = _dump(
    {
        "title": "Web application deployment",
        "provider": "generic",
        "groups": [
            {"id": "dmz", "label": "DMZ", "type": "zone"},
            {"id": "prod", "label": "Production", "type": "env"},
            {"id": "app", "label": "App tier", "type": "system", "parent": "prod"},
            {"id": "data", "label": "Data tier", "type": "system", "parent": "prod"},
        ],
        "nodes": [
            {"id": "client", "label": "Browsers", "kind": "user"},
            {"id": "fw", "label": "Firewall", "kind": "firewall", "group": "dmz"},
            {
                "id": "lb",
                "label": "Load balancer",
                "kind": "loadbalancer",
                "group": "dmz",
            },
            {
                "id": "web1",
                "label": "web-1",
                "service": "kubernetes:pod",
                "group": "app",
            },
            {
                "id": "web2",
                "label": "web-2",
                "service": "kubernetes:pod",
                "group": "app",
            },
            {"id": "cache", "label": "Redis", "kind": "cache", "group": "data"},
            {"id": "db", "label": "PostgreSQL", "kind": "database", "group": "data"},
        ],
        "links": [
            {"from": "client", "to": "fw", "label": "443"},
            {"from": "fw", "to": "lb"},
            {"from": "lb", "to": "web1"},
            {"from": "lb", "to": "web2"},
            {"from": "web1", "to": "cache"},
            {"from": "web2", "to": "cache"},
            {"from": "web1", "to": "db", "label": "5432"},
            {"from": "web2", "to": "db"},
        ],
    }
)

TOPOLOGY_TEMPLATE = _dump(
    {
        "title": "Deployment",
        "nodes": [
            {"id": "lb", "label": "Load balancer", "kind": "loadbalancer"},
            {"id": "app", "label": "App", "kind": "server"},
            {"id": "db", "label": "Database", "kind": "database"},
        ],
        "links": [{"from": "lb", "to": "app"}, {"from": "app", "to": "db"}],
    }
)

SAMPLES: dict[str, tuple[str, str]] = {
    "d3_force": (FORCE_EXAMPLE, FORCE_TEMPLATE),
    "d3_architecture": (ARCHITECTURE_EXAMPLE, ARCHITECTURE_TEMPLATE),
    "d3_topology": (TOPOLOGY_EXAMPLE, TOPOLOGY_TEMPLATE),
}
