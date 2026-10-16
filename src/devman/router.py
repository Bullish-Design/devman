"""Turn one event into queued Dagu runs and one `events.jsonl` line (CONCEPT §7).

The router reads `compile.json`, not `projects.toml`. So the `on` entries always
agree with the files Dagu runs, also for a stale project (B8).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from devman import dagu
from devman.manifest import EVENT_RE, OnEntry, matches
from devman.paths import Paths

KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Event:
    name: str
    project: str | None = None
    subjects: tuple[str, ...] = ()
    source: str = "cli"
    fields: dict[str, str] = field(default_factory=dict)
    cwd: Path | None = None  # finds the project when `project` is None
    implicit: bool = False  # `devman run`: subject 0 is the workflow, no `on` table


@dataclass(frozen=True)
class Outcome:
    code: int  # 0 done, 1 an enqueue failed, 2 refused
    lines: list[str]  # what the CLI prints
    record: dict[str, Any]  # the line written to events.jsonl


def parse_fields(items: list[str]) -> tuple[dict[str, str], str | None]:
    """Split KEY=VALUE arguments (§A.5). Return the fields and a usage error."""
    fields: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not KEY_RE.match(key):
            return {}, f"{item} is not KEY=VALUE with KEY like [A-Za-z_][A-Za-z0-9_]*"
        if key.startswith("DEVMAN_"):
            return {}, f"{key}: the prefix DEVMAN_ is reserved"
        fields[key] = value
    return fields, None


def check_event(name: str) -> str | None:
    if EVENT_RE.match(name):
        return None
    return f"event {name} does not match [a-z][a-z0-9._-]*"


def find_project(records: dict[str, dict], cwd: Path) -> str | None:
    """The project whose `path` is the deepest parent of `cwd`."""
    best, depth = None, -1
    here = Path(os.path.realpath(cwd))
    for name, rec in records.items():
        if not rec.get("path"):
            continue
        for root in {Path(rec["path"]), Path(os.path.realpath(rec["path"]))}:
            if here.is_relative_to(root) and len(root.parts) > depth:
                best, depth = name, len(root.parts)
    return best


def _normalise(subject: str, root: Path) -> str:
    """An absolute path under the project becomes relative to it."""
    if not os.path.isabs(subject):
        return subject
    for base in (root, Path(os.path.realpath(root))):
        for candidate in (Path(subject), Path(os.path.realpath(subject))):
            if candidate.is_relative_to(base):
                return PurePosixPath(candidate.relative_to(base)).as_posix()
    return subject


def _entries(rec: dict) -> list[OnEntry]:
    return [
        OnEntry(e["event"], tuple(e["match"]), tuple(e["exclude"]), e["run"])
        for e in rec.get("on", [])
    ]


def _write(paths: Paths, record: dict) -> None:
    """Append one line with one `write` call (O_APPEND keeps lines whole)."""
    paths.events.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(record, ensure_ascii=False) + "\n").encode()
    fd = os.open(paths.events, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _refuse(paths: Paths, record: dict, reason: str) -> Outcome:
    record["refusal"] = reason
    _write(paths, record)
    return Outcome(2, [f"devman: emit refused: {reason}"], record)


def emit(paths: Paths, event: Event) -> Outcome:
    """Route one event. Write one event line. Never raise for content."""
    record: dict[str, Any] = {
        "at": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "event": event.name,
        "project": event.project,
        "source": event.source,
        "subjects": list(event.subjects),
        "fields": dict(event.fields),
        "stale": False,
        "matches": [],
        "refusal": None,
    }
    try:
        projects = paths.records()
    except (OSError, ValueError, KeyError) as exc:
        return _refuse(paths, record, f"cannot read {paths.compile_json}: {exc}")

    name = event.project
    if name is None:
        name = find_project(projects, event.cwd or Path.cwd())
        if name is None:
            return _refuse(paths, record, "no project contains the current directory")
        record["project"] = name
    elif name not in projects:
        return _refuse(paths, record, f"unknown project {name}")

    rec = projects[name]
    record["stale"] = bool(rec.get("stale"))
    root = Path(rec["path"])
    # Dagu would create a missing working_dir and the run would succeed (M2).
    if not root.is_dir():
        return _refuse(paths, record, f"path {root} is not a directory")

    subjects = [_normalise(s, root) for s in event.subjects]
    record["subjects"] = subjects

    # One enqueue per workflow, whatever the number of entries and subjects.
    chosen: dict[str, str] = {}
    if event.implicit:
        if subjects[0] not in rec.get("workflows", {}):
            return _refuse(paths, record, f"{name} has no workflow {subjects[0]}")
        chosen[subjects[0]] = subjects[0]
    for entry in [] if event.implicit else _entries(rec):
        run = entry.run
        if entry.event != event.name or run in chosen:
            continue
        hit = next((s for s in subjects or [""] if matches(entry, s)), None)
        if hit is not None:
            chosen[run] = hit

    if chosen and paths.dagu_config is None:
        return _refuse(paths, record, "DEVMAN_DAGU_CONFIG is not set")

    code, lines = 0, []
    for run, subject in chosen.items():
        flow = rec.get("workflows", {}).get(run, {})
        run_id = str(uuid.uuid4())
        match: dict[str, Any] = {
            "workflow": run,
            "dag": flow.get("dag", f"{name}.{run}"),
            "run_id": run_id,
        }
        file = Path(flow.get("file", ""))
        if not file.is_file():
            error = f"compiled file {file} is missing; run devman compile"
        else:
            params = [f"DEVMAN_EVENT={event.name}", f"DEVMAN_SUBJECT={subject}"]
            params += [f"{k}={v}" for k, v in event.fields.items()]
            assert paths.dagu_config is not None
            error = dagu.enqueue(paths.dagu_config, file, run_id, event.name, params)
        if error is None:
            match["result"] = "enqueued"
            lines.append(f"enqueued {match['dag']} run={run_id}")
        else:
            match.update(result="failed", error=error)
            lines.append(f"failed {match['dag']}: {error}")
            code = 1
        record["matches"].append(match)

    _write(paths, record)
    return Outcome(code, lines, record)
