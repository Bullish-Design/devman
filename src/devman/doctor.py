"""`devman doctor` — the only thing in this design that tells the developer anything.

§5.2 establishes that registration cannot report on the path that writes: devenv
discards the output of the firing that performs the write, so there is no
"devman: registered" line and there cannot be one. A quiet shell entry is the
design. Everything the plane knows and nobody can see arrives here.

**It reads far more than it computes** (E5). Dagu already diagnoses the failure
§15.3 accepts as the price of one shared instance — a wedged queue explains
itself, item by item, with a reason and a message. Six things it must compute
itself, because nothing in Dagu reports them, and §10 numbers them:

    1  a workflow that fails to load — `dagu ls` lists it with no indication
    2  a misspelled queue name — accepted silently, with no limit at all
    3  an unresolved directory variable — a literally-named directory
    4  shadowed files and their drift
    5  a stale registry entry — the only thing that ever notices a deleted repo
    6  a `.runs/` that has stopped ageing out

Plus §11's mechanical check, and — since stage 3 — what the watcher is watching
and what it last fired, because one watcher writing in six repositories is a
shared *write* failure rather than only a shared availability one.

**Five of the six are file checks over the projection**, so this works with the
daemon down and says plainly which checks it could not run.

It writes nothing unless `--prune` is given (§10 check 5).
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .registry import Registry
from .watch import WatchState, watch_map
from .workflow import PROJECT_DIR, SELF_DIR, Workflow

# The two names of §7.1's four that are directories. Dagu creates a directory
# named literally `${NAME}` when either is unset, and reports success (§7.2).
LITERAL_DIRS = (f"${{{PROJECT_DIR}}}", f"${{{SELF_DIR}}}")


@dataclass
class Report:
    sections: list[tuple[str, str, list[str]]] = field(default_factory=list)

    def add(self, name: str, status: str, lines: list[str]) -> None:
        self.sections.append((name, status, lines))

    @property
    def findings(self) -> int:
        return sum(len(lines) for _, status, lines in self.sections if status == "!!")

    def print(self) -> None:
        width = max(len(n) for n, _, _ in self.sections)
        for name, status, lines in self.sections:
            head = lines[0] if lines else ""
            print(f"{status}  {name.ljust(width)}  {head}")
            for line in lines[1:]:
                print(f"    {' ' * width}  {line}")


def _get(base: str, path: str, timeout: float = 1.5):
    with urllib.request.urlopen(f"{base}{path}", timeout=timeout) as resp:
        return json.load(resp)


def _config(dagu_home: Path) -> dict:
    """The instance config the machine module wrote. Read, never restated."""
    try:
        return yaml.safe_load((dagu_home / "config.yaml").read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _base(dagu_home: Path) -> dict:
    try:
        return yaml.safe_load((dagu_home / "base.yaml").read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}


# ---------------------------------------------------------------------------
# what Dagu reports about itself (E5)


def check_plane(rep: Report, base_url: str) -> bool:
    try:
        health = _get(base_url, "/api/v1/health")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        rep.add(
            "plane",
            "..",
            [
                f"no answer from {base_url} — {exc}",
                "the file checks below still ran; the queue checks did not",
            ],
        )
        return False
    rep.add(
        "plane",
        "ok",
        [
            f"{health.get('status', '?')} — dagu {health.get('version', '?')}, "
            f"up {int(health.get('uptime', 0)) // 3600}h"
        ],
    )
    return True


def check_queues(rep: Report, base_url: str) -> None:
    """A wedged queue explains itself. Read it, do not reimplement it (E5)."""
    try:
        data = _get(base_url, "/api/v1/queues")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        rep.add("queues", "..", [f"could not read the queues: {exc}"])
        return
    queues = data.get("queues", [])
    waiting = [q for q in queues if q.get("queuedCount")]
    if not waiting:
        running = sum(q.get("runningCount", 0) for q in queues)
        rep.add(
            "queues", "ok", [f"{len(queues)} queues, {running} running, none waiting"]
        )
        return
    lines = []
    for q in waiting:
        lines.append(
            f"{q['name']}: {q['queuedCount']} waiting, limit {q.get('maxConcurrency')}"
        )
        for run in q.get("running", []):
            lines.append(
                f"  held by {run.get('name')} {run.get('dagRunId')} since {run.get('startedAt')}"
            )
        try:
            items = _get(base_url, f"/api/v1/queues/{q['name']}/items")
        except (urllib.error.URLError, OSError, ValueError):
            continue
        for item in items.get("items", [])[:3]:
            for cond in item.get("conditions", []):
                if cond.get("status") == "False":
                    lines.append(
                        f"  {item.get('name')}: {cond.get('reason')} — {cond.get('message')}"
                    )
                    break
    rep.add("queues", "!!", lines)


# ---------------------------------------------------------------------------
# §10's six checks


def check_load(rep: Report, reg: Registry, dagu_home: Path) -> None:
    """Check 1 — a workflow that fails to load is invisible to `dagu ls` (E5)."""
    dagu = shutil.which("dagu")
    files = reg.projected_files()
    if dagu is None:
        rep.add("validate", "..", ["dagu is not on PATH, so no file was validated"])
        return
    bad = []
    for proj, name, path in files:
        result = subprocess.run(
            [dagu, "--dagu-home", str(dagu_home), "validate", str(path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            first = (result.stdout + result.stderr).strip().splitlines()
            bad.append(f"{proj.name}-{name}: {' '.join(first[:2])}")
    if bad:
        rep.add("validate", "!!", bad)
    else:
        rep.add("validate", "ok", [f"{len(files)} projected workflows load"])


def check_queue_names(rep: Report, reg: Registry, dagu_home: Path) -> None:
    """Check 2 — Dagu accepts an undefined queue silently, with no limit (§15.4)."""
    cfg = _config(dagu_home)
    declared = {
        q.get("name")
        for q in (cfg.get("queues", {}) or {}).get("config", []) or []
        if isinstance(q, dict)
    }
    if not declared:
        rep.add("queue names", "..", [f"no queue list in {dagu_home}/config.yaml"])
        return
    default = _base(dagu_home).get("queue")
    bad = []
    for proj, name, path in reg.projected_files():
        for queue in Workflow.read(path).queues():
            if queue not in declared:
                bad.append(
                    f"{proj.name}-{name} names queue '{queue}', which the machine does not declare"
                )
    if bad:
        rep.add("queue names", "!!", bad)
    else:
        rep.add(
            "queue names",
            "ok",
            [
                f"every queue named is one of: {', '.join(sorted(declared))} (default {default})"
            ],
        )


def _literal_dirs(root: Path, depth: int = 2) -> list[Path]:
    """Directories named literally `${DEVMAN_…_DIR}`, to a bounded depth.

    §15.1 forbids scanning the filesystem for repositories. This walks inside
    paths the registry already names, which is the opposite: it is O(registered
    projects) and it stops at `depth`.
    """
    found: list[Path] = []
    if not root.is_dir():
        return found
    stack = [(root, 0)]
    while stack:
        here, level = stack.pop()
        try:
            entries = list(os.scandir(here))
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            if entry.name in LITERAL_DIRS:
                found.append(Path(entry.path))
            elif level + 1 < depth and entry.name not in (".git", ".devenv", ".direnv"):
                stack.append((Path(entry.path), level + 1))
    return found


def check_literal(rep: Report, reg: Registry, dagu_home: Path) -> None:
    """Check 3 — the visible symptom of a trigger that forgot the environment.

    **Widened at stage 3 to search the registered repositories.** §10 wrote this
    check against a directory in the daemon's own working directory. The one
    real occurrence landed inside a project and was committed there
    (`STAGE_2_LOG.md` S15), and the second was produced by `dagu dry` in
    whatever directory it was called from (S1). Both names are searched, because
    §7.1's list of four holds two directory variables.
    """
    roots = [proj.path for proj in reg.projects().values() if proj.exists]
    roots += [reg.root, dagu_home, Path.cwd()]
    hits: list[Path] = []
    for root in roots:
        for hit in _literal_dirs(root):
            if hit not in hits:
                hits.append(hit)
    if hits:
        rep.add(
            "literal dir",
            "!!",
            [str(h) for h in hits]
            + ["a trigger passed the parameter and forgot the environment (§7.2)"],
        )
    else:
        rep.add(
            "literal dir",
            "ok",
            [f"none in {len(roots)} places (each to depth 2)"],
        )


def check_drift(rep: Report, reg: Registry) -> None:
    """Check 4 — an overriding file stops tracking its group (§15.6)."""
    lines = []
    shadowing = 0
    for proj in reg.projects().values():
        for name in proj.local:
            source = (proj.workflows.get(name) or {}).get("source")
            own = proj.path / ".devman" / "workflows" / f"{name}.yaml"
            if not source:
                lines.append(f"{proj.name}/{name}: invented — no group version to diff")
                continue
            shadowing += 1
            try:
                group_text = Path(source).read_text().splitlines()
                own_text = own.read_text().splitlines()
            except OSError as exc:
                lines.append(f"{proj.name}/{name}: cannot diff — {exc}")
                continue
            group = (proj.workflows.get(name) or {}).get("group", "?")
            same_all, of_all = _same_lines(group_text, own_text)
            same_exe, of_exe = _same_lines(
                _executable(group_text), _executable(own_text)
            )
            # Both figures, because the gap between them is the story: the group
            # files are mostly comment, so a whole-file percentage measures
            # documentation rather than duplication (`STAGE_2_LOG.md`, S14).
            lines.append(
                f"{proj.name}/{name}: shadows {group} — {same_exe} of {of_exe} "
                f"executable lines unchanged (whole file {same_all} of {of_all})"
            )
    # Drift is a fact, not a fault: §7.3 offers no partial override, so a
    # shadowing file is the mechanism working. `doctor` counts it (§15.6).
    rep.add("shadowing", "ok", lines or ["no repository shadows a group file"])


def _executable(lines: list[str]) -> list[str]:
    """Lines that do something. Blank and comment lines are documentation."""
    return [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def _same_lines(left: list[str], right: list[str]) -> tuple[int, int]:
    """How many of `left`'s lines survive into `right`, and how many there were."""
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks()), len(left)


def check_stale(rep: Report, reg: Registry, prune: bool) -> None:
    """Check 5 — the only thing that ever notices a deleted repository (§10).

    Pruning is safe because the registry is derived (§9.3): an entry pruned
    wrongly, because a disk was unmounted, restores itself the next time that
    repository's shell is entered. It is still behind a flag — `doctor` is the
    command a developer runs to find out what is wrong, and a diagnostic that
    deletes state by default is one a developer hesitates to run.
    """
    stale = [p for p in reg.projects().values() if not p.exists]
    if not stale:
        rep.add("stale entries", "ok", ["every registered path is a directory"])
        return
    lines = []
    for proj in stale:
        if prune:
            removed = reg.unproject(proj)
            lines.append(
                f"{proj.name} -> {proj.path} (gone) — pruned, {len(removed)} links removed"
            )
        else:
            lines.append(
                f"{proj.name} -> {proj.path} (gone) — its workflows still project "
                "and would pass, vacuously, in a directory Dagu creates"
            )
    if not prune:
        lines.append("run `devman doctor --prune` to remove them")
    rep.add("stale entries", "!!", lines)


def check_ageing(rep: Report, reg: Registry, dagu_home: Path) -> None:
    """Check 6 — retention is per DAG and runs when that DAG runs (§9.2, D5).

    A project whose workflows stop running keeps its `.runs/` forever. That is a
    check, not a setting.
    """
    days = _base(dagu_home).get("hist_retention_days")
    if not isinstance(days, int):
        rep.add("run output", "..", ["no hist_retention_days in base.yaml"])
        return
    cutoff = time.time() - days * 86400
    lines = []
    for proj in reg.projects().values():
        logs = proj.runs_dir / "logs"
        if not logs.is_dir():
            continue
        # The newest run in the project, not the oldest. Retention prunes a
        # DAG's history when that DAG runs, so what matters is whether anything
        # still runs here: once the newest run is older than the window, every
        # run in the project is, and nothing will ever prune any of it.
        runs = [d for d in logs.glob("*/dag-run_*") if d.is_dir()]
        if not runs:
            continue
        newest = max(d.stat().st_mtime for d in runs)
        if newest < cutoff:
            age = int((time.time() - newest) / 86400)
            lines.append(
                f"{proj.name}: {len(runs)} run log trees, newest {age} days old,"
                f" retention {days} — its workflows have stopped running, so"
                " nothing here will age out"
            )
    if lines:
        rep.add("run output", "!!", lines)
    else:
        rep.add(
            "run output", "ok", [f"nothing older than hist_retention_days ({days})"]
        )


def check_cross_repo(rep: Report, reg: Registry) -> None:
    """§11's mechanical check, in the shape S8 corrected it to.

    A workflow containing `action: dag.run` must not define `DEVMAN_PROJECT_DIR`
    **for itself**. Inside a step's `with.params` the name is correct: that is
    how a parent directs a child. The rule that forbade mentioning it at all
    reported the only correct cross-repo workflow in this repository as broken.
    """
    lines = []
    parents = 0
    for proj, name, path in reg.projected_files():
        wf = Workflow.read(path)
        if not wf.triggers_other_dags():
            continue
        parents += 1
        held = wf.holds_project_dir()
        if held:
            lines.append(
                f"{proj.name}-{name} holds {PROJECT_DIR} in: {', '.join(held)}"
            )
        elif SELF_DIR not in wf.params():
            lines.append(f"{proj.name}-{name} declares no {SELF_DIR} parameter")
    if lines:
        rep.add("cross-repo", "!!", lines)
    else:
        rep.add(
            "cross-repo",
            "ok",
            [f"{parents} workflows trigger others, all name {SELF_DIR}"],
        )


def check_watcher(rep: Report, reg: Registry) -> None:
    """What the watcher is watching, and what it last fired (§8, stage 3).

    One watcher serves every registered repository, so a mistake in it is a
    mistake in all of them at once — a shared *write* failure, which is more
    than the shared availability failure §15.3 already accepts.
    """
    watching = watch_map(reg)
    state = WatchState(reg).read()
    lines = []
    if not watching:
        lines.append("no registered project takes a group that declares triggers")
    for entry in watching:
        lines.append(
            f"{entry.project}: {', '.join(entry.globs)} -> {entry.workflow}"
            f"  [{entry.group}]"
        )
    if state is None:
        lines.append("the watcher has never run — no state file")
        rep.add("watcher", "ok" if not watching else "..", lines)
        return
    # A state file outlives the process that wrote it, so ask the kernel rather
    # than the file. A watcher that died looks exactly like a watcher that is
    # watching, and the difference is every save going unnoticed.
    pid = state.get("pid")
    alive = isinstance(pid, int) and Path(f"/proc/{pid}").exists()
    if not alive:
        rep.add(
            "watcher",
            "!!",
            lines
            + [
                f"it is NOT running — the last one started"
                f" {state.get('started_at', '?')} as pid {pid} and is gone",
                "nothing is watching these repositories:"
                " systemctl --user start devman-watch",
            ],
        )
        return
    lines.append(f"running since {state.get('started_at', '?')}, pid {pid}")

    # The watched PATHS are fixed when the service starts, because that is what
    # watchexec is given on its command line; the MAPPING is re-read per event.
    # So a project that adopted reactivity after the watcher started is not
    # watched, and nothing else would ever say so.
    running = {w.get("project") for w in state.get("watching", [])}
    current = {e.project for e in watching}
    if running != current:
        rep.add(
            "watcher",
            "!!",
            lines
            + [
                f"it started with {sorted(running) or 'nothing'} and the registry now"
                f" says {sorted(current) or 'nothing'}",
                "restart it: systemctl --user restart devman-watch",
            ],
        )
        return
    fired = WatchState(reg).last_fired(3)
    if fired:
        for line in fired:
            lines.append(
                f"fired {line.get('at', '?')}  {line.get('project')}/{line.get('workflow')}"
                f"  <- {line.get('path', '?')}"
            )
    else:
        lines.append("it has fired nothing yet")
    rep.add("watcher", "ok", lines)


def main(args, reg: Registry) -> int:
    dagu_home = Path(args.dagu_home).expanduser()
    cfg = _config(dagu_home)
    host = cfg.get("host", "127.0.0.1")
    port = cfg.get("port", 8080)
    base_url = f"http://{host}:{port}"

    projects = reg.projects()
    print(
        f"devman doctor — {len(projects)} projects, {len(reg.projected_files())} workflows"
    )
    print(f"    registry   {reg.root}")
    print(f"    dagu home  {dagu_home}")
    print()

    rep = Report()
    if check_plane(rep, base_url):
        check_queues(rep, base_url)
    check_load(rep, reg, dagu_home)
    check_queue_names(rep, reg, dagu_home)
    check_literal(rep, reg, dagu_home)
    check_drift(rep, reg)
    check_stale(rep, reg, args.prune)
    check_ageing(rep, reg, dagu_home)
    check_cross_repo(rep, reg)
    check_watcher(rep, reg)
    rep.print()

    print()
    if rep.findings:
        print(f"{rep.findings} findings.")
        return 1
    print("Nothing to report.")
    return 0
