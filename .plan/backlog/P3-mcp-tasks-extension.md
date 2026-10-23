# Tasks extension for long renders (SEP-2663)

- **Priority:** P3   **Size:** L
- **Depends on:** FastMCP / SDK support for `io.modelcontextprotocol/tasks`

## Why

Tasks moved out of core into an official extension with pollable `tasks/get` and `tasks/update`. Good fit for `generate_uml_batch` and `architecture_report` multi-diagram runs that outlive a single HTTP request on serverless.

## Scope

- Optional: return a task handle for large batches; clients poll `tasks/get`.
- Prefer URL-first partial results where possible so hosts without Tasks still work.
- No session affinity (stateless handles / shared store — see [Redis shared state](P2-shared-state-redis.md) if multi-replica).

## Refs

- SEP-2663 · [2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
