"""Example sources: every one renders, and the docs and skills quote them."""

from __future__ import annotations

import json

#: A web app's package.json: runtime, dev, peer and optional dependencies.
EXAMPLE = json.dumps(
    {
        "name": "storefront",
        "version": "2.4.0",
        "license": "MIT",
        "dependencies": {
            "react": "^18.3.1",
            "react-dom": "^18.3.1",
            "zod": "^3.23.8",
            "@tanstack/react-query": "^5.59.0",
        },
        "peerDependencies": {"typescript": ">=5.4"},
        "optionalDependencies": {"fsevents": "^2.3.3"},
        "devDependencies": {
            "vite": "^5.4.10",
            "vitest": "^2.1.4",
            "eslint": "^9.14.0",
        },
    },
    indent=2,
)

#: The smallest useful source.
TEMPLATE = json.dumps(
    {"name": "my-app", "dependencies": {"express": "^4.21.0"}}, indent=2
)

#: A generic graph with transitive levels, licences and two versions of one package.
GRAPH = json.dumps(
    {
        "title": "billing-service dependencies",
        "ecosystem": "pypi",
        "root": "billing-service",
        "nodes": [
            {"id": "billing-service", "version": "1.0.0", "license": "Apache-2.0"},
            {"id": "fastapi@0.115.4", "version": "0.115.4", "license": "MIT"},
            {"id": "starlette@0.41.2", "version": "0.41.2", "license": "BSD-3-Clause"},
            {"id": "pydantic@2.9.2", "version": "2.9.2", "license": "MIT"},
            {"id": "anyio@4.6.2", "version": "4.6.2", "license": "MIT"},
            {"id": "anyio@3.7.1", "version": "3.7.1", "license": "MIT"},
            {"id": "httpx@0.27.2", "version": "0.27.2", "license": "BSD-3-Clause"},
            {"id": "pytest@8.3.3", "version": "8.3.3", "license": "MIT", "dev": True},
        ],
        "edges": [
            {"from": "billing-service", "to": "fastapi@0.115.4", "range": ">=0.115"},
            {"from": "billing-service", "to": "httpx@0.27.2", "range": "~=0.27"},
            {"from": "billing-service", "to": "pytest@8.3.3", "range": ">=8"},
            {"from": "fastapi@0.115.4", "to": "starlette@0.41.2"},
            {"from": "fastapi@0.115.4", "to": "pydantic@2.9.2"},
            {"from": "starlette@0.41.2", "to": "anyio@4.6.2"},
            {"from": "httpx@0.27.2", "to": "anyio@3.7.1"},
        ],
    },
    indent=2,
)

REQUIREMENTS = """\
# web
fastapi>=0.115  # API
uvicorn[standard]==0.32.0
httpx~=0.27 ; python_version >= "3.10"
-r dev.txt
"""
