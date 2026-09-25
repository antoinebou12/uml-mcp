# Shared state for multi-replica deployments

- **Priority:** P2   **Size:** L
- **Why:** rate limits, the dashboard audit buffer and AG-UI start/events runs are per process today.
- **Done when:** optional `state: {backend: redis, url_env: REDIS_URL}` in uml-mcp.yaml; token buckets and AG-UI runs shared; tests with fakeredis.
