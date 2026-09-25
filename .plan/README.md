# `.plan/` — project plan and backlog

Lightweight, file-based planning for humans and coding agents. One Markdown file
per work item; **the folder is the status**.

| Folder | Meaning |
| --- | --- |
| [`backlog/`](backlog/) | Accepted, not started (priority in the file name: `P1-…`, `P2-…`, `P3-…`) |
| [`in-progress/`](in-progress/) | Someone is working on it (branch + PR in the file) |
| [`blocked/`](blocked/) | Waiting on a decision, credential or upstream change (say what unblocks it) |
| [`done/`](done/) | Shipped (PR link + version) |

Top-level files:

| File | Purpose |
| --- | --- |
| [`BACKLOG.md`](BACKLOG.md) | Prioritized roadmap: every item with priority, size and status |
| [`STATUS.md`](STATUS.md) | Current health: versions, CI, test/coverage numbers, known failures |
| [`DECISIONS.md`](DECISIONS.md) | Architecture decision log (why things are the way they are) |

## Workflow

1. Pick the highest-priority file in `backlog/` (or add one with the template below).
2. `git mv .plan/backlog/<item>.md .plan/in-progress/` and add the branch name.
3. On merge, move it to `done/` with the PR link; update `BACKLOG.md` and `STATUS.md`.
4. Blocked? Move it to `blocked/` and write the unblock condition.

## Item template

```markdown
# <Title>

- **Priority:** P1 | P2 | P3   **Size:** S | M | L
- **Branch / PR:** –
- **Why:** one or two sentences (user or operator value)
- **Done when:** observable acceptance criteria (tests, docs, CI)
- **Notes:** links to code (`path:line`) and docs
```
