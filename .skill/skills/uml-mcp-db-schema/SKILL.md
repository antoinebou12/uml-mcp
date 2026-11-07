---
name: uml-mcp-db-schema
description: Draw database schema (ER) diagrams from SQL DDL or JSON tables (db_schema).
---

# Database schema diagrams

Follow `skill://uml-mcp-diagrams/SKILL.md`. Table cards with key, link, null and unique markers and crow's-foot relationships attached at the column rows, laid out by foreign-key direction with groups as tinted containers. The page focuses a table, traces a column's keys and searches.

## Types

| Type | Use for | Example prompt |
| --- | --- | --- |
| `db_schema` | a database schema or ER diagram from SQL DDL or a list of tables | Draw the schema of my shop database from this CREATE TABLE script. |

## Steps

1. Check the live catalog (`list_diagram_types` or `uml://types`); the bundled plugins are on by default, but a server may turn them off with `plugins.bundled: false`.
2. Read the type's example from `uml://examples` and keep its field names.
3. Call `validate_uml`; an error names the field and, for a bad reference, lists the known ids, so fix it and validate again.
4. Render with `generate_uml_image` for a chat image, or `generate_uml` with `output_format: "html"` for the interactive page in the MCP App viewer. Clients without MCP Apps still get the PNG and SVG.
5. Pass `theme` (`auto`, `dark`, `light`) rather than editing colours.

## Example

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
