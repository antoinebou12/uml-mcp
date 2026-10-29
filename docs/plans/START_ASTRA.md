# Start Astra in Cursor

Open the repository in Cursor, pull this branch, then start a **parent Agent** conversation:

> Act as Astra, the UML-MCP main orchestrator. Read `docs/plans/ASTRA_MASTER_PLAN.md` and `.cursor/rules/astra-orchestrator.mdc`. Audit the current branch, local uncommitted changes and task ledger first. Use the actual Cursor subagent mechanism to delegate scoped MCP Apps/D3 viewer work to Luna (`.cursor/agents/luna.md`). Astra owns plugin infrastructure, specialized diagram types, repository indexing, security, CI and Manufact verification. Integrate Luna's patches only after tests and screenshots. Implement the backlog incrementally; do not stop after planning or falsely claim a deployment is verified.

If subagents are not available in this Cursor configuration, treat `luna.md` as a task handoff specification and explicitly report the blocker. Adding these files does not launch agents by itself.
