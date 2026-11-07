"""Read manifests and lock files into a :class:`~.model.Graph`.

Standard library only (``json``, ``tomllib``, ``re``); nothing is fetched. The file kind
is detected from the text itself:

* JSON: ``package-lock.json`` (v2/v3), ``package.json``, or a generic graph
  ``{root, nodes, edges}``.
* TOML: ``uv.lock`` or ``pyproject.toml`` (PEP 621, ``dependency-groups``, Poetry).
* Anything else is read as ``requirements.txt``.
"""

from __future__ import annotations

import json
import re
import tomllib
from typing import Any

from .model import Edge, Graph, Package, SpecError, pypi_name

THEMES = ("auto", "light", "dark")

# PEP 508, loosely: name, optional [extras], then a version specifier or `@ url`,
# then an optional `; marker`.
_REQ = re.compile(
    r"^(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*"
    r"(?:\[(?P<extras>[^\]]*)\])?\s*"
    r"(?P<spec>@\s*\S+|\(?[<>=!~][^;]*?\)?|)\s*"
    r"(?:;\s*(?P<marker>.+))?$"
)
_EXACT_PEP440 = re.compile(r"^===?\s*([0-9][A-Za-z0-9.+!-]*)$")
_EXACT_SEMVER = re.compile(r"^=?v?(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$")
_REQ_OPTION = re.compile(r"\s--?[a-z][a-z-]*(?:[= ]\S+)?")

_NPM_SECTIONS = (
    ("dependencies", "runtime"),
    ("peerDependencies", "peer"),
    ("optionalDependencies", "optional"),
    ("devDependencies", "dev"),
)


def parse(code: str) -> Graph:
    """Detect the file kind and read it; raise :class:`SpecError` with readable messages."""
    text = code.lstrip("﻿").strip()
    if not text:
        raise SpecError(
            [
                (
                    "the source is empty: paste a package.json, package-lock.json, "
                    "pyproject.toml, requirements.txt or uv.lock, or a JSON graph"
                )
            ]
        )
    if text.startswith("{") or (text.startswith("[") and _is_json(text)):
        graph = _parse_json(text)
    elif _looks_like_toml(text):
        graph = _parse_toml(text)
    else:
        graph = _requirements(text)
    return graph.finish()


# ----------------------------------------------------------------------------- JSON


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


def _parse_json(text: str) -> Graph:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SpecError(
            [
                (
                    f"the source looks like JSON but could not be parsed: {exc.msg} "
                    f"at line {exc.lineno}, column {exc.colno}"
                )
            ]
        ) from exc
    if not isinstance(data, dict):
        raise SpecError(
            [
                (
                    "JSON source must be an object: a package.json, a package-lock.json, or "
                    '{"root": ..., "nodes": [...], "edges": [...]}'
                )
            ]
        )
    if "lockfileVersion" in data:
        graph = _package_lock(data)
    elif isinstance(data.get("nodes"), list):
        graph = _generic(data)
    elif any(k in data for k in ("name", "version", "dependencies", "devDependencies")):
        graph = _package_json(data)
    else:
        raise SpecError(
            [
                (
                    "could not tell which file this JSON is: expected package.json (name, "
                    "dependencies), package-lock.json (lockfileVersion, packages) or a graph "
                    "with nodes and edges"
                )
            ]
        )
    _options(graph, data)
    return graph


def _options(graph: Graph, data: dict[str, Any]) -> None:
    theme = data.get("theme")
    if isinstance(theme, str) and theme.lower() in THEMES:
        graph.theme = theme.lower()
    title = data.get("title")
    if isinstance(title, str) and title.strip():
        graph.title = title.strip()[:120]


def _exact_npm(spec: str) -> str:
    match = _EXACT_SEMVER.match(spec.strip())
    return match.group(1) if match else ""


def _package_json(data: dict[str, Any]) -> Graph:
    name = _str(data.get("name")) or "package.json"
    root = Package(
        id=name,
        name=name,
        version=_str(data.get("version")),
        license=_license(data.get("license")),
        ecosystem="npm",
        root=True,
    )
    graph = Graph("package.json", root.id)
    graph.add(root)
    problems: list[str] = []
    optional_peers = {
        k
        for k, v in (data.get("peerDependenciesMeta") or {}).items()
        if isinstance(v, dict) and v.get("optional")
    }
    for section, kind in _NPM_SECTIONS:
        deps = data.get(section)
        if deps is None:
            continue
        if not isinstance(deps, dict):
            problems.append(f"package.json: {section} must be an object of name: range")
            continue
        for dep, spec in deps.items():
            if not isinstance(spec, str):
                problems.append(
                    f"package.json: {section}.{dep} must be a version range string"
                )
                continue
            dep_kind = "optional" if kind == "peer" and dep in optional_peers else kind
            pkg = graph.add(
                Package(
                    id=dep,
                    name=dep,
                    version=_exact_npm(spec),
                    kind=dep_kind,
                    ecosystem="npm",
                )
            )
            graph.link(Edge(root.id, pkg.id, spec, dep_kind))
    if problems:
        raise SpecError(problems)
    return graph


def _license(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()[:40]
    if isinstance(value, dict) and isinstance(value.get("type"), str):
        return value["type"].strip()[:40]
    if isinstance(value, list):
        names = [_license(v) for v in value]
        return " OR ".join(n for n in names if n)[:40]
    return ""


def _str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _npm_name(path: str, entry: dict[str, Any]) -> str:
    if isinstance(entry.get("name"), str) and entry["name"]:
        return entry["name"]
    cut = path.rfind("node_modules/")
    return path[cut + len("node_modules/") :] if cut >= 0 else path


def _package_lock(data: dict[str, Any]) -> Graph:
    version = data.get("lockfileVersion")
    packages = data.get("packages")
    if not isinstance(packages, dict):
        raise SpecError(
            [
                (
                    f"package-lock.json lockfileVersion {version} has no `packages` map; "
                    "regenerate it with npm 7 or later (lockfileVersion 2 or 3)"
                )
            ]
        )
    top = packages.get("")
    if not isinstance(top, dict):
        top = {"name": data.get("name"), "version": data.get("version")}
    name = _str(top.get("name")) or _str(data.get("name")) or "package-lock.json"
    graph = Graph("package-lock.json", "", has_lock=True)
    ids: dict[str, str] = {}

    def node_id(path: str) -> str:
        if path in ids:
            return ids[path]
        entry = packages[path]
        if entry.get("link") and isinstance(entry.get("resolved"), str):
            target = entry["resolved"]
            if target in packages and target != path:
                ids[path] = node_id(target)
                return ids[path]
        if path == "":
            ids[path] = name
            return name
        pname = _npm_name(path, entry)
        ver = _str(entry.get("version"))
        ids[path] = f"{pname}@{ver}" if ver else pname
        return ids[path]

    def resolve(path: str, dep: str) -> str | None:
        cur = path
        while True:
            candidate = f"{cur}/node_modules/{dep}" if cur else f"node_modules/{dep}"
            if candidate in packages:
                return candidate
            if not cur:
                return None
            cut = cur.rfind("/node_modules/")
            cur = cur[:cut] if cut >= 0 else ""

    root_id = node_id("")
    graph.root = root_id
    graph.add(
        Package(
            id=root_id,
            name=name,
            version=_str(top.get("version")),
            license=_license(top.get("license")),
            ecosystem="npm",
            root=True,
        )
    )
    problems: list[str] = []
    for path, entry in packages.items():
        if not isinstance(entry, dict):
            problems.append(f"package-lock.json: packages[{path!r}] must be an object")
            continue
        if path == "" or entry.get("link"):
            continue
        kind = ""
        if entry.get("dev") or entry.get("devOptional"):
            kind = "dev"
        elif entry.get("optional"):
            kind = "optional"
        elif entry.get("peer"):
            kind = "peer"
        graph.add(
            Package(
                id=node_id(path),
                name=_npm_name(path, entry),
                version=_str(entry.get("version")),
                license=_license(entry.get("license")),
                kind=kind,
                ecosystem="npm",
            )
        )
    if problems:
        raise SpecError(problems)
    missing = 0
    for path, entry in packages.items():
        if not isinstance(entry, dict) or (entry.get("link") and path):
            continue
        for section, kind in _NPM_SECTIONS:
            deps = entry.get(section)
            if not isinstance(deps, dict) or (section == "devDependencies" and path):
                continue  # a dependency's own devDependencies are never installed
            for dep, spec in deps.items():
                target = resolve(path, dep)
                if target is None:
                    if kind in ("runtime", "dev"):
                        missing += 1
                    continue
                graph.link(Edge(node_id(path), node_id(target), _str(spec), kind))
    if missing:
        graph.notes.append(
            f"{missing} declared dependenc{'y is' if missing == 1 else 'ies are'} "
            "not in the lock file's packages map"
        )
    return graph


def _generic(data: dict[str, Any]) -> Graph:
    problems: list[str] = []
    ecosystem = _str(data.get("ecosystem")).lower()
    if ecosystem and ecosystem not in ("npm", "pypi"):
        problems.append("ecosystem must be 'npm' or 'pypi'")
        ecosystem = ""
    graph = Graph("JSON graph", "", has_lock=True)
    for i, node in enumerate(data["nodes"]):
        where = f"nodes[{i}]"
        if not isinstance(node, dict):
            problems.append(f"{where} must be an object with an id")
            continue
        nid = node.get("id")
        if not isinstance(nid, str) or not nid.strip():
            problems.append(f"{where} needs a non-empty string id")
            continue
        if nid in graph.packages:
            problems.append(f"{where}: duplicate id {nid!r}")
            continue
        kind = _str(node.get("kind")).lower()
        if kind and kind not in ("runtime", "dev", "optional", "peer"):
            problems.append(
                f"{where} ({nid}): kind must be runtime, dev, optional or peer"
            )
            kind = ""
        if node.get("dev") is True:
            kind = "dev"
        docs = _str(node.get("docs"))
        if docs and not docs.startswith("https://"):
            problems.append(f"{where} ({nid}): docs must be an https:// URL")
            docs = ""
        node_eco = _str(node.get("ecosystem")).lower() or ecosystem
        version = _str(node.get("version"))
        name = _str(node.get("name")) or (
            nid.rsplit("@", 1)[0] if version and nid.endswith("@" + version) else nid
        )
        graph.add(
            Package(
                id=nid,
                name=name,
                version=version,
                license=_license(node.get("license")),
                kind=kind,
                group=_str(node.get("group")),
                ecosystem=node_eco if node_eco in ("npm", "pypi") else "",
                docs=docs,
            )
        )
    root = data.get("root")
    if not isinstance(root, str) or not root:
        problems.append("root must be the id of the project node")
    elif root not in graph.packages:
        graph.add(Package(id=root, name=root))
    edges = data.get("edges", [])
    if not isinstance(edges, list):
        problems.append("edges must be a list of {from, to}")
        edges = []
    known = ", ".join(sorted(graph.packages)[:12])
    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            problems.append(f"edges[{i}] must be an object with from and to")
            continue
        src, dst = edge.get("from"), edge.get("to")
        bad = [
            end
            for end in (src, dst)
            if not isinstance(end, str) or end not in graph.packages
        ]
        if bad:
            problems.append(f"edges[{i}]: unknown node {bad[0]!r} (known ids: {known})")
            continue
        kind = _str(edge.get("kind")).lower()
        if kind not in ("runtime", "dev", "optional", "peer"):
            kind = graph.packages[str(dst)].kind or "runtime"
        graph.link(Edge(str(src), str(dst), _str(edge.get("range")), kind))
    if problems:
        raise SpecError([f"JSON graph: {p}" for p in problems])
    graph.root = str(root)
    graph.packages[graph.root].root = True
    graph.packages[graph.root].kind = ""
    if not any(e.source == graph.root for e in graph.edges):
        graph.has_lock = False
    return graph


# ----------------------------------------------------------------------------- TOML


def _looks_like_toml(text: str) -> bool:
    return bool(
        re.search(r"^\s*\[\[?[A-Za-z0-9_.\"' -]+\]\]?\s*$", text, re.MULTILINE)
        or re.search(r"^\s*[A-Za-z0-9_-]+\s*=\s*[\"'\[{0-9tf]", text, re.MULTILINE)
    )


def _parse_toml(text: str) -> Graph:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        # a requirements file has no `=` sections, so this really was meant as TOML
        raise SpecError(
            [f"the source looks like TOML but could not be parsed: {exc}"]
        ) from exc
    if isinstance(data.get("package"), list):
        if isinstance(data.get("metadata"), dict) and "lock-version" in data.get(
            "metadata", {}
        ):
            raise SpecError(
                [
                    (
                        "poetry.lock is not supported: pass pyproject.toml (direct "
                        "dependencies) or a uv.lock (the full tree)"
                    )
                ]
            )
        return _uv_lock(data)
    if "project" in data or "tool" in data or "dependency-groups" in data:
        return _pyproject(data)
    raise SpecError(
        [
            (
                "could not tell which TOML file this is: expected pyproject.toml ([project] "
                "or [tool.poetry]) or uv.lock ([[package]] entries)"
            )
        ]
    )


def _requirement(line: str, where: str) -> tuple[Package, str] | str:
    """Parse one PEP 508 string; return (package, range) or an error message."""
    match = _REQ.match(line.strip())
    if not match:
        return f"{where}: could not parse requirement {line.strip()!r}"
    name = match.group("name")
    spec = (match.group("spec") or "").strip().strip("()").strip()
    exact = _EXACT_PEP440.match(spec.replace(" ", ""))
    return (
        Package(
            id=pypi_name(name),
            name=name,
            version=exact.group(1) if exact else "",
            ecosystem="pypi",
            extras=(match.group("extras") or "").replace(" ", ""),
            marker=(match.group("marker") or "").strip(),
        ),
        spec,
    )


def _add_reqs(
    graph: Graph,
    items: Any,
    kind: str,
    group: str,
    where: str,
    problems: list[str],
) -> None:
    if not isinstance(items, list):
        problems.append(f"{where} must be a list of requirement strings")
        return
    for i, item in enumerate(items):
        if not isinstance(item, str):
            problems.append(f"{where}[{i}] must be a requirement string")
            continue
        parsed = _requirement(item, f"{where}[{i}]")
        if isinstance(parsed, str):
            problems.append(parsed)
            continue
        package, spec = parsed
        package.kind, package.group = kind, group
        stored = graph.add(package)
        graph.link(Edge(graph.root, stored.id, spec, kind, group))


def _pyproject(data: dict[str, Any]) -> Graph:
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    tool = data.get("tool") if isinstance(data.get("tool"), dict) else {}
    poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
    name = _str(project.get("name")) or _str(poetry.get("name")) or "pyproject.toml"
    version = _str(project.get("version")) or _str(poetry.get("version"))
    graph = Graph("pyproject.toml", pypi_name(name))
    graph.add(
        Package(
            id=graph.root,
            name=name,
            version=version,
            license=_license(project.get("license") or poetry.get("license")),
            ecosystem="pypi",
            root=True,
        )
    )
    problems: list[str] = []
    if "dependencies" in project:
        _add_reqs(
            graph,
            project["dependencies"],
            "runtime",
            "",
            "project.dependencies",
            problems,
        )
    extras = project.get("optional-dependencies") or {}
    if not isinstance(extras, dict):
        problems.append("project.optional-dependencies must be a table of lists")
        extras = {}
    for extra, items in extras.items():
        _add_reqs(
            graph,
            items,
            "optional",
            extra,
            f"project.optional-dependencies.{extra}",
            problems,
        )
    groups = data.get("dependency-groups") or {}
    if not isinstance(groups, dict):
        problems.append("dependency-groups must be a table of lists")
        groups = {}

    def expand(group: str, trail: tuple[str, ...]) -> list[Any]:
        items = groups.get(group)
        if not isinstance(items, list):
            problems.append(f"dependency-groups.{group} must be a list")
            return []
        flat: list[Any] = []
        for item in items:
            if isinstance(item, dict) and "include-group" in item:
                inc = str(item["include-group"])
                if inc in trail:
                    problems.append(
                        f"dependency-groups.{group}: include-group {inc!r} is a cycle"
                    )
                elif inc not in groups:
                    problems.append(
                        f"dependency-groups.{group}: unknown include-group {inc!r}"
                    )
                else:
                    flat.extend(expand(inc, (*trail, inc)))
            else:
                flat.append(item)
        return flat

    for group in groups:
        _add_reqs(
            graph,
            expand(group, (group,)),
            "dev",
            group,
            f"dependency-groups.{group}",
            problems,
        )
    if poetry:
        _poetry(graph, poetry, problems)
    if problems:
        raise SpecError([f"pyproject.toml: {p}" for p in problems])
    if len(graph.packages) == 1:
        graph.notes.append("pyproject.toml declares no dependencies")
    return graph


def _poetry(graph: Graph, poetry: dict[str, Any], problems: list[str]) -> None:
    tables: list[tuple[str, Any, str, str]] = [
        ("tool.poetry.dependencies", poetry.get("dependencies"), "runtime", ""),
        ("tool.poetry.dev-dependencies", poetry.get("dev-dependencies"), "dev", "dev"),
    ]
    for gname, gdata in (poetry.get("group") or {}).items():
        if isinstance(gdata, dict):
            tables.append(
                (
                    f"tool.poetry.group.{gname}.dependencies",
                    gdata.get("dependencies"),
                    "dev",
                    gname,
                )
            )
    for where, table, kind, group in tables:
        if table is None:
            continue
        if not isinstance(table, dict):
            problems.append(f"{where} must be a table")
            continue
        for dep, value in table.items():
            if dep.lower() == "python":
                continue
            dep_kind, spec, extras = kind, "", ""
            if isinstance(value, str):
                spec = value
            elif isinstance(value, dict):
                spec = _str(value.get("version")) or (
                    "git" if "git" in value else "path" if "path" in value else ""
                )
                if value.get("optional") and kind == "runtime":
                    dep_kind = "optional"
                if isinstance(value.get("extras"), list):
                    extras = ",".join(str(e) for e in value["extras"])
            elif isinstance(value, list):
                spec = " | ".join(
                    _str(v.get("version")) for v in value if isinstance(v, dict)
                )
            else:
                problems.append(f"{where}.{dep} must be a version string or a table")
                continue
            exact = _EXACT_PEP440.match(spec.replace(" ", "")) or re.match(
                r"^(\d+(?:\.\d+)*)$", spec.strip()
            )
            stored = graph.add(
                Package(
                    id=pypi_name(dep),
                    name=dep,
                    version=exact.group(1) if exact else "",
                    kind=dep_kind,
                    group=group,
                    ecosystem="pypi",
                    extras=extras,
                )
            )
            graph.link(Edge(graph.root, stored.id, spec, dep_kind, group))


def _uv_lock(data: dict[str, Any]) -> Graph:
    packages = data["package"]
    problems: list[str] = []
    by_name: dict[str, list[dict[str, Any]]] = {}
    for i, entry in enumerate(packages):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            problems.append(f"uv.lock: package #{i + 1} has no name")
            continue
        by_name.setdefault(pypi_name(entry["name"]), []).append(entry)
    if problems:
        raise SpecError(problems)

    def is_root(entry: dict[str, Any]) -> bool:
        source = entry.get("source")
        return isinstance(source, dict) and (
            source.get("editable") == "." or source.get("virtual") == "."
        )

    roots = [e for e in packages if is_root(e)] or [
        e
        for e in packages
        if isinstance(e.get("source"), dict)
        and ("editable" in e["source"] or "virtual" in e["source"])
    ]
    if not roots:
        raise SpecError(
            [
                (
                    "uv.lock: no project package found (one with source editable or "
                    'virtual = "."); is this the lock of a project?'
                )
            ]
        )
    root_entry = roots[0]

    def node_id(entry: dict[str, Any]) -> str:
        name = pypi_name(entry["name"])
        if entry is root_entry:
            return name
        version = _str(entry.get("version"))
        return f"{name}@{version}" if version else name

    graph = Graph("uv.lock", node_id(root_entry), has_lock=True)
    for entry in packages:
        graph.add(
            Package(
                id=node_id(entry),
                name=entry["name"],
                version=_str(entry.get("version")),
                ecosystem="pypi",
                root=entry is root_entry,
            )
        )

    def target(dep: dict[str, Any]) -> dict[str, Any] | None:
        options = by_name.get(pypi_name(str(dep.get("name", ""))), [])
        if not options:
            return None
        wanted = _str(dep.get("version"))
        for option in options:
            if not wanted or _str(option.get("version")) == wanted:
                return option
        return options[0]

    # requested ranges, from the project's own metadata
    meta = (
        root_entry.get("metadata")
        if isinstance(root_entry.get("metadata"), dict)
        else {}
    )
    ranges: dict[tuple[str, str], str] = {}
    for item in meta.get("requires-dist", []) or []:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            key = (pypi_name(item["name"]), _str(item.get("extra")))
            ranges[key] = _str(item.get("specifier"))
    for group, items in (meta.get("requires-dev") or {}).items():
        for item in items or []:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                ranges[(pypi_name(item["name"]), group)] = _str(item.get("specifier"))

    # extras a dependent asks for (`uvicorn[standard]`) pull in that package's extra deps
    wanted_extras: dict[int, set[str]] = {}
    for entry in packages:
        groups = [entry.get("dependencies") or []]
        groups += list((entry.get("optional-dependencies") or {}).values())
        groups += list((entry.get("dev-dependencies") or {}).values())
        for deps in groups:
            for dep in deps or []:
                found = target(dep) if isinstance(dep, dict) else None
                if found is not None and isinstance(dep.get("extra"), list):
                    wanted_extras.setdefault(id(found), set()).update(
                        str(x) for x in dep["extra"]
                    )

    for entry in packages:
        sections: list[tuple[str, str, Any]] = [
            ("runtime", "", entry.get("dependencies"))
        ]
        if entry is not root_entry:
            extras = entry.get("optional-dependencies") or {}
            for extra in sorted(wanted_extras.get(id(entry), ())):
                sections.append(("runtime", "", extras.get(extra)))
        if entry is root_entry:
            for extra, deps in (entry.get("optional-dependencies") or {}).items():
                sections.append(("optional", extra, deps))
            for group, deps in (entry.get("dev-dependencies") or {}).items():
                sections.append(("dev", group, deps))
        for kind, group, deps in sections:
            for dep in deps or []:
                if not isinstance(dep, dict):
                    continue
                found = target(dep)
                if found is None:
                    continue
                spec = ""
                if entry is root_entry:
                    name = pypi_name(str(dep.get("name")))
                    spec = ranges.get((name, group), ranges.get((name, ""), ""))
                graph.link(Edge(node_id(entry), node_id(found), spec, kind, group))
                if entry is root_entry and group:
                    graph.packages[node_id(found)].group = group
    return graph


# --------------------------------------------------------------------- requirements


def _requirements(text: str) -> Graph:
    graph = Graph("requirements.txt", "requirements.txt")
    graph.add(
        Package(id=graph.root, name="requirements.txt", ecosystem="pypi", root=True)
    )
    problems: list[str] = []
    skipped: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        number = i + 1
        line = lines[i]
        while line.rstrip().endswith("\\") and i + 1 < len(lines):
            i += 1
            line = line.rstrip()[:-1] + " " + lines[i]
        i += 1
        line = re.sub(r"(^|\s)#.*$", "", line).strip()
        if not line:
            continue
        if line.startswith("-"):
            flag = line.split()[0].split("=")[0]
            if flag in ("-r", "--requirement", "-c", "--constraint"):
                skipped.append(f"line {number}: {line} (included files are not read)")
            elif flag in ("-e", "--editable"):
                egg = re.search(r"#egg=([A-Za-z0-9._-]+)", lines[number - 1])
                if egg:
                    stored = graph.add(
                        Package(
                            id=pypi_name(egg.group(1)),
                            name=egg.group(1),
                            ecosystem="pypi",
                        )
                    )
                    graph.link(Edge(graph.root, stored.id, "editable", "runtime"))
                else:
                    skipped.append(f"line {number}: {line} (editable install)")
            continue
        line = _REQ_OPTION.sub("", " " + line).strip()  # per-line --hash=... options
        parsed = _requirement(line, f"line {number}")
        if isinstance(parsed, str):
            problems.append(parsed)
            continue
        package, spec = parsed
        package.kind = "runtime"
        stored = graph.add(package)
        graph.link(Edge(graph.root, stored.id, spec, "runtime"))
    if problems:
        if len(graph.packages) == 1:
            problems.insert(
                0,
                "could not detect the file kind: read it as requirements.txt, but no line "
                "parsed (paste a package.json, package-lock.json, pyproject.toml, "
                "requirements.txt or uv.lock)",
            )
        raise SpecError(
            [
                p if p.startswith("could not") else f"requirements.txt {p}"
                for p in problems[:20]
            ]
        )
    if len(graph.packages) == 1:
        raise SpecError(
            ["requirements.txt: no requirements found (only comments or options)"]
        )
    graph.notes.extend(skipped[:5])
    return graph
