# Installation

This guide explains how to install and set up the UML-MCP server.

## System requirements

- Python **3.12** (see `requires-python` in `pyproject.toml`)
- [uv](https://docs.astral.sh/uv/) (recommended), [Poetry](https://python-poetry.org/), or pip
- Optional: Docker for local PlantUML or Kroki

## Installation steps

1. Clone the repository:

```bash
git clone https://github.com/antoinebou12/uml-mcp.git
cd uml-mcp
```

1. Install dependencies:

**With uv (recommended):**

```bash
uv sync
```

**With Poetry:**

```bash
poetry install
```

**With pip:**

```bash
pip install -e .
```

Alternatively, for a lockfile-derived pip install:

```bash
uv export --frozen --no-dev --no-hashes -o requirements.txt
pip install -r requirements.txt
```

1. For development (tests, linting, docs):

```bash
uv sync --all-groups
# or: poetry install --with dev
# or: pip install -r requirements-dev.txt
```

## Run the server

From the project root:

```bash
python server.py
```

Default transport is **stdio** (for MCP clients). For local HTTP:

```bash
python server.py --transport http --host 127.0.0.1 --port 8000
```

With uv: `uv run python server.py` (same flags).

## Verifying installation

```bash
uv run python server.py --list-tools
```

You should see a table listing **`generate_uml`** and **`validate_uml`**, plus registered prompts/resources in logs or `--list-tools` output depending on UI settings.

## IDE integration

Point your MCP client at `server.py` with **absolute** paths for `args` and `cwd` (project root); optional `MCP_OUTPUT_DIR` in `env`. **[config/README.md](https://github.com/antoinebou12/uml-mcp/blob/main/config/README.md)** has example JSON; **[User Manual – Configuration](user-manual.md#configuration)** summarizes Cursor and Claude Desktop. Step-by-step: [Cursor](integrations/cursor.md), [Claude Desktop](integrations/claude_desktop.md).

## Optional components

### Local diagram servers

For better performance or offline use:

#### PlantUML server

```bash
docker run -d -p 8080:8080 plantuml/plantuml-server
```

#### Kroki server

```bash
docker run -d -p 8000:8000 yuzutech/kroki
```

Then point UML-MCP at the local instances:

```bash
export USE_LOCAL_PLANTUML=true
export PLANTUML_SERVER=http://localhost:8080
export USE_LOCAL_KROKI=true
export KROKI_SERVER=http://localhost:8000
```

(On Windows, use `set` in `cmd` or `$env:VAR = "value"` in PowerShell instead of `export`.)

## Troubleshooting

1. Ensure Python **3.12** is installed and on your PATH
2. Confirm dependencies installed (`uv sync` or equivalent)
3. Verify any local servers are running
4. Ensure write permissions if you use `output_dir` with `generate_uml`
