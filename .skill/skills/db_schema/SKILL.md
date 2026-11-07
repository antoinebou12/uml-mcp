---
name: db_schema
description: >-
  Writes valid db_schema SQL DDL or JSON for uml-mcp (diagram_type=db_schema, bundled plugin schema). Use when the user asks for a database schema or ER diagram from SQL DDL or a list of tables; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# db_schema diagram (uml-mcp plugin `schema`)

**`diagram_type`:** `db_schema`  
**Backend:** `plugin:schema` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

Database schema (ER) from SQL DDL (CREATE TABLE; Postgres, MySQL, SQLite) or JSON tables: column cards with PK/FK/null/unique markers, crow's-foot relationships at the column rows, groups; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/db-schema/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Draw the schema of my shop database from this CREATE TABLE script.

## Notation tips

- Paste SQL DDL as is: `CREATE TABLE` with `PRIMARY KEY`, `REFERENCES`, `FOREIGN KEY`, `UNIQUE`, `NOT NULL`, `DEFAULT` (Postgres, MySQL, SQLite); other statements are skipped.
- Comment directives: `-- title: Shop`, `-- theme: dark`, `-- group: Billing` (tables below it go in a tinted container; `-- group:` ends it).
- Or JSON: `tables` (`name`, `group`, `note`, `columns`: `name`, `type`, `pk`, `fk` `{"table","column"}` or `"table.column"`, `nullable`, `unique`, `note`) and optional `relations` (`from`, `to`, `kind`: `one-to-one`, `one-to-many`, `many-to-many`, `label`).
- A unique or primary-key foreign key draws one-to-one; a table keyed by two foreign keys is marked as an M:N join table. `validate_uml` lists every bad reference with its line.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```sql
-- title: Shop database
-- group: Customers
CREATE TABLE customers (
  id          BIGSERIAL PRIMARY KEY,
  email       VARCHAR(255) NOT NULL UNIQUE,
  full_name   TEXT NOT NULL,
  referred_by BIGINT REFERENCES customers (id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE addresses (
  id          BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers (id) ON DELETE CASCADE,
  line1       TEXT NOT NULL,
  city        TEXT NOT NULL,
  country     CHAR(2) NOT NULL
);

-- group: Catalog
CREATE TABLE products (
  id          BIGSERIAL PRIMARY KEY,
  sku         VARCHAR(32) NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  price_cents INTEGER NOT NULL CHECK (price_cents >= 0)
);

CREATE TABLE categories (
  id   SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE product_categories (
  product_id  BIGINT NOT NULL REFERENCES products (id),
  category_id INTEGER NOT NULL REFERENCES categories (id),
  PRIMARY KEY (product_id, category_id)
);

-- group: Orders
CREATE TABLE orders (
  id          BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL,
  ship_to     BIGINT,
  status      VARCHAR(16) NOT NULL DEFAULT 'pending',
  placed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers (id),
  FOREIGN KEY (ship_to) REFERENCES addresses (id)
);

CREATE TABLE order_items (
  order_id    BIGINT NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
  product_id  BIGINT NOT NULL REFERENCES products (id),
  quantity    INTEGER NOT NULL DEFAULT 1,
  price_cents INTEGER NOT NULL,
  PRIMARY KEY (order_id, product_id)
);

CREATE TABLE payments (
  id        BIGSERIAL PRIMARY KEY,
  order_id  BIGINT NOT NULL UNIQUE REFERENCES orders (id),
  provider  TEXT NOT NULL,
  paid_at   TIMESTAMPTZ
);

COMMENT ON TABLE orders IS 'One checkout; its lines are in order_items';
CREATE INDEX orders_customer_idx ON orders (customer_id);
```
