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

Project 009 added four more, and each replaces a claim that was true when it was
written and stopped being true without anything noticing:

    registry      an entry this cannot read, NAMED rather than skipped (P2-3)
    schema        an entry written by a devman this one does not know
    dag names     now both halves of the identity, not the workflow half (P1-5)
    daemon shell  `SHELL` in the running Dagu's own environment (P1-3)

The last of those is the durable form of a whack-a-mole invariant: clearing
`SHELL` per enqueue owner is a rule somebody has to keep, and reading the
running process is a fact.

**Five of the six are file checks over the projection**, so this works with the
daemon down and says plainly which checks it could not run.

It writes nothing unless `--prune` is given (§10 check 5).
"""

from __future__ import annotations

import collections
import contextlib
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

from devman_link.state import STATE_FILE

from . import central, project, watch

# `cli` is not imported for its command-line surface. `_manifest_candidates`
# (`cli.py:289-333`) is the one place that already compares two on-disk
# `.devman/project.toml` manifests for a shared project name — built for
# `devman link status --all` and, per project 041's audit, reachable from
# nowhere else. `check_duplicate_identity` below is the second caller, so
# this reuses that comparison rather than re-deriving it here (AGENTS.md:
# re-implementing a check the repository already has is a smell). `cli`
# itself deliberately does not import `doctor` (its own comment there, on
# load cost for every OTHER command); the reverse does not reinstate that
# cost, because every module `cli` pulls in beyond what `doctor` already
# imports is cheap relative to `doctor`'s own `dagu validate` fan-out —
# measured at parity, `python -c 'import devman.doctor'` against the same
# plus `import devman.cli`, three runs each, well inside noise.
from .cli import _manifest_candidates
from .registry import Registry, RegistryError, dag_name_fault, identity_fault
from .watch import WatchState, watch_map
from .workflow import PROJECT_DIR, SELF_DIR, Workflow

# The two names of §7.1's four that are directories. Dagu creates a directory
# named literally `${NAME}` when either is unset, and reports success (§7.2).
LITERAL_DIRS = (f"${{{PROJECT_DIR}}}", f"${{{SELF_DIR}}}")

# THE STATUS LEGEND (project 041, Phase 1, Part 3).
#
#   ok   the check ran, against a real population, and found nothing wrong.
#   ..   the check could not run at all — no Dagu, no `dagu` on PATH, no
#        queue list in config.yaml. Never counted in the exit code (below):
#        "I could not look" is not a finding about the fleet.
#   !!   the check ran and found something wrong. Counted in the exit code.
#   --   EMPTY, new here. The check ran, but what it iterates — the thing it
#        exists to examine — was a population of zero. Distinct from `ok`
#        on purpose: `check_link_drift` printed `ok  no registered project
#        declares a link` for twelve days while its real input (325 live
#        symlinks) stayed nonzero, because an empty collection and a
#        populated-but-clean one render the identical sentence. A reader
#        cannot tell "zero problems" from "zero input" out of an `ok` line;
#        `--` says which one this was. See `EMPTY` below for the checks that
#        use it and why it does not count toward the exit code either.
#
# `mode` (`check_mode`) and `shadowing` (`check_drift`) print `ok` and never
# anything else, by design — they are status lines, not fault detectors (each
# function's own docstring says so). They are informational rows, not absent
# ones: read their `ok` as "here is the fact," never as "nothing is wrong,"
# because the second reading does not apply to them (project 041 Part 4).
EMPTY = "--"


@dataclass
class Report:
    sections: list[tuple[str, str, list[str]]] = field(default_factory=list)

    def add(self, name: str, status: str, lines: list[str]) -> None:
        self.sections.append((name, status, lines))

    @property
    def findings(self) -> int:
        """The exit code's input (`main()` returns `1` iff this is nonzero).

        Only `!!` counts. `..` is a check that could not run, and `EMPTY`
        (`--`) is a check that ran against zero population — neither is a
        finding ABOUT THE FLEET, which is what the `0`/`1`/`2`/`3` contract
        means by a finding (025 §10 item 11: `1` is reserved for a finding).
        A fresh machine's doctor exits `0` on `--` the same way it exits `0`
        on `..` when Dagu is not running yet — both say "there was nothing
        here to check," not "something here is wrong." Folding `EMPTY` into
        `!!` would make `devman doctor` fail on every new machine's first
        run, for a reason that goes away the moment one repository
        registers — the "a check that screams on every run is worse than the
        silence it replaced" failure this project's brief itself warns
        against, aimed at the exit code instead of the report body.
        """
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

    **A queued item can read as "0 running" for longer than an instant before
    Dagu's own scheduler dispatches it** — measured against the NixOS service
    test under a loaded host (project 038, §7): a `devman doctor` call landed
    between a batch being queued and dispatched, and reported a plane draining
    its own work as wedged, and a single half-second re-check was not always
    enough to clear it. Up to three one-second re-checks, only while a queue
    looks empty of runners, tell that dispatch delay from an actually wedged
    queue at a bounded cost of at most three seconds.
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

    for _ in range(3):
        if not any(q.get("runningCount", 0) == 0 for q in waiting):
            break
        time.sleep(1)
        try:
            data = _get(base_url, "/api/v1/queues")
            queues = data.get("queues", [])
            waiting = [q for q in queues if q.get("queuedCount")]
        except (urllib.error.URLError, OSError, ValueError):
            break
        if not waiting:
            running = sum(q.get("runningCount", 0) for q in queues)
            rep.add(
                "queues",
                "ok",
                [f"{len(queues)} queues, {running} running, none waiting"],
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
    # PROJECT 041 PART 2. Zero projected files is zero files `dagu validate`
    # can be run against, and the `ok` below would read the same whether the
    # registry is genuinely empty or merely stopped projecting (the original
    # defect's shape).
    if not files:
        rep.add("validate", EMPTY, ["no projected workflow to validate"])
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
    files = reg.projected_files()
    # PROJECT 041 PART 2. `ok` below is trivially true of zero files — a
    # workflow that does not exist names no undeclared queue either. `EMPTY`
    # instead, so "no project named one correctly" cannot be misread for
    # "nothing was projected."
    if not files:
        rep.add("queue names", EMPTY, ["no projected workflow names a queue"])
        return
    bad = []
    for proj, name, path in files:
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
    roots += [reg.root, reg.state, dagu_home, Path.cwd()]
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
    """Check 4 — an overriding file stops tracking its group (§15.6).

    **PROJECT 041 PART 4 — RELABELLED, NOT GIVEN A FAULT BRANCH.** This row
    has no `!!` by construction, and the comment at the bottom of this
    function already said why: §7.3 offers no partial override, so a
    shadowing file existing at all is the mechanism working as designed, not
    a defect. Measuring the drift percentage is still useful — it answers
    "how far has this repository's copy wandered" — but a number is not a
    verdict, and giving it a threshold that turns into `!!` would invent an
    opinion about how much drift is too much that nothing in §7.3 states.
    See the status legend above `Report`: this is an informational row, read
    for its content, not for whether it says `ok`.
    """
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
    projects = reg.projects()
    # PROJECT 041 PART 2. "every registered path is a directory" is vacuously
    # true of zero registered paths, which is exactly `check_link_drift`'s
    # regression shape: 0 of 0 reads identically to N of N clean.
    if not projects:
        rep.add("stale entries", EMPTY, ["the registry has no projects to check"])
        return
    stale = [p for p in projects.values() if not p.exists]
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
    # PROJECT 041 PART 2. Zero registered projects is zero places to look for
    # ageing run output, and the loop below would print `ok` either way — the
    # same shape `check_link_drift` had before this project, and this check
    # had ZERO test coverage at any level (RESEARCH-check-efficacy.md Part 3
    # #2), so nothing would have caught the input going silently empty.
    projects = reg.projects()
    if not projects:
        rep.add(
            "run output",
            EMPTY,
            ["no registered project to check for ageing run output"],
        )
        return
    cutoff = time.time() - days * 86400
    lines = []
    for proj in projects.values():
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
    """Does `dags/<project>.<workflow>` still point at that project's file?

    Everything else in `doctor` checks a projected file. This checks the one
    thing between a projected file and the name a trigger uses: a DAG name is
    machine-global, `<project>-<workflow>` is not injective, and the projection
    is `ln -sfn` — so a second project rendering the same flat name silently
    takes the first one's link.

    It costs one `readlink` per projected workflow and needs no running daemon.

    A missing link is a projection fault. The codec migration is complete, so
    every projected workflow must have its current link.
    """
    files = reg.projected_files()
    # PROJECT 041 PART 2. Zero projected files is zero DAG names to compare
    # against their links, and "N point at their own file" reads identically
    # for N=0 whether that is because nothing is wrong or because nothing was
    # projected.
    if not files:
        rep.add("projection", EMPTY, ["no projected workflow to check"])
        return
    bad = []
    for proj, name, _path in files:
        fault = reg.dag_link_fault(proj, name)
        if not fault:
            continue
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
    rep.add(
        "projection",
        "ok",
        [f"{len(files)} DAG names each point at their own project's file"],
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
    projects = reg.projects()
    # PROJECT 041 PART 2. Zero registered projects is zero names for the codec
    # to render, and "N render one DAG name each" reads the same for N=0
    # whether that is a clean fleet or an empty registry.
    if not projects:
        rep.add("dag names", EMPTY, ["no registered project or workflow to check"])
        return
    files = reg.projected_files()
    bad = []
    for proj in projects.values():
        fault = identity_fault("project", proj.name)
        if fault:
            meta = (proj.entry or reg.state_projects_dir / proj.name) / "metadata.json"
            bad.append(f"{proj.name}: {fault.splitlines()[0]}\n     {meta}")
    for proj, name, _path in files:
        fault = identity_fault("workflow", name) or dag_name_fault(name)
        if fault:
            bad.append(f"{proj.name}/{name}: {fault.splitlines()[0]}")
    if bad:
        rep.add("dag names", "!!", bad)
    else:
        rep.add(
            "dag names",
            "ok",
            [f"{len(files)} workflow names render one DAG name each"],
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
    files = reg.projected_files()
    # PROJECT 041 PART 2. Zero projected files is zero workflows to read a
    # `handler_on` out of, and this check had NO doctor-level test at all
    # before this project (RESEARCH-check-efficacy.md row `handlers`).
    if not files:
        rep.add("handlers", EMPTY, ["no projected workflow to check"])
        return
    lines = []
    for proj, name, path in files:
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
    files = reg.projected_files()
    # PROJECT 041 PART 2. Zero projected files is zero workflows to check for
    # a cross-repo trigger, and this check's doctor-level wiring had no test
    # exercising a firing fixture before this project (the predicate itself
    # is tested at the `Workflow` level only).
    if not files:
        rep.add("cross-repo", EMPTY, ["no projected workflow to check"])
        return
    lines = []
    parents = 0
    for proj, name, path in files:
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
    files = reg.projected_files()
    # PROJECT 041 PART 2. Zero projected files is zero workflows to check for
    # an unbounded fan-out, and this check's doctor-level wiring had no test
    # exercising a firing fixture before this project either.
    if not files:
        rep.add("fan-out", EMPTY, ["no projected workflow to check"])
        return
    lines = []
    parents = 0
    for proj, name, path in files:
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


def check_writes(rep: Report, reg: Registry) -> None:
    """A workflow that writes must say what it writes, and under which tier.

    **This check exists because §12 rule 3 stopped being a refusal.** Until 015
    the rule forbade every unattended write to tracked source, and a flat
    refusal needs no audit: nothing was permitted, so nothing could be wrong.
    The amendment replaced it with three tiers — free, on a lane, refused — and
    a tier is a claim the workflow makes about itself. An unchecked claim is
    weaker than the refusal it replaced, and this is what makes it checkable.

    **What it can decide, and it is set membership rather than a heuristic, so
    §15.7 does not reach it.** Every finding here is a comparison against a
    stated set: a tier that is not one of the three names, a declaration naming a
    workflow the project does not project, and — the one that matters — a
    `tier = "free"` claim over a path outside tier A's agent surface. That last
    one is the whole point: free-tier writes land in the working tree with
    nobody present, so a workflow claiming it for `src/**` is claiming to edit
    code unattended, which is precisely what the lane exists to prevent.

    **What it CANNOT decide, stated so nobody reads more into a clean run.** It
    cannot tell that a workflow which declares nothing writes nothing, and it
    cannot tell that a declaration is true. `doctor` reads YAML and a TOML
    table; it does not run the step. A silent finding here means every
    declaration present is well formed — not that every writer declared.
    """
    projects = reg.projects()
    # PROJECT 041 PART 2. Zero registered projects is zero declarations to
    # audit, which must not print the same "ok, unaudited" sentence a clean,
    # populated fleet with no declarations prints (`test_a_project_declaring_
    # nothing_is_reported_unaudited_not_clean` covers that still-legitimate
    # case — it registers a project first).
    if not projects:
        rep.add("writes", EMPTY, ["no registered project to check"])
        return
    tiers: collections.Counter[str] = collections.Counter()
    lines: list[str] = []
    declaring = 0
    for proj in projects.values():
        decls = proj.raw_writes() or {}
        if not decls:
            continue
        declaring += 1
        known = set(proj.workflow_names())
        for name, decl in sorted(decls.items()):
            if not isinstance(decl, dict):
                lines.append(f"{proj.name}/{name}: not a table")
                continue
            tier = decl.get("tier")
            if tier not in project.TIERS:
                lines.append(
                    f"{proj.name}/{name}: tier {tier!r} is not one of"
                    f" {', '.join(project.TIERS)}"
                )
                continue
            tiers[tier] += 1
            if known and name not in known:
                lines.append(
                    f"{proj.name}/{name}: declared, but this project projects"
                    " no such workflow"
                )
            paths = decl.get("paths") or []
            if tier == "free":
                outside = [g for g in paths if not project.free_path(g)]
                if outside:
                    lines.append(
                        f"{proj.name}/{name}: tier free over {', '.join(outside)}"
                        " — outside agent surface"
                    )
    if lines:
        lines.append(
            "tier free is agent surface only ("
            + ", ".join(project.FREE_PREFIXES)
            + "); an edit to existing tracked source is tier lane, and tier"
            " insitu is format's bounded exception — its own group, a content"
            " hash, a fixpoint (§12 rule 3)"
        )
        rep.add("writes", "!!", lines)
    else:
        spread = ", ".join(f"{n} {t}" for t, n in sorted(tiers.items())) or "none"
        rep.add(
            "writes",
            "ok",
            [
                f"{declaring} projects declare output ownership — {spread}",
                "a workflow that declares none is unaudited, not proven silent",
            ],
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
    marker = f"--project-origin={reg.state}".encode()
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


def check_faults(rep: Report, reg: Registry) -> None:
    """Registry entries that cannot be read, named rather than skipped (P2-3).

    **The silence this replaces was worse diagnostically than a crash.** An
    entry with invalid JSON was passed over as if the project did not exist,
    while its `dags/` links and its schedules stayed live — so a scheduled
    workflow kept firing and every reader of the registry, this command
    included, was blind to the project it belonged to.

    Each fault names its `metadata.json`, because the repair is either one shell
    entry or `devman doctor --prune`, and the developer has to know which
    repository to enter.
    """
    faults = reg.faults()
    if not faults:
        rep.add("registry", "ok", ["every entry under projects/ reads"])
        return
    lines = []
    for fault in faults:
        lines.append(f"{fault.name}: {fault.why}")
        lines.append(f"  {fault.path}")
    lines.append(
        "enter that repository's shell to rewrite the entry, or"
        " `devman doctor --prune` if the repository is gone"
    )
    rep.add("registry", "!!", lines)


def check_schema(rep: Report, reg: Registry) -> None:
    """A registry entry written by a devman this one does not understand.

    The schema is a version number with soft degradation, and that only works
    if something says when it degraded. Schema 4 changed what `plan` MEANS
    rather than adding a field (009 stage 3), which is exactly the shape of
    change a reader cannot detect by looking at the fields — an older `doctor`
    reading a schema 4 entry would compare a plan path against a script path
    and report a mismatch it cannot explain.

    So this reports the number rather than guessing at the content. §15.7 is
    untouched: it reads one integer the entry states about itself.
    """
    known = project.SCHEMA
    projects = reg.projects()
    # PROJECT 041 PART 2. "every entry is schema N or older" is vacuously true
    # of zero entries, the same shape as every other FRAGILE row this project
    # found.
    if not projects:
        rep.add("schema", EMPTY, ["no registered project to check"])
        return
    ahead = [
        f"{proj.name}: schema {proj.schema}, and this devman knows {known}"
        for proj in projects.values()
        if proj.schema > known
    ]
    if ahead:
        rep.add(
            "schema",
            "!!",
            ahead
            + [
                "a newer devman wrote these entries — the checks above may be"
                " reading fields that have changed meaning",
                "upgrade this machine's devman, or re-enter those shells with"
                " the older plane",
            ],
        )
    else:
        rep.add("schema", "ok", [f"every entry is schema {known} or older"])


def check_mode(rep: Report, reg: Registry) -> None:
    """Which projection is authoritative for this registry root (§7, project 038).

    Vendomat's plane always writes `generation.json` at the active root
    (`GenerationStore.build`, vendomat); the compatibility shell-entry
    projection never does. Its presence is the one fact the registry states on
    disk, so this reads it rather than inferring the mode from which binary
    happens to be first on PATH.

    **PROJECT 041 PART 4 — RELABELLED, NOT GIVEN A FAULT BRANCH.** This row
    has no `!!` by construction: "plane" and "compatibility" are two names for
    one fact, neither wrong. Inventing a failing case (`RESEARCH-check-
    efficacy.md` floated "compatibility while a generation.json sits unused
    nearby," which is contradictory on inspection — `generation.json`
    present IS the plane-mode test above) would manufacture a predicate this
    check was never meant to have. The honest fix is the one the research
    recommended and the legend above states: this is a status line, read as
    "here is the fact," not a health check read as "nothing is wrong."
    """
    mode = "plane" if (reg.root / "generation.json").is_file() else "compatibility"
    rep.add("mode", "ok", [mode])


def check_generation(rep: Report, reg: Registry) -> None:
    """Check generation identities when the registry is a plane projection."""

    records: list[Path] = []
    for project_entry in reg.projects().values():
        active = reg.projects_dir / project_entry.name / "projection.json"
        state = project_entry.entry / "projection.json" if project_entry.entry else None
        if active.is_file():
            records.append(active)
        elif state is not None and state.is_file():
            records.append(state)
    if not records:
        return
    generation_path = reg.root / "generation.json"
    try:
        generation = json.loads(generation_path.read_text())
        number = generation["generation"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        rep.add("generation", "!!", [f"cannot read {generation_path}: {exc}"])
        return

    stale: list[str] = []
    for path in records:
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            stale.append(f"{path.parent.name}: cannot read {path}: {exc}")
            continue
        if record.get("plane_generation") != number:
            stale.append(
                f"{record.get('project', path.parent.name)}: projection generation "
                f"{record.get('plane_generation', '?')} != active {number}"
            )
    if stale:
        rep.add(
            "generation", "!!", stale + ["render the project through the active plane"]
        )
    else:
        rep.add(
            "generation",
            "ok",
            [f"{len(records)} projections match generation {number}"],
        )


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


# ---------------------------------------------------------------------------
# what the plane's only verb pays for (014)

# devenv's shell-script cache. `write_executable_script` (devenv 2.1.2,
# `devenv/src/devenv/mod.rs:2163`) writes `<dotfile>/shell-<hash>.sh` for every
# distinct shell environment it ever realises, and NOTHING DELETES THEM.
# `devenv gc` does not: all 85 lines of `devenv/src/devenv/gc.rs` collect Nix
# store paths and dangling GC-root symlinks, and never look in the dotfile.
SHELL_CACHE_GLOB = "shell-*.sh"

# 50 MB of `.devenv` inside a `path:` input. Not a taste — a measurement. 014
# timed the verb against the same tree at three sizes: 29 MB is 287 ms, 117 MB
# is 802 ms, 298 MB is 1448 ms. About 4.3 ms per megabyte, on every invocation,
# in every repository that takes it. 50 MB is therefore ~215 ms, already more
# than devenv's ENTIRE startup floor of 146 ms measured with no `path:` input.
PATH_INPUT_DOTFILE_MB = 50


def _path_inputs(root: Path) -> list[Path]:
    """Every local `path:` input `<root>/devenv.yaml` names, resolved.

    Read rather than parsed for meaning: the file is the repository's, and this
    only needs the targets. Relative forms (`path:./modules`, `path:../vendomat`)
    resolve against the repository that names them.
    """
    try:
        raw = yaml.safe_load((root / "devenv.yaml").read_text()) or {}
    except (OSError, yaml.YAMLError):
        return []
    out = []
    for spec in (raw.get("inputs") or {}).values():
        url = (spec or {}).get("url") if isinstance(spec, dict) else None
        if isinstance(url, str) and url.startswith("path:"):
            out.append(Path(os.path.normpath(root / url[len("path:") :])))
    return out


def _dotfile(target: Path) -> tuple[int, int]:
    """`(bytes, shell-script count)` of `<target>/.devenv`. Missing is `(0, 0)`.

    The whole dotfile, because the whole dotfile is what Nix copies. The shell
    scripts are counted separately only to say how much of it is the part that
    grows without bound.
    """
    total = scripts = 0
    dotfile = target / ".devenv"
    for parent, _, files in os.walk(dotfile):
        for name in files:
            if (
                parent == str(dotfile)
                and name.startswith("shell-")
                and name.endswith(".sh")
            ):
                scripts += 1
            with contextlib.suppress(OSError):
                total += os.lstat(os.path.join(parent, name)).st_size
    return total, scripts


# ---------------------------------------------------------------------------
# what a repository's local libraries actually resolve to (015/016)


def _local_git_inputs(root: Path) -> list[tuple[Path, str | None]]:
    """Every `git+file:` lock node this repository holds, as `(source, rev)`.

    Reads BOTH lockfiles because the two behave differently and that difference
    is the whole finding: `devenv.lock` records a local git input as `{type,
    url}` with NO `rev`, while `flake.lock` records a full pin. Measured across
    this machine: 91 of 93 local inputs carry no rev, and 100 % of remote inputs
    carry one.
    """
    out: list[tuple[Path, str | None]] = []
    for name in ("devenv.lock", "flake.lock"):
        try:
            lock = json.loads((root / name).read_text())
        except (OSError, ValueError):
            continue
        for node in (lock.get("nodes") or {}).values():
            locked = (node or {}).get("locked") or {}
            url = locked.get("url", "")
            if locked.get("type") != "git" or not url.startswith("file://"):
                continue
            src = Path(url[len("file://") :].split("?")[0].rstrip("/"))
            out.append((src, locked.get("rev")))
    return out


def _source_state(src: Path) -> tuple[str | None, bool]:
    """`(head, dirty)` for a local source repository. `(None, False)` if absent."""
    if not (src / ".git").exists():
        return None, False

    def git(*args: str) -> str | None:
        try:
            r = subprocess.run(
                ["git", "-C", str(src), *args],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout if r.returncode == 0 else None

    head = git("rev-parse", "HEAD")
    status = git("status", "--porcelain")
    return (head.strip() if head else None), bool(status and status.strip())


def check_local_sources(rep: Report, reg: Registry) -> None:
    """What a repository's local libraries resolve to, which is not what it says.

    **THE FINDING THIS EXISTS TO MAKE IS THE OPPOSITE OF THE ONE EXPECTED.** A
    `git+file:` input looks pinned, and 016 set out to build a workflow that
    would update the stale ones. Measured: `devenv.lock` records a local git
    input as `{type, url}` with **no `rev` and no `narHash`**, so devenv's
    generated resolver hands the bare attrset to `builtins.fetchTree`, which
    resolves it LIVE. 91 of 93 local inputs on this machine are that shape, and
    an update workflow would therefore have produced 52 empty branches — §12
    rule 4, and the reason no such workflow was built.

    What is left is the exposure underneath it. An unpinned input follows its
    source's working tree, so **a source with uncommitted changes is consumed as
    that working tree, not as any commit**: `fetchTree` returns `rev: NONE` and
    a `-dirty` marker. Measured when this was written: `shellij` had 15
    uncommitted files including `devenv.nix`, and 51 of the 54 registered
    repositories consumed it. Nothing said so.

    **IT IS CHEAP BECAUSE IT READS SOURCES, NOT CONSUMERS.** The consumer count
    is 54 and the distinct-source count is 8, so this forks two `git` calls per
    SOURCE and none per consumer — the arithmetic that makes it a check rather
    than a fan-out (§12 rules 8 and 9).

    **WHAT IT CANNOT SEE.** It reads lockfiles, not evaluations. A repository
    that names an input it never uses is counted, and one that reaches a library
    some other way is not.
    """
    projects = reg.projects()
    # PROJECT 041 PART 2. Zero registered projects is zero sources to check
    # for a dirty working tree or a stale pin — "none dirty and no pin behind
    # its source" reads the same for 0 consumers as for a clean fleet of 54.
    if not projects:
        rep.add("local sources", EMPTY, ["no registered project to check"])
        return
    consumers: dict[Path, set[str]] = {}
    pinned: list[tuple[str, Path, str]] = []
    for proj in projects.values():
        root = Path(proj.path)
        for src, rev in _local_git_inputs(root):
            consumers.setdefault(src, set()).add(proj.name)
            if rev:
                pinned.append((proj.name, src, rev))

    state = {src: _source_state(src) for src in consumers}

    lines: list[str] = []
    for src, names in sorted(consumers.items(), key=lambda kv: -len(kv[1])):
        head, dirty = state[src]
        if head is None:
            lines.append(
                f"{src.name}: consumed by {len(names)}, and is not a git repository"
            )
        elif dirty:
            lines.append(
                f"{src.name}: **uncommitted changes**, consumed unpinned by"
                f" {len(names)} project(s) — they resolve to this working tree,"
                " not to a commit"
            )
    for name, src, rev in sorted(pinned):
        head, _ = state.get(src, (None, False))
        if head and head != rev:
            lines.append(
                f"{name}: pins {src.name} at {rev[:8]}, and its HEAD is {head[:8]}"
            )

    if lines:
        lines.append(
            "an unpinned `git+file:` input has no rev in devenv.lock and is"
            " resolved live by fetchTree — commit the source, or pin it in"
            " flake.nix"
        )
        rep.add("local sources", "!!", lines)
    else:
        rep.add(
            "local sources",
            "ok",
            [
                f"{len(consumers)} local libraries feed {sum(len(v) for v in consumers.values())}"
                " inputs, none dirty and no pin behind its source"
            ],
        )


def check_path_inputs(rep: Report, reg: Registry) -> None:
    """A `path:` input copies everything git ignores, `.devenv` included (014).

    **This is why the plane's only verb costs what it costs.** A warm
    `devenv tasks run` here was 1562 ms at n=20, of which the span
    `Validating lock` is 94 %. Nix evaluation is 1.8 ms: the eval cache is not
    the problem and never was.

    `validate_lock_file` (`devenv-nix-backend/src/lib.rs:363`) re-resolves every
    input on every invocation. A `path:` node carries no revision and no
    narHash, so Nix must copy the directory and hash it to learn what it is —
    **and `path:` does not honour `.gitignore`.** Measured: the same tree with
    `.git` removed costs the same, and `/nix/store` held copies of a live
    repository including 2179 of its `shell-*.sh` files.

    **`git+file:` is the fix, and it is one line.** It resolves through
    `git ls-files`, so the dotfile and `.git` are excluded — and it still uses
    the WORKING TREE, not `HEAD`: 014 verified the store copy carries
    uncommitted edits to tracked files and staged-but-uncommitted additions.
    Measured on the same input, n=20: `path:` 802 ms, `git+file:` **149 ms**,
    which is devenv's bare floor. The one behaviour it changes is that a brand
    new file is invisible until `git add` — a loud failure, not a silent one.

    Sweeping `shell-*.sh` is the stopgap and has a floor: a virtualenv lives in
    the dotfile too, and 014 measured 1562 -> 913 ms from sweeping alone against
    913 -> 149 ms from changing the input.

    This reports and never deletes. Law 6 says only the projection and
    `--prune` write.

    Not a heuristic. It reads `url: path:…` out of each repository's own
    `devenv.yaml` and `stat`s what is there.
    """
    projects = reg.projects()
    # PROJECT 041 PART 2. Zero registered projects is zero `devenv.yaml`s to
    # read a `path:` input out of — "0 directories are path: inputs" reads
    # the same whether the fleet is clean or the registry is empty.
    if not projects:
        rep.add("path inputs", EMPTY, ["no registered project to check"])
        return
    takers: dict[Path, set[str]] = {}
    for name, proj in sorted(projects.items()):
        for target in _path_inputs(proj.path):
            takers.setdefault(target, set()).add(name)

    lines = []
    for target in sorted(takers):
        size, scripts = _dotfile(target)
        megabytes = size / 1_000_000
        if megabytes < PATH_INPUT_DOTFILE_MB:
            continue
        who = sorted(takers[target])
        lines.append(
            f"{target}: .devenv = {megabytes:.0f} MB ({scripts} {SHELL_CACHE_GLOB}),"
            f" copied into every run of {len(who)} projects"
        )
        remedy = (
            "url: git+file://<path> excludes it"
            if (target / ".git").exists()
            else "not a git worktree — delete shell-*.sh"
        )
        lines.append(
            f"    ~{megabytes * 4.3:.0f} ms on every devenv invocation in"
            f" {', '.join(who[:6])}{' …' if len(who) > 6 else ''} — {remedy}"
        )
    if lines:
        lines.append(
            "devenv gc collects none of this; `path:` ignores .gitignore and"
            " `git+file:` does not (014)"
        )
        rep.add("path inputs", "!!", lines)
    else:
        rep.add(
            "path inputs",
            "ok",
            [
                f"{len(takers)} directories are path: inputs, none carrying"
                f" a .devenv over {PATH_INPUT_DOTFILE_MB} MB"
            ],
        )


def check_duplicate_identity(
    rep: Report, *, fleet: Path = central.DEFAULT_FLEET
) -> None:
    """Two checkouts cannot share a project name, and nothing automatic asks.

    **This is the detection half of O9; the other half is a refusal, and a**
    **refusal is not this.** Project 041 found the duplicate-registration
    refusal LOST (`PRESERVED-ITEMS-AUDIT.md` item 2): no code path compares a
    project name's already-registered root against a new checkout's root
    before a registration writes. Restoring that refusal — elsewhere — stops
    a THIRD checkout from joining a name already in use. It does nothing
    about a collision already sitting on disk, and 025 §6.4 is the sharpest
    statement of why that gap cannot close by hand: two `dags/` entries
    resolving to one name make `dagu ls` print the name once, exit 0, no
    warning, and manual verification cannot see the file it did not pick.
    The only existing detector was `devman link status --all
    --projects-root <dir>` (`cli.py:286-333`) — manual, opt-in, and reachable
    from nowhere else in the codebase (same audit). This check is what makes
    it run on its own, every night, with the rest of the fleet.

    **Checked it is not already covered.** `check_dag_names` reads one
    registry entry's own name for grammar; `check_projection` reads one
    entry's own `dags/` link against its own file. Neither reads a SECOND
    checkout, so neither can see two of them agreeing on a name.

    **What it reads, and why not the registry.** 041's D1 is that the
    registry is derived, and trusting it for a link check already failed
    silently once: `check_link_drift` read a registry field that had emptied
    and reported `ok` for twelve days (this file, above). A name collision
    is exactly the shape where the registry is least trustworthy — the
    registry entry is one slot, so the second checkout's write either lands
    beside the first (two entries, one name) or replaces it outright
    depending on which path wrote it, and either way reading the registry
    risks seeing only the survivor. What is NOT derived is each checkout's
    own `.devman/project.toml`: the file a repository states its identity
    in, on its own disk, independent of whatever the registry currently
    holds. `cli._manifest_candidates` already walks that source and already
    reports a `project` field two children agree on — built for `devman link
    status --all`, reused here rather than re-derived (see the import
    comment above).

    **Set membership, not a heuristic (§15.7).** The only question asked is
    whether two direct children of `fleet` hold a `project.toml` naming the
    same project. Both sides are facts a checkout states about itself; there
    is no guess about which one is right.

    **Cost.** One `iterdir()` of `fleet` and one manifest read per direct
    child that has one — no subprocess, no Dagu call. `check_link_drift` and
    `check_ledger_stale` already default to this same fleet root for the
    identical reason: cheap enough for `plane-report` to run nightly for the
    whole machine without a second scheduled report.
    """
    try:
        candidates, errors = _manifest_candidates([str(fleet)])
    except RegistryError:
        # PROJECT 041 PART 2's shape: an absent or manifest-free fleet root is
        # zero checkouts to compare, not zero collisions found among some.
        rep.add(
            "duplicate name",
            EMPTY,
            [f"no checkout with a .devman/project.toml under {fleet}"],
        )
        return
    dupes = [
        (path, why) for path, why in errors if "duplicate manifest identity" in why
    ]
    if dupes:
        lines = [f"{path}: {why.splitlines()[0]}" for path, why in dupes]
        lines.append(
            "two checkouts under the fleet root declare one devman.project —"
            " the registry, dags/ and the scheduler each resolve it to"
            " whichever wrote last (025 §6.4); rename one and re-enter its"
            " shell, or run `devman link status --all --projects-root"
            f" {fleet}` for the full picture"
        )
        rep.add("duplicate name", "!!", lines)
        return
    rep.add(
        "duplicate name",
        "ok",
        [f"{len(candidates)} checkouts under {fleet}, no two declare one project"],
    )


def check_link_drift(
    rep: Report,
    *,
    fleet: Path = central.DEFAULT_FLEET,
    central_root: Path = central.DEFAULT_CENTRAL,
) -> None:
    """Report drift in the live symlinks that reach into the central overlay.

    **The state names are the reconciler's contract, so doctor and**
    **`central-verify` cannot disagree about what drift means.** This stays
    a filesystem read, not a subprocess per project, for the same reason the
    prior version gave: cheap enough for `plane-report` to run nightly for
    the whole machine without a second scheduled report (CONCEPT.md §4.5).

    **Regression record, so the next person does not re-learn it.** Until
    commit `37050e9` (2026-09-19, "link-only compatibility shim") deleted
    `modules/devenv.nix`, this check read `proj.links`, a projection that
    module wrote into the registry — project 036's verification record,
    2026-09-11, shows it live: *two* real link-drift findings. The deleted
    commit's message does not mention `doctor`'s dependency on that output.
    After it, 0 of 48 registry entries ever declared a link again, the loop
    body never ran, and `doctor` reported `ok  no registered project
    declares a link` — a check that could not fail, not a clean plane
    (project 041, CONCEPT.md §1.1).

    **The fix changes the input, not the question.** This now reads
    `devman.central.reverse_index()` — every live symlink in the fleet whose
    raw target lands inside the overlay, found by walking the filesystem
    rather than by trusting a record of it (DECISIONS.md D1: the registry is
    empty and the link-state ledger is stale by 34 projects). It asserts C2
    (the target exists) and, new here, **C3** (the target is reachable from
    trunk, not merely present in an unlanded lane) — C3 is the condition
    behind the 2026-10-01 incidents project 041 was opened to answer, and it
    is exactly the branch that could not fire before: `!!` is reachable now.
    """
    views = central.reverse_index(fleet=fleet, central=central_root)
    trunk = central.trunk_name(central_root)
    missing = central.check_c2_missing(views)
    lane_only = central.check_c3_lane_only(views, central_root, trunk)

    findings = [central.format_view(v) for v in missing]
    findings += [central.format_view(v, trunk=trunk) for v in lane_only]

    if findings:
        rep.add("link drift", "!!", findings)
    elif views:
        rep.add(
            "link drift",
            "ok",
            [f"{len(views)} live views into the overlay are present and on {trunk}"],
        )
    else:
        # Zero views is EMPTY, not `ok`. A machine that has linked nothing is
        # legitimate, and so is a broken walk; `ok` cannot tell them apart, and
        # "ok with a zero population" is the exact sentence this check reported
        # for twelve days while blind (CONCEPT.md §1.1). The reverse index is a
        # filesystem read rather than a projection, so this is far less likely
        # than it was — but "less likely" is not what the rule says.
        rep.add("link drift", EMPTY, ["no live view into the overlay was found"])

    # C5 gets its own row rather than folding into "link drift". It is not
    # drift: nothing moved, and no lane operation created it or will close it.
    # A hollow target is a standing gap — an onboarding that never finished —
    # and naming it under a check called "drift" would misfile the cause for
    # whoever reads the report (central.check_c5_empty_surface).
    hollow = central.check_c5_empty_surface(views, central_root)
    if hollow:
        rep.add(
            "empty surface",
            "!!",
            [central.format_empty_view(v, central=central_root) for v in hollow],
        )
    elif views:
        rep.add("empty surface", "ok", [f"{len(views)} live view targets hold content"])
    else:
        rep.add("empty surface", EMPTY, ["no live view into the overlay was found"])


def _read_ledger_raw(central_root: Path) -> str | None:
    """The ledger's raw text, or `None` when there is no file yet.

    A fresh machine has made no link and has no ledger (project 033). That
    is not a fault, so it reads the same as a clean check, never as `!!`.
    """
    try:
        return (central_root / STATE_FILE).read_text()
    except FileNotFoundError:
        return None


def _write_ledger(central_root: Path, state: dict, *, trailing_newline: bool) -> None:
    """Rewrite the ledger atomically: a temp file in the same directory,
    then `os.replace`. A partial write of this file is worse than a stale
    one — it is the `{canonical, hash}` baseline
    `devman_link.excludes.ensure_local_gitignore` reads to refuse a
    two-sided edit (033; DECISIONS.md D15), and a reader must never see half
    of it. Mirrors `devman_link.state.write_state`'s own pattern, except the
    trailing newline is read from the file as found rather than assumed —
    "preserve the JSON shape exactly" (project 041 open question O5) means
    matching what is on disk, not what the sibling writer happens to do.
    """
    text = json.dumps(state, indent=2, sort_keys=True)
    if trailing_newline:
        text += "\n"
    temp = central_root / f".{STATE_FILE}.doctor-prune.new"
    temp.write_text(text)
    os.replace(temp, central_root / STATE_FILE)


def check_ledger_stale(
    rep: Report,
    *,
    prune: bool,
    fleet: Path = central.DEFAULT_FLEET,
    central_root: Path = central.DEFAULT_CENTRAL,
) -> None:
    """The reconciler's ledger accumulates an entry for every project it has
    ever linked and nothing ever removes one (CONCEPT.md §2.4, open question
    O5). `check_stale` above prunes the *registry* when a repository is
    gone; `Registry.unproject` (`registry.py:587-607`) does not touch
    `.devman-link-state.json`, so the two have drifted apart for as long as
    the registry has existed without the ledger following it.

    **Liveness is the repository directory on disk, and nothing else — never
    the registry.** Project 041 measured the registry at 48 entries against
    66 repositories that carry a live symlink into the overlay (CONCEPT.md
    §2.4, §3.3). Gating this prune on the registry would delete the
    two-sided-edit baseline of those 18 *live* but unregistered repositories
    — AGENTS.md property 6 names the registry as derived, not authoritative,
    and `devman.central.reverse_index` (DECISIONS.md D1) made the identical
    choice for the identical reason: the registry and the ledger can both go
    stale, and the filesystem cannot.

    **The prune is safe by construction, not by care.** An entry is removed
    only when `fleet / <project>` is not a directory. A repository that does
    not exist on disk cannot have a two-sided edit between its working copy
    and the central `.local.gitignore` — there is no working copy to edit —
    so removing its baseline cannot weaken any refusal
    `devman_link.excludes.ensure_local_gitignore` makes for a live project
    (033; DECISIONS.md D15, which this check is built to leave intact for
    every surviving entry).

    **The total entry and project count is reported even when nothing is
    stale**, per AGENTS.md property 4: a check that only speaks when it
    finds something cannot show a count disappearing between two runs. The
    ledger shrank from 456 entries / 84 projects to 450 / 82 inside three
    hours on 2026-10-01, and nothing recorded the write (CONCEPT.md §2.4,
    §12.2). A count in a nightly report is what makes the next shrink loud.

    **A malformed ledger is reported and left alone, never overwritten.** A
    file that does not parse, or parses to something other than a JSON
    object, is the one state this check cannot safely act on — rewriting it
    would guess at content that might still hold a real baseline, and a
    silent "nothing to report" would hide the one failure mode worse than
    staleness. It reports `!!` and prunes nothing, with or without `--prune`.
    """
    raw = _read_ledger_raw(central_root)
    if raw is None:
        rep.add("ledger", "ok", [f"no {STATE_FILE} — a fresh machine has none"])
        return

    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        rep.add(
            "ledger",
            "!!",
            [
                f"{STATE_FILE} is not valid JSON ({exc}) — refusing to read or"
                " prune it; the two-sided-edit baseline may still be inside it,"
                " fix the file by hand"
            ],
        )
        return
    if not isinstance(state, dict):
        rep.add(
            "ledger",
            "!!",
            [
                f"{STATE_FILE} does not hold a JSON object — refusing to read or prune it"
            ],
        )
        return

    by_project: dict[str, list[str]] = collections.defaultdict(list)
    for key in state:
        # Key shape is "<project>:<view>" (`devman_link.paths.ResolvedLink.key`).
        project_name, _, _ = str(key).partition(":")
        by_project[project_name].append(key)

    dead = {
        name: keys for name, keys in by_project.items() if not (fleet / name).is_dir()
    }
    header = f"{len(state)} entries, {len(by_project)} projects"

    if not dead:
        rep.add(
            "ledger", "ok", [header, "every ledger project has a repository directory"]
        )
        return

    # One line per project, not per entry (015: "54 identical reports is one
    # report nobody opens"). 16 projects is a readable finding; the 76
    # entries behind them are not.
    lines = [header]
    for name in sorted(dead):
        keys = dead[name]
        if prune:
            for key in keys:
                del state[key]
            lines.append(
                f"{name}: repository directory gone — pruned {len(keys)} entries"
            )
        else:
            lines.append(f"{name}: repository directory gone — {len(keys)} entries")
    if prune:
        _write_ledger(central_root, state, trailing_newline=raw.endswith("\n"))
    else:
        lines.append("run `devman doctor --prune` to remove them")
    rep.add("ledger", "!!", lines)


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
        # PROJECT 041 PART 2 — THE CLOSEST LIVING RELATIVE OF THE ORIGINAL
        # DEFECT. `watch_map(reg)` reads `proj.triggers`, a registry-projected
        # field, exactly as `check_link_drift` read `proj.links` before this
        # project. `checked == 0` means either no project declares a trigger
        # (a plain fact) or the projection stopped writing `triggers` the way
        # it stopped writing `links` — this check cannot tell those apart, so
        # it must not say `ok` for either. `EMPTY` instead of a silent "ok"
        # with a zero count (the exact shape the regression this project
        # fixes had).
        rep.add("trigger target", EMPTY, ["no registered project declares a trigger"])


def check_reload(rep: Report, reg: Registry) -> None:
    """Whether the active-generation reload adapter is mid-flight or stuck (§5, project 038).

    `reload.pending` and `reload.blocked` are the reload service's own markers,
    written under the stable state root so they outlive whichever generation is
    active. Their absence is the normal state — nothing is reloading, and
    `devman run` enqueues freely.
    """
    pending = reg.state / "reload.pending"
    blocked = reg.state / "reload.blocked"
    if blocked.is_file():
        blocked_at = blocked.read_text().strip()
        rep.add(
            "reload",
            "!!",
            [
                f"blocked since {blocked_at} — an active run outlasted the max wait",
                "Dagu was not restarted; the previous generation is still serving runs",
                "operator action: once the run finishes, run"
                " `systemctl --user restart devman-dagu-reload.service`",
            ],
        )
        if pending.is_file():
            rep.sections[-1][2].append(
                f"pending since {pending.read_text().strip()} — the reload gate remains open"
            )
        return
    if pending.is_file():
        rep.add(
            "reload",
            "..",
            [
                f"pending since {pending.read_text().strip()} — waiting for active runs to finish"
            ],
        )
        return
    rep.add("reload", "ok", ["no reload in progress"])


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
        # The ignore list is printed beside the globs it narrows, because "why
        # does saving this file do nothing" is answered by the two together and
        # by neither alone (009 P3-3).
        narrowed = f"  except {', '.join(entry.ignore)}" if entry.ignore else ""
        lines.append(
            f"{entry.project}: {', '.join(entry.globs)} -> {entry.workflow}"
            f"{narrowed}  [{entry.group}]"
        )
    # A stale entry that declares triggers is dropped from the watch set, or
    # watchexec would refuse to start and take reactivity down for every
    # repository (S2). The stale-entry check above says the path is gone; this
    # says what it costs, because the two facts were reported side by side and
    # unconnected the first time this happened.
    # A faulted entry has no path to watch, so the watcher skipped it. Reported
    # here as well as under `registry`, because "my saves stopped firing" is the
    # symptom a developer actually notices (009 P2-3).
    for skip in (state or {}).get("skipped", []):
        lines.append(
            f"{skip.get('project')}: NOT watched — its registry entry is"
            f" unreadable ({skip.get('why')})"
        )
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


def _print_header(reg: Registry, dagu_home: Path) -> None:
    """Name the project source that supplied the reported project count."""
    projects = reg.projects()
    print(
        f"devman doctor — {len(projects)} projects, {len(reg.projected_files())} workflows"
    )
    print(f"    registry   {reg.root}")
    print(f"    state      {reg.state}")
    print(f"    projects   {reg.project_source or reg.state_projects_dir}")
    print(f"    dagu home  {dagu_home}")
    print()


def main(args, reg: Registry) -> int:
    dagu_home = Path(args.dagu_home).expanduser()
    cfg = _config(dagu_home)
    host = cfg.get("host", "127.0.0.1")
    port = cfg.get("port", 8080)
    base_url = f"http://{host}:{port}"

    plane = (reg.root / "generation.json").is_file()
    if plane:
        # The generation is the complete plane. The stable state root is
        # regenerated by shell entry and may contain only a partial rollout.
        reg = reg.for_active_generation()

    _print_header(reg, dagu_home)

    rep = Report()
    check_mode(rep, reg)
    if check_plane(rep, base_url):
        check_queues(rep, base_url)
    check_faults(rep, reg)
    check_load(rep, reg, dagu_home)
    check_queue_names(rep, reg, dagu_home)
    check_literal(rep, reg, dagu_home)
    check_drift(rep, reg)
    check_stale(rep, reg, args.prune)
    check_ageing(rep, reg, dagu_home)
    check_projection(rep, reg)
    check_dag_names(rep, reg)
    check_schema(rep, reg)
    check_generation(rep, reg)
    check_handlers(rep, reg)
    check_cross_repo(rep, reg)
    check_fanout(rep, reg)
    check_writes(rep, reg)
    check_trigger_targets(rep, reg)
    check_duplicate_identity(rep)
    check_link_drift(rep)
    check_ledger_stale(rep, prune=args.prune)
    check_local_sources(rep, reg)
    check_path_inputs(rep, reg)
    check_daemon_shell(rep, dagu_home)
    check_reload(rep, reg)
    check_watcher(rep, reg)
    rep.print()

    print()
    if rep.findings:
        print(f"{rep.findings} findings.")
        return 1
    print("Nothing to report.")
    return 0
