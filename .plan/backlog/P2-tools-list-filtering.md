# Filter tools/list by permission

- **Priority:** P2   **Size:** S
- **Done when:** read-only callers don't see write tools in `tools/list` (opt-in `auth.filter_tools_list`), calls still return 403 with a step-up challenge.
