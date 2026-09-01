"""The watcher (CONCEPT.md §8, finding D7) — one process for the whole machine.

    filesystem change → watchexec → devman watch --dispatch → devman run → dagu enqueue

**One watcher per machine, not one per repository, and the deciding fact is
lifetime rather than capability.** A per-repository watcher has one plausible
home — a `processes.` entry in that repository's own devenv — and devenv
processes start under `devenv up` and nothing else. Not `devenv shell`, not
direnv entry, not `devenv test`. Reactivity would then apply to whichever
repositories somebody happened to have open (C1, D7).

**Which glob triggers which workflow is group content** (§8). A group declares
its own reactivity in `groups/<group>/triggers.toml`; the devenv module resolves
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

**`devman watch` is a supervisor around watchexec, not watchexec itself.** The
set of watched PATHS is watchexec's command line, so it is fixed when watchexec
starts; the MAPPING is re-read per event by the dispatcher below. A repository
that adopts reactivity after the watcher started would therefore go unwatched
until somebody restarted the service. The supervisor closes that gap: it
re-derives the watch set from the registry every `POLL_SECONDS` and replaces its
watchexec child when the path set changes. See `STAGE_3_LOG.md`, S16.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePath

from .registry import Project, Registry, deepest

# The watcher's own state, machine-side beside the registry it reads. Derived
# and reconstructable like everything else under `~/.local/share/devman/`
# (§9.3): deleting it costs the answer to "what did it last fire", which the
# next event restores.
WATCH_DIR = "watch"

# A run writes its logs under `.devman/.runs/`, inside the tree being watched.
# Without the first pattern every run is its own next event, whatever the
# workflow declares. The rest are directories a repository generates rather than
# edits — a write in one is not a save.
#
# This list matters more than it looks, because watchexec's own project and VCS
# ignore discovery is switched off below: the watcher gives `--project-origin`
# explicitly, so no repository's `.gitignore` is read. A group's globs and this
# list are therefore the whole filter, and a glob like `**/*.py` would otherwise
# fire on a write inside a virtual environment.
DEFAULT_IGNORES = (
    "**/.devman/.runs/**",
    "**/.git/**",
    "**/.devenv/**",
    "**/.direnv/**",
    "**/.venv/**",
    "**/__pycache__/**",
    "**/node_modules/**",
)

# How often the supervisor re-derives the watch set from the registry.
#
# It is a poll rather than an inotify watch on `<registry>/projects/`, and the
# reason is that the answer costs almost nothing: one `readdir` plus one small
# `metadata.json` per registered project, measured at 0.44 ms for six projects
# on a loaded machine (S16). At five seconds that is 0.009% of one core. An
# inotify watch would save that and cost a second event source to get wrong.
#
# It reads devman's own registry and never the disk at large, so §15.1's ban on
# scanning for repositories is untouched.
#
# Five seconds is the delay between a repository entering its shell for the
# first time and its saves firing. A developer who has just run `devenv shell`
# is not saving inside the same five seconds.
POLL_SECONDS = 5.0

# How long a watchexec child gets to leave after SIGTERM, before SIGKILL.
STOP_GRACE = 5.0


def nothing_to_watch(poll: float) -> str:
    return (
        "devman watch: no registered project takes a group that declares triggers.\n"
        "  Nothing to watch yet. This is not an error — reactivity is opt-in, by\n"
        "  taking a group whose triggers.toml names the globs (§8).\n"
        f"  Staying up and re-reading the registry every {poll:g}s, so a repository\n"
        "  that adopts a reactive group is watched without a restart."
    )


def _now() -> str:
    """Millisecond resolution, because a loop is measured in fractions of a
    second and a second-resolution stamp cannot tell one save's two events from
    a save and the formatter's answer to it (S6)."""
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


@dataclass
class WatchEntry:
    project: str
    path: Path
    globs: list[str]
    workflow: str
    group: str
    # Globs this repository never fires on, from its own `.devman/triggers.toml`
    # (009 P3-3). The group owns the trigger glob and the repository owns what
    # its tasks actually touch; this is where the repository says so.
    ignore: list[str] = field(default_factory=list)


def watch_map(reg: Registry) -> list[WatchEntry]:
    """Every `(project, globs, workflow)` the registry declares, deepest last.

    **A project whose registered path is gone is skipped, and that is not a
    tidiness rule — it is what keeps one repository's move from stopping
    reactivity for every repository on the machine.** watchexec exits
    immediately when any `--watch` path does not exist:

        Error:   × No such file or directory (os error 2)

    The supervisor exits with it, `Restart=on-failure` tries five times, and
    `startLimitBurst` then leaves the unit **failed** — 30 seconds from the
    first restart, with every other repository's saves going nowhere. Nothing
    brings it back: not the registry healing when the repository is entered
    again, because a failed unit is not restarted by anything except a person or
    an activation (`STAGE_5_LOG.md`, S2).

    The window is ordinary. A registry entry names a path that is not a
    directory between a repository moving and its shell being entered again, and
    a watcher restart in that window is a rebuild, a reboot, or another
    repository adopting a reactive group.

    Skipping is right rather than merely safe: watching a path that does not
    exist watches nothing, and §10 check 5 already owns a registered path that
    is gone. `unwatchable` below is what says so out loud.
    """
    out: list[WatchEntry] = []
    for proj in reg.projects().values():
        triggers = proj_triggers(proj)
        if not triggers or not proj.exists:
            continue
        group = (proj.raw_triggers() or {}).get("group", "?")
        by_workflow: dict[str, list[str]] = {}
        for pattern, workflow in triggers.items():
            by_workflow.setdefault(workflow, []).append(pattern)
        ignore = (proj.raw_triggers() or {}).get("ignore", []) or []
        for workflow, globs in by_workflow.items():
            out.append(
                WatchEntry(
                    proj.name, proj.path, sorted(globs), workflow, group, list(ignore)
                )
            )
    return out


def proj_triggers(proj: Project) -> dict[str, str]:
    raw = proj.raw_triggers()
    return (raw or {}).get("map", {}) or {}


def unwatchable(reg: Registry) -> list[Project]:
    """Registered projects that declare triggers and whose path is gone.

    `watch_map` drops them so that watchexec still starts. This names them, so
    that the smaller watch set is a sentence in the journal and in `devman
    doctor` rather than a silence — the developer is told which repository is
    missing, which watchexec's own message never says.
    """
    return [
        proj
        for proj in reg.projects().values()
        if proj_triggers(proj) and not proj.exists
    ]


class WatchState:
    def __init__(self, reg: Registry) -> None:
        self.dir = reg.root / WATCH_DIR
        self.state = self.dir / "state.json"
        self.fired = self.dir / "fired.jsonl"
        # When THIS process began. The supervisor rewrites the state file every
        # time the watch set changes, so a single `started_at` would report the
        # last pickup as the watcher's start and hide an old process (S16).
        self.started_at = _now()

    def start(
        self,
        entries: list[WatchEntry],
        argv: list[str],
        skipped: list | None = None,
    ) -> None:
        """Record what watchexec is watching RIGHT NOW.

        The supervisor writes this after it has started the child, never before,
        so `doctor` reads the watch set that exists rather than the one being
        built. A supervisor wedged between the two therefore still shows up as a
        discrepancy, which is the check §10 wants to keep (S16).

        `skipped` is every project the registry could not read (009 P2-3). The
        watcher cannot watch one — it has no path to give watchexec — so it
        skips it and RECORDS the skip, because a repository that silently stops
        being reactive looks exactly like a repository whose globs do not match.
        `doctor` reads this back.
        """
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "started_at": self.started_at,
                    "watching_since": _now(),
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
                    "skipped": [
                        {"project": f.name, "why": f.why, "entry": str(f.path)}
                        for f in (skipped or [])
                    ],
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
                "at": _now(),
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
    `--emit-events-to=json-stdio` hands the dispatcher the paths that changed,
    and the dispatcher matches each one against the project it sits in.
    """
    binary = shutil.which("watchexec") or "watchexec"
    argv = [
        binary,
        # One JSON object per event on the child's stdin. The spelling is
        # `json-stdio`; `json-stdin` is rejected at start-up with a list of the
        # valid modes, which is the loud kind of failure.
        "--emit-events-to=json-stdio",
        # Without this, watchexec runs the command once at start-up with an
        # empty batch — which would mean every mapped workflow fires whenever
        # the service restarts, and nobody saved anything.
        "--postpone",
        # Events that arrive while a dispatch is running are handled after it,
        # rather than killing it. A dispatch only enqueues, so it is short.
        "--on-busy-update=queue",
        # STATE THE ORIGIN, OR WATCHEXEC GOES LOOKING FOR IT.
        #
        # Watchexec resolves a "project origin" at start-up to find ignore files
        # and the VCS in use. Left to search, one watcher over several
        # repositories resolves their common ancestor — `/tmp`, or
        # `~/Documents/Projects`, or `$HOME` for a service systemd starts there —
        # and walks it. Measured: the same command line spun a core at 99.4% for
        # over a minute with the origin searched, and sat at 0.3% with it given
        # (S5). The registry root is the honest answer: it is devman's own
        # directory, it is small, and it is where this process's state lives.
        #
        # The cost is that no repository's `.gitignore` is consulted, which is
        # what `DEFAULT_IGNORES` above is for.
        f"--project-origin={reg.root}",
    ]
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


def announce(entries: list[WatchEntry], skipped: list[Project] = ()) -> None:
    for entry in entries:
        print(
            f"devman watch: {entry.project} {entry.globs} -> {entry.workflow}"
            f" [{entry.group}]",
            file=sys.stderr,
        )
    for proj in skipped:
        print(
            f"devman watch: skipping {proj.name} — its registered path"
            f" {proj.path} is not a directory, and watchexec exits on one."
            " Enter its shell to re-register it, or `devman doctor --prune`",
            file=sys.stderr,
        )


def watch_paths(entries: list[WatchEntry]) -> tuple[str, ...]:
    """The part of the watch set that is watchexec's command line.

    Only these force a new child. A changed glob does not: the dispatcher calls
    `watch_map` again for every batch, so which glob fires which workflow is
    already live.
    """
    return tuple(sorted({str(e.path) for e in entries}))


def watch_shape(entries: list[WatchEntry]) -> list[tuple]:
    """Everything the state file reports, so `doctor` never shows a stale glob."""
    return [
        (e.project, str(e.path), tuple(e.globs), e.workflow, e.group) for e in entries
    ]


def stop_child(child: subprocess.Popen) -> None:
    """SIGTERM, then SIGKILL. watchexec kills its own command group on SIGTERM."""
    child.terminate()
    try:
        child.wait(timeout=STOP_GRACE)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


def supervise(args, reg: Registry) -> int:
    """Run watchexec, and keep its watch set equal to the registry's.

    THE OBVIOUS IMPLEMENTATION IS THE WRONG ONE. `systemctl --user restart
    devman-watch` issued from inside the unit does not return: systemd stops the
    unit, which kills the process that asked, so every line after the call is
    dead code. Measured — 15 restarts in 30 seconds, not one of them reaching
    the next line, and `NRestarts=0` throughout, so `startLimitBurst` does not
    stop the loop either (S16). The supervisor therefore replaces its own child
    and never touches its unit.

    Exiting when watchexec exits is deliberate: `Restart=on-failure` then does
    its ordinary job, and a watchexec that died stays visible.
    """
    state = WatchState(reg)
    child: subprocess.Popen | None = None
    paths: tuple[str, ...] | None = None
    shape: list[tuple] | None = None
    argv: list[str] = []
    try:
        while True:
            entries = watch_map(reg)
            if watch_paths(entries) != paths:
                if child is not None:
                    stop_child(child)
                    child = None
                paths = watch_paths(entries)
                if entries:
                    announce(entries, unwatchable(reg))
                    argv = watchexec_command(
                        reg, entries, args.watchexec_arg, args.dagu_home
                    )
                    child = subprocess.Popen(argv)
                else:
                    argv = []
                    announce([], unwatchable(reg))
                    print(nothing_to_watch(args.poll_seconds), file=sys.stderr)
                shape = None
            if watch_shape(entries) != shape:
                shape = watch_shape(entries)
                state.start(entries, argv, reg.faults())

            if child is None:
                time.sleep(args.poll_seconds)
                continue
            try:
                return child.wait(timeout=args.poll_seconds)
            except subprocess.TimeoutExpired:
                continue
    except KeyboardInterrupt:
        return 130
    finally:
        if child is not None:
            stop_child(child)


def main(args, reg: Registry) -> int:
    if args.dispatch:
        return dispatch(args, reg)

    if args.print_only:
        entries = watch_map(reg)
        if not entries:
            announce([], unwatchable(reg))
            print(nothing_to_watch(args.poll_seconds), file=sys.stderr)
            return 0
        announce(entries, unwatchable(reg))
        print(
            " ".join(
                watchexec_command(reg, entries, args.watchexec_arg, args.dagu_home)
            )
        )
        return 0

    return supervise(args, reg)


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

    **Ownership is resolved once per path, by `registry.deepest()` — the same
    rule `project_for()` uses.** This function used to decide containment for
    itself and accept every registered root holding the path, so one save inside
    a nested checkout fired the inner project AND the outer one (009 P1-4). The
    outer repository's formatter then rewrote source across the repository
    boundary, and both runs reported success. Coalescing now runs after
    ownership, rather than instead of it.
    """
    entries = watch_map(reg)
    roots = {e.project: e.path for e in entries}
    by_project: dict[str, list[WatchEntry]] = {}
    for entry in entries:
        by_project.setdefault(entry.project, []).append(entry)

    hits: dict[tuple[str, str], tuple[WatchEntry, str]] = {}
    for raw in paths:
        path = Path(raw)
        try:
            here = path.resolve()
        except OSError:
            here = path
        owner = deepest(roots, here)
        if owner is None:
            continue
        for entry in by_project[owner]:
            try:
                rel = here.relative_to(entry.path.resolve())
            except (OSError, ValueError):
                continue
            # The repository's own layer, applied before its group's globs. A
            # path it excludes fires nothing at all — the run it would have
            # started does the work in a domain the repository's task does not
            # cover, which is a run that costs a queue slot and changes nothing
            # (009 P3-3).
            if any(PurePath(rel).full_match(g) for g in entry.ignore):
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
