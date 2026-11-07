"""The schema model, the JSON source form, and validation that reports every problem.

Two source forms share one model:

* SQL DDL (``CREATE TABLE`` ...), parsed by :mod:`.ddl`;
* JSON ``{title, tables: [{name, columns: [...], note, group}], relations}``.

Problems are collected, not raised one at a time, so a model can fix them all in one go.
Each carries the source line it came from.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from typing import Any

MAX_TABLES = 150
MAX_COLUMNS = 200
MAX_SOURCE = 400_000
THEMES = ("auto", "light", "dark")


class SchemaError(ValueError):
    """The source has problems; ``problems`` lists every one of them."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class Column:
    name: str
    type: str = ""
    pk: bool = False
    nullable: bool = True
    unique: bool = False
    default: str = ""
    note: str = ""
    #: (table, column or "" for "the target's primary key")
    fk: tuple[str, str] | None = None
    line: int = 0


@dataclass
class ForeignKey:
    """A reference from ``columns`` of one table to ``ref_columns`` of another."""

    table: str
    columns: list[str]
    ref_table: str
    ref_columns: list[str]
    line: int = 0
    label: str = ""
    #: "many-to-one" (the default), "one-to-one" or "many-to-many"
    kind: str = ""


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    note: str = ""
    group: str = ""
    line: int = 0
    #: composite primary key columns declared at table level
    primary_key: list[str] = field(default_factory=list)
    uniques: list[list[str]] = field(default_factory=list)

    def column(self, name: str) -> Column | None:
        key = name.lower()
        return next((c for c in self.columns if c.name.lower() == key), None)


@dataclass
class Relation:
    """One drawn edge: ``source`` (the referencing side) to ``target``."""

    source: str
    source_column: str
    target: str
    target_column: str
    #: cardinality at each end: "one", "many"
    source_card: str
    target_card: str
    #: the referencing column may be null (zero-or-...)
    optional: bool
    label: str = ""
    columns: tuple[str, ...] = ()


@dataclass
class Schema:
    title: str
    tables: list[Table]
    relations: list[Relation]
    theme: str = "auto"
    #: tables that only join two others (their key is made of foreign keys)
    join_tables: set[str] = field(default_factory=set)

    def table(self, name: str) -> Table | None:
        key = name.lower()
        return next((t for t in self.tables if t.name.lower() == key), None)


# ----------------------------------------------------------------------------- JSON


def _line_of(code: str, needle: str, start: int = 0) -> tuple[int, int]:
    """1-based line of the first ``"needle"`` at or after ``start``, and its offset."""
    at = code.find(json.dumps(needle), start)
    if at < 0:
        return 0, start
    return code.count("\n", 0, at) + 1, at


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value).strip()
    return default


def _ref(value: Any) -> tuple[str, str] | None:
    """``{"table": t, "column": c}``, ``"t.c"`` or ``"t"`` -> (t, c)."""
    if isinstance(value, dict):
        table = _text(value.get("table"))
        return (table, _text(value.get("column"))) if table else None
    if isinstance(value, str) and value.strip():
        table, _, column = value.strip().partition(".")
        return table.strip(), column.strip()
    return None


def parse_json(code: str) -> tuple[str, str, list[Table], list[ForeignKey], list[str]]:
    """Read the JSON form. Returns title, theme, tables, explicit relations, problems."""
    problems: list[str] = []
    try:
        data = json.loads(code)
    except ValueError as exc:
        raise SchemaError([f"the source is not valid JSON or SQL: {exc}"]) from exc
    if isinstance(data, list) and data and all(isinstance(t, dict) for t in data):
        raise SchemaError(['wrap the list of tables as {"tables": [...]}'])
    if not isinstance(data, dict):
        raise SchemaError(["a JSON source must be an object with a `tables` list"])
    title = _text(data.get("title"))
    theme = _text(data.get("theme"), "auto").lower()
    if theme not in THEMES:
        problems.append(f"theme must be one of {', '.join(THEMES)}, not {theme!r}")
        theme = "auto"
    if isinstance(data.get("sql"), str) and "tables" not in data:
        from .ddl import parse_ddl

        parsed = parse_ddl(data["sql"])
        return (
            title or parsed.title,
            theme if "theme" in data else parsed.theme,
            parsed.tables,
            parsed.foreign_keys,
            problems + parsed.problems,
        )
    raw_tables = data.get("tables")
    if not isinstance(raw_tables, list) or not raw_tables:
        problems.append("`tables` must be a non-empty list of {name, columns}")
        raise SchemaError(problems)
    tables: list[Table] = []
    fks: list[ForeignKey] = []
    cursor = 0
    for i, raw in enumerate(raw_tables, 1):
        if not isinstance(raw, dict):
            problems.append(f"table #{i} must be an object with a name and columns")
            continue
        name = _text(raw.get("name"))
        if not name:
            problems.append(f"table #{i} has no name")
            continue
        line, cursor = _line_of(code, name, cursor)
        table = Table(
            name,
            note=_text(raw.get("note")),
            group=_text(raw.get("group")),
            line=line,
        )
        raw_columns = raw.get("columns")
        if not isinstance(raw_columns, list):
            problems.append(f"line {line}: table {name}: `columns` must be a list")
            raw_columns = []
        col_cursor = cursor
        for j, rc in enumerate(raw_columns, 1):
            if isinstance(rc, str):
                rc = {"name": rc}
            if not isinstance(rc, dict) or not _text(rc.get("name")):
                problems.append(f"line {line}: table {name}: column #{j} has no name")
                continue
            cname = _text(rc["name"])
            cline, col_cursor = _line_of(code, cname, col_cursor)
            pk = bool(rc.get("pk") or rc.get("primary_key"))
            column = Column(
                cname,
                type=_text(rc.get("type")),
                pk=pk,
                nullable=bool(rc.get("nullable", not pk)),
                unique=bool(rc.get("unique")),
                default=_text(rc.get("default")),
                note=_text(rc.get("note")),
                line=cline or line,
            )
            if rc.get("fk") is not None or rc.get("references") is not None:
                ref = _ref(rc.get("fk", rc.get("references")))
                if ref is None:
                    problems.append(
                        f"line {column.line}: {name}.{cname}: `fk` must be "
                        '{"table": ..., "column": ...} or "table.column"'
                    )
                else:
                    column.fk = ref
                    fks.append(
                        ForeignKey(
                            name,
                            [cname],
                            ref[0],
                            [ref[1]] if ref[1] else [],
                            column.line,
                        )
                    )
            table.columns.append(column)
        tables.append(table)
    rels = data.get("relations") or []
    if not isinstance(rels, list):
        problems.append("`relations` must be a list")
        rels = []
    for k, rel in enumerate(rels, 1):
        if not isinstance(rel, dict):
            problems.append(f"relation #{k} must be an object with from and to")
            continue
        a, b = _ref(rel.get("from")), _ref(rel.get("to"))
        rline = _relation_line(code, k)
        if not a or not b:
            problems.append(
                f"line {rline}: relation #{k} needs `from` and `to` "
                '("table.column" or {"table", "column"})'
            )
            continue
        kind = _text(rel.get("kind") or rel.get("type")).lower().replace("_", "-")
        if kind and kind not in {
            "one-to-one",
            "one-to-many",
            "many-to-one",
            "many-to-many",
        }:
            problems.append(
                f"line {rline}: relation #{k}: kind must be one-to-one, one-to-many, "
                f"many-to-one or many-to-many, not {kind!r}"
            )
            kind = ""
        if kind == "one-to-many":  # "a has many b": b references a
            a, b, kind = b, a, "many-to-one"
        fks.append(
            ForeignKey(
                a[0],
                [a[1]] if a[1] else [],
                b[0],
                [b[1]] if b[1] else [],
                rline,
                label=_text(rel.get("label")),
                kind=kind,
            )
        )
    return title, theme, tables, fks, problems


def _relation_line(code: str, index: int) -> int:
    at = code.find('"relations"')
    if at < 0:
        return 0
    pos = at
    for _ in range(index):
        nxt = code.find('"from"', pos + 1)
        if nxt < 0:
            break
        pos = nxt
    return code.count("\n", 0, pos) + 1


# ----------------------------------------------------------------------------- checks


def _suggest(name: str, known: list[str]) -> str:
    close = difflib.get_close_matches(name, known, n=1, cutoff=0.6)
    if close:
        return f" (did you mean {close[0]}?)"
    shown = ", ".join(known[:12]) + (", ..." if len(known) > 12 else "")
    return f" (known: {shown})" if known else ""


def build(
    title: str,
    theme: str,
    tables: list[Table],
    fks: list[ForeignKey],
    problems: list[str],
) -> Schema:
    """Check references, resolve keys, and derive the relations to draw."""
    if not tables and not problems:
        problems.append(
            "no tables found: write CREATE TABLE statements, or JSON with a `tables` list"
        )
    if len(tables) > MAX_TABLES:
        problems.append(f"{len(tables)} tables is more than the limit of {MAX_TABLES}")
    seen: dict[str, Table] = {}
    unique_tables: list[Table] = []
    for t in tables:
        key = t.name.lower()
        if key in seen:
            problems.append(
                f"line {t.line}: table {t.name} is defined twice "
                f"(first on line {seen[key].line})"
            )
            continue
        seen[key] = t
        unique_tables.append(t)
        if len(t.columns) > MAX_COLUMNS:
            problems.append(
                f"line {t.line}: table {t.name} has {len(t.columns)} columns "
                f"(limit {MAX_COLUMNS})"
            )
        names: dict[str, Column] = {}
        for c in t.columns:
            if c.name.lower() in names:
                problems.append(
                    f"line {c.line}: table {t.name} has two columns named {c.name}"
                )
            names[c.name.lower()] = c
        for col in t.primary_key:
            found = t.column(col)
            if found is None:
                problems.append(
                    f"line {t.line}: table {t.name}: PRIMARY KEY names unknown column "
                    f"{col}{_suggest(col, [c.name for c in t.columns])}"
                )
            else:
                found.pk, found.nullable = True, False
        for group in t.uniques:
            for col in group:
                if t.column(col) is None:
                    problems.append(
                        f"line {t.line}: table {t.name}: UNIQUE names unknown column "
                        f"{col}{_suggest(col, [c.name for c in t.columns])}"
                    )
            if len(group) == 1 and (found := t.column(group[0])):
                found.unique = True
    known = [t.name for t in unique_tables]
    relations: list[Relation] = []
    for fk in fks:
        source = seen.get(fk.table.lower())
        where = f"line {fk.line}: " if fk.line else ""
        if source is None:
            problems.append(
                f"{where}foreign key from unknown table {fk.table}"
                f"{_suggest(fk.table, known)}"
            )
            continue
        target = seen.get(fk.ref_table.lower())
        cols = fk.columns or [c.name for c in source.columns if c.pk][:1]
        label = f"{source.name}.{', '.join(cols) or '?'}"
        if target is None:
            problems.append(
                f"{where}{label} references unknown table {fk.ref_table}"
                f"{_suggest(fk.ref_table, known)}"
            )
            continue
        bad = False
        for col in cols:
            if source.column(col) is None:
                problems.append(
                    f"{where}table {source.name} has no column {col} for its foreign key"
                    f"{_suggest(col, [c.name for c in source.columns])}"
                )
                bad = True
        ref_cols = fk.ref_columns or [c.name for c in target.columns if c.pk]
        if not ref_cols:
            problems.append(
                f"{where}{label} references {target.name}, which has no primary key; "
                "name the referenced column"
            )
            continue
        for col in ref_cols:
            if target.column(col) is None:
                problems.append(
                    f"{where}{label} references unknown column {target.name}.{col}"
                    f"{_suggest(col, [c.name for c in target.columns])}"
                )
                bad = True
        if not bad and cols and len(cols) != len(ref_cols):
            problems.append(
                f"{where}{label} has {len(cols)} column(s) but references "
                f"{len(ref_cols)} in {target.name}"
            )
            bad = True
        if bad or not cols:
            continue
        first = source.column(cols[0])
        tcol = target.column(ref_cols[0])
        assert first is not None and tcol is not None
        if first.fk is None:
            first.fk = (target.name, tcol.name)
        for extra, ref in zip(cols[1:], ref_cols[1:], strict=False):
            col = source.column(extra)
            if col is not None and col.fk is None:
                col.fk = (target.name, ref)
        pk_cols = {c.name.lower() for c in source.columns if c.pk}
        is_unique = (len(cols) == 1 and first.unique) or (
            {c.lower() for c in cols} == pk_cols and pk_cols
        )
        kind = fk.kind
        if kind == "many-to-many":
            source_card, target_card = "many", "many"
        elif kind == "one-to-one" or (not kind and is_unique):
            source_card, target_card = "one", "one"
        else:
            source_card, target_card = "many", "one"
        optional = all(
            (c := source.column(n)) is not None and c.nullable and not c.pk
            for n in cols
        )
        relations.append(
            Relation(
                source.name,
                first.name,
                target.name,
                tcol.name,
                source_card,
                target_card,
                optional,
                fk.label,
                tuple(cols),
            )
        )
    if problems:
        raise SchemaError(problems)
    schema = Schema(title or "Database schema", unique_tables, relations, theme)
    schema.join_tables = _join_tables(schema)
    return schema


def _join_tables(schema: Schema) -> set[str]:
    """Tables whose key is two or more foreign keys to different tables: M:N links."""
    out: set[str] = set()
    for t in schema.tables:
        refs = {r.target for r in schema.relations if r.source == t.name}
        fk_cols = {
            c.lower() for r in schema.relations if r.source == t.name for c in r.columns
        }
        pk = {c.name.lower() for c in t.columns if c.pk}
        if len(refs) < 2:
            continue
        if (pk and pk <= fk_cols) or (not pk and len(t.columns) <= len(fk_cols) + 2):
            out.add(t.name)
    return out


def parse(code: str) -> Schema:
    """SQL DDL or JSON -> a checked :class:`Schema`. Raises :class:`SchemaError`."""
    if not isinstance(code, str) or not code.strip():
        raise SchemaError(
            ["the source is empty: write CREATE TABLE statements or JSON"]
        )
    if len(code) > MAX_SOURCE:
        raise SchemaError([f"the source is longer than {MAX_SOURCE} characters"])
    text = code.removeprefix(chr(0xFEFF))
    head = text.lstrip()
    if head.startswith(("{", "[")):
        title, theme, tables, fks, problems = parse_json(text)
    else:
        from .ddl import parse_ddl

        parsed = parse_ddl(text)
        title, theme, tables, fks, problems = (
            parsed.title,
            parsed.theme,
            parsed.tables,
            parsed.foreign_keys,
            parsed.problems,
        )
    return build(title, theme, tables, fks, problems)
