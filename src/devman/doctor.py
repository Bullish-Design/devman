"""`devman doctor`: one line per check (CONCEPT §11, PLAN Stage 6)."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from devman import dagu, state
from devman.health import global_health
from devman.paths import Paths

WATCH_WARN = 0.5  # M5: warn above half of fs.inotify.max_user_watches


def watcher_pids(paths: Paths) -> list[int]:
    """Processes that are the watcher's watchexec (they name our state as origin)."""
    mark = f"--project-origin={paths.state}".encode()
    found = []
    for entry in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            argv = entry.read_bytes().split(b"\0")
        except OSError:
            continue
        name = Path(argv[0].decode(errors="replace")).name
        if name == "watchexec" and mark in argv:
            found.append(int(entry.parent.name))
    return found


def inotify_watches(pid: int) -> int:
    """The inotify watches that one process holds."""
    total = 0
    for fd in Path(f"/proc/{pid}/fd").iterdir():
        try:
            if os.readlink(fd) == "anon_inode:inotify":
                info = Path(f"/proc/{pid}/fdinfo/{fd.name}").read_text()
                total += sum(ln.startswith("inotify wd:") for ln in info.splitlines())
        except OSError:
            continue
    return total


def check_api(paths: Paths) -> str | None:
    if paths.dagu_config is None:
        return "DEVMAN_DAGU_CONFIG is not set"
    try:
        dagu.get(paths.dagu_config, "/dag-runs?limit=1")
    except (OSError, ValueError) as exc:
        return f"Dagu does not answer: {exc}"
    return None


def check_version(paths: Paths) -> str | None:
    if paths.dagu_version is None:
        return None  # nothing to compare with
    found = dagu.version()
    if found != paths.dagu_version:
        return f"dagu is {found}, expected {paths.dagu_version}"
    return None


def check_watcher(paths: Paths) -> str | None:
    return None if watcher_pids(paths) else "no watcher process is running"


def check_budget(paths: Paths) -> str | None:
    try:
        limit = int(Path("/proc/sys/fs/inotify/max_user_watches").read_text())
    except (OSError, ValueError):
        return None
    used = sum(inotify_watches(pid) for pid in watcher_pids(paths))
    if used > limit * WATCH_WARN:
        return f"the watcher holds {used} of {limit} inotify watches"
    return None


def check_compile(paths: Paths) -> str | None:
    try:
        doc = state.read(paths.compile_json)
    except state.StateError as exc:
        return str(exc)
    if doc is None:
        return f"{paths.compile_json} is missing; run devman compile"
    health = global_health(doc, paths)
    if health["status"] != "ok" or health["stale"]:
        reasons = "; ".join(health["reasons"])
        return f"global compile {health['status']} (stale): {reasons}"
    bad = [n for n, r in doc["projects"].items() if r["status"] != "ok"]
    bad += [f"{o} (orphan)" for o in doc.get("orphans", [])]
    return f"refused: {', '.join(bad)}" if bad else None


class _StateCheckError(Exception):
    """Carries the state error text into one doctor finding."""


def _state_or_none(paths: Paths) -> dict:
    """Validated compile state, `{}` when missing; a finding cannot come from here."""
    try:
        return state.read(paths.compile_json) or {}
    except state.StateError as exc:
        raise _StateCheckError(str(exc)) from exc


def check_dags(paths: Paths) -> str | None:
    """Every compiled file exists with its hash, and no other file is in `dags/`."""
    expect: dict[Path, str] = {}
    try:
        doc = _state_or_none(paths)
    except _StateCheckError as exc:
        return str(exc)
    for rec in doc.get("projects", {}).values():
        for info in rec["workflows"].values():
            expect[Path(info["file"])] = info["sha256"]
    problems = []
    for file, digest in expect.items():
        try:
            if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
                problems.append(f"{file.name} changed since compile")
        except OSError:
            problems.append(f"{file.name} is missing")
    problems += [
        f"{f.name} is not in compile.json"
        for f in sorted(paths.dags.rglob("*.yaml"))
        if f not in expect
    ]
    return "; ".join(problems) or None


def check_checkouts(paths: Paths) -> str | None:
    """Every project path holds `.git` or `.jj`, so the guard passes."""
    try:
        doc = _state_or_none(paths)
    except _StateCheckError as exc:
        return str(exc)
    gone = [
        n
        for n, r in doc.get("projects", {}).items()
        if not any(os.path.exists(Path(r["path"]) / m) for m in (".git", ".jj"))
    ]
    return f"no .git or .jj in: {', '.join(gone)}" if gone else None


def _actions(node: Any) -> set[str]:
    if isinstance(node, dict):
        found = {node["action"]} if isinstance(node.get("action"), str) else set()
        return found.union(*(_actions(v) for v in node.values()))
    if isinstance(node, list):
        return set().union(*(_actions(v) for v in node))
    return set()


def check_actions(paths: Paths) -> str | None:
    """Every `action:` a library workflow names is defined in `base.yaml`."""
    try:
        known = set(
            (yaml.safe_load(paths.base_src.read_text()) or {}).get("actions", {})
        )
    except (OSError, yaml.YAMLError) as exc:
        return f"cannot read {paths.base_src}: {exc}"
    problems = []
    for file in sorted((paths.library / "workflows").glob("*.yaml")):
        try:
            names = _actions(list(yaml.safe_load_all(file.read_text())))
        except (OSError, yaml.YAMLError) as exc:
            problems.append(f"{file.name}: {exc}")
            continue
        problems += [f"{file.name} names action {a}" for a in sorted(names - known)]
    return "; ".join(problems) or None


CHECKS: list[tuple[str, Callable[[Paths], str | None]]] = [
    ("Dagu answers", check_api),
    ("Dagu version", check_version),
    ("watcher runs", check_watcher),
    ("watch budget", check_budget),
    ("compile clean", check_compile),
    ("dags match compile", check_dags),
    ("checkouts", check_checkouts),
    ("library actions", check_actions),
]


def doctor(paths: Paths) -> tuple[int, list[str]]:
    """Run every check. Return (exit code, one line per check)."""
    lines, failed = [], 0
    for name, check in CHECKS:
        reason = check(paths)
        failed += reason is not None
        lines.append(f"FAIL {name}: {reason}" if reason else f"ok   {name}")
    return (1 if failed else 0), lines
