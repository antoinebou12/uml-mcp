---
title: Frontend (admin console)
description: "Develop the React + Vite + TypeScript admin console: dev server, components, tests, build and the committed assets check."
---

# Frontend: the admin console

| | |
| --- | --- |
| Source | `frontend/` (React 19, Vite, TypeScript, Tailwind v4 with shadcn "new-york" zinc tokens, lucide-react icons, Recharts, Radix primitives) |
| Built assets | `mcp_core/admin_ui/dist/` (**committed**, so `pip`/`uvx` installs need no Node) |
| Served by | `mcp_core/admin_ui/__init__.py` (`/admin`, `/admin/assets/*`, strict CSP) |
| API | `/admin/api/*` in `mcp_core/admin/` (see [Admin console](../admin/index.md)) |

## Develop

```bash
uml-mcp admin --no-open --port 8765      # terminal 1: backend (prints the setup token)
cd frontend && npm ci && npm run dev     # terminal 2: http://localhost:5173/admin/
```

Vite proxies `/admin/api`, `/mcp` and `/health` to port 8765. Open
`http://localhost:5173/admin/#/overview?token=<setup token>` to be able to save.

## Structure

```text
frontend/src/
├── components/ui/      shadcn-style primitives (button, card, dialog/sheet, switch, table, tabs…)
├── components/app/     shell (Sidebar, TopBar), SchemaForm, charts, common blocks
├── lib/                api client (token + write header), session, theme, hooks, types
└── pages/              one file per route (Overview, Setup, Settings, Activity, Logs…)
```

- **Routing:** hash routes (`#/settings`), so the server needs no rewrites.
- **Loading:** pages are lazy-loaded behind an error boundary.
- **Settings form:** built from the JSON schema returned by `/admin/api/settings/schema`
  (`SchemaForm.tsx`). A new setting shows up automatically once it has a field with a
  `description` in `mcp_core/core/settings_file.py`.
- **Adding a component:** copy the shadcn source into `components/ui/` and keep the
  design tokens (`bg-card`, `text-muted-foreground`, …) so light and dark mode both work.

## Checks

```bash
npm run lint        # eslint
npm run typecheck   # tsc 7 (native compiler)
npm test            # vitest + Testing Library
npm run build       # typecheck, then writes ../mcp_core/admin_ui/dist (deterministic)
```

- **Two TypeScript versions:** `tsc` comes from the `typescript-7` alias (the native
  TypeScript 7 compiler, about 6x faster here), while `typescript` stays on 6 because
  `typescript-eslint` needs the JavaScript compiler API that TypeScript 7 no longer ships.
  When `typescript-eslint` supports 7, drop the alias, bump `typescript` and remove the
  Renovate rule that holds it back. Run the compiler through `npm run typecheck`, not
  `npx tsc`, which would pick up version 6.

- **CI:** the `frontend` job runs the checks above, rebuilds, and fails if
  `mcp_core/admin_ui/dist` differs from the commit. Always commit the build output
  together with the source change.
- **Browser tests:** the Python Playwright suite (`tests/test_e2e_playwright.py`) drives
  the built console on desktop and mobile. `UML_MCP_SCREENSHOTS=docs/assets/admin`
  refreshes the screenshots used in these docs.
