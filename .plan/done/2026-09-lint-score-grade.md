# Linter: mcpx rule set, score, grade, token budget

- **Priority:** P1   **Size:** M
- **Branch / PR:** `claude/observability-config`
- **Why:** LLMs choose tools from metadata; a score/grade and token estimate make quality measurable and gate regressions.
- **Done when:** `uml-mcp lint` implements the mcpx rules (tool/prop/prompt/resource/server), prints score, grade A–F and token estimate, supports `--min-grade` and `--token-budget`; our server scores A; CI gates on it.
- **Notes:** `mcp_core/quality/lint.py`; rules from mcpplayground.tech/docs/grading and mxcp.dev/quality/linting.
