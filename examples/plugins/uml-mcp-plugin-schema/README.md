# uml-mcp-plugin-schema

Database schema (ER) diagrams for [UML-MCP](https://github.com/antoinebou12/uml-mcp), drawn from
the SQL DDL you already have or from a short JSON list of tables.

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-schema   # ships inside uml-mcp already
uml-mcp plugins enable schema
```

The `db_schema` type renders to `html` (focus a table and its joins, hover a column to trace its
keys, search, export SVG/PNG/HTML, light and dark) or `svg`.

```sql
-- title: Blog
CREATE TABLE users (id UUID PRIMARY KEY, handle TEXT NOT NULL UNIQUE);
CREATE TABLE posts (
  id        UUID PRIMARY KEY,
  author_id UUID NOT NULL REFERENCES users (id),
  title     TEXT NOT NULL
);
```

The DDL reader is small, tolerant and dependency-free (Postgres, MySQL, SQLite and SQL Server
dialects). See [`docs/plugins/schema.md`](../../../docs/plugins/schema.md) for the JSON form,
comment directives, relationship notation and validation messages.
