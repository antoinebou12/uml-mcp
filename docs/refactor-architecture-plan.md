# Repository refactor plan (concrete moves)

This document turns the “clean architecture” goals into **exact paths, import updates, and phased work**. It matches the repository as of the date it was written (`mcp_core` + `tools` packages, Kroki-heavy rendering, optional `ai_uml/` tree).

## Current snapshot (what exists today)

| Area | Location | Notes |
|------|-----------|--------|
| MCP runtime | `mcp_core/` | Server, tools, resources, prompts, config |
| Rendering / Kroki clients | `tools/kroki/` | PlantUML, Mermaid, D2, TikZ, templates — name `kroki` is historical |
| HTTP / Vercel | `app.py`, `api/app.py` | FastAPI surface |
| Stdio / CLI entry | `server.py` → `mcp_core.core.server` | Documented entrypoints |
| Experimental ML | `ai_uml/` | Not imported by MCP; **not** listed in `[tool.poetry] packages` (wheel is `mcp_core` + `tools` only) |
| Service-ish layer | `mcp_core/core/diagram_service.py` | `DiagramRequest` + `generate_from_request()` already exist |
| Validation models | `mcp_core/tools/schemas.py` | e.g. `GenerateUMLInput` (Pydantic) |
| Capability table | `tools/kroki/kroki.py` | `LANGUAGE_OUTPUT_SUPPORT` — single runtime source today; also referenced from `config.py`, `app.py` |

## Target layout (end state)

```text
uml-mcp/                          # repo root (PyPI name can stay uml-mcp)
  README.md                       # short overview + quick start only
  EXPERIMENTAL.md                 # pointer to experimental subtree (see repo root)
  pyproject.toml
  server.py
  app.py
  api/                            # keep or fold into app.py — optional cleanup
  mcp_core/
    config/                       # split from core/config.py when ready
    models/                       # request/response + capability registry types
    services/                     # diagram workflow (expand diagram_service)
    tools/                        # MCP tool registration only (thin)
    resources/
    prompts/
    server/
    core/                         # shrink over time; or rename package (see below)
  renderers/                      # renamed from tools/; not “Kroki-only”
    kroki/                        # HTTP client, LANGUAGE_OUTPUT_SUPPORT, scale_svg
    plantuml.py                   # optional: lift from kroki/plantuml.py
    mermaid.py                    # optional: lift from kroki/mermaid.py
    ...                           # phased splits; see Phase B
  experimental/
    ai_uml/                       # moved from ./ai_uml
  docs/
    architecture.md               # runtime boundaries
    configuration.md              # (existing)
    resources.md / prompts.md / backends.md  # split from README & user-manual
    deploy/
      vercel.md
      docker.md
      http.md
    clients/
      cursor.md
      claude_desktop.md
  tests/
    unit/
    integration/                  # partial: tests/integration/ already exists
    contracts/
```

### Optional: rename Python package `mcp_core` → `uml_mcp`

**Pros:** Aligns folder name with product. **Cons:** Every `from mcp_core...` import, docs, and downstream forks break; requires a major version and deprecation shim (`mcp_core` = re-export package) if you care about compatibility.

**Recommendation:** Treat as **Phase F** (last) or skip unless you are doing a major release anyway. The table below assumes **keeping `mcp_core`** until that decision is explicit.

---

## Phase A — Isolate experimental code (priority 1)

### Moves

```bash
mkdir experimental
git mv ai_uml experimental/ai_uml
```

### Files to update (search/replace `ai_uml` path and CI globs)

| File | Change |
|------|--------|
| `pyproject.toml` | `[tool.ruff] exclude`: `experimental/ai_uml` (or `experimental/**` if you want all experiments excluded) |
| `pyproject.toml` | `[tool.ty.src] exclude`: `experimental/ai_uml/**` |
| `.github/workflows/ci.yml` | `paths` filter: `experimental/ai_uml/**` instead of `ai_uml/**` |
| `.github/workflows/publish.yml` | Same; loop `for dir in mcp_core tools experimental/ai_uml` only if you still want that check — or drop `ai_uml` from publish loop if it is never packaged |
| `README.md` | Point to `experimental/ai_uml/` and `EXPERIMENTAL.md` |
| `docs/ai_uml.md` | Retitle paths to `experimental/ai_uml/...`; add nav note “Experiments” |
| `mkdocs.yml` | Move nav entry under e.g. `Experiments → ai_uml` or `experimental/ai_uml.md` if you relocate the doc |
| `.skill/agents.md`, `.skill/skills/modern-python/SKILL.md` | Update layout description |

### Root `EXPERIMENTAL.md`

Short contract: what lives under `experimental/`, that it is excluded from type/lint scope, not in the default wheel, and not part of MCP tool surface.

---

## Phase B — Rename `tools` → `renderers` (priority 2)

### Moves (minimal churn)

```bash
git mv tools renderers
# results in renderers/kroki/... (unchanged internal structure)
```

### Import remap (global)

| From | To |
|------|-----|
| `from tools.` | `from renderers.` |
| `import tools` | `import renderers` |
| `--cov=tools` | `--cov=renderers` |
| `packages = [..., { include = "tools" }]` | `{ include = "renderers" }` |
| `[tool.coverage.run] source = [..., "tools"]` | `"renderers"` |

**Touched Python modules (current grep set):**  
`mcp_core/core/diagram_rendering.py`, `mcp_core/core/utils.py`, `mcp_core/core/config.py`, `mcp_core/resources/diagram_resources.py`, `app.py`, tests under `tests/test_*.py`, `examples/*.py`.

### Later split (optional, Phase B2)

Inside `renderers/kroki/`, files like `plantuml.py`, `mermaid.py`, `d2.py` can become `renderers/plantuml.py` etc. with thin imports from `renderers.kroki` to avoid a big-bang. Not required for the rename.

---

## Phase C — Service layer and models (priorities 3–4)

### Already in place

- **Tool layer:** `mcp_core/tools/diagram_tools.py` (MCP registration + `DiagramRequest` construction).
- **Validation:** `GenerateUMLInput` in `schemas.py`.
- **Workflow entry:** `generate_from_request` in `diagram_service.py`.

### Target refinement

1. **`mcp_core/models/diagram.py`** (or `mcp_core/models/requests.py`): Own the dataclass/Pydantic pair:
   - Move or re-export `DiagramRequest` here.
   - Keep `GenerateUMLInput` next to it or import from a single module so tools import one namespace.

2. **`mcp_core/services/diagram_generation.py`**: Move `generate_from_request` and any orchestration now living in `utils.generate_diagram` / `diagram_rendering` that is “workflow” not “transport”.

3. **`mcp_core/core/utils.py` / `diagram_rendering.py`**: Reserve for pure helpers (encoding, Kroki calls) or rename to `renderers` facades.

4. **Storage layer:** Centralize “write bytes to `output_dir`” in one module (e.g. `mcp_core/services/storage.py`) with `Path`-only APIs.

---

## Phase D — Capability registry (priority 5)

### Today

- `LANGUAGE_OUTPUT_SUPPORT` in `tools/kroki/kroki.py` (after Phase B: `renderers/kroki/kroki.py`).

### Target

- **`mcp_core/models/capabilities.py`** (or `mcp_core/registry.py`):
  - Import or duplicate-merge Kroki’s table once.
  - Add **backend** metadata (`kroki` vs local/fallback), **file extension** map, **text vs binary** flags.
  - Expose functions: `supported_formats(diagram_type)`, `normalize_diagram_type()`, etc.
- **`config.py` / resources:** Import registry only — no second copy of the table.
- **Docs:** Generate “supported types” section from the same module (optional script) or test that docs examples match registry keys.

---

## Phase E — Pathlib and normalized tool responses (priorities 6 & 8)

### Pathlib

- Thread `Path | None` inside the service layer; convert from MCP string arguments at the tool boundary only.
- `output_dir.mkdir(parents=True, exist_ok=True)` in one place.

### Normalized JSON (breaking change — bump minor/major)

Define a single TypedDict or Pydantic model, e.g.:

```python
class DiagramToolResult(TypedDict, total=False):
    ok: bool
    diagram_type: str
    output_format: str
    backend_used: str
    fallback_used: bool
    file_path: str | None
    url: str | None
    playground: str | None
    content_base64: str | None
    error: str | None
    warnings: list[str]
```

Map existing keys (`local_path` → `file_path`, etc.) and keep **one** compatibility shim release if needed.

---

## Phase G — Documentation split (priorities 7–8)

| New / updated doc | Content source (today) |
|-------------------|-------------------------|
| `docs/architecture.md` | README “how it fits”, server vs app vs renderers |
| `docs/resources.md` | MCP resources (from user-manual / README) |
| `docs/prompts.md` | Registered prompts |
| `docs/backends.md` | Kroki, PlantUML, Mermaid, D2, fallback — merge `fallback-mechanism.md` links |
| `docs/deploy/*.md` | Vercel, Docker, HTTP — split from README and `integrations/vercel_smithery.md` |
| `docs/clients/*.md` | Move from `docs/integrations/` or symlink nav |

**README:** Goal ≤ ~80–120 lines: what it is, install, one stdio + one HTTP example, link to docs.

**MkDocs:** Update `nav` to reflect the new tree; keep “Experiments” at the bottom.

---

## Phase H — New MCP tools (priority 10)

- **`validate_uml`:** Run `GenerateUMLInput` + registry checks + optional Kroki dry-run or syntax-only path; return normalized result with `ok` and warnings.
- **`convert_diagram_syntax`:** Only if you have a clear, testable mapping (e.g. subset of PlantUML ↔ Mermaid); otherwise defer.

---

## Phase I — Test layout (priority 12)

```text
tests/
  unit/
    test_config.py
    test_capabilities.py
    ...
  integration/
    ...                    # keep existing tests/integration/
  contracts/
    test_tool_response_shape.py
    test_mcp_resources_list.py
```

Migration strategy: `git mv tests/test_config.py tests/unit/test_config.py` in batches; fix `pytest` paths if any scripts assume flat layout. `testpaths = ["tests"]` already recurse.

---

## Suggested merge order (PRs)

1. **PR1 — Experimental move + EXPERIMENTAL.md + doc/CI excludes** (low risk, easy review).
2. **PR2 — `tools` → `renderers` + pyproject/coverage/ruff** (mechanical, medium diff).
3. **PR3 — Registry module + pathlib in storage** (behavior-preserving).
4. **PR4 — Normalized responses** (explicit version note in CHANGELOG).
5. **PR5 — Docs split + mkdocs nav** (editorial).
6. **PR6 — `validate_uml` + contract tests** (feature).

---

## Verification checklist (after each PR)

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

For packaging: `poetry build` (or `uv build`) and confirm wheel contents list only intended top-level packages (`mcp_core`, `renderers`, …).

---

## Open decisions (record before Phase B2 / F)

1. Whether **`renderers`** stays one PyPI top-level package or becomes **`mcp_core.renderers`** (fewer top-level names, more nesting).
2. Whether to **rename `mcp_core`** to `uml_mcp` and whether to add a **compat shim** package.
3. Whether **normalized responses** require a **FastMCP / client migration** note in README.

This plan is intended to be executed incrementally; each phase should leave the tree green under CI.
