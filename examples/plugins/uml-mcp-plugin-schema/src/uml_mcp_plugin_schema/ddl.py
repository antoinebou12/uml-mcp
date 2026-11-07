"""A small, tolerant SQL DDL reader: tables, columns, keys and references.

It understands enough of PostgreSQL, MySQL/MariaDB, SQLite and SQL Server DDL to draw a
schema: ``CREATE TABLE`` (with ``IF NOT EXISTS``, ``TEMP``, schema-qualified and quoted
names), column types with arguments, ``PRIMARY KEY``, ``UNIQUE``, ``NOT NULL``,
``DEFAULT``, ``REFERENCES`` and table-level ``FOREIGN KEY``, plus
``ALTER TABLE ... ADD [CONSTRAINT x] FOREIGN KEY`` and ``COMMENT ON TABLE/COLUMN``.
Everything else (indexes, views, inserts, functions...) is skipped.

Two comment directives set page options: ``-- title: Shop`` and ``-- theme: dark``.
A comment ``-- group: billing`` puts the tables that follow into a group (``-- group:``
with no name ends it); a non-default schema name (``billing.invoices``) does the same.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .model import THEMES, Column, ForeignKey, Table

_DEFAULT_SCHEMAS = {"public", "dbo", "main", "temp"}
#: words that end a column's type and start its constraints
_CONSTRAINT_WORDS = {
    "NOT",
    "NULL",
    "PRIMARY",
    "UNIQUE",
    "DEFAULT",
    "REFERENCES",
    "CHECK",
    "CONSTRAINT",
    "COLLATE",
    "GENERATED",
    "AUTO_INCREMENT",
    "AUTOINCREMENT",
    "IDENTITY",
    "COMMENT",
    "ON",
    "AS",
    "KEY",
    "CHARACTER",
    "CHARSET",
}
_TABLE_LEVEL = {"PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT", "KEY", "INDEX",
                "EXCLUDE", "LIKE", "FULLTEXT", "SPATIAL", "PERIOD"}  # fmt: skip

_TOKEN = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<line_comment>(?:--|\#)[^\n]*)
  | (?P<block_comment>/\*.*?(?:\*/|\Z))
  | (?P<string>(?:[NEB]|_utf8mb4)?'(?:[^']|'')*'?)
  | (?P<dollar>\$(?P<tag>[A-Za-z_]*)\$.*?(?:\$(?P=tag)\$|\Z))
  | (?P<quoted>"(?:[^"]|"")*"?|`(?:[^`]|``)*`?|\[[^\]\n]*\]?)
  | (?P<number>\d+(?:\.\d+)?)
  | (?P<word>[A-Za-z_À-￿][\w$À-￿]*)
  | (?P<op>::|[(),;.=])
  | (?P<other>.)
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass
class Tok:
    kind: str  # word, ident (quoted), string, number, op, other
    text: str
    line: int

    @property
    def upper(self) -> str:
        return self.text.upper() if self.kind == "word" else ""

    @property
    def name(self) -> str:
        """The identifier this token spells, quotes removed."""
        if self.kind != "ident":
            return self.text
        body = self.text[1:-1] if len(self.text) > 1 else self.text
        quote = self.text[0]
        return body.replace(quote * 2, quote) if quote in '"`' else body


@dataclass
class Parsed:
    title: str = ""
    theme: str = "auto"
    tables: list[Table] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _tokens(code: str, parsed: Parsed) -> list[Tok]:
    out: list[Tok] = []
    line = 1
    for m in _TOKEN.finditer(code):
        kind, text = m.lastgroup or "other", m.group()
        if kind == "tag":
            kind = "dollar"
        if kind == "line_comment":
            body = text.lstrip("-#").strip()
            key, sep, value = body.partition(":")
            key, value = key.strip().lower(), value.strip()
            if sep and key == "title" and value:
                parsed.title = value
            elif sep and key == "theme" and value.lower() in THEMES:
                parsed.theme = value.lower()
            elif sep and key == "group":
                out.append(Tok("group", value, line))
        elif kind not in {"ws", "block_comment"}:
            if kind == "quoted":
                kind = "ident"
            elif kind == "dollar":
                kind = "string"
            out.append(Tok(kind, text, line))
        line += text.count("\n")
    return out


def _statements(tokens: list[Tok]) -> list[list[Tok]]:
    out: list[list[Tok]] = []
    cur: list[Tok] = []
    later: list[list[Tok]] = []  # group directives met inside a statement
    for tok in tokens:
        if tok.kind == "op" and tok.text == ";":
            if cur:
                out.append(cur)
            out += later
            cur, later = [], []
        elif tok.kind == "group":
            (later if cur else out).append([tok])
        else:
            cur.append(tok)
    if cur:
        out.append(cur)
    return out + later


def _split(items: list[Tok]) -> list[list[Tok]]:
    """Split on top-level commas."""
    parts: list[list[Tok]] = [[]]
    depth = 0
    for tok in items:
        if tok.kind == "op" and tok.text == "(":
            depth += 1
        elif tok.kind == "op" and tok.text == ")":
            depth -= 1
        if depth == 0 and tok.kind == "op" and tok.text == ",":
            parts.append([])
        else:
            parts[-1].append(tok)
    return [p for p in parts if p]


def _paren(tokens: list[Tok], i: int) -> tuple[list[Tok], int]:
    """Tokens inside the parenthesis opening at ``i``; returns them and the index after."""
    depth = 0
    for j in range(i, len(tokens)):
        t = tokens[j]
        if t.kind == "op" and t.text == "(":
            depth += 1
        elif t.kind == "op" and t.text == ")":
            depth -= 1
            if depth == 0:
                return tokens[i + 1 : j], j + 1
    return tokens[i + 1 :], len(tokens)


def _is(tok: Tok | None, *words: str) -> bool:
    return tok is not None and tok.upper in words


def _at(tokens: list[Tok], i: int) -> Tok | None:
    return tokens[i] if 0 <= i < len(tokens) else None


def _qualified(tokens: list[Tok], i: int) -> tuple[list[str], int]:
    """A dotted name (``db.schema.table``) at ``i``: its parts and the index after."""
    parts: list[str] = []
    while i < len(tokens) and tokens[i].kind in {"word", "ident"}:
        parts.append(tokens[i].name)
        i += 1
        if _at(tokens, i) and tokens[i].text == "." and tokens[i].kind == "op":
            i += 1
            continue
        break
    return parts, i


def _names(tokens: list[Tok]) -> list[str]:
    """Column names in a ``(a, b DESC, c(10))`` list."""
    out = []
    for part in _split(tokens):
        first = part[0]
        if first.kind in {"word", "ident"}:
            out.append(first.name)
    return out


def _string(tok: Tok) -> str:
    text = tok.text
    q = text.find("'")
    if q >= 0:
        body = (
            text[q + 1 : -1]
            if text.endswith("'") and len(text) > q + 1
            else text[q + 1 :]
        )
        return body.replace("''", "'")
    if text.startswith("$"):
        return re.sub(r"^\$[A-Za-z_]*\$|\$[A-Za-z_]*\$$", "", text)
    return text


def _text(tokens: list[Tok]) -> str:
    out = ""
    for t in tokens:
        piece = t.text
        if out and not (
            piece in {")", ",", ".", "::", "(", "[]"} or out.endswith(("(", ".", "::"))
        ):
            out += " "
        if piece == "(" and out.endswith(" "):
            out = out[:-1]
        out += piece
    return out


def _references(tokens: list[Tok], i: int) -> tuple[tuple[str, list[str]] | None, int]:
    """``REFERENCES t [(c, ...)]`` starting at the word after REFERENCES."""
    parts, i = _qualified(tokens, i)
    if not parts:
        return None, i
    cols: list[str] = []
    if _at(tokens, i) and tokens[i].text == "(":
        inner, i = _paren(tokens, i)
        cols = _names(inner)
    return (parts[-1], cols), i


def _index_clause(toks: list[Tok]) -> bool:
    """``KEY name (a, b)`` (MySQL) rather than a column called key or index."""
    second, third, fourth = _at(toks, 1), _at(toks, 2), _at(toks, 3)
    if second is not None and second.text == "(":
        return True
    return (
        third is not None
        and third.text == "("
        and fourth is not None
        and fourth.kind in {"word", "ident"}
    )


class _Reader:
    def __init__(self, parsed: Parsed):
        self.parsed = parsed
        self.group = ""
        self.pending_pk: list[tuple[str, list[str]]] = []
        self.pending_notes: list[tuple[str, str, str]] = []

    def statement(self, toks: list[Tok]) -> None:
        if toks[0].kind == "group":
            self.group = toks[0].text
            return
        i = 0
        if not _is(_at(toks, 0), "CREATE", "ALTER", "COMMENT"):
            return
        head = toks[0].upper
        if head == "CREATE":
            i = 1
            while _at(toks, i) and toks[i].kind == "word" and toks[i].upper != "TABLE":
                if toks[i].upper in {"VIEW", "INDEX", "FUNCTION", "TYPE", "SEQUENCE",
                                     "TRIGGER", "PROCEDURE", "SCHEMA", "EXTENSION",
                                     "DATABASE", "DOMAIN", "MATERIALIZED", "POLICY",
                                     "ROLE", "USER"}:  # fmt: skip
                    return
                i += 1
            if not _is(_at(toks, i), "TABLE"):
                return
            self.create(toks, i + 1)
        elif head == "ALTER" and _is(_at(toks, 1), "TABLE"):
            self.alter(toks, 2)
        elif head == "COMMENT" and _is(_at(toks, 1), "ON"):
            self.comment(toks)

    def create(self, toks: list[Tok], i: int) -> None:
        start = toks[0].line
        if _is(_at(toks, i), "IF"):
            i += 3 if _is(_at(toks, i + 1), "NOT") else 2
        if _is(_at(toks, i), "ONLY"):
            i += 1
        parts, i = _qualified(toks, i)
        if not parts:
            self.parsed.problems.append(
                f"line {start}: CREATE TABLE without a table name"
            )
            return
        name = parts[-1]
        group = self.group
        if len(parts) > 1 and parts[-2].lower() not in _DEFAULT_SCHEMAS and not group:
            group = parts[-2]
        table = Table(name, group=group, line=toks[0].line)
        if not (_at(toks, i) and toks[i].text == "("):
            if any(_is(t, "AS") for t in toks[i:]) or any(
                _is(t, "LIKE") for t in toks[i:]
            ):
                # CREATE TABLE x AS SELECT / LIKE y: no column list to draw
                self.parsed.tables.append(table)
                return
            self.parsed.problems.append(
                f"line {start}: CREATE TABLE {name} has no column list in parentheses"
            )
            return
        body, i = _paren(toks, i)
        for item in _split(body):
            self.item(table, item)
        # MySQL: ... ) ENGINE=InnoDB COMMENT='...'
        rest = toks[i:]
        for k, t in enumerate(rest):
            if _is(t, "COMMENT"):
                nxt = rest[k + 1] if k + 1 < len(rest) else None
                if nxt is not None and nxt.text == "=":
                    nxt = rest[k + 2] if k + 2 < len(rest) else None
                if nxt is not None and nxt.kind == "string":
                    table.note = _string(nxt)
        self.parsed.tables.append(table)

    def item(self, table: Table, toks: list[Tok]) -> None:
        first = toks[0]
        if (
            first.kind == "word"
            and first.upper in _TABLE_LEVEL
            and not (first.upper in {"KEY", "INDEX"} and not _index_clause(toks))
        ):
            self.constraint(table, toks, first.line)
            return
        if first.kind not in {"word", "ident"}:
            return
        self.column(table, toks)

    def constraint(self, table: Table, toks: list[Tok], line: int) -> None:
        i = 0
        if _is(_at(toks, 0), "CONSTRAINT"):
            i = 2
        word = _at(toks, i)
        if _is(word, "PRIMARY") and _is(_at(toks, i + 1), "KEY"):
            j = i + 2
            while _at(toks, j) and toks[j].text != "(":
                j += 1  # CLUSTERED, USING BTREE...
            if _at(toks, j):
                inner, _ = _paren(toks, j)
                table.primary_key = _names(inner)
        elif _is(word, "UNIQUE"):
            j = i + 1
            while _at(toks, j) and toks[j].text != "(":
                j += 1  # UNIQUE KEY name (...)
            if _at(toks, j):
                inner, _ = _paren(toks, j)
                table.uniques.append(_names(inner))
        elif _is(word, "FOREIGN") and _is(_at(toks, i + 1), "KEY"):
            self.foreign_key(table.name, toks, i + 2, line)

    def foreign_key(self, table: str, toks: list[Tok], j: int, line: int) -> None:
        while _at(toks, j) and toks[j].text != "(":
            j += 1  # MySQL: FOREIGN KEY fk_name (...)
        if not _at(toks, j):
            return
        inner, j = _paren(toks, j)
        cols = _names(inner)
        if not _is(_at(toks, j), "REFERENCES"):
            self.parsed.problems.append(
                f"line {line}: FOREIGN KEY in {table} has no REFERENCES clause"
            )
            return
        ref, _ = _references(toks, j + 1)
        if ref is None:
            self.parsed.problems.append(
                f"line {line}: FOREIGN KEY in {table} references no table"
            )
            return
        self.parsed.foreign_keys.append(ForeignKey(table, cols, ref[0], ref[1], line))

    def column(self, table: Table, toks: list[Tok]) -> None:
        col = Column(toks[0].name, line=toks[0].line)
        i = 1
        type_toks: list[Tok] = []
        while i < len(toks):
            t = toks[i]
            if t.kind == "word" and t.upper in _CONSTRAINT_WORDS:
                # "double precision", "character varying" and "with time zone" are types
                if t.upper == "CHARACTER" and not type_toks:
                    pass
                else:
                    break
            if t.text == "(":
                inner, i = _paren(toks, i)
                type_toks += [Tok("op", "(", t.line), *inner, Tok("op", ")", t.line)]
                continue
            type_toks.append(t)
            i += 1
        col.type = _text(type_toks)
        while i < len(toks):
            t = toks[i]
            up = t.upper
            if up == "NOT" and _is(_at(toks, i + 1), "NULL"):
                col.nullable = False
                i += 2
            elif up == "NULL":
                i += 1
            elif up == "PRIMARY" and _is(_at(toks, i + 1), "KEY"):
                col.pk, col.nullable = True, False
                i += 2
            elif up == "UNIQUE":
                col.unique = True
                i += 2 if _is(_at(toks, i + 1), "KEY") else 1
            elif up == "REFERENCES":
                ref, i = _references(toks, i + 1)
                if ref is not None:
                    col.fk = (ref[0], ref[1][0] if ref[1] else "")
                    self.parsed.foreign_keys.append(
                        ForeignKey(table.name, [col.name], ref[0], ref[1][:1], col.line)
                    )
            elif up == "DEFAULT":
                j = i + 1
                expr: list[Tok] = []
                while j < len(toks):
                    u = toks[j]
                    if u.text == "(":
                        inner, j = _paren(toks, j)
                        expr += [Tok("op", "(", u.line), *inner, Tok("op", ")", u.line)]
                        continue
                    if u.kind == "word" and u.upper in _CONSTRAINT_WORDS - {"NULL"}:
                        break
                    if u.upper == "NOT" or (u.upper == "NULL" and expr):
                        break
                    expr.append(u)
                    j += 1
                col.default = _text(expr)
                i = j
            elif up == "COMMENT" and _at(toks, i + 1) and toks[i + 1].kind == "string":
                col.note = _string(toks[i + 1])
                i += 2
            elif up in {"CHECK", "GENERATED", "AS"} and _at(toks, i + 1):
                # skip to the parenthesised expression and past it
                j = i + 1
                while _at(toks, j) and toks[j].text != "(":
                    j += 1
                i = _paren(toks, j)[1] if _at(toks, j) else len(toks)
            else:
                i += 1
        table.columns.append(col)

    def alter(self, toks: list[Tok], i: int) -> None:
        line = toks[0].line
        while _is(_at(toks, i), "IF", "EXISTS", "ONLY"):
            i += 1
        parts, i = _qualified(toks, i)
        if not parts:
            return
        for action in _split(toks[i:]):
            if not _is(_at(action, 0), "ADD"):
                continue
            j = 1
            if _is(_at(action, j), "CONSTRAINT"):
                j += 2
            if _is(_at(action, j), "FOREIGN") and _is(_at(action, j + 1), "KEY"):
                self.foreign_key(parts[-1], action, j + 2, action[0].line or line)
            elif _is(_at(action, j), "PRIMARY") and _is(_at(action, j + 1), "KEY"):
                k = j + 2
                while _at(action, k) and action[k].text != "(":
                    k += 1
                if _at(action, k):
                    self.pending_pk.append((parts[-1], _names(_paren(action, k)[0])))

    def comment(self, toks: list[Tok]) -> None:
        kind = _at(toks, 2)
        if not _is(kind, "TABLE", "COLUMN"):
            return
        parts, i = _qualified(toks, 3)
        if not (_is(_at(toks, i), "IS") and _at(toks, i + 1)):
            return
        value = toks[i + 1]
        if value.kind != "string":
            return
        text = _string(value)
        if kind is not None and kind.upper == "TABLE" and parts:
            self.pending_notes.append((parts[-1], "", text))
        elif len(parts) >= 2:
            self.pending_notes.append((parts[-2], parts[-1], text))


def parse_ddl(code: str) -> Parsed:
    parsed = Parsed()
    reader = _Reader(parsed)
    for stmt in _statements(_tokens(code, parsed)):
        try:
            reader.statement(stmt)
        except (IndexError, ValueError):  # pragma: no cover - defensive: skip it
            parsed.problems.append(
                f"line {stmt[0].line}: could not read this statement; check its brackets"
            )
    by_name = {t.name.lower(): t for t in parsed.tables}
    for name, cols in reader.pending_pk:
        table = by_name.get(name.lower())
        if table is not None:
            table.primary_key = cols
    for name, col, text in reader.pending_notes:
        table = by_name.get(name.lower())
        if table is None:
            continue
        if not col:
            table.note = text
        elif (c := table.column(col)) is not None:
            c.note = text
    return parsed
