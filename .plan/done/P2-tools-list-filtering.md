# Filter tools/list by permission

- **Priority:** P2   **Size:** S
- **Status:** done
- **Done when:** read-only callers don't see write tools in `tools/list` (opt-in `auth.filter_tools_list`), calls still return 403 with a step-up challenge.

Shipped as opt-in `auth.filter_tools_list` / `MCP_AUTH_FILTER_TOOLS_LIST`: AuthMiddleware filters JSON `tools/list` responses for principals without write; write `tools/call` still returns 403 + step-up.
