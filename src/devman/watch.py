"""`devman watch`: one watchexec turns saves into events (PLAN Stage 5).

The watcher compiles at start. It recompiles when the overlay changes. It
sends a `save` event for each project that has a `save` entry. It restarts
watchexec only when the set of watched paths changes (B21), because a start
costs about 14 s of one core over 33 repositories (M5).
"""

from __future__ import annotations

import json
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from devman import router
from devman.compile import compile as run_compile
from devman.paths import Paths

# Generated or tool-owned in every repository (PLAN §A.1 rule 8, B3). The
# patterns start with `**/` because watchexec matches them against paths
# relative to `--project-origin`, which is the state directory and not the
# project. A bare name matched nothing outside it (measured, Stage 5).
IGNORE = (
    ".git",
    ".jj",
    ".devenv",
    ".direnv",
    ".venv",
    "node_modules",
    "__pycache__",
    ".gitman",
    ".worktrees",
    ".devman",
)
SKIPPED_KINDS = {"access", "remove"}  # a read or a delete is not a save
MAX_BATCH_SECONDS = 5.0


@dataclass(frozen=True)
class Targets:
    """What watchexec watches. Sorted, so two sets compare equal."""

    deep: tuple[Path, ...]  # projects with a `save` entry, `workflows/`, `library/`
    shallow: tuple[Path, ...]  # the overlay, for `projects.toml` and new folders
    canary: Path  # a state directory that proves the watcher is live

    def count(self) -> int:
        return len(self.deep) + len(self.shallow) + 1


def log(text: str) -> None:
    print(f"devman watch: {text}", file=sys.stderr, flush=True)


def seconds(text: str) -> float:
    """Read a watchexec duration: `300ms`, `2s`, `1m`. A bare number is ms."""
    found = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m)?", text.strip())
    if not found:
        raise ValueError(f"{text} is not a duration like 300ms, 2s or 1m")
    unit = {"ms": 0.001, "s": 1.0, "m": 60.0}[found.group(2) or "ms"]
    return float(found.group(1)) * unit


def save_projects(paths: Paths) -> dict[str, dict]:
    """The `compile.json` records of the projects with a `save` entry."""
    try:
        records = json.loads(paths.compile_json.read_text())["projects"]
    except (OSError, ValueError, KeyError):
        return {}
    return {
        name: rec
        for name, rec in records.items()
        if rec.get("path") and any(e.get("event") == "save" for e in rec.get("on", []))
    }


def targets(paths: Paths) -> Targets:
    """Only existing paths: watchexec exits when a watched path is missing."""
    deep = {Path(r["path"]) for r in save_projects(paths).values()}
    deep |= {paths.workflows, paths.library}
    shallow = {paths.overlay}
    return Targets(
        tuple(sorted(p for p in deep if p.is_dir())),
        tuple(sorted(p for p in shallow if p.is_dir())),
        paths.state / "watch",
    )


def command(paths: Paths, wanted: Targets, debounce: str) -> list[str]:
    argv = [
        "watchexec",
        "--only-emit-events",
        "--emit-events-to=json-stdio",
        f"--project-origin={paths.state}",
        "--debounce",
        debounce,
    ]
    for path in wanted.deep:
        argv += ["--watch", str(path)]
    for path in (*wanted.shallow, wanted.canary):
        argv += ["--watch-non-recursive", str(path)]
    for name in IGNORE:
        argv += ["--ignore", f"**/{name}", "--ignore", f"**/{name}/**"]
    return argv


def event_paths(line: str) -> list[str]:
    """The absolute file paths of one watchexec JSON event, or []."""
    try:
        tags = json.loads(line)["tags"]
    except (ValueError, KeyError, TypeError):
        return []
    if any(t.get("kind") == "fs" and t.get("simple") in SKIPPED_KINDS for t in tags):
        return []
    return [
        t["absolute"]
        for t in tags
        if t.get("kind") == "path" and "absolute" in t and t.get("filetype") != "dir"
    ]


def classify(paths: Paths, found: list[str]) -> tuple[bool, dict[str, list[str]]]:
    """Split changed paths into (overlay touched, project -> paths)."""
    records = save_projects(paths)
    overlay, by_project = False, {}
    for item in sorted(set(found)):
        path = Path(item)
        if path.is_relative_to(paths.overlay):
            overlay = True
        elif path.is_relative_to(paths.state):
            continue  # the canary
        elif project := router.find_project(records, path):
            by_project.setdefault(project, []).append(item)
    return overlay, by_project


def next_batch(lines: queue.Queue, quiet: float) -> list[str] | None:
    """Block for one event, then collect until `quiet` seconds pass with none.

    Return None when watchexec closed its output.
    """
    first = lines.get()
    if first is None:
        return None
    batch, deadline = [first], time.monotonic() + MAX_BATCH_SECONDS
    while time.monotonic() < deadline:
        try:
            more = lines.get(timeout=quiet)
        except queue.Empty:
            break
        if more is None:
            lines.put(None)  # report the end on the next call
            break
        batch.append(more)
    return batch


def _compile(paths: Paths) -> None:
    try:
        code = run_compile(paths, None, False)
    except Exception:  # the watcher must outlive a compile bug
        traceback.print_exc()
        code = 1
    if code:
        log(f"compile exited {code}")


def _canary(path: Path, ready: threading.Event) -> None:
    while not ready.wait(0.5):
        (path / "canary").write_text(str(time.time()))


def _read(stream, lines: queue.Queue) -> None:
    for line in stream:
        lines.put(line)
    lines.put(None)


def _stop(proc: subprocess.Popen) -> int:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    return proc.returncode


def _serve(paths: Paths, debounce: str, wanted: Targets) -> int | None:
    """Run one watchexec. Return None to restart it, else the exit code."""
    quiet = seconds(debounce)
    wanted.canary.mkdir(parents=True, exist_ok=True)  # watchexec needs it first
    log(f"watchexec starting, {wanted.count()} paths")
    proc = subprocess.Popen(
        command(paths, wanted, debounce),
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    lines: queue.Queue = queue.Queue()
    ready = threading.Event()
    threading.Thread(target=_read, args=(proc.stdout, lines), daemon=True).start()
    threading.Thread(target=_canary, args=(wanted.canary, ready), daemon=True).start()
    try:
        while (batch := next_batch(lines, quiet)) is not None:
            found = [p for line in batch for p in event_paths(line)]
            if not ready.is_set() and any(
                Path(p).is_relative_to(wanted.canary) for p in found
            ):
                ready.set()
                log("watchexec ready")
            overlay, by_project = classify(paths, found)
            if overlay:
                _compile(paths)
            for project, changed in by_project.items():
                outcome = router.emit(
                    paths, router.Event("save", project, tuple(changed), "watcher")
                )
                if outcome.code:
                    log(f"save {project}: {'; '.join(outcome.lines)}")
            if overlay and targets(paths) != wanted:
                log("the watch set changed")
                return None
        code = proc.wait()
        log(f"watchexec exited {code}")
        return code if code > 0 else 1
    finally:
        ready.set()
        _stop(proc)


def watch(paths: Paths, debounce: str = "300ms") -> int:
    """The service entry point. Return the exit code."""
    if shutil.which("watchexec") is None:
        log("watchexec is not on PATH")
        return 2
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    _compile(paths)
    while True:
        wanted = targets(paths)
        if not wanted.shallow:
            log(f"nothing to watch: {paths.overlay} is not a directory")
            return 1
        code = _serve(paths, debounce, wanted)
        if code is not None:
            return code
