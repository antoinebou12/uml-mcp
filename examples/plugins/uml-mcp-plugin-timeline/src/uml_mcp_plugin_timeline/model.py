"""The timeline source: JSON lanes and items, parsed and checked with readable messages.

Dates are ISO days (``2026-11-07``), months (``2026-11``) or quarters (``2026-Q3``). A month or
quarter used as a ``start`` means its first day and, as an ``end``, its last day. Every date is
held as an *epoch day* (days since 1970-01-01) and ``end`` is inclusive.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

MAX_ITEMS = 400
MAX_LANES = 40
MAX_TEXT = 400
KINDS = ("task", "milestone", "phase", "release")
POINT_KINDS = ("milestone", "release")
STATUSES = ("planned", "active", "done", "blocked", "at-risk")
SCALES = ("day", "week", "month", "quarter")
THEMES = ("auto", "light", "dark")
PALETTE = (
    "#6366f1",
    "#0ea5e9",
    "#14b8a6",
    "#f59e0b",
    "#ec4899",
    "#8b5cf6",
    "#22c55e",
    "#ef4444",
)
EPOCH = date(1970, 1, 1)

_TOP_KEYS = {
    "title",
    "subtitle",
    "today",
    "scale",
    "theme",
    "lanes",
    "items",
    "$schema",
}
_LANE_KEYS = {"id", "name", "color"}
_ITEM_KEYS = {
    "id",
    "lane",
    "name",
    "start",
    "end",
    "kind",
    "status",
    "owner",
    "progress",
    "depends_on",
    "link",
    "note",
}
#: field names models reach for, and the one this format uses
_ALIASES = {
    "title": "name",
    "label": "name",
    "type": "kind",
    "start_date": "start",
    "end_date": "end",
    "due": "end",
    "dependencies": "depends_on",
    "depends": "depends_on",
    "after": "depends_on",
    "url": "link",
    "assignee": "owner",
    "description": "note",
    "notes": "note",
    "colour": "color",
    "label_color": "color",
}
_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_QUARTER = re.compile(r"^(\d{4})-[Qq]([1-4])$")
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_LINK = re.compile(r"^https://[^\s\"'<>]+$")


class SpecError(ValueError):
    """One or more problems in a timeline source; ``problems`` lists each message."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass(frozen=True)
class Lane:
    id: str
    name: str
    color: str


@dataclass(frozen=True)
class Item:
    id: str
    lane: str
    name: str
    kind: str
    status: str
    start: int
    end: int
    owner: str
    progress: int
    depends_on: tuple[str, ...]
    link: str
    note: str

    @property
    def point(self) -> bool:
        return self.kind in POINT_KINDS


@dataclass(frozen=True)
class Timeline:
    title: str
    subtitle: str
    today: int | None
    scale: str | None
    theme: str
    lanes: tuple[Lane, ...]
    items: tuple[Item, ...]

    @property
    def span(self) -> tuple[int, int]:
        """First day and the day after the last one (exclusive)."""
        return (
            min(i.start for i in self.items),
            max(i.end for i in self.items) + 1,
        )

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["items"] = [asdict(i) | {"point": i.point} for i in self.items]
        return data


def to_day(value: date) -> int:
    return (value - EPOCH).days


def from_day(day: int) -> date:
    return EPOCH + timedelta(days=day)


def iso(day: int) -> str:
    return from_day(day).isoformat()


def parse_date(text: Any, *, end: bool = False) -> int:
    """An epoch day, or ``ValueError`` with the reason. ``end`` picks a period's last day."""
    if not isinstance(text, str):
        raise TypeError("must be a date string such as 2026-11-07 or 2026-Q3")
    raw = text.strip()
    if m := _DAY.match(raw):
        try:
            return to_day(date(int(m[1]), int(m[2]), int(m[3])))
        except ValueError as exc:
            raise ValueError(f'"{raw}" is not a real date ({exc})') from None
    if m := _MONTH.match(raw):
        year, month = int(m[1]), int(m[2])
        if not 1 <= month <= 12:
            raise ValueError(f'"{raw}" has no month {month}')
        first = date(year, month, 1)
        if not end:
            return to_day(first)
        following = date(year + month // 12, month % 12 + 1, 1)
        return to_day(following) - 1
    if m := _QUARTER.match(raw):
        year, quarter = int(m[1]), int(m[2])
        first = date(year, quarter * 3 - 2, 1)
        if not end:
            return to_day(first)
        following = (
            date(year + 1, 1, 1) if quarter == 4 else date(year, quarter * 3 + 1, 1)
        )
        return to_day(following) - 1
    raise ValueError(f'"{raw}" is not a date; use YYYY-MM-DD, YYYY-MM or YYYY-Qn')


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise TypeError("must be text")
    return str(value).strip()[:MAX_TEXT]


def _unknown(keys: set[str], allowed: set[str], where: str) -> list[str]:
    problems = []
    for key in sorted(keys - allowed):
        hint = _ALIASES.get(key)
        if hint and hint in allowed:
            problems.append(f'{where}: unknown field "{key}"; use "{hint}"')
        else:
            problems.append(
                f'{where}: unknown field "{key}"; fields are {", ".join(sorted(allowed))}'
            )
    return problems


def _find_cycle(deps: dict[str, tuple[str, ...]]) -> list[str] | None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for nxt in deps.get(node, ()):
            if nxt not in deps:
                continue
            if state.get(nxt) == 1:
                return stack[stack.index(nxt) :] + [nxt]
            if nxt not in state and (found := visit(nxt)):
                return found
        stack.pop()
        state[node] = 2
        return None

    for node in deps:
        if node not in state and (found := visit(node)):
            return found
    return None


def parse(code: str, *, max_items: int = MAX_ITEMS) -> Timeline:
    """Parse and check a timeline source. Raises :class:`SpecError` listing every problem."""
    try:
        data = json.loads(code)
    except (TypeError, ValueError) as exc:
        raise SpecError([f"source is not valid JSON: {exc}"]) from None
    if not isinstance(data, dict):
        raise SpecError(["source must be a JSON object with lanes and items"])
    problems = _unknown(set(data), _TOP_KEYS, "timeline")

    def field(where: str, name: str, value: Any, default: str = "") -> str:
        try:
            return _text(value, default)
        except (TypeError, ValueError) as exc:
            problems.append(f"{where}: {name} {exc}")
            return default

    title = field("timeline", "title", data.get("title"), "Roadmap") or "Roadmap"
    subtitle = field("timeline", "subtitle", data.get("subtitle"))
    today: int | None = None
    if data.get("today") not in (None, ""):
        try:
            today = parse_date(data["today"])
        except (TypeError, ValueError) as exc:
            problems.append(f"timeline: today {exc}")
    scale = data.get("scale")
    if scale is not None and scale not in SCALES:
        problems.append(f'timeline: scale "{scale}" is not one of {", ".join(SCALES)}')
        scale = None
    theme = data.get("theme") or "auto"
    if theme not in THEMES:
        problems.append(f'timeline: theme "{theme}" is not one of {", ".join(THEMES)}')
        theme = "auto"

    raw_lanes = data.get("lanes")
    raw_items = data.get("items")
    if not isinstance(raw_lanes, list) or not raw_lanes:
        problems.append(
            'timeline: "lanes" must be a non-empty list of {id, name, color}'
        )
        raw_lanes = []
    if not isinstance(raw_items, list) or not raw_items:
        problems.append('timeline: "items" must be a non-empty list of items')
        raw_items = []
    if len(raw_lanes) > MAX_LANES:
        problems.append(f"timeline: {len(raw_lanes)} lanes; the limit is {MAX_LANES}")
    if len(raw_items) > max_items:
        problems.append(f"timeline: {len(raw_items)} items; the limit is {max_items}")
    if problems and (not raw_lanes or not raw_items or len(raw_items) > max_items):
        raise SpecError(problems)

    lanes: list[Lane] = []
    for n, raw in enumerate(raw_lanes[:MAX_LANES]):
        where = f"lane {n + 1}"
        if not isinstance(raw, dict):
            problems.append(f"{where}: must be an object with id, name and color")
            continue
        lane_id = field(where, "id", raw.get("id"))
        if not lane_id:
            problems.append(f"{where}: id is required")
            continue
        where = f'lane "{lane_id}"'
        problems += _unknown(set(raw), _LANE_KEYS, where)
        if any(lane.id == lane_id for lane in lanes):
            problems.append(f"{where}: duplicate lane id")
            continue
        color = raw.get("color") or PALETTE[n % len(PALETTE)]
        if not isinstance(color, str) or not _HEX.match(color):
            problems.append(
                f'{where}: color "{color}" must be a hex colour like #6366f1'
            )
            color = PALETTE[n % len(PALETTE)]
        name = field(where, "name", raw.get("name"), lane_id) or lane_id
        lanes.append(Lane(lane_id, name, color.lower()))
    lane_ids = [lane.id for lane in lanes]

    items: list[Item] = []
    seen: set[str] = set()
    for n, raw in enumerate(raw_items):
        where = f"item {n + 1}"
        if not isinstance(raw, dict):
            problems.append(f"{where}: must be an object with id, lane, name and start")
            continue
        item_id = field(where, "id", raw.get("id"))
        if not item_id:
            problems.append(f"{where}: id is required")
            continue
        where = f'item "{item_id}"'
        problems += _unknown(set(raw), _ITEM_KEYS, where)
        if item_id in seen:
            problems.append(f"{where}: duplicate item id")
            continue
        seen.add(item_id)

        kind = raw.get("kind") or "task"
        if kind not in KINDS:
            problems.append(f'{where}: kind "{kind}" is not one of {", ".join(KINDS)}')
            kind = "task"
        status = raw.get("status") or "planned"
        if status not in STATUSES:
            problems.append(
                f'{where}: status "{status}" is not one of {", ".join(STATUSES)}'
            )
            status = "planned"

        lane = raw.get("lane")
        if lane in (None, "") and len(lane_ids) == 1:
            lane = lane_ids[0]
        if lane in (None, ""):
            problems.append(f"{where}: lane is required (lanes: {', '.join(lane_ids)})")
            continue
        if lane not in lane_ids:
            problems.append(
                f'{where}: lane "{lane}" is not a lane id (lanes: {", ".join(lane_ids)})'
            )
            continue

        if raw.get("start") in (None, ""):
            problems.append(f"{where}: start is required, e.g. 2026-11-07 or 2026-Q3")
            continue
        try:
            start = parse_date(raw["start"])
        except (TypeError, ValueError) as exc:
            problems.append(f"{where}: start {exc}")
            continue
        end_raw = raw.get("end")
        if end_raw in (None, ""):
            end_raw = None if kind in POINT_KINDS else raw["start"]
        try:
            end = start if end_raw is None else parse_date(end_raw, end=True)
        except (TypeError, ValueError) as exc:
            problems.append(f"{where}: end {exc}")
            continue
        if end < start:
            problems.append(f"{where}: end {iso(end)} is before start {iso(start)}")
            continue
        if kind in POINT_KINDS and end != start:
            problems.append(
                f"{where}: a {kind} is a single date; drop end or use kind task"
            )
            continue

        progress_raw = raw.get("progress")
        if progress_raw is None:
            progress = 100 if status == "done" else 0
        elif (
            isinstance(progress_raw, bool)
            or not isinstance(progress_raw, (int, float))
            or not 0 <= progress_raw <= 100
        ):
            problems.append(f"{where}: progress must be a number from 0 to 100")
            progress = 0
        else:
            progress = round(progress_raw)

        deps_raw = raw.get("depends_on") or []
        if isinstance(deps_raw, str):
            deps_raw = [deps_raw]
        if not isinstance(deps_raw, list) or not all(
            isinstance(d, str) for d in deps_raw
        ):
            problems.append(f"{where}: depends_on must be a list of item ids")
            deps_raw = []
        deps = tuple(dict.fromkeys(d.strip() for d in deps_raw if d.strip()))
        if item_id in deps:
            problems.append(f"{where}: depends on itself")
            deps = tuple(d for d in deps if d != item_id)

        link = field(where, "link", raw.get("link"))
        if link and not _LINK.match(link):
            problems.append(f'{where}: link "{link}" must be an https:// URL')
            link = ""

        items.append(
            Item(
                id=item_id,
                lane=lane,
                name=field(where, "name", raw.get("name"), item_id) or item_id,
                kind=kind,
                status=status,
                start=start,
                end=end,
                owner=field(where, "owner", raw.get("owner")),
                progress=progress,
                depends_on=deps,
                link=link,
                note=field(where, "note", raw.get("note")),
            )
        )

    ids = [i.id for i in items]
    for item in items:
        for dep in item.depends_on:
            if dep not in seen:
                problems.append(
                    f'item "{item.id}": depends_on "{dep}" is not an item id'
                    f" (items: {', '.join(ids[:12])}{'…' if len(ids) > 12 else ''})"
                )
    cycle = _find_cycle({i.id: i.depends_on for i in items})
    if cycle:
        problems.append(f"dependency cycle: {' → '.join(cycle)}")
    if problems:
        raise SpecError(problems)
    return Timeline(
        title=title,
        subtitle=subtitle,
        today=today,
        scale=scale,
        theme=theme,
        lanes=tuple(lanes),
        items=tuple(items),
    )
