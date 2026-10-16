"""Parse and validate `projects.toml` (PLAN §A.1, CONCEPT §4).

`load` never raises for content. A bad table refuses its own project and
leaves the others intact. A TOML syntax error refuses the file.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
WORKFLOW_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
EVENT_RE = re.compile(r"^[a-z][a-z0-9._-]*$")

PROJECT_KEYS = ("path", "take", "on")
ON_KEYS = ("event", "match", "exclude", "run")


@dataclass(frozen=True)
class OnEntry:
    event: str
    match: tuple[str, ...]
    exclude: tuple[str, ...]
    run: str


@dataclass(frozen=True)
class Project:
    name: str
    path: Path  # expanded and absolute; not checked against the disk here
    take: tuple[str, ...]
    on: tuple[OnEntry, ...]


@dataclass(frozen=True)
class Manifest:
    projects: dict[str, Project]  # the projects that parsed
    errors: dict[str, list[str]]  # project name -> reasons; "" for the file


def matches(on: OnEntry, subject: str) -> bool:
    """True when a glob of `match` accepts the subject and none of `exclude` does."""
    path = PurePosixPath(subject)
    return any(path.full_match(g) for g in on.match) and not any(
        path.full_match(g) for g in on.exclude
    )


def workflow_name_error(name: Any) -> str | None:
    """The reason a workflow name is refused (rule 4), or None."""
    if isinstance(name, str) and WORKFLOW_RE.match(name):
        return None
    if isinstance(name, str) and "." in name:
        return f"workflow name {name} must not contain a dot"
    return f"workflow name {name} does not match [A-Za-z0-9][A-Za-z0-9_-]*"


def _workflow_name(name: Any, reasons: list[str]) -> bool:
    error = workflow_name_error(name)
    if error:
        reasons.append(error)
    return error is None


def _globs(value: Any, *, single: bool) -> tuple[str, ...] | None:
    if single and isinstance(value, str):
        value = [value]
    ok = isinstance(value, list) and (value or not single)
    if not ok or not all(isinstance(g, str) and g for g in value):
        return None
    return tuple(value)


def _parse_on(index: int, raw: Any, reasons: list[str]) -> OnEntry | None:
    where = f"on[{index}]"
    if not isinstance(raw, dict):
        reasons.append(f"{where} is not a table")
        return None
    start = len(reasons)
    reasons.extend(f"unknown key {k}" for k in raw if k not in ON_KEYS)
    reasons.extend(
        f"{where} needs {k}" for k in ("event", "match", "run") if k not in raw
    )
    event, run = raw.get("event"), raw.get("run")
    if "event" in raw and not (isinstance(event, str) and EVENT_RE.match(event)):
        reasons.append(f"{where} event {event} does not match [a-z][a-z0-9._-]*")
    if "run" in raw:
        _workflow_name(run, reasons)
    match = _globs(raw.get("match"), single=True)
    if "match" in raw and match is None:
        reasons.append(
            f"{where} match must be a string or a list of strings, none empty"
        )
    exclude = _globs(raw.get("exclude", []), single=False)
    if exclude is None:
        reasons.append(f"{where} exclude must be a list of non-empty strings")
    if len(reasons) > start:
        return None
    return OnEntry(event, match or (), exclude or (), run)


def _parse_project(
    name: str, table: dict[str, Any]
) -> tuple[Project | None, list[str]]:
    reasons: list[str] = []
    if not PROJECT_RE.match(name):
        reasons.append(f"project name {name} does not match [A-Za-z0-9][A-Za-z0-9._-]*")
    reasons.extend(f"unknown key {k}" for k in table if k not in PROJECT_KEYS)

    path = None
    raw_path = table.get("path")
    if raw_path is None:
        reasons.append("path is required")
    elif not isinstance(raw_path, str):
        reasons.append("path must be a string")
    else:
        expanded = os.path.expanduser(raw_path)
        if os.path.isabs(expanded):
            path = Path(os.path.normpath(expanded))
        else:
            reasons.append(f"path {raw_path} is not absolute")

    take = table.get("take", [])
    if not isinstance(take, list):
        reasons.append("take must be a list of workflow names")
        take = []
    take = [n for n in take if _workflow_name(n, reasons)]

    raw_on = table.get("on", [])
    entries: list[OnEntry] = []
    if not isinstance(raw_on, list):
        reasons.append("on must be an array of tables")
    else:
        for i, raw in enumerate(raw_on):
            entry = _parse_on(i, raw, reasons)
            if entry:
                entries.append(entry)

    if not reasons:
        loop = _find_loop(take, entries)
        if loop:
            reasons.append("on entries form a loop: " + " -> ".join(loop))
    if reasons or path is None:
        return None, reasons
    return Project(name, path, tuple(dict.fromkeys(take)), tuple(entries)), reasons


def _find_loop(take: list[str], entries: list[OnEntry]) -> list[str] | None:
    """Return a cycle among the `done`/`failed` entries, or None (rule 9)."""
    names = sorted({*take, *(e.run for e in entries)})
    edges: dict[str, list[str]] = {n: [] for n in names}
    for entry in entries:
        if entry.event in ("done", "failed"):
            for name in names:
                if matches(entry, name):
                    edges[name].append(entry.run)

    def walk(node: str, trail: list[str]) -> list[str] | None:
        if node in trail:
            return [*trail[trail.index(node) :], node]
        for nxt in edges[node]:
            found = walk(nxt, [*trail, node])
            if found:
                return found
        return None

    for name in names:
        found = walk(name, [])
        if found:
            return found
    return None


def load(path: Path) -> Manifest:
    try:
        data = tomllib.loads(Path(path).read_text())
    except (OSError, UnicodeDecodeError) as exc:
        return Manifest({}, {"": [f"cannot read {path}: {exc}"]})
    except tomllib.TOMLDecodeError as exc:
        return Manifest({}, {"": [f"{path} is not valid TOML: {exc}"]})

    projects: dict[str, Project] = {}
    errors: dict[str, list[str]] = {}
    for name, table in data.items():
        if not isinstance(table, dict):
            errors.setdefault("", []).append(f"{name} is not a table")
            continue
        project, reasons = _parse_project(name, table)
        if project:
            projects[name] = project
        else:
            errors[name] = reasons

    # Rule 6: two projects with one path are both refused.
    for name, project in list(projects.items()):
        others = [
            o for o, p in projects.items() if o != name and p.path == project.path
        ]
        if others:
            errors[name] = [f"path shared with {', '.join(others)}"]
    for name in errors:
        projects.pop(name, None)
    return Manifest(projects, errors)
