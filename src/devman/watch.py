"""The watcher (CONCEPT.md §8, finding D7) — one process for the whole machine.

    filesystem change → watchexec → devman watch --dispatch → devman run → dagu enqueue

**One watcher per machine, not one per repository, and the deciding fact is
lifetime rather than capability.** A per-repository watcher has one plausible
home — a `processes.` entry in that repository's own devenv — and devenv
processes start under `devenv up` and nothing else. Not `devenv shell`, not
direnv entry, not `devenv test`. Reactivity would then apply to whichever
repositories somebody happened to have open (C1, D7).

**Which glob triggers which workflow is group content** (§8). A group declares
its own reactivity in `groups/<group>/triggers.nix`; the devenv module resolves
it at evaluation time, exactly as it resolves workflows (§7.3), and records the
outcome in the registry entry. This process reads the registry and nothing else:
it never parses a group file, never scans the disk for repositories (§15.1), and
holds no list of its own.

**Two layers stop a formatter chasing itself, and they are different layers.**

  * `--ignore` keeps the watcher out of `.devman/.runs/`, so a run's own log
    writes are not events. Without it every run re-fires every watcher in that
    repository, whatever the workflow does.
  * The workflow's own `preconditions:` compare a content hash, so a workflow
    that rewrites the files it watches does no work the second time — and your
    own edit right after the formatter's write still fires, because a hash is
    not a window (§8, E1).

The plane owns neither mechanism. Both are Dagu's and watchexec's own.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePath

from .registry import Project, Registry

# The watcher's own state, machine-side beside the registry it reads. Derived
# and reconstructable like everything else under `~/.local/share/devman/`
# (§9.3): deleting it costs the answer to "what did it last fire", which the
# next event restores.
WATCH_DIR = "watch"

# A run writes its logs under `.devman/.runs/`, inside the tree being watched.
# Without this every run is its own next event, whatever the workflow declares.
DEFAULT_IGNORES = ("**/.devman/.runs/**", "**/.devenv/**", "**/.direnv/**")


@dataclass
class WatchEntry:
    project: str
    path: Path
    globs: list[str]
    workflow: str
    group: str


def watch_map(reg: Registry) -> list[WatchEntry]:
    """Every `(project, globs, workflow)` the registry declares, deepest last."""
    out: list[WatchEntry] = []
    for proj in reg.projects().values():
        triggers = proj_triggers(proj)
        if not triggers:
            continue
        group = (proj.raw_triggers() or {}).get("group", "?")
        by_workflow: dict[str, list[str]] = {}
        for pattern, workflow in triggers.items():
            by_workflow.setdefault(workflow, []).append(pattern)
        for workflow, globs in by_workflow.items():
            out.append(
                WatchEntry(proj.name, proj.path, sorted(globs), workflow, group)
            )
    return out


def proj_triggers(proj: Project) -> dict[str, str]:
    raw = proj.raw_triggers()
    return (raw or {}).get("map", {}) or {}


class WatchState:
    def __init__(self, reg: Registry) -> None:
        self.dir = reg.root / WATCH_DIR
        self.state = self.dir / "state.json"
        self.fired = self.dir / "fired.jsonl"

    def start(self, entries: list[WatchEntry], argv: list[str]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "watching": [
                        {
                            "project": e.project,
                            "path": str(e.path),
                            "globs": e.globs,
                            "workflow": e.workflow,
                            "group": e.group,
                        }
                        for e in entries
                    ],
                    "command": argv,
                },
                indent=2,
            )
            + "\n"
        )

    def read(self) -> dict | None:
        try:
            return json.loads(self.state.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def record(self, project: str, workflow: str, path: str, outcome: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "project": project,
                "workflow": workflow,
                "path": path,
                "outcome": outcome,
            }
        )
        with self.fired.open("a") as fh:
            fh.write(line + "\n")

    def last_fired(self, count: int) -> list[dict]:
        try:
            lines = self.fired.read_text().splitlines()
        except OSError:
            return []
        out = []
        for line in lines[-count:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


# ---------------------------------------------------------------------------
# the supervisor


def watchexec_command(
    reg: Registry, entries: list[WatchEntry], extra: list[str], dagu_home: str
) -> list[str]:
    """One watchexec for every watched repository.

    watchexec applies its filters across every `--watch` path, so the mapping
    from a path back to a project and a workflow is done here rather than there:
    `--emit-events-to=json-stdin` hands the dispatcher the paths that changed,
    and the dispatcher matches each one against the project it sits in.
    """
    binary = shutil.which("watchexec") or "watchexec"
    argv = [binary, "--emit-events-to=json-stdin", "--on-busy-update=queue"]
    for pattern in DEFAULT_IGNORES:
        argv += ["--ignore", pattern]
    for path in sorted({str(e.path) for e in entries}):
        argv += ["--watch", path]
    argv += extra
    argv += ["--", *dispatch_command(reg, dagu_home)]
    return argv


def self_binary() -> str:
    """This CLI, by the name the watcher's PATH resolves.

    Not an environment variable: Dagu passes every `DEVMAN_*` in the enqueueing
    process's environment through to the run (`env_passthrough_prefixes`), and
    §7.1's list of four names is closed.
    """
    return shutil.which("devman") or sys.argv[0]


def dispatch_command(reg: Registry, dagu_home: str) -> list[str]:
    return [
        self_binary(),
        "--registry",
        str(reg.root),
        "--dagu-home",
        dagu_home,
        "watch",
        "--dispatch",
    ]


def main(args, reg: Registry) -> int:
    if args.dispatch:
        return dispatch(args, reg)

    entries = watch_map(reg)
    if not entries:
        print(
            "devman watch: no registered project takes a group that declares triggers.\n"
            "  Nothing to watch. This is not an error — reactivity is opt-in, by\n"
            "  taking a group whose triggers.nix names the globs (§8).",
            file=sys.stderr,
        )
        # Exit 0 and stop. A user service that fails here would restart forever.
        return 0

    argv = watchexec_command(reg, entries, args.watchexec_arg, args.dagu_home)
    state = WatchState(reg)
    state.start(entries, argv)
    for entry in entries:
        print(
            f"devman watch: {entry.project} {entry.globs} -> {entry.workflow}"
            f" [{entry.group}]",
            file=sys.stderr,
        )
    if args.print_only:
        print(" ".join(argv))
        return 0
    return subprocess.run(argv, check=False).returncode


# ---------------------------------------------------------------------------
# the dispatcher — one invocation per batch of filesystem events


def changed_paths(raw: str) -> list[str]:
    """The paths in one watchexec `json-stdin` batch."""
    paths = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for tag in event.get("tags", []):
            if tag.get("kind") == "path" and tag.get("absolute"):
                paths.append(tag["absolute"])
    return paths


def match(reg: Registry, paths: list[str]) -> list[tuple[WatchEntry, str]]:
    """Which `(entry, path)` pairs a batch of changed paths triggers.

    One pair per workflow per batch, so a save that touches three files is one
    run rather than three. That is coalescing at the detector, and it is not the
    loop break: the loop break is the workflow's own content-hash precondition
    (§8, E1). A batch is not a time window and swallows no later edit.
    """
    entries = watch_map(reg)
    hits: dict[tuple[str, str], tuple[WatchEntry, str]] = {}
    for raw in paths:
        path = Path(raw)
        for entry in entries:
            try:
                rel = path.relative_to(entry.path)
            except ValueError:
                continue
            if any(PurePath(rel).full_match(g) for g in entry.globs):
                hits.setdefault((entry.project, entry.workflow), (entry, str(path)))
    return list(hits.values())


def dispatch(args, reg: Registry) -> int:
    paths = changed_paths(sys.stdin.read())
    state = WatchState(reg)
    rc = 0
    for entry, path in match(reg, paths):
        argv = [
            self_binary(),
            "--registry",
            str(reg.root),
            "--dagu-home",
            args.dagu_home,
            "run",
            entry.workflow,
            "--project",
            entry.project,
        ]
        result = subprocess.run(argv, check=False)
        state.record(
            entry.project,
            entry.workflow,
            path,
            "enqueued" if result.returncode == 0 else f"refused ({result.returncode})",
        )
        rc = rc or result.returncode
    return rc
