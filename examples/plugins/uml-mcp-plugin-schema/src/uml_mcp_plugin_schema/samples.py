"""Example and template sources (every one of them renders)."""

from __future__ import annotations

import json

#: The catalog example: a small shop in PostgreSQL DDL, with a join table and groups.
EXAMPLE = """-- title: Shop database
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
"""

#: The same idea in the JSON form.
JSON_EXAMPLE = json.dumps(
    {
        "title": "Blog",
        "tables": [
            {
                "name": "users",
                "group": "Accounts",
                "columns": [
                    {"name": "id", "type": "uuid", "pk": True},
                    {
                        "name": "handle",
                        "type": "text",
                        "unique": True,
                        "nullable": False,
                    },
                    {"name": "bio", "type": "text"},
                ],
            },
            {
                "name": "posts",
                "note": "Published and draft posts",
                "columns": [
                    {"name": "id", "type": "uuid", "pk": True},
                    {
                        "name": "author_id",
                        "type": "uuid",
                        "nullable": False,
                        "fk": {"table": "users", "column": "id"},
                    },
                    {"name": "title", "type": "text", "nullable": False},
                    {"name": "published_at", "type": "timestamptz"},
                ],
            },
            {
                "name": "tags",
                "columns": [
                    {"name": "id", "type": "serial", "pk": True},
                    {"name": "label", "type": "text", "unique": True},
                ],
            },
            {
                "name": "post_tags",
                "columns": [
                    {"name": "post_id", "type": "uuid", "pk": True, "fk": "posts.id"},
                    {"name": "tag_id", "type": "int", "pk": True, "fk": "tags.id"},
                ],
            },
        ],
    },
    indent=2,
)

TEMPLATE = """-- title: My schema
CREATE TABLE parent (
  id   SERIAL PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE child (
  id        SERIAL PRIMARY KEY,
  parent_id INTEGER NOT NULL REFERENCES parent (id),
  label     TEXT
);
"""
