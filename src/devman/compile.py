"""`devman compile`: resolve, render, validate and publish (PLAN Stage 3).

A project that fails any step is refused as a whole. Its published files keep
their bytes, and `compile.json` records the reason.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from devman import __version__, dagu
from devman.manifest import PROJECT_RE, Project, load, workflow_name_error
from devman.paths import Paths
from devman.render import check_source, render

TOKEN_RE = re.compile(r"@([A-Za-z][A-Za-z0-9]*)@")
TOKEN_ENV = {
    "bash": "DEVMAN_BASH",
    "guard": "DEVMAN_GUARD",
    "devman": "DEVMAN_BIN",
    "stateDir": "DEVMAN_STATE",
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def fill_base(paths: Paths) -> tuple[bool, str | None]:
    """Fill the tokens of the library `base.yaml`; write `<state>/base.yaml`.

    Return (changed, error). The file is not written when it is unchanged.
    """
    try:
        text = paths.base_src.read_text()
    except OSError as exc:
        return False, f"cannot read {paths.base_src}: {exc.strerror}"
    values = {
        "bash": paths.bash,
        "guard": paths.guard,
        "devman": paths.bin,
        "stateDir": str(paths.state),
    }
    # A comment may name a token (the seed file does); only code needs a value.
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    for token in dict.fromkeys(TOKEN_RE.findall(code)):
        if token not in values:
            return False, f"{paths.base_src}: unknown token @{token}@"
        if not values[token]:
            return (
                False,
                f"{paths.base_src}: @{token}@ has no value; set {TOKEN_ENV[token]}",
            )
    filled = TOKEN_RE.sub(lambda m: values.get(m.group(1)) or m.group(0), text)
    try:
        if not isinstance(yaml.safe_load(filled) or {}, dict):
            return False, f"{paths.base_src}: base.yaml is not a mapping"
    except yaml.YAMLError as exc:
        return False, f"{paths.base_src}: invalid YAML: {str(exc).splitlines()[0]}"
    if paths.base_out.exists() and paths.base_out.read_text() == filled:
        return False, None
    _write_atomic(paths.base_out, filled)
    return True, None


def _resolve(
    paths: Paths, project: Project
) -> tuple[dict[str, tuple[Path, str]], list[str]]:
    """Map each workflow name to (source path, origin). Return the reasons too."""
    reasons: list[str] = []
    own_dir = paths.workflows / project.name
    own = (
        {p.stem: p for p in sorted(own_dir.glob("*.yaml"))} if own_dir.is_dir() else {}
    )
    sources: dict[str, tuple[Path, str]] = {n: (p, "project") for n, p in own.items()}
    for name in own:
        error = workflow_name_error(name)
        if error:
            reasons.append(f"workflows/{project.name}/{name}.yaml: {error}")
    for name in project.take:
        library = paths.library / "workflows" / f"{name}.yaml"
        if name not in sources and library.is_file():
            sources[name] = (library, "library")
        elif name not in sources:
            reasons.append(
                f"take names {name}, which is neither in workflows/{project.name}/"
                " nor in the library"
            )
    for entry in project.on:
        if entry.run not in sources and entry.run not in project.take:
            reasons.append(
                f"on entry runs {entry.run}, which is not a workflow of this project"
            )
    return sources, reasons


def _compile_project(
    paths: Paths, queues: list[str], project: Project, validate_all: bool
) -> tuple[dict[str, Any] | None, list[str], int]:
    """Return (record, reasons, files changed). The record is None when refused."""
    if not project.path.is_dir():
        return None, [f"path {project.path} is not a directory"], 0
    sources, reasons = _resolve(paths, project)
    if reasons:
        return None, reasons, 0

    out_dir = paths.dags / project.name
    tmp_dir = paths.tmp / project.name
    shutil.rmtree(tmp_dir, ignore_errors=True)
    rendered: dict[str, str] = {}
    for name, (source, origin) in sources.items():
        label = f"{project.name}/{name}"
        try:
            text = source.read_text()
        except OSError as exc:
            reasons.append(f"{label}: cannot read {source}: {exc.strerror}")
            continue
        problems = check_source(text, queues, label)
        reasons.extend(problems)
        if not problems:
            rendered[name] = render(
                project.name,
                name,
                project.path,
                paths.runs / project.name,
                origin,
                source,
                text,
            )
    if reasons:
        return None, reasons, 0

    def published(name: str) -> Path:
        return out_dir / f"{project.name}.{name}.yaml"

    def changed(name: str) -> bool:
        file = published(name)
        return not file.exists() or file.read_text() != rendered[name]

    todo = [n for n in rendered if validate_all or changed(n)]
    tmp_dir.mkdir(parents=True, exist_ok=True)

    def check(name: str) -> str | None:
        file = tmp_dir / f"{project.name}.{name}.yaml"
        file.write_text(rendered[name])
        error = dagu.validate(paths.dagu_config, file)
        return f"{project.name}.{name}: {error}" if error else None

    with ThreadPoolExecutor(max_workers=4) as pool:
        reasons = [r for r in pool.map(check, todo) if r]
    if reasons:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None, reasons, 0

    out_dir.mkdir(parents=True, exist_ok=True)
    (paths.runs / project.name).mkdir(parents=True, exist_ok=True)
    count = 0
    for name in todo:
        if changed(name):
            os.replace(tmp_dir / f"{project.name}.{name}.yaml", published(name))
            count += 1
    shutil.rmtree(tmp_dir, ignore_errors=True)
    keep = {published(n).name for n in rendered}
    for stale in out_dir.glob(f"{project.name}.*.yaml"):
        if stale.name not in keep:
            stale.unlink()
            count += 1

    workflows = {
        name: {
            "dag": f"{project.name}.{name}",
            "file": str(published(name)),
            "origin": sources[name][1],
            "source": str(sources[name][0]),
            "sha256": hashlib.sha256(rendered[name].encode()).hexdigest(),
        }
        for name in rendered
    }
    on = [
        {
            "event": e.event,
            "match": list(e.match),
            "exclude": list(e.exclude),
            "run": e.run,
        }
        for e in project.on
    ]
    record = {
        "status": "ok",
        "stale": False,
        "at": _now(),
        "path": str(project.path),
        "reasons": [],
        "on": on,
        "workflows": workflows,
    }
    return record, [], count


def _refused(
    prev: dict[str, Any] | None, reasons: list[str], path: Path | None
) -> dict[str, Any]:
    """A refused record. It keeps the last good `on` and `workflows` (A.3)."""
    stale = bool(prev and prev.get("workflows"))
    return {
        "status": "refused",
        "stale": stale,
        "at": _now(),
        "path": str(path) if path else (prev or {}).get("path"),
        "reasons": reasons,
        "on": prev["on"] if stale and prev else [],
        "workflows": prev["workflows"] if stale and prev else {},
    }


def _read_doc(paths: Paths) -> dict[str, Any]:
    try:
        return json.loads(paths.compile_json.read_text())
    except (OSError, ValueError):
        return {}


def compile(
    paths: Paths, names: list[str] | None = None, validate_all: bool = False
) -> int:
    """Compile the named projects, or all. Return the exit code (0, 1 or 2)."""
    if paths.dagu_config is None:
        print("devman: DEVMAN_DAGU_CONFIG is not set", file=sys.stderr)
        return 2
    paths.state.mkdir(parents=True, exist_ok=True)
    with open(paths.lock, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _compile_locked(paths, names, validate_all)


def _compile_locked(paths: Paths, names: list[str] | None, validate_all: bool) -> int:
    assert paths.dagu_config is not None
    manifest = load(paths.projects_toml)
    unknown = [n for n in names or [] if n not in manifest.projects | manifest.errors]
    if unknown:
        print(f"devman: unknown project {', '.join(unknown)}", file=sys.stderr)
        return 2

    changed, error = fill_base(paths)
    if error:
        print(f"devman: compile refused library: {error}", file=sys.stderr)
        return 1
    try:
        queues = dagu.configured_queues(paths.dagu_config)
    except (OSError, yaml.YAMLError) as exc:
        print(f"devman: cannot read {paths.dagu_config}: {exc}", file=sys.stderr)
        return 1

    previous = _read_doc(paths).get("projects", {})
    records = dict(previous)
    refused: dict[str, list[str]] = {}
    written = 0

    for name in sorted(manifest.projects.keys() | manifest.errors.keys() - {""}):
        if names and name not in names:
            continue
        project = manifest.projects.get(name)
        if project:
            record, reasons, count = _compile_project(
                paths, queues, project, validate_all or changed
            )
            written += count
        else:
            record, reasons = None, manifest.errors[name]
        if record is None:
            refused[name] = reasons
            records[name] = _refused(
                previous.get(name), reasons, project.path if project else None
            )
        else:
            records[name] = record

    full = not names
    orphans: list[str] = []
    if full:
        for reason in manifest.errors.get("", []):
            refused["projects.toml"] = [*refused.get("projects.toml", []), reason]
        if paths.workflows.is_dir():
            known = manifest.projects.keys() | manifest.errors.keys()
            orphans = sorted(
                d.name
                for d in paths.workflows.iterdir()
                if d.is_dir() and d.name not in known
            )
        for orphan in orphans:
            refused[orphan] = [f"workflows/{orphan}/ has no table in projects.toml"]
        # A project that left the manifest loses its files. A broken
        # `projects.toml` proves nothing about which projects left.
        if not manifest.errors.get(""):
            for name in (
                set(previous) - manifest.projects.keys() - manifest.errors.keys()
            ):
                if PROJECT_RE.match(name):
                    shutil.rmtree(paths.dags / name, ignore_errors=True)
                records.pop(name, None)

    # A run with no change writes nothing: keep each unchanged record, and
    # skip the file when nothing but the clock moved.
    for name, record in records.items():
        old = previous.get(name)
        if old and {k: v for k, v in old.items() if k != "at"} == {
            k: v for k, v in record.items() if k != "at"
        }:
            records[name] = old
    old_doc = _read_doc(paths)
    core = {
        "version": 1,
        "devman": __version__,
        "orphans": orphans if full else old_doc.get("orphans", []),
        "projects": dict(sorted(records.items())),
    }
    if {k: v for k, v in old_doc.items() if k != "compiled_at"} != core:
        doc = {"version": 1, "compiled_at": _now(), **core}
        _write_atomic(paths.compile_json, json.dumps(doc, indent=2) + "\n")
    for name, reasons in refused.items():
        print(f"devman: compile refused {name}: {'; '.join(reasons)}", file=sys.stderr)
    return 1 if refused else 0
