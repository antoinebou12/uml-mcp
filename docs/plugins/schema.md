# Database schema plugin

`uml-mcp-plugin-schema` adds one diagram type, `db_schema`: an entity-relationship drawing of
a database from the SQL you already have, or from a short JSON description.

| Type | Output | Opens as |
| --- | --- | --- |
| `db_schema` | `html`, `svg` | An interactive schema page; a static SVG (and PNG in chat) |

Each table is a card: a header with its name, then one row per column with the name, the
type, a key icon for primary-key columns, a link icon for foreign keys, and `null` and `UQ`
badges for nullable and unique columns. Relationships are right-angled lines in crow's-foot
notation that leave and enter at the exact column rows. Tables are laid out left to right by
foreign-key direction, so referenced tables sit to the left of the tables that point at them,
and groups are drawn as tinted containers. A table keyed by two foreign keys to different
tables is marked `M:N`: it is the join table of a many-to-many relationship.

The page runs locally with no network access, in the sandboxed plugin frame, under a
hash-based CSP. The plugin ships with uml-mcp and is on by default.

```bash
uml-mcp plugins enable schema   # only needed when plugins.bundled is false
```

## SQL source

Paste DDL as it is. The reader is small and tolerant, has no dependencies, and understands
enough of PostgreSQL, MySQL/MariaDB, SQLite and SQL Server to draw a schema:

| Read | Notes |
| --- | --- |
| `CREATE TABLE` | `IF NOT EXISTS`, `TEMP`/`UNLOGGED`, schema-qualified and quoted names (`"x"`, `` `x` ``, `[x]`) |
| Column types | With arguments and arrays: `NUMERIC(10, 2)`, `character varying(80)`, `int[]` |
| Column constraints | `PRIMARY KEY`, `NOT NULL`, `NULL`, `UNIQUE`, `DEFAULT <expr>`, `REFERENCES t (c)`, MySQL `COMMENT '...'` |
| Table constraints | `[CONSTRAINT x] PRIMARY KEY (a, b)`, `UNIQUE (a)`, `FOREIGN KEY (a) REFERENCES t (c)` |
| `ALTER TABLE ... ADD` | `[CONSTRAINT x] FOREIGN KEY` and `PRIMARY KEY`, as `pg_dump` writes them |
| `COMMENT ON TABLE/COLUMN ... IS '...'` | Becomes the table's or column's note |
| Comments | `--`, `#` and `/* */` |
| Everything else | Indexes, views, inserts, functions, `CHECK` and `GENERATED` expressions are skipped |

`REFERENCES t` without a column points at `t`'s primary key. Comment directives set page
options:

| Directive | Effect |
| --- | --- |
| `-- title: Shop` | The diagram title (default *Database schema*) |
| `-- theme: dark` | `auto` (default), `light` or `dark` |
| `-- group: Billing` | Puts the tables that follow into the *Billing* container; `-- group:` with no name ends it |

A table in a non-default schema (`billing.invoices`, anything but `public`, `dbo` or `main`)
joins a group named after its schema unless a `-- group:` directive is active.

```sql
-- title: Shop database
-- group: Orders
CREATE TABLE orders (
  id          BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers (id),
  status      VARCHAR(16) NOT NULL DEFAULT 'pending'
);
```

## JSON source

| Field | Notes |
| --- | --- |
| `title`, `theme` | As above |
| `tables[]` | `name` (required), `group`, `note`, `columns[]` |
| `columns[]` | `name` (required), `type`, `pk`, `fk`, `nullable` (default: true unless `pk`), `unique`, `default`, `note`. A column may also be a bare string |
| `fk` | `{"table": "users", "column": "id"}` or `"users.id"`; `"users"` alone means its primary key |
| `relations[]` | Optional extra edges: `from`, `to` (`"table.column"` or objects), `kind` (`one-to-one`, `one-to-many`, `many-to-one`, `many-to-many`), `label` |
| `sql` | Instead of `tables`: a DDL string, so a JSON wrapper can carry `theme` and `title` for SQL |

```json
{
  "title": "Blog",
  "tables": [
    {"name": "users", "columns": [{"name": "id", "type": "uuid", "pk": true}]},
    {"name": "posts", "columns": [
      {"name": "id", "type": "uuid", "pk": true},
      {"name": "author_id", "type": "uuid", "nullable": false, "fk": "users.id"}
    ]}
  ]
}
```

## Relationships

| Situation | Drawn as |
| --- | --- |
| A foreign key | Many-to-one: a crow's foot at the referencing column, two bars at the referenced one |
| The foreign key is `UNIQUE`, or is the whole primary key | One-to-one: bars at both ends |
| The foreign-key column is nullable | A circle instead of a bar at the referencing end (zero or many, zero or one) |
| A join table (key made of foreign keys to two or more tables) | `M:N` badge on the table, many-to-one lines to each side |
| `kind: "many-to-many"` in JSON `relations` | Crow's feet at both ends |

## Validation

`validate_uml` reads the whole source and returns every problem at once, each with its line:

- a foreign key to an unknown table or column, with the closest name (*did you mean customers?*)
  or the known names;
- a table defined twice, two columns with the same name;
- `PRIMARY KEY` or `UNIQUE` lists that name an unknown column;
- a foreign key whose column counts differ, or that points at a table without a primary key;
- a `CREATE TABLE` without a column list.

## The page

| Action | Effect |
| --- | --- |
| Click a table | Highlights it and the tables it joins, dims the rest, and opens its detail card: columns with types, defaults and notes, and its outgoing and incoming foreign keys. Click one to jump to the other table |
| Hover a column | Traces its foreign-key path: the chain of references it follows and the columns that point at it |
| Search (`/`) | Finds tables and columns as you type; Enter or a click jumps to the match |
| Drag, wheel, `+` `-` `0` | Pan, zoom, fit. The page opens fitted to its frame |
| Light / Dark | Switches the theme; `auto` follows the system |
| Export | SVG, PNG or the page itself as HTML, in the current theme. Inside the MCP App viewer the export goes through the host |
| Esc | Clears the focus |

Inside the MCP App viewer the page hides its own title (the viewer shows one), and in a
narrow frame, such as a chat's 560 × 430 pixels, the detail card docks at the bottom.

## Limits

150 tables (`plugins.settings.schema.max_tables` can lower it) and 200 columns per table.
Static output with the `auto` theme is dark, like the other plugins.
