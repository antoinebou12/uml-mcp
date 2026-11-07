"""The database schema plugin: DDL and JSON parsing, validation, layout, SVG/HTML and the page."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "examples/plugins/uml-mcp-plugin-schema/src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from uml_mcp_plugin_schema import SchemaRenderer
from uml_mcp_plugin_schema.ddl import parse_ddl
from uml_mcp_plugin_schema.layout import layout
from uml_mcp_plugin_schema.model import SchemaError, parse
from uml_mcp_plugin_schema.samples import EXAMPLE, JSON_EXAMPLE, TEMPLATE

NS = "{http://www.w3.org/2000/svg}"


def col(schema, table: str, column: str):
    t = schema.table(table)
    assert t is not None, table
    c = t.column(column)
    assert c is not None, column
    return c


def problems(code: str) -> list[str]:
    return SchemaRenderer().validate("db_schema", code)


# ----------------------------------------------------------------------------- registration


def test_registers_db_schema():
    spec = SchemaRenderer().diagram_types["db_schema"]
    assert spec.formats == ("html", "svg")
    assert spec.security_profile == "sandboxed"
    assert spec.example == EXAMPLE and spec.template == TEMPLATE


def test_configure_limits_tables():
    renderer = SchemaRenderer()
    renderer.configure({"max_tables": 2})
    assert "limit of 2" in problems_with(renderer, EXAMPLE)[0]
    with pytest.raises(ValueError):
        renderer.configure({"max_tables": 0})
    with pytest.raises(ValueError):
        renderer.configure({"max_tables": "9"})


def problems_with(renderer: SchemaRenderer, code: str) -> list[str]:
    return renderer.validate("db_schema", code)


@pytest.mark.parametrize("source", [EXAMPLE, JSON_EXAMPLE, TEMPLATE])
def test_samples_validate(source):
    assert problems(source) == []


@pytest.mark.parametrize("source", [EXAMPLE, JSON_EXAMPLE])
@pytest.mark.parametrize("fmt", ["svg", "html"])
def test_samples_render(source, fmt):
    out = SchemaRenderer().render("db_schema", source, fmt)
    assert out.content
    if fmt == "svg":
        assert out.mime_type == "image/svg+xml"
        ET.fromstring(out.content)
        assert b"<script" not in out.content
    else:
        assert out.mime_type.startswith("text/html")


def test_render_rejects_bad_format_and_source():
    renderer = SchemaRenderer()
    with pytest.raises(ValueError, match="html or svg"):
        renderer.render("db_schema", EXAMPLE, "png")
    with pytest.raises(ValueError, match="invalid db_schema source"):
        renderer.render("db_schema", "CREATE TABLE a (x INT REFERENCES b);", "svg")
    assert problems("") and "empty" in problems("")[0]
    assert "unknown schema type" in SchemaRenderer().validate("other", EXAMPLE)[0]


# ----------------------------------------------------------------------------- DDL


def test_example_ddl_reads_keys_groups_and_notes():
    schema = parse(EXAMPLE)
    assert schema.title == "Shop database"
    names = [t.name for t in schema.tables]
    assert names[:2] == ["customers", "addresses"] and len(names) == 8
    orders = schema.table("orders")
    assert orders is not None and orders.group == "Orders"
    assert orders.note.startswith("One checkout")
    status = orders.column("status")
    assert status is not None and status.default == "'pending'" and not status.nullable
    assert schema.join_tables == {"order_items", "product_categories"}
    payments = next(r for r in schema.relations if r.source == "payments")
    assert (payments.source_card, payments.target_card) == ("one", "one")
    ship = next(r for r in schema.relations if r.source_column == "ship_to")
    assert ship.optional and ship.target == "addresses"
    selfref = next(r for r in schema.relations if r.source_column == "referred_by")
    assert selfref.source == selfref.target == "customers"


def test_dialects_quotes_comments_and_alter():
    code = """
    /* MySQL */
    CREATE TABLE IF NOT EXISTS `users` (
      `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
      `key` VARCHAR(40) NOT NULL COMMENT 'api key',
      `created` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_key` (`key`),
      KEY `idx_created` (`created`)
    ) ENGINE=InnoDB COMMENT='people';
    # SQL Server and Postgres
    CREATE TABLE [dbo].[Teams] ([Id] INT NOT NULL, CONSTRAINT [PK_Teams] PRIMARY KEY CLUSTERED ([Id]));
    CREATE TABLE "billing"."Invoice Lines" (
      line_id serial,
      user_id integer,
      amount numeric(10, 2) DEFAULT 0.00 NOT NULL,
      tags text[],
      price double precision,
      at timestamp with time zone
    );
    ALTER TABLE ONLY "billing"."Invoice Lines"
      ADD CONSTRAINT il_pk PRIMARY KEY (line_id),
      ADD CONSTRAINT il_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
    COMMENT ON COLUMN "billing"."Invoice Lines".amount IS 'in euros';
    CREATE INDEX x ON users (created);
    CREATE VIEW v AS SELECT 1;
    INSERT INTO users VALUES (1, 'a', now());
    CREATE TABLE copy AS SELECT * FROM users;
    """
    schema = parse(code)
    users = schema.table("users")
    assert users is not None and users.note == "people"
    key = users.column("key")
    assert key is not None and key.unique and key.note == "api key"
    assert col(schema, "users", "id").pk
    assert col(schema, "users", "created").default == "CURRENT_TIMESTAMP"
    assert col(schema, "Teams", "Id").pk
    lines = schema.table("Invoice Lines")
    assert lines is not None and lines.group == "billing"
    types = {c.name: c.type for c in lines.columns}
    assert types["amount"] == "numeric(10, 2)" and types["tags"] == "text[]"
    assert types["price"] == "double precision"
    assert types["at"] == "timestamp with time zone"
    assert col(schema, "Invoice Lines", "line_id").pk
    assert col(schema, "Invoice Lines", "amount").note == "in euros"
    assert [r.target for r in schema.relations] == ["users"]
    assert schema.relations[0].optional
    assert schema.table("copy") is not None and schema.table("v") is None


def test_group_directive_and_theme():
    code = "-- theme: dark\n-- group: A\nCREATE TABLE a (id int primary key);\n-- group:\nCREATE TABLE b (id int);"
    schema = parse(code)
    assert schema.theme == "dark"
    assert [t.group for t in schema.tables] == ["A", ""]


def test_parse_ddl_reports_missing_parts():
    parsed = parse_ddl(
        "CREATE TABLE;\nCREATE TABLE nolist;\n"
        "CREATE TABLE t (a int, FOREIGN KEY (a));\nCREATE TABLE u (a int, FOREIGN KEY (a) REFERENCES);"
    )
    text = " | ".join(parsed.problems)
    assert "line 1: CREATE TABLE without a table name" in text
    assert "line 2: CREATE TABLE nolist has no column list" in text
    assert "no REFERENCES clause" in text and "references no table" in text


# ----------------------------------------------------------------------------- validation


def test_validation_lists_every_problem_with_lines():
    code = (
        "CREATE TABLE customers (id int primary key);\n"
        "CREATE TABLE orders (\n"
        "  id int primary key,\n"
        "  customer_id int references customer(id),\n"
        "  item_id int references items(id),\n"
        "  cust2 int references customers(uuid)\n"
        ");\n"
        "CREATE TABLE customers (id int);\n"
        "CREATE TABLE dup (a int, a text, PRIMARY KEY (b), UNIQUE (c));\n"
        "CREATE TABLE nopk (x int);\n"
        "CREATE TABLE refs (y int references nopk);\n"
        "CREATE TABLE pair (a int, b int, FOREIGN KEY (a, b) REFERENCES customers (id));\n"
    )
    found = problems(code)
    text = "\n".join(found)
    assert (
        "line 4: orders.customer_id references unknown table customer (did you mean customers?)"
        in text
    )
    assert "line 5: orders.item_id references unknown table items" in text
    assert "line 6: orders.cust2 references unknown column customers.uuid" in text
    assert "line 8: table customers is defined twice (first on line 1)" in text
    assert "line 9: table dup has two columns named a" in text
    assert (
        "PRIMARY KEY names unknown column b" in text
        and "UNIQUE names unknown column c" in text
    )
    assert "line 11: refs.y references nopk, which has no primary key" in text
    assert "has 2 column(s) but references 1 in customers" in text
    assert len(found) >= 9


def test_json_validation_and_relations():
    src = json.dumps(
        {
            "title": "T",
            "theme": "light",
            "tables": [
                {"name": "a", "columns": [{"name": "id", "pk": True}, "label"]},
                {
                    "name": "b",
                    "columns": [
                        {"name": "id", "pk": True},
                        {"name": "a_id", "fk": "a"},
                    ],
                },
                {
                    "name": "c",
                    "columns": [{"name": "x", "fk": "zz.id"}, {"name": "y", "fk": 3}],
                },
            ],
            "relations": [
                {
                    "from": "a.id",
                    "to": "b.id",
                    "kind": "many-to-many",
                    "label": "pairs",
                },
                {"from": "a", "to": "b", "kind": "one-to-many"},
                {"from": "a.id", "to": "b.id", "kind": "sideways"},
                {"to": "b.id"},
            ],
        },
        indent=2,
    )
    text = "\n".join(problems(src))
    assert "c.x references unknown table zz" in text
    assert "`fk` must be" in text
    assert "kind must be one-to-one" in text
    assert "relation #4 needs `from` and `to`" in text
    assert re.search(r"line \d+: ", text)
    ok = json.loads(src)
    ok["tables"].pop()
    ok["relations"] = ok["relations"][:2]
    schema = parse(json.dumps(ok))
    assert schema.theme == "light"
    mm = next(r for r in schema.relations if r.label == "pairs")
    assert (mm.source_card, mm.target_card) == ("many", "many")
    flipped = schema.relations[-1]
    assert (flipped.source, flipped.target) == ("b", "a")


@pytest.mark.parametrize(
    ("code", "needle"),
    [
        ("{not json", "not valid JSON"),
        ("[1]", "must be an object"),
        ('[{"name": "a"}]', "wrap the list"),
        ('{"tables": []}', "non-empty list"),
        (
            '{"tables": [1, {"columns": []}, {"name": "x", "columns": 3}], "theme": "neon"}',
            "theme must be",
        ),
        (
            '{"tables": [{"name": "x", "columns": [{}]}], "relations": 3}',
            "`relations` must be a list",
        ),
        ("-- nothing here\nSELECT 1;", "no tables found"),
    ],
)
def test_bad_sources_say_what_is_wrong(code, needle):
    assert needle in "\n".join(problems(code))


def test_json_wrapper_can_carry_sql():
    schema = parse(json.dumps({"sql": TEMPLATE, "theme": "dark"}))
    assert schema.theme == "dark" and schema.title == "My schema"
    assert len(schema.relations) == 1


def test_size_limits():
    with pytest.raises(SchemaError, match="longer than"):
        parse("-" * 400_001)
    many = "".join(f"CREATE TABLE t{i} (id int);" for i in range(151))
    assert "more than the limit" in problems(many)[0]
    wide = "CREATE TABLE w (" + ",".join(f"c{i} int" for i in range(201)) + ");"
    assert "201 columns" in problems(wide)[0]


# ----------------------------------------------------------------------------- layout


def _boxes(lay):
    return {n: (c.x, c.y, c.right, c.bottom) for n, c in lay.cards.items()}


def test_layout_layers_by_reference_and_keeps_cards_apart():
    schema = parse(EXAMPLE)
    lay = layout(schema)
    boxes = _boxes(lay)
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            ax1, ay1, ax2, ay2 = boxes[a]
            bx1, by1, bx2, by2 = boxes[b]
            assert ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1, (a, b)
    # referenced tables sit to the left of the tables that point at them
    assert boxes["orders"][0] > boxes["customers"][2]
    assert boxes["order_items"][0] > boxes["orders"][2]
    # group containers hold their tables and never overlap
    for g in lay.groups:
        for t in g.tables:
            x1, y1, x2, y2 = boxes[t]
            assert g.x <= x1 and x2 <= g.x + g.w and g.y <= y1 and y2 <= g.y + g.h
    gs = lay.groups
    for i, a in enumerate(gs):
        for b in gs[i + 1 :]:
            assert (
                a.x + a.w <= b.x
                or b.x + b.w <= a.x
                or a.y + a.h <= b.y
                or b.y + b.h <= a.y
            )


def test_edges_attach_at_column_rows_and_stay_orthogonal():
    schema = parse(EXAMPLE)
    lay = layout(schema)
    for route in lay.routes:
        rel = route.relation
        src, dst = lay.cards[rel.source], lay.cards[rel.target]
        (sx, sy), (tx, ty) = route.points[0], route.points[-1]
        assert sy == pytest.approx(src.row_y(rel.source_column))
        assert ty == pytest.approx(dst.row_y(rel.target_column))
        assert sx in (src.x, src.right) and tx in (dst.x, dst.right)
        for (x1, y1), (x2, y2) in zip(route.points, route.points[1:], strict=False):
            assert x1 == x2 or y1 == y2
        # the straight run out of each card leaves room for the crow's foot
        assert abs(route.points[1][0] - sx) >= 20 or len(route.points) == 2


def test_routes_do_not_cross_other_cards():
    schema = parse(EXAMPLE)
    lay = layout(schema)
    for route in lay.routes:
        rel = route.relation
        for name, c in lay.cards.items():
            if name in (rel.source, rel.target):
                continue
            for (x1, y1), (x2, y2) in zip(route.points, route.points[1:], strict=False):
                lo_x, hi_x, lo_y, hi_y = (
                    min(x1, x2),
                    max(x1, x2),
                    min(y1, y2),
                    max(y1, y2),
                )
                assert not (
                    c.x < hi_x and lo_x < c.right and c.y < hi_y and lo_y < c.bottom
                ), (
                    rel.source,
                    rel.target,
                    name,
                )


def test_layout_handles_cycles_lonely_tables_and_large_schemas():
    code = "CREATE TABLE a (id int primary key, b_id int references b);\n"
    code += "CREATE TABLE b (id int primary key, a_id int references a);\n"
    code += "".join(f"CREATE TABLE lone{i} (id int primary key);\n" for i in range(12))
    code += "".join(
        f"CREATE TABLE c{i} (id int primary key, a_id int references a);\n"
        for i in range(40)
    )
    lay = layout(parse(code))
    assert len(lay.routes) == 42
    assert lay.width > 0 and lay.height > 0
    svg = SchemaRenderer().render("db_schema", code, "svg").content
    ET.fromstring(svg)


# ----------------------------------------------------------------------------- SVG and HTML


def test_svg_draws_cards_icons_badges_and_crows_feet():
    svg = SchemaRenderer().render("db_schema", EXAMPLE, "svg").content.decode()
    root = ET.fromstring(svg)
    tables = [
        g for g in root.iter(f"{NS}g") if "table" in (g.get("class") or "").split()
    ]
    assert len(tables) == 8
    assert svg.count('href="#i-key"') == 10  # 6 single keys + two composite pairs
    assert svg.count('href="#i-link"') == 9
    assert svg.count(">M:N<") == 2
    assert ">UQ<" in svg and ">null<" in svg
    rels = [g for g in root.iter(f"{NS}g") if g.get("class") == "rel"]
    assert len(rels) == 9
    assert svg.count('class="dot-o"') == 2  # the optional ship_to and referred_by
    assert "#0e131d" in svg  # auto is dark in static output
    assert "var(--" not in svg
    light = SchemaRenderer().render(
        "db_schema", json.dumps({"sql": TEMPLATE, "theme": "light"}), "svg"
    )
    assert b"#f6f7f9" in light.content


def test_svg_escapes_names_and_labels():
    src = json.dumps(
        {
            "title": "<b>&",
            "tables": [
                {
                    "name": "a<x>",
                    "group": "g&",
                    "columns": [{"name": "id", "pk": True, "type": "<t>"}],
                },
                {"name": "b", "columns": [{"name": 'a"', "fk": "a<x>.id"}]},
            ],
            "relations": [{"from": 'b.a"', "to": "a<x>.id", "label": "<lbl>"}],
        }
    )
    svg = SchemaRenderer().render("db_schema", src, "svg").content.decode()
    ET.fromstring(svg)
    assert "<b>" not in svg and "&lt;lbl&gt;" in svg


def _grab(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.DOTALL)
    assert m
    return m.group(1)


def test_page_is_csp_locked_and_offline():
    page = SchemaRenderer().render("db_schema", EXAMPLE, "html").content.decode()
    csp = unescape(_grab(r'Content-Security-Policy" content="([^"]+)"', page))
    script = _grab(r"<script>(.*?)</script>", page)
    style = _grab(r"<style>(.*?)</style>", page)
    for text in (script, style):
        digest = base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
        assert f"sha256-{digest}" in csp
    assert "default-src 'none'" in csp
    assert "http" not in script.replace("http://www.w3.org/2000/svg", "")
    assert ' style="' not in page
    data = json.loads(
        _grab(r'<script type="application/json" id="schema-data">(.*?)</script>', page)
    )
    assert {t["name"] for t in data["tables"]} >= {"orders", "payments"}
    assert (
        next(r for r in data["relations"] if r["from"] == "payments")["card"] == "1:1"
    )


# ----------------------------------------------------------------------------- the page

playwright = pytest.importorskip("playwright.sync_api")


def _open(pw, html: str, width: int, height: int):
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": width, "height": height})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.set_content(html)
    return browser, page, errors


@pytest.mark.parametrize(("width", "height"), [(1280, 820), (560, 430)])
def test_page_focus_trace_search_and_export(width, height):
    html = SchemaRenderer().render("db_schema", EXAMPLE, "html").content.decode()
    with playwright.sync_playwright() as pw:
        browser, page, errors = _open(pw, html, width, height)
        # fitted on load: the whole drawing is inside the frame
        box = page.locator("#stage svg").bounding_box()
        main = page.locator("main").bounding_box()
        assert box and main
        assert (
            box["x"] >= main["x"] - 1
            and box["x"] + box["width"] <= main["x"] + main["width"] + 1
        )
        assert (
            box["y"] >= main["y"] - 1
            and box["y"] + box["height"] <= main["y"] + main["height"] + 1
        )
        # click a table: it and its joins stay, the rest dims, the card opens
        page.locator('.table[data-table="orders"] .tname').click()
        assert page.evaluate("window.__schema.selected") == "orders"
        assert page.is_visible("#detail")
        assert page.inner_text("#detail h2") == "orders"
        assert "dim" in (
            page.get_attribute('.table[data-table="categories"]', "class") or ""
        )
        assert "dim" not in (
            page.get_attribute('.table[data-table="customers"]', "class") or ""
        )
        # jump through the card to the referenced table
        page.locator("#detail .link", has_text="customers.id").click()
        assert page.evaluate("window.__schema.selected") == "customers"
        page.keyboard.press("Escape")
        assert page.is_hidden("#detail")
        # hover a column: its key path lights up
        assert page.evaluate("window.__schema.trace('order_items', 'order_id')")
        assert page.locator(".rel.on").count() == 1
        assert page.locator(".col.hl").count() == 2
        # search
        page.click("#q")
        page.keyboard.type("price")
        assert page.locator("#results button").count() == 2
        page.keyboard.press("Enter")
        assert page.evaluate("window.__schema.selected") in {"products", "order_items"}
        # theme and exports
        before = page.get_attribute("html", "data-theme")
        page.click("#theme")
        assert page.get_attribute("html", "data-theme") != before
        svg = page.evaluate("window.__schema.svgText()")
        ET.fromstring(svg)
        assert "var(--" not in svg
        assert not re.search(r'class="[^"]*\b(dim|on|hl)\b', svg)
        with page.expect_download() as dl:
            page.click("details.menu summary")
            page.click("#x-svg")
        assert dl.value.suggested_filename == "Shop-database.svg"
        with page.expect_download() as dl:
            page.click("details.menu summary")
            page.click("#x-png")
        assert dl.value.suggested_filename == "Shop-database.png"
        exported = page.evaluate("window.__schema.htmlText()")
        tag = exported[: exported.index(">", exported.index("<html"))]
        assert (
            "<script>" in exported
            and "data-embedded" not in tag
            and 'data-auto="0"' in tag
        )
        assert not errors, errors
        browser.close()


def test_exported_page_reopens_without_errors():
    html = SchemaRenderer().render("db_schema", JSON_EXAMPLE, "html").content.decode()
    with playwright.sync_playwright() as pw:
        browser, page, errors = _open(pw, html, 900, 600)
        exported = page.evaluate("window.__schema.htmlText()")
        page.set_content(exported)
        page.locator('.table[data-table="posts"] .tname').click()
        assert page.inner_text("#detail h2") == "posts"
        assert not errors, errors
        browser.close()


def test_page_inside_a_frame_hands_exports_to_the_host():
    html = SchemaRenderer().render("db_schema", EXAMPLE, "html").content.decode()
    host = (
        "<!doctype html><body style='margin:0'><iframe id='f' style='width:560px;height:430px;border:0'></iframe>"
        "<script>window.got=[];addEventListener('message',e=>{window.got.push(e.data);"
        "if(e.data.type==='uml-mcp/plugin-ready'){f.contentWindow.postMessage({type:'uml-mcp/plugin-bridge-ready'},'*');"
        "f.contentWindow.postMessage({type:'uml-mcp/plugin-export',format:'svg'},'*');}});"
        "document.getElementById('f').srcdoc="
        + json.dumps(html).replace("</", "<\\/")
        + ";</script></body>"
    )
    with playwright.sync_playwright() as pw:
        browser, page, errors = _open(pw, host, 600, 480)
        page.wait_for_function(
            "window.got.some(m => m.type === 'uml-mcp/plugin-download')", timeout=5000
        )
        got = page.evaluate("window.got")
        download = next(m for m in got if m["type"] == "uml-mcp/plugin-download")
        assert download["filename"] == "Shop-database.svg"
        assert base64.b64decode(download["blob"]).startswith(b"<svg")
        frame = page.frame_locator("#f")
        assert frame.locator("html").get_attribute("data-embedded") == "1"
        assert frame.locator(".ident").is_hidden()
        assert not errors, errors
        browser.close()
