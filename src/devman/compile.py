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
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from devman import dagu, state
from devman.health import input_digest
from devman.manifest import PROJECT_RE, Project, load, workflow_name_error
from devman.paths import Paths
from devman.render import check_source, render

TOKEN_RE = re.compile(r"@([A-Za-z][A-Za-z0-9]*)@")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, path)


def fill_base(paths: Paths) -> tuple[bool, str | None]:
    """Stage the packaged base template for validation.

    Return (changed, error). The active base stays unchanged until publication.
    """
    try:
        text = paths.base_src.read_text()
    except OSError as exc:
        return False, f"cannot read {paths.base_src}: {exc.strerror}"
    # token -> (value, the variable that supplies it)
    values = {
        "bash": (paths.bash, "DEVMAN_BASH"),
        "devman": (paths.bin, "DEVMAN_BIN"),
        "stateDir": (str(paths.state), "DEVMAN_STATE"),
    }
    # A comment may name a token (the seed file does); only code needs a value.
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    for token in dict.fromkeys(TOKEN_RE.findall(code)):
        if token not in values:
            return False, f"{paths.base_src}: unknown token @{token}@"
        value, variable = values[token]
        if not value:
            return False, f"{paths.base_src}: @{token}@ has no value; set {variable}"
    filled = TOKEN_RE.sub(
        lambda m: values.get(m.group(1), ("",))[0] or m.group(0), text
    )
    try:
        base = yaml.safe_load(filled)
        if not isinstance(base, dict):
            return False, f"{paths.base_src}: base.yaml is not a mapping"
    except yaml.YAMLError as exc:
        return False, f"{paths.base_src}: invalid YAML: {str(exc).splitlines()[0]}"
    handler = base.get("handler_on")
    actions = base.get("actions")
    if not isinstance(handler, dict) or not isinstance(handler.get("exit"), dict):
        return False, f"{paths.base_src}: required handler_on.exit is missing"
    if not isinstance(actions, dict) or not isinstance(
        actions.get("devman.task"), dict
    ):
        return False, f"{paths.base_src}: required action devman.task is missing"
    if "queue" in base:
        return False, f"{paths.base_src}: base.yaml must not set queue"
    if base.get("hist_retention_days") != 7:
        return False, f"{paths.base_src}: hist_retention_days must be 7"
    candidate = paths.tmp / "base.yaml"
    if candidate.exists() and candidate.read_text() == filled:
        return not (
            paths.base_out.exists() and paths.base_out.read_text() == filled
        ), None
    _write_atomic(candidate, filled)
    return not (paths.base_out.exists() and paths.base_out.read_text() == filled), None


def _candidate_config(paths: Paths) -> Path:
    """Make a Dagu config that reads the staged base candidate."""
    assert paths.dagu_config is not None
    config = yaml.safe_load(paths.dagu_config.read_text()) or {}
    config.setdefault("paths", {})["base_config"] = str(paths.tmp / "base.yaml")
    candidate = paths.tmp / "dagu-candidate.yaml"
    _write_atomic(candidate, yaml.safe_dump(config, sort_keys=False))
    return candidate


def _publish_base(paths: Paths) -> bool:
    """Publish the staged base by atomic rename when its bytes changed."""
    candidate = paths.tmp / "base.yaml"
    if not candidate.exists():
        return False
    if (
        paths.base_out.exists()
        and paths.base_out.read_bytes() == candidate.read_bytes()
    ):
        return False
    paths.base_out.parent.mkdir(parents=True, exist_ok=True)
    os.replace(candidate, paths.base_out)
    return True


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
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (record, reasons). The record is None when the project is refused."""
    if not project.path.is_dir():
        return None, [f"path {project.path} is not a directory"]
    sources, reasons = _resolve(paths, project)
    if reasons:
        return None, reasons

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
                paths.guard or "",
            )
    if reasons:
        return None, reasons

    files = {n: out_dir / f"{project.name}.{n}.yaml" for n in rendered}

    def changed(name: str) -> bool:
        return not files[name].exists() or files[name].read_text() != rendered[name]

    todo = [n for n in rendered if validate_all or changed(n)]
    tmp_dir.mkdir(parents=True, exist_ok=True)

    def check(name: str) -> str | None:
        file = tmp_dir / files[name].name
        file.write_text(rendered[name])
        error = dagu.validate(paths.dagu_config, file)
        return f"{project.name}.{name}: {error}" if error else None

    with ThreadPoolExecutor(max_workers=4) as pool:
        reasons = [r for r in pool.map(check, todo) if r]
    if reasons:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None, reasons

    out_dir.mkdir(parents=True, exist_ok=True)
    (paths.runs / project.name).mkdir(parents=True, exist_ok=True)
    for name in todo:
        if changed(name):
            os.replace(tmp_dir / files[name].name, files[name])
    shutil.rmtree(tmp_dir, ignore_errors=True)
    keep = {f.name for f in files.values()}
    for stale in out_dir.glob(f"{project.name}.*.yaml"):
        if stale.name not in keep:
            stale.unlink()

    workflows = {
        name: {
            "dag": f"{project.name}.{name}",
            "file": str(files[name]),
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
    return record, []


def _without(doc: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    """A copy of `doc` without `key`, so two records compare apart from the clock."""
    return {k: v for k, v in doc.items() if k != key} if doc else None


def _refused(
    prev: dict[str, Any] | None, reasons: list[str], path: Path | None
) -> dict[str, Any]:
    """A refused record. It keeps the last good `on` and `workflows` (A.3)."""
    prev = prev or {}
    stale = bool(prev.get("workflows"))
    return {
        "status": "refused",
        "stale": stale,
        "at": _now(),
        "path": str(path) if path else prev.get("path"),
        "reasons": reasons,
        "on": prev["on"] if stale else [],
        "workflows": prev["workflows"] if stale else {},
    }


def compile(
    paths: Paths, names: list[str] | None = None, validate_all: bool = False
) -> int:
    """Compile the named projects, or all. Return the exit code (0, 1 or 2)."""
    try:
        paths.state.mkdir(parents=True, exist_ok=True)
        with open(paths.lock, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                return _compile_locked(paths, names, validate_all)
            except Exception as exc:
                try:
                    old_doc = _read_compile_doc(paths)
                    return _global_refusal(
                        paths, old_doc, f"unexpected compile error: {exc}"
                    )
                except Exception as state_error:
                    print(
                        f"devman: cannot record compile failure: {state_error}",
                        file=sys.stderr,
                    )
                    return 1
    except OSError as exc:
        print(f"devman: cannot access compile state: {exc}", file=sys.stderr)
        return 1


def _read_compile_doc(paths: Paths) -> dict[str, Any]:
    """Validated prior compile state, or `{}` when the file is missing.

    Raise StateError when the file exists but is malformed. A malformed file
    is an error, not a first compile: this run must not replace it, because
    its last good routes cannot be recovered.
    """
    doc = state.read(paths.compile_json)
    return doc if doc is not None else {}


def _write_result(
    paths: Paths,
    old_doc: dict[str, Any],
    records: dict[str, Any],
    status: str,
    reasons: list[str],
    successful_digest: str | None,
) -> None:
    old_global = old_doc.get("global", {})
    same_global = (
        old_global.get("status") == status
        and old_global.get("reasons", []) == reasons
        and old_global.get("successful_input_sha256") == successful_digest
    )
    global_record = {
        "status": status,
        "at": old_global.get("at") if same_global else _now(),
        "reasons": reasons,
        "successful_input_sha256": successful_digest,
    }
    core = {
        "version": 2,
        "global": global_record,
        "projects": dict(sorted(records.items())),
    }
    if old_doc.get("version") == 2 and _without(old_doc, "compiled_at") == core:
        return
    doc = {"compiled_at": _now(), **core}
    _write_atomic(paths.compile_json, json.dumps(doc, indent=2) + "\n")


def _snapshot_outputs(paths: Paths) -> dict[Path, bytes]:
    snapshot = {}
    if paths.base_out.exists():
        snapshot[paths.base_out] = paths.base_out.read_bytes()
    if paths.dags.exists():
        for file in paths.dags.rglob("*.yaml"):
            snapshot[file] = file.read_bytes()
    return snapshot


def _restore_outputs(paths: Paths, snapshot: dict[Path, bytes]) -> None:
    old_dags = {path for path in snapshot if path != paths.base_out}
    if paths.dags.exists():
        for file in paths.dags.rglob("*.yaml"):
            if file not in old_dags:
                file.unlink()
    for path, content in snapshot.items():
        _write_bytes_atomic(path, content)


def _restore_project(paths: Paths, name: str, snapshot: dict[Path, bytes]) -> None:
    root = paths.dags / name
    old = {path for path in snapshot if path.is_relative_to(root)}
    if root.exists():
        for file in root.rglob("*.yaml"):
            if file not in old:
                file.unlink()
    for path in old:
        _write_bytes_atomic(path, snapshot[path])


def _global_refusal(
    paths: Paths,
    old_doc: dict[str, Any],
    reason: str,
) -> int:
    previous = old_doc.get("projects", {})
    old_global = old_doc.get("global", {})
    successful = old_global.get("successful_input_sha256")
    try:
        _write_result(paths, old_doc, previous, "refused", [reason], successful)
    except OSError as exc:
        print(f"devman: cannot write {paths.compile_json}: {exc}", file=sys.stderr)
        return 1
    print(f"devman: compile refused: {reason}", file=sys.stderr)
    return 1


def _compile_locked(paths: Paths, names: list[str] | None, validate_all: bool) -> int:
    try:
        old_doc = _read_compile_doc(paths)
    except state.StateError as exc:
        # Refuse before any publication. The malformed file and every
        # published file keep their bytes.
        print(f"devman: {exc}", file=sys.stderr)
        return 1
    # Missing state has no records; malformed state never reaches this line.
    previous = old_doc.get("projects", {})

    digest, digest_errors = input_digest(paths)
    if digest_errors:
        return _global_refusal(paths, old_doc, "; ".join(digest_errors))
    try:
        manifest = load(paths.projects_toml)
        if manifest.errors.get(""):
            return _global_refusal(
                paths,
                old_doc,
                "projects.toml: " + "; ".join(manifest.errors[""]),
            )
        unknown = [
            name
            for name in names or []
            if name not in manifest.projects | manifest.errors
        ]
        if unknown:
            print(f"devman: unknown project {', '.join(unknown)}", file=sys.stderr)
            return 2
        assert paths.dagu_config is not None
        queues = dagu.configured_queues(paths.dagu_config)
        changed, error = fill_base(paths)
        if error:
            return _global_refusal(paths, old_doc, f"base: {error}")
        candidate_config = _candidate_config(paths)
        if changed or not paths.base_out.exists():
            probe = paths.tmp / "base-probe.yaml"
            probe.write_text('steps:\n  - name: devman-base-check\n    run: "true"\n')
            error = dagu.validate(candidate_config, probe)
            if error:
                return _global_refusal(
                    paths, old_doc, f"invalid packaged base: {error}"
                )
        if not (paths.guard and Path(paths.guard).is_file()):
            return _global_refusal(
                paths, old_doc, f"DEVMAN_GUARD {paths.guard} is not a file"
            )
    except (OSError, yaml.YAMLError, TypeError, AttributeError, AssertionError) as exc:
        return _global_refusal(paths, old_doc, f"compile input error: {exc}")
    except Exception as exc:
        return _global_refusal(paths, old_doc, f"unexpected compile error: {exc}")

    records = dict(previous)
    refused: dict[str, list[str]] = {}
    full = not names
    orphans: list[str] = []
    if full and paths.workflows.is_dir():
        known = manifest.projects.keys() | manifest.errors.keys()
        orphans = sorted(
            directory.name
            for directory in paths.workflows.iterdir()
            if directory.is_dir() and directory.name not in known
        )

    try:
        output_snapshot = _snapshot_outputs(paths)
    except OSError as exc:
        return _global_refusal(paths, old_doc, f"cannot read published files: {exc}")

    for name in sorted(manifest.projects.keys() | manifest.errors.keys()):
        if names and name not in names:
            continue
        project = manifest.projects.get(name)
        if project:
            try:
                record, reasons = _compile_project(
                    replace(paths, dagu_config=candidate_config),
                    queues,
                    project,
                    validate_all or changed,
                )
            except Exception as exc:
                _restore_project(paths, name, output_snapshot)
                record, reasons = None, [f"unexpected project error: {exc}"]
        else:
            record, reasons = None, manifest.errors[name]
        if record is None:
            refused[name] = reasons
            records[name] = _refused(
                previous.get(name), reasons, project.path if project else None
            )
        else:
            records[name] = record

    for orphan in orphans:
        refused[orphan] = [f"workflows/{orphan}/ has no table in projects.toml"]
    if full:
        for name in set(previous) - manifest.projects.keys() - manifest.errors.keys():
            if PROJECT_RE.match(name):
                shutil.rmtree(paths.dags / name, ignore_errors=True)
            records.pop(name, None)

    for name, record in records.items():
        if _without(previous.get(name), "at") == _without(record, "at"):
            records[name] = previous.get(name, record)

    global_reasons = [*sorted(refused)]
    if not full and not refused:
        old_global = old_doc.get("global", {})
        if (
            old_global.get("status") == "ok"
            and old_global.get("successful_input_sha256") == digest
        ):
            global_status = "ok"
            successful_digest = old_global["successful_input_sha256"]
            global_reasons = list(old_global.get("reasons", []))
        else:
            global_status = "refused"
            successful_digest = old_global.get("successful_input_sha256")
            global_reasons = ["partial compile does not cover current inputs"]
    elif refused:
        global_status = "refused"
        old_global = old_doc.get("global", {})
        successful_digest = old_global.get("successful_input_sha256")
    else:
        global_status = "ok"
        successful_digest = digest
        global_reasons = []

    try:
        _publish_base(paths)
        _write_result(
            paths,
            old_doc,
            records,
            global_status,
            global_reasons,
            successful_digest,
        )
    except Exception as exc:
        try:
            _restore_outputs(paths, output_snapshot)
        except OSError as restore_error:
            print(
                f"devman: compile failed: {exc}; restore failed: {restore_error}",
                file=sys.stderr,
            )
            return 1
        if isinstance(exc, OSError) and paths.compile_json.exists():
            print(f"devman: cannot write {paths.compile_json}: {exc}", file=sys.stderr)
            return 1
        return _global_refusal(paths, old_doc, f"unexpected compile error: {exc}")

    for name, reasons in refused.items():
        print(f"devman: compile refused {name}: {'; '.join(reasons)}", file=sys.stderr)
    return 1 if refused or global_status != "ok" else 0
