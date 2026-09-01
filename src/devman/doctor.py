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
    2  a misspelled queue name — accepted silently, at a concurrency nobody chose
    3  an unresolved directory variable — a literally-named directory
    4  shadowed files and their drift
    5  a stale registry entry — the only thing that ever notices a deleted repo
    6  a `.runs/` that has stopped ageing out

Plus §11's mechanical check, plus — since stage 5 — a workflow that defines its
own `handler_on` and therefore records none of its runs (§9.2), and — since
stage 3 — what the watcher is watching
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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import watch
from .registry import Registry, dag_name_fault, identity_fault
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
    """A wedged queue explains itself. Read it, do not reimplement it (E5).

    **WAITING IS NOT WEDGED, AND THIS CHECK USED TO CONFUSE THE TWO.** It
    reported `!!` for any queue with a queued item, which is what a queue is
    for. Nothing noticed until stage 4 gave the machine enough work to have two
    runs in flight at once: four `maintain` runs fired together filled the
    `light` queue for about a second, `doctor` called it a finding, exited 1,
    and failed three of the four runs — a maintenance workflow reporting itself
    as a fault (`STAGE_4_LOG.md`, S14).

    §15.3 asks this check to diagnose a **wedged** plane, and the difference is
    whether anything is draining the queue:

    * queued **and** something running — the queue is working. `ok`, with the
      counts, because a developer wondering why a run has not started should
      still be able to see it.
    * queued **and nothing running** — nothing will drain it. `!!`.
    * an item carrying a failed condition — `!!`, with Dagu's own reason. A
      merely-queued item carries no conditions at all on 2.15.0; this stays
      because it is the path E5 measured and it is Dagu reporting, not devman
      guessing.
    """
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
    wedged = False
    for q in waiting:
        draining = q.get("runningCount", 0) > 0
        state = "draining" if draining else "NOTHING RUNNING — wedged"
        wedged = wedged or not draining
        lines.append(
            f"{q['name']}: {q['queuedCount']} waiting, "
            f"{q.get('runningCount', 0)} running, limit {q.get('maxConcurrency')}"
            f" — {state}"
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
                    wedged = True
                    lines.append(
                        f"  {item.get('name')}: {cond.get('reason')} — {cond.get('message')}"
                    )
                    break
    rep.add("queues", "!!" if wedged else "ok", lines)


# ---------------------------------------------------------------------------
# §10's six checks


def check_load(rep: Report, reg: Registry, dagu_home: Path) -> None:
    """Check 1 — a workflow that fails to load is invisible to `dagu ls` (E5)."""
    dagu = shutil.which("dagu")
    files = reg.projected_files()
    if dagu is None:
        rep.add("validate", "..", ["dagu is not on PATH, so no file was validated"])
        return

    # THIS CHECK IS 86% OF `doctor`'S RUNTIME, AND ALL OF IT IS SPAWN COST.
    #
    # One `dagu validate` per projected file, and `dagu` is a Go binary that
    # starts, parses one YAML file and exits. Measured at 174 files — the size
    # of a 58-project plane — 13.35 s serially against 1.86 s across 8 workers,
    # because the cost is process startup rather than the daemon
    # (`STAGE_7_LOG.md`, I-2a). Threads and not processes: a worker only waits
    # on `subprocess.run`, which releases the GIL for the whole of it.
    #
    # `ThreadPoolExecutor.map` returns results IN INPUT ORDER, so the report is
    # byte-identical to the serial version rather than merely equivalent. This
    # check does not need that — `bad` is a list nobody sorts — but it is free,
    # so the output cannot drift with thread scheduling.
    def _validate(item: tuple) -> str | None:
        proj, name, path = item
        result = subprocess.run(
            [dagu, "--dagu-home", str(dagu_home), "validate", str(path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return None
        first = (result.stdout + result.stderr).strip().splitlines()
        return f"{proj.name}-{name}: {' '.join(first[:2])}"

    bad: list[str] = []
    if files:
        # 8 is the measured knee on this machine, capped by `len(files)` so a
        # small plane never starts more workers than it has work.
        with ThreadPoolExecutor(max_workers=min(8, len(files))) as pool:
            bad = [line for line in pool.map(_validate, files) if line]
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


def check_projection(rep: Report, reg: Registry) -> None:
    """Does `dags/<project>-<workflow>` still point at that project's file?

    Everything else in `doctor` checks a projected file. This checks the one
    thing between a projected file and the name a trigger uses: a DAG name is
    machine-global, `<project>-<workflow>` is not injective, and the projection
    is `ln -sfn` — so a second project rendering the same flat name silently
    takes the first one's link.

    It costs one `readlink` per projected workflow and needs no running daemon.

    **Since S-12 it separates two answers that used to look identical.** A
    missing link is not a collision when the codec has changed underneath the
    machine: the repository simply has not been entered since, so it still
    projects under `<project>-<workflow>`. That is a migration note and a fix a
    developer can run, not a wrong-file hazard — and reporting it as `!!` would
    have made every repository on the machine a fault for as long as the
    migration took.
    """
    bad, unmigrated = [], []
    for proj, name, _path in reg.projected_files():
        fault = reg.dag_link_fault(proj, name)
        if not fault:
            continue
        if reg.unmigrated(proj, name):
            unmigrated.append(f"{proj.name}/{name}")
        else:
            dag = reg.dag_name(proj, name)
            bad.append(f"{dag}: the DAG of that name points at {fault}")
    if bad:
        rep.add(
            "projection",
            "!!",
            bad
            + [
                "a trigger enqueues by name, so these run the wrong file and"
                " report success — enter the repository's shell to re-project"
                " it (§9.2)"
            ],
        )
        return
    total = len(reg.projected_files())
    if unmigrated:
        projects = sorted({line.split("/")[0] for line in unmigrated})
        rep.add(
            "projection",
            "ok",
            [
                f"{total - len(unmigrated)} of {total} DAG names each point at"
                " their own project's file",
                f"{len(unmigrated)} still project under the pre-codec name, in"
                f" {len(projects)} repositories: {', '.join(projects)}",
                "each migrates itself the next time its shell is entered"
                " (§9.2, S-12) — `devman run` says so and falls back until then",
            ],
        )
        return
    rep.add(
        "projection",
        "ok",
        [f"{total} DAG names each point at their own project's file"],
    )


def check_dag_names(rep: Report, reg: Registry) -> None:
    """A name the codec cannot render, on either half (§9.2, S-12; 009 P1-5).

    A dot in the workflow half makes the last dot of `<project>.<workflow>`
    ambiguous, so the name stops being injective — which is the one property the
    codec exists to provide. The devenv module refuses such a name at evaluation
    time for a group and at shell entry for a local override, so this catches
    only a projection written before the codec landed.

    **The PROJECT half is checked too, and it was not before.** `devman.project`
    was a bare `types.str` until 009, so a legacy entry can hold a name the
    grammar now refuses — and after this stage that repository cannot enter its
    shell. `doctor` naming it is what gives the developer a rename path instead
    of a broken shell, so it names the metadata file as well as the project.

    **This is set membership, not a heuristic, so §15.7 does not reach it.** It
    reads the characters in a name the registry already holds.
    """
    bad = []
    for proj in reg.projects().values():
        fault = identity_fault("project", proj.name)
        if fault:
            meta = (proj.entry or reg.projects_dir / proj.name) / "metadata.json"
            bad.append(f"{proj.name}: {fault.splitlines()[0]}\n     {meta}")
    for proj, name, _path in reg.projected_files():
        fault = identity_fault("workflow", name) or dag_name_fault(name)
        if fault:
            bad.append(f"{proj.name}/{name}: {fault.splitlines()[0]}")
    if bad:
        rep.add("dag names", "!!", bad)
    else:
        rep.add(
            "dag names",
            "ok",
            [f"{len(reg.projected_files())} workflow names render one DAG name each"],
        )


def check_handlers(rep: Report, reg: Registry) -> None:
    """A workflow that defines `handler_on` stops recording its own runs (§9.2).

    **Why this is not §15.7.** §15.7 says the plane holds no opinion about what
    a workflow *does* — how long a `check` takes, what it costs, whether it
    still fits. This check has no opinion about any of that. It is the same
    shape as §11's check above: a workflow that silently takes away something
    the **machine** promised. `base.yaml` is inherited whole-field, so a DAG
    with its own `handler_on` replaces the machine's exit handler, and
    `metadata.jsonl` — the one file §9.2 says survives every retention setting,
    and the file the release gate reads — gains no line for that run.

    Nothing else notices. The run succeeds, the logs land in the right project,
    and `dagu status` is clean. Stage 4 measured it, wrote it into §9.2 in
    prose, and left the mechanical check to stage 5 (`STAGE_4_LOG.md`, S3, and
    its "what stage 4 did not do").

    It is `!!` rather than a note, because the loss is silent and permanent: no
    later run puts back the line that was never written.
    """
    lines = []
    for proj, name, path in reg.projected_files():
        events = Workflow.read(path).handlers()
        if events:
            lines.append(
                f"{proj.name}-{name} defines handler_on ({', '.join(events)})"
                " — it replaces base.yaml's, so its runs append no line to"
                " .devman/.runs/metadata.jsonl (§9.2)"
            )
    if lines:
        rep.add("handlers", "!!", lines)
    else:
        rep.add(
            "handlers",
            "ok",
            ["no workflow defines handler_on, so every run is recorded"],
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


def check_fanout(rep: Report, reg: Registry) -> None:
    """A parent that starts child runs must state how many it starts at once.

    **The queue does not reach a fan-out.** §12 rule 8 says a scheduled run
    bypasses its queue; S-8 measured the sibling path: a `dag.run` child bypasses
    it too, because the parent executes the child in place rather than enqueueing
    it. Two children naming a queue of limit 1 ran concurrently, and the same two
    through `dag.enqueue` did not. So the machine's limits protect it from a
    burst of `devman run` and from nothing a parent starts itself.

    Nothing else would say so. The children succeed, the parent succeeds, and the
    only trace is load — which is §12 rule 4's shape, seen from the machine's
    side rather than the workflow's.

    This is set membership, not a heuristic, so §15.7 does not reach it: it reads
    three field names Dagu documents and reports their absence. A stated bound is
    never a finding, whatever its value.
    """
    lines = []
    parents = 0
    for proj, name, path in reg.projected_files():
        wf = Workflow.read(path)
        if not wf.child_runs():
            continue
        parents += 1
        for why in wf.unbounded_fanout():
            lines.append(f"{proj.name}-{name}: {why}")
    if lines:
        lines.append(
            "a dag.run child takes no queue slot (S-8) — bound it with type:"
            " chain, max_active_steps, or parallel.max_concurrent"
        )
        rep.add("fan-out", "!!", lines)
    else:
        rep.add(
            "fan-out",
            "ok",
            [f"{parents} workflows start child runs, each with a stated bound"],
        )


def running_watchers(reg: Registry) -> list[tuple[int, int]]:
    """Every watchexec aimed at this registry, as `(pid, parent pid)`.

    **Ask the kernel, not the state file.** `<registry>/watch/state.json` has one
    slot and the last writer wins, so a second watcher does not appear in it —
    it overwrites it. Deriving liveness from the file therefore reports the
    newest watcher as the only one, which is exactly backwards when the problem
    is that there are two.

    §8 says one watcher per machine, and a second is not a second opinion: every
    watcher dispatches the same event, so each save fires once more than it
    should and the extra run looks exactly like a loop that did not break.

    A second one is easy to make and hard to notice. `devman watch` run by hand
    leaves its watchexec **orphaned** when the supervisor dies — reparented to
    init, still holding its inotify watches, and surviving a rebuild, because
    systemd never owned it. Three of them once tripled every run in this
    repository (S18).

    This reads `/proc`, which is the process table rather than the filesystem.
    §15.1 forbids walking the disk to find repositories; it says nothing about
    asking the kernel what is running.
    """
    marker = f"--project-origin={reg.root}".encode()
    found = []
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return found
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
            stat = (entry / "stat").read_text()
        except OSError:
            continue  # the process ended while we looked at it
        if not argv or b"watchexec" not in argv[0] or marker not in argv:
            continue
        # Field 4 of `stat` is the parent pid. Split after the last `)` because
        # the second field is the command name and may hold anything.
        ppid = int(stat.rsplit(")", 1)[1].split()[1])
        found.append((int(entry.name), ppid))
    return sorted(found)


def check_daemon_shell(rep: Report, dagu_home: Path) -> None:
    """`SHELL` in the running Dagu's own environment (009 P1-3, S13).

    Dagu resolves a step's shell from `$SHELL` and falls back to the instance's
    `default_shell` only when `$SHELL` is unset — and it reads that from
    whichever process enqueues the run. So every enqueue owner has to clear it:
    `devman run` does, for the CLI, the watcher and the hook; the unit does,
    with `UnsetEnvironment=SHELL`, for the runs the daemon enqueues itself under
    a `schedule:`.

    **Clearing per owner is a whack-a-mole invariant.** Two owners today, and the
    module's comment claimed for a whole stage that there was one. This check is
    the durable form: it reads what is actually there rather than counting the
    places that ought to have cleared it.

    The failure it catches is silent until a workflow uses a shell-specific
    construct. A benchmark campaign reading bash's `$EPOCHREALTIME` is the one
    that found it, with `parameter not set` (`STAGE_4_LOG.md` S9, S13).

    This reads `/proc`, which is the process table rather than the filesystem
    (§15.1 says nothing about asking the kernel what is running).
    """
    pids = _dagu_pids(dagu_home)
    if not pids:
        rep.add("daemon shell", "..", ["no running Dagu found in the process table"])
        return
    held = []
    for pid in pids:
        try:
            raw = Path(f"/proc/{pid}/environ").read_bytes()
        except OSError:
            continue  # not ours to read, or it ended while we looked
        for item in raw.split(b"\0"):
            if item.startswith(b"SHELL="):
                held.append(f"pid {pid}: {item.decode(errors='replace')}")
    if held:
        rep.add(
            "daemon shell",
            "!!",
            held
            + [
                "a scheduled run would take this shell instead of the instance's"
                " default_shell (S13)",
                'the unit should state serviceConfig.UnsetEnvironment = "SHELL";'
                " restart it after a rebuild",
            ],
        )
    else:
        rep.add(
            "daemon shell",
            "ok",
            [f"SHELL is unset in {len(pids)} dagu process(es) — default_shell governs"],
        )


def _dagu_pids(dagu_home: Path) -> list[int]:
    """Every running Dagu that serves this home, by its command line."""
    marker = str(dagu_home).encode()
    found = []
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return found
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if not argv or not argv[0]:
            continue
        if Path(argv[0].decode(errors="replace")).name != "dagu":
            continue
        if b"start-all" not in argv:
            continue
        # A machine may run a second Dagu on another home (§4). Match the home
        # this doctor was pointed at, from the argv or from the environment.
        try:
            env = (entry / "environ").read_bytes()
        except OSError:
            env = b""
        if marker in b"\0".join(argv) or b"DAGU_HOME=" + marker in env:
            found.append(int(entry.name))
    return sorted(found)


def check_trigger_targets(rep: Report, reg: Registry) -> None:
    """A trigger must name a workflow the project actually projects (S-3).

    **Nothing checked this, and the failure is silent in the worst direction.**
    A group that is tombstoned — its workflows deleted, its `triggers.toml`
    left behind — keeps a `triggers` block in every registry entry that took it.
    The watcher then fires `devman run <workflow>` on every matching save,
    `devman run` refuses because the name resolves to nothing, and the developer
    sees nothing at all: the refusal goes to a watcher log nobody opens. Worse,
    `check_watcher` below PRINTS the mapping, so `doctor` shows the broken
    trigger as evidence of health.

    **This is set membership, not a heuristic, so §15.7 does not reach it.**
    §15.7 forbids `doctor` guessing what a workflow means or whether it is
    correct. Here both sides come from one registry entry that Nix wrote: the
    trigger's target name, and the set of workflow names the same entry says
    this project projects. The question is `in`, and it has exactly one answer.
    """
    projects = reg.projects()
    checked = 0
    bad = []
    for entry in watch_map(reg):
        proj = projects.get(entry.project)
        if proj is None:
            continue
        checked += 1
        names = proj.workflow_names()
        if entry.workflow not in names:
            bad.append(
                f"{entry.project}: {', '.join(entry.globs)} -> {entry.workflow}"
                f"  [{entry.group}] — '{entry.workflow}' is not projected."
            )
            bad.append(f"  this project projects: {', '.join(names) or '(nothing)'}")
            bad.append(
                "  every matching save fires a run devman refuses;"
                " drop the trigger, or restore the workflow"
            )
    if bad:
        rep.add("trigger target", "!!", bad)
    elif checked:
        rep.add(
            "trigger target",
            "ok",
            [f"{checked} triggers each name a workflow their project projects"],
        )
    else:
        rep.add("trigger target", "ok", ["no registered project declares a trigger"])


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
    # A stale entry that declares triggers is dropped from the watch set, or
    # watchexec would refuse to start and take reactivity down for every
    # repository (S2). The stale-entry check above says the path is gone; this
    # says what it costs, because the two facts were reported side by side and
    # unconnected the first time this happened.
    for proj in watch.unwatchable(reg):
        lines.append(
            f"{proj.name}: NOT watched — {proj.path} is not a directory."
            " Enter its shell to re-register it, or `devman doctor --prune`"
        )
    # Liveness comes from the process table. The state file says what a watcher
    # recorded; the kernel says what is running, and those differ in both of the
    # ways that matter — a state file outlives the process that wrote it, and a
    # second watcher overwrites it rather than appearing in it.
    live = running_watchers(reg)
    pid = state.get("pid") if state else None
    # A supervisor with nothing to watch has NO watchexec child: it is waiting
    # for the first repository to adopt a reactive group (S16). Counting only
    # watchexec would report that healthy machine as a dead watcher, which the
    # NixOS test caught the first time this check was written.
    supervisor_alive = isinstance(pid, int) and Path(f"/proc/{pid}").exists()

    if not live:
        if state is None:
            lines.append("the watcher has never run — no state file")
            rep.add("watcher", "ok" if not watching else "..", lines)
            return
        if supervisor_alive and not watching:
            lines.append(f"running as pid {pid}, with nothing to watch yet")
            rep.add("watcher", "ok", lines)
            return
        if supervisor_alive:
            rep.add(
                "watcher",
                "!!",
                lines
                + [
                    f"the supervisor is alive as pid {pid} and is watching nothing",
                    "it should have started watchexec for the repositories above:"
                    " journalctl --user -u devman-watch",
                ],
            )
            return
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

    if len(live) > 1:
        # Name the remedy per watcher, because it differs. An orphan has no
        # supervisor to stop, and killing the watchexec of a live supervisor
        # only makes that supervisor start another one.
        extra = []
        for wpid, ppid in live:
            if ppid == 1:
                extra.append(f"watchexec pid {wpid} is ORPHANED — stop it: kill {wpid}")
            else:
                extra.append(
                    f"watchexec pid {wpid} belongs to supervisor {ppid}"
                    f" — stop that supervisor, not its child"
                )
        rep.add(
            "watcher",
            "!!",
            lines
            + [f"{len(live)} watchers are running, and §8 allows one"]
            + extra
            + [
                "every watcher dispatches the same event, so each save fires once"
                " more than it should, and the extra run looks like a loop"
            ],
        )
        return

    wpid, ppid = live[0]
    if state is None:
        lines.append(f"running as watchexec {wpid} under supervisor {ppid}")
        lines.append("no state file — it has recorded nothing yet")
        rep.add("watcher", "..", lines)
        return
    if ppid != pid:
        # One watcher, but not the one the state file names. The file is stale,
        # so everything below it — the watch set, the fired log — describes a
        # watcher that is gone.
        lines.append(
            f"running as watchexec {wpid} under supervisor {ppid}, but the state"
            f" file names pid {pid}"
        )
        lines.append("the recorded watch set and fired log belong to an older watcher")
        rep.add("watcher", "!!", lines)
        return
    lines.append(f"running since {state.get('started_at', '?')}, pid {pid}")
    # Two stamps, because the supervisor outlives its watchexec child. A watch
    # set younger than the process is the supervisor having picked up a new
    # project by itself, which is the thing it exists to do (S16).
    since = state.get("watching_since")
    if since and since != state.get("started_at"):
        lines.append(f"watching this set since {since}")

    # The watched PATHS are fixed when watchexec starts, because that is what it
    # is given on its command line. `devman watch` is therefore a supervisor: it
    # re-reads the registry every `POLL_SECONDS` and replaces its watchexec child
    # when the path set changes (S16). So this is no longer the normal state of a
    # machine that gained a project — it is either the few seconds before the
    # next poll, or a supervisor that is wedged.
    #
    # The check stays, and it stays "!!", because the state file is written AFTER
    # the child starts. A discrepancy that survives one poll means saves in those
    # repositories are going nowhere, and nothing else would ever say so.
    running = {w.get("project") for w in state.get("watching", [])}
    current = {e.project for e in watching}
    if running != current:
        rep.add(
            "watcher",
            "!!",
            lines
            + [
                f"it is watching {sorted(running) or 'nothing'} and the registry now"
                f" says {sorted(current) or 'nothing'}",
                f"the supervisor re-reads the registry every"
                f" {watch.POLL_SECONDS:.0f}s — run doctor again",
                "if it persists: systemctl --user restart devman-watch",
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
    check_projection(rep, reg)
    check_dag_names(rep, reg)
    check_handlers(rep, reg)
    check_cross_repo(rep, reg)
    check_fanout(rep, reg)
    check_trigger_targets(rep, reg)
    check_daemon_shell(rep, dagu_home)
    check_watcher(rep, reg)
    rep.print()

    print()
    if rep.findings:
        print(f"{rep.findings} findings.")
        return 1
    print("Nothing to report.")
    return 0
