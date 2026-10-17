"""`devman status` and `devman show` (CONCEPT §6, PLAN §A.7).

Both read `compile.json` for local facts and Dagu's REST API for the last run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from devman import dagu, state
from devman.health import global_health
from devman.paths import Paths
from devman.router import find_project


def _yaml(path: str) -> dict:
    try:
        return yaml.safe_load(Path(path).read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _base_queue(paths: Paths) -> str | None:
    return _yaml(str(paths.base_out)).get("queue")


def describe(paths: Paths, name: str, rec: dict, reach: bool) -> dict[str, Any]:
    """The §A.7 object of one project. `reach` is False when Dagu is down."""
    flows = []
    for flow, info in rec["workflows"].items():
        doc = _yaml(info["file"])
        run = None
        if reach:
            try:
                run = dagu.last_run(paths.dagu_config, info["dag"])
            except (OSError, ValueError, KeyError, TypeError):
                reach = False
        flows.append(
            {
                "name": flow,
                "dag": info["dag"],
                "origin": info["origin"],
                "source": info["source"],
                "triggers": [
                    {k: e[k] for k in ("event", "match", "exclude")}
                    for e in rec["on"]
                    if e["run"] == flow
                ],
                "schedule": doc.get("schedule"),
                "queue": doc.get("queue") or _base_queue(paths),
                "last_run": run
                and {
                    "run_id": run["dagRunId"],
                    "status": run["statusLabel"],
                    "started_at": run.get("startedAt"),
                    "finished_at": run.get("finishedAt"),
                },
            }
        )
    return {
        "project": name,
        "path": rec["path"],
        "compile": {k: rec[k] for k in ("status", "stale", "at", "reasons")},
        "dagu": "reachable" if reach else "unreachable",
        "workflows": flows,
    }


def _text(info: dict[str, Any]) -> list[str]:
    comp = info["compile"]
    head = f"{info['project']}  {info['path']}  compile: {comp['status']}"
    lines = [
        head
        + (" (stale: the files are from an earlier compile)" if comp["stale"] else "")
    ]
    lines += [f"  refused: {reason}" for reason in comp["reasons"]]
    for w in info["workflows"]:
        trig = "; ".join(f"{t['event']} {' '.join(t['match'])}" for t in w["triggers"])
        run = w["last_run"]
        last = (
            f"{run['status']} {run['started_at']}"
            if run
            else ("none" if info["dagu"] == "reachable" else "Dagu unreachable")
        )
        lines.append(
            f"  {w['name']}  {w['origin']}  queue={w['queue']}"
            f"  schedule={w['schedule'] or '-'}  triggers: {trig or '-'}"
            f"  last run: {last}"
        )
    return lines


def _global_text(info: dict[str, Any]) -> list[str]:
    state = info["global"]
    lines = [
        "global compile: " + state["status"] + (" (stale)" if state["stale"] else "")
    ]
    lines.extend(f"  global reason: {reason}" for reason in state["reasons"])
    return lines


def status(paths: Paths, name: str | None, as_json: bool, cwd: Path) -> tuple[int, str]:
    """Return (exit code, output). Unreachable Dagu is not an error.

    Missing state is an initial condition and exits 2. Malformed state
    exits 2 with the field path and never emits a partial result.
    """
    try:
        doc = state.read(paths.compile_json)
    except state.StateError as exc:
        return 2, f"devman: {exc}"
    if doc is None:
        return 2, f"devman: {paths.compile_json} is missing; run devman compile"
    projects = doc["projects"]
    health = global_health(doc, paths)
    exit_code = 1 if health["status"] != "ok" or health["stale"] else 0
    name = name or find_project(projects, cwd)
    if name is not None and name not in projects:
        return 2, f"devman: unknown project {name}"
    reach = paths.dagu_config is not None
    if name is None and not as_json:
        lines = _global_text({"global": health})
        lines.extend(
            f"{n}  {r['path']}  compile: {r['status']}  workflows: {len(r['workflows'])}"
            for n, r in projects.items()
        )
        return exit_code, "\n".join(lines)
    names = [name] if name else list(projects)
    infos = [describe(paths, n, projects[n], reach) for n in names]
    if as_json:
        payload = (
            {"global": health, "project": infos[0]}
            if name
            else {"global": health, "projects": infos}
        )
        return exit_code, json.dumps(payload, indent=2)
    return exit_code, "\n".join([*_global_text({"global": health}), *_text(infos[0])])


def show(paths: Paths, flow: str, name: str | None, cwd: Path) -> tuple[int, str]:
    """Return (exit code, output): the compiled path, the source path, the file."""
    try:
        doc = state.read(paths.compile_json)
    except state.StateError as exc:
        return 2, f"devman: {exc}"
    if doc is None:
        return 2, f"devman: {paths.compile_json} is missing; run devman compile"
    projects = doc["projects"]
    name = name or find_project(projects, cwd)
    if name is None or name not in projects:
        return 2, f"devman: no project {name or os.fspath(cwd)}"
    info = projects[name]["workflows"].get(flow)
    if info is None:
        return 2, f"devman: {name} has no workflow {flow}"
    try:
        text = Path(info["file"]).read_text()
    except OSError as exc:
        return 1, f"devman: cannot read {info['file']}: {exc.strerror}"
    return 0, f"# compiled: {info['file']}\n# source: {info['source']}\n{text}"
