"""Parse and check an XState-like state machine.

The source is JSON::

    {"id": "light", "title": "Traffic light", "initial": "green",
     "context": {...},
     "states": {
       "green": {"on": {"TIMER": "yellow"}},
       "yellow": {"on": {"TIMER": {"target": "red", "guard": "safe", "actions": ["log"]}}},
       "red": {"type": "final"}}}

Every problem is collected and reported together, each naming the state path
(``state "checkout.payment"``) so a model can fix them in one pass. States nothing can
reach are not errors; :func:`warnings_for` lists them.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from typing import Any

MAX_STATES = 300
MAX_SOURCE = 400_000
STATE_TYPES = ("atomic", "compound", "parallel", "final", "history")
#: keys a state may have; ``meta``, ``tags`` and ``invoke`` are accepted and ignored
STATE_KEYS = frozenset(
    {
        "on",
        "entry",
        "exit",
        "type",
        "initial",
        "states",
        "description",
        "id",
        "label",
        "onDone",
        "always",
        "after",
        "history",
        "target",
        "meta",
        "tags",
        "invoke",
    }
)
MACHINE_KEYS = frozenset(
    {
        "id",
        "title",
        "initial",
        "context",
        "states",
        "type",
        "description",
        "theme",
        "direction",
        "on",
        "entry",
        "exit",
        "version",
        "predictableActionArguments",
    }
)
TRANSITION_KEYS = frozenset(
    {"target", "guard", "cond", "actions", "description", "reenter", "internal"}
)


class SpecError(ValueError):
    """The source is not a valid state machine; ``problems`` lists every issue."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass
class Transition:
    id: str
    source: str
    event: str
    targets: list[str]
    guard: str | None = None
    actions: list[str] = field(default_factory=list)
    #: "event", "done" (onDone, fired automatically), "always" or "after"
    kind: str = "event"

    @property
    def label(self) -> str:
        text = "onDone" if self.kind == "done" else self.event
        if self.guard:
            text += f" [{self.guard}]"
        if self.actions:
            text += " / " + ", ".join(self.actions)
        return text


@dataclass
class State:
    id: str
    key: str
    parent: str | None
    type: str = "atomic"
    label: str = ""
    initial: str | None = None
    children: list[str] = field(default_factory=list)
    entry: list[str] = field(default_factory=list)
    exit: list[str] = field(default_factory=list)
    description: str = ""
    history: str = "shallow"
    history_target: str | None = None
    transitions: list[Transition] = field(default_factory=list)
    depth: int = 0
    alias: str | None = None  # the state's own ``id`` field, for ``#alias`` targets

    @property
    def name(self) -> str:
        return self.label or self.key


@dataclass
class Machine:
    id: str
    title: str
    description: str
    context: Any
    theme: str
    direction: str
    states: dict[str, State]
    transitions: list[Transition]

    @property
    def root(self) -> State:
        return self.states[""]

    def path(self, state_id: str) -> str:
        return state_id or "(machine)"


def _where(state_id: str) -> str:
    return f'state "{state_id}"' if state_id else "the machine"


def _names(value: Any, where: str, what: str, problems: list[str]) -> list[str]:
    """Action lists: a string, a list of strings, or ``{"type": name}`` objects."""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    out: list[str] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict) and isinstance(item.get("type"), str):
            out.append(item["type"])
        else:
            problems.append(
                f"{where}: {what} must be a name or a list of names, got {json.dumps(item)[:60]}"
            )
    return out


class _Parser:
    def __init__(self, max_states: int) -> None:
        self.max_states = max_states
        self.problems: list[str] = []
        self.states: dict[str, State] = {}
        self.raw: dict[str, dict[str, Any]] = {}
        self.transitions: list[Transition] = []
        self.too_many = False
        self.machine_id = "machine"

    # ---- states ---------------------------------------------------------------------
    def state(
        self, key: str, data: Any, parent: State | None, *, root: bool = False
    ) -> None:
        state_id = (
            "" if root else (f"{parent.id}.{key}" if parent and parent.id else key)
        )
        where = _where(state_id)
        if not isinstance(data, dict):
            self.problems.append(
                f'{where} must be an object like {{"on": {{...}}}}, got {type(data).__name__}'
            )
            data = {}
        if not root:
            if not key or "." in key or key.startswith("#"):
                self.problems.append(
                    f'{where}: state names cannot be empty, contain "." or start with "#"'
                )
            unknown = sorted(set(data) - STATE_KEYS)
            if unknown:
                self.problems.append(
                    f"{where}: unknown key{'s' if len(unknown) > 1 else ''} "
                    f"{', '.join(repr(k) for k in unknown)}; a state may have "
                    + ", ".join(sorted(STATE_KEYS - {"meta", "tags", "invoke"}))
                )
        if len(self.states) >= self.max_states:
            self.too_many = True
            return
        children = data.get("states")
        if children is not None and not isinstance(children, dict):
            self.problems.append(f'{where}: "states" must be an object of named states')
            children = None
        kind = data.get("type")
        if kind is None:
            kind = "compound" if children else "atomic"
        if kind not in STATE_TYPES:
            self.problems.append(
                f'{where}: unknown type "{kind}"; use one of {", ".join(STATE_TYPES)}'
            )
            kind = "compound" if children else "atomic"
        if root and kind not in ("compound", "parallel"):
            kind = "compound"
        st = State(
            id=state_id,
            key=key,
            parent=None if parent is None else parent.id,
            type=kind,
            depth=0 if parent is None else parent.depth + 1,
        )
        label = data.get("label")
        if isinstance(label, str):
            st.label = label.strip()
        description = data.get("description")
        if isinstance(description, str):
            st.description = description.strip()
        elif description is not None:
            self.problems.append(f'{where}: "description" must be text')
        if isinstance(data.get("id"), str) and not root:
            st.alias = data["id"]
        st.entry = _names(data.get("entry"), where, '"entry"', self.problems)
        st.exit = _names(data.get("exit"), where, '"exit"', self.problems)
        self.states[state_id] = st
        self.raw[state_id] = data

        if kind in ("atomic", "final", "history") and children:
            self.problems.append(
                f'{where} is {kind} and cannot have child "states"; '
                'use "type": "compound" or "parallel"'
            )
            children = None
        if kind in ("compound", "parallel") and not children:
            self.problems.append(f'{where} is {kind} but has no child "states"')
        if kind == "final":
            for bad in ("on", "always", "after", "onDone"):
                if data.get(bad):
                    self.problems.append(
                        f'{where} is final and cannot have "{bad}": nothing leaves a final state'
                    )
        if kind == "history":
            hist = data.get("history", "shallow")
            if hist not in ("shallow", "deep"):
                self.problems.append(
                    f'{where}: "history" must be "shallow" or "deep", got {json.dumps(hist)}'
                )
                hist = "shallow"
            st.history = hist
            for bad in ("on", "entry", "exit", "always", "after", "onDone"):
                if data.get(bad):
                    self.problems.append(
                        f'{where} is a history state and cannot have "{bad}"'
                    )
        for child_key, child in (children or {}).items():
            st.children.append(f"{state_id}.{child_key}" if state_id else child_key)
            self.state(str(child_key), child, st)

        if kind == "compound":
            initial = data.get("initial")
            names = [self.states[c].key for c in st.children if c in self.states]
            if initial is None:
                if names:
                    self.problems.append(
                        f'{where} is compound but has no "initial"; set it to one of '
                        + ", ".join(names)
                    )
            elif not isinstance(initial, str) or initial not in names:
                hint = difflib.get_close_matches(str(initial), names, n=1)
                self.problems.append(
                    f'{where}: initial "{initial}" is not one of its child states'
                    + (f'; did you mean "{hint[0]}"?' if hint else "")
                    + (f" (children: {', '.join(names)})" if names else "")
                )
            else:
                st.initial = f"{state_id}.{initial}" if state_id else initial
                if self.states[st.initial].type == "history":
                    self.problems.append(
                        f'{where}: initial "{initial}" cannot be a history state'
                    )
        elif data.get("initial") is not None and kind == "parallel":
            self.problems.append(
                f'{where} is parallel: every region starts at once, so it takes no "initial"'
            )

    # ---- transitions ------------------------------------------------------------------
    def transitions_of(self, st: State) -> None:
        data = self.raw[st.id]
        where = _where(st.id)
        on = data.get("on")
        if on is not None and not isinstance(on, dict):
            self.problems.append(
                f'{where}: "on" must map event names to targets, like {{"NEXT": "done"}}'
            )
            on = None
        for event, spec in (on or {}).items():
            if not str(event).strip():
                self.problems.append(f"{where}: an event name is empty")
                continue
            self.alternatives(st, str(event), spec, "event")
        if data.get("onDone") is not None:
            if st.type not in ("compound", "parallel"):
                self.problems.append(
                    f'{where}: "onDone" only applies to compound and parallel states'
                )
            else:
                self.alternatives(
                    st, f"done.state.{st.id or 'machine'}", data["onDone"], "done"
                )
        if data.get("always") is not None:
            self.alternatives(st, "always", data["always"], "always")
        after = data.get("after")
        if after is not None:
            if not isinstance(after, dict):
                self.problems.append(
                    f'{where}: "after" must map delays to targets, like {{"1000": "next"}}'
                )
            else:
                for delay, spec in after.items():
                    text = f"{delay}ms" if str(delay).isdigit() else str(delay)
                    self.alternatives(st, f"after {text}", spec, "after")

    def alternatives(self, st: State, event: str, spec: Any, kind: str) -> None:
        where = _where(st.id)
        items = spec if isinstance(spec, list) else [spec]
        if not items:
            self.problems.append(
                f'{where}: event "{event}" has an empty list of transitions'
            )
        for item in items:
            if isinstance(item, str) or item is None:
                item = {"target": item}
            if not isinstance(item, dict):
                self.problems.append(
                    f'{where}: event "{event}" must target a state name or '
                    '{"target": ..., "guard": ..., "actions": [...]}'
                )
                continue
            unknown = sorted(set(item) - TRANSITION_KEYS)
            if unknown:
                self.problems.append(
                    f'{where}: event "{event}" has unknown key(s) '
                    + ", ".join(repr(k) for k in unknown)
                    + "; use target, guard, actions"
                )
            raw_targets = item.get("target")
            if raw_targets is None:
                targets: list[str] = []
            elif isinstance(raw_targets, str):
                targets = [raw_targets]
            elif isinstance(raw_targets, list) and all(
                isinstance(t, str) for t in raw_targets
            ):
                targets = list(raw_targets)
            else:
                self.problems.append(
                    f'{where}: event "{event}" target must be a state name or a list of names'
                )
                targets = []
            resolved: list[str] = []
            for target in targets:
                found = self.resolve(st, target)
                if found is None:
                    self.problems.append(self.unknown_target(st, event, target))
                elif found == "":
                    self.problems.append(
                        f'{where}: event "{event}" cannot target the machine itself'
                    )
                else:
                    resolved.append(found)
            guard = item.get("guard", item.get("cond"))
            if isinstance(guard, dict) and isinstance(guard.get("type"), str):
                guard = guard["type"]
            if guard is not None and not isinstance(guard, str):
                self.problems.append(f'{where}: event "{event}" guard must be a name')
                guard = None
            actions = _names(
                item.get("actions"),
                f'{where}, event "{event}"',
                '"actions"',
                self.problems,
            )
            if not targets and not actions and kind != "event":
                self.problems.append(f'{where}: "{event}" needs a target')
            tr = Transition(
                id=f"t{len(self.transitions)}",
                source=st.id,
                event=event,
                targets=resolved,
                guard=guard or None,
                actions=actions,
                kind=kind,
            )
            self.transitions.append(tr)
            st.transitions.append(tr)

    def resolve(self, st: State, target: str) -> str | None:
        target = target.strip()
        if not target:
            return None
        if target.startswith("#"):
            ref = target[1:]
            for s in self.states.values():
                if s.alias == ref and s.key:
                    return s.id
            head, _, rest = ref.partition(".")
            if head == self.machine_id:
                return rest if rest in self.states else None
            return ref if ref in self.states else None
        if target.startswith("."):
            ref = f"{st.id}{target}" if st.id else target[1:]
            return ref if ref in self.states else None
        # a sibling first, then the siblings of each ancestor, then a path from the root
        cursor = self.states.get(st.parent) if st.parent is not None else None
        while cursor is not None:
            ref = f"{cursor.id}.{target}" if cursor.id else target
            if ref in self.states:
                return ref
            cursor = (
                self.states.get(cursor.parent) if cursor.parent is not None else None
            )
        return target if target in self.states else None

    def unknown_target(self, st: State, event: str, target: str) -> str:
        pool = sorted(
            {s.id for s in self.states.values() if s.id}
            | {s.key for s in self.states.values() if s.key}
        )
        hint = difflib.get_close_matches(target.lstrip("#."), pool, n=3, cutoff=0.5)
        message = (
            f'{_where(st.id)}: event "{event}" targets "{target}", which does not exist'
        )
        if hint:
            message += "; did you mean " + " or ".join(f'"{h}"' for h in hint) + "?"
        siblings = (
            [self.states[c].key for c in self.states[st.parent].children]
            if st.parent is not None and st.parent in self.states
            else []
        )
        if siblings:
            message += f" (siblings: {', '.join(siblings)})"
        return message

    def history_targets(self) -> None:
        for st in self.states.values():
            if st.type != "history" or not st.key:
                continue
            target = self.raw[st.id].get("target")
            if target is None:
                continue
            found = self.resolve(st, target) if isinstance(target, str) else None
            parent = st.parent or ""
            if found is None:
                self.problems.append(
                    f'{_where(st.id)}: default target "{target}" does not exist'
                )
            elif not (parent == "" or found.startswith(parent + ".")):
                self.problems.append(
                    f'{_where(st.id)}: default target "{target}" must be inside "{parent}"'
                )
            else:
                st.history_target = found

    def run(self, code: str) -> Machine:
        if len(code) > MAX_SOURCE:
            raise SpecError(
                [f"source is too large: the limit is {MAX_SOURCE} characters"]
            )
        try:
            data = json.loads(code)
        except json.JSONDecodeError as exc:
            raise SpecError(
                [
                    f"source is not valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"
                ]
            ) from None
        if not isinstance(data, dict):
            raise SpecError(
                [
                    'source must be a JSON object like {"initial": "idle", "states": {...}}'
                ]
            )
        unknown = sorted(set(data) - MACHINE_KEYS)
        if unknown:
            self.problems.append(
                "unknown top-level key(s) "
                + ", ".join(repr(k) for k in unknown)
                + "; use id, title, initial, context, states, description, theme, direction"
            )
        if not isinstance(data.get("states"), dict) or not data["states"]:
            raise SpecError(
                ['"states" is required: an object of named states, like {"idle": {}}']
                + self.problems
            )
        self.machine_id = (
            data.get("id") if isinstance(data.get("id"), str) else "machine"
        )
        root_data = {
            k: data[k]
            for k in ("states", "initial", "type", "on", "entry", "exit")
            if k in data
        }
        if root_data.get("type") not in (None, "compound", "parallel"):
            self.problems.append('the machine "type" must be "compound" or "parallel"')
            root_data.pop("type")
        self.state("", root_data, None, root=True)
        if self.too_many:
            raise SpecError(
                [f"too many states: the limit is {self.max_states}", *self.problems]
            )
        for st in list(self.states.values()):
            self.transitions_of(st)
        self.history_targets()
        theme = data.get("theme", "auto")
        if theme not in ("auto", "light", "dark"):
            self.problems.append('"theme" must be "auto", "light" or "dark"')
            theme = "auto"
        direction = str(data.get("direction", "LR")).upper()
        if direction not in ("LR", "TB"):
            self.problems.append(
                '"direction" must be "LR" (left to right) or "TB" (top down)'
            )
            direction = "LR"
        title = data.get("title")
        if title is not None and not isinstance(title, str):
            self.problems.append('"title" must be text')
            title = None
        if self.problems:
            raise SpecError(self.problems)
        description = data.get("description")
        return Machine(
            id=self.machine_id,
            title=(
                title or self.machine_id.replace("_", " ").replace("-", " ").title()
            ).strip(),
            description=description if isinstance(description, str) else "",
            context=data.get("context"),
            theme=theme,
            direction=direction,
            states=self.states,
            transitions=self.transitions,
        )


def parse(code: str, *, max_states: int = MAX_STATES) -> Machine:
    """The machine in ``code``; raises :class:`SpecError` listing every problem."""
    return _Parser(max_states).run(code)


def reachable(machine: Machine) -> set[str]:
    """States some sequence of events can enter, starting from the initial configuration."""
    states = machine.states
    seen: set[str] = set()
    todo = [""]

    def visit(state_id: str) -> None:
        cursor: str | None = state_id
        while cursor is not None and cursor not in seen:
            seen.add(cursor)
            todo.append(cursor)
            cursor = states[cursor].parent

    while todo:
        st = states[todo.pop()]
        if st.type == "compound" and st.initial:
            visit(st.initial)
        elif st.type == "parallel":
            for child in st.children:
                visit(child)
        elif st.type == "history":
            # with no history yet it takes its default; otherwise it restores states
            # that were reached before
            parent = states[st.parent or ""]
            default = st.history_target or parent.initial
            if default:
                visit(default)
        for tr in st.transitions:
            for target in tr.targets:
                visit(target)
    return seen


def warnings_for(machine: Machine) -> list[str]:
    """Things that render but are probably mistakes: unreachable states."""
    seen = reachable(machine)
    out = []
    for st in machine.states.values():
        if st.id and st.id not in seen:
            parent = machine.states.get(st.parent or "")
            # children of an unreachable state are covered by their parent's warning
            if parent is not None and parent.id and parent.id not in seen:
                continue
            out.append(
                f"{_where(st.id)} is unreachable: no initial state or transition leads to it"
            )
    return out
