"""The decisions `doctor` makes itself.

Most of `doctor` is a loop over `Workflow` and `Registry`, and those are tested
where they live. What is here is the rest: the checks that read the machine's own
config, the bounded walk, and the report's own arithmetic.

**Nothing here mocks Dagu's HTTP API.** `check_plane` and `check_queues` read
what a running Dagu reports about itself (E5), and a stub of that API would test
the stub. The `!!` wedged-queue path belongs to `nix/tests/dagu-service.nix`,
which runs a real one. Their down-path (`..`) is tested below by pointing at a
port nothing listens on — a real connection refusal, not a stub of a response,
so it stays within this file's own rule.

**Project 041 Phase 2 — the enforceable gap-closing pass.** `FIRING_TESTS`
near the foot of this file is the registry every check `doctor.main()` calls
must appear in, each pointing at a test that makes that check report a
non-`ok` status. The check list itself is read out of `main()`'s own source
(`_checks_in_main()`), never hand-copied, so a new check missing its entry
here fails the suite by construction rather than by someone remembering.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from helpers import ORDINARY

from devman import doctor, watch
from devman.registry import Registry
from devman.workflow import PROJECT_DIR

pytestmark = pytest.mark.unit
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs a git binary")

needs_dagu = pytest.mark.skipif(
    shutil.which("dagu") is None, reason="needs a dagu binary"
)
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs a git binary")


def dagu_home(tmp_path, *, queues=("light", "heavy"), retention=7):
    """The two files the machine module writes, and `doctor` reads."""
    home = tmp_path / "dagu"
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        yaml.safe_dump(
            {"queues": {"enabled": True, "config": [{"name": q} for q in queues]}}
        )
    )
    (home / "base.yaml").write_text(
        yaml.safe_dump({"queue": "light", "hist_retention_days": retention})
    )
    return home


# ---------------------------------------------------------------------------
# what Dagu reports about itself (E5) — the down-path, demonstrated without
# mocking Dagu's API: a port nothing listens on gives `check_plane` and
# `check_queues` the identical `urllib` failure a stopped Dagu would. Neither
# counts toward the exit code (`Report.findings` only counts `!!`), but both
# are LIVE in RESEARCH-check-efficacy.md's terms — they report loudly (`..`),
# not `ok` — and neither had a test anywhere before this project.


def test_plane_reports_unreachable_as_a_loud_non_finding():
    rep = doctor.Report()

    reached = doctor.check_plane(rep, "http://127.0.0.1:1")

    name, status, lines = rep.sections[0]
    assert reached is False
    assert (name, status) == ("plane", "..")
    assert "no answer from" in lines[0]


def test_queues_reports_unreachable_as_a_loud_non_finding():
    rep = doctor.Report()

    doctor.check_queues(rep, "http://127.0.0.1:1")

    name, status, lines = rep.sections[0]
    assert (name, status) == ("queues", "..")


# ---------------------------------------------------------------------------
# the report's own arithmetic


def test_only_findings_are_counted():
    """`..` is a check that could not run, and `ok` is a check that ran. Neither
    is a fault, and the exit code is the finding count."""
    rep = doctor.Report()
    rep.add("a", "ok", ["fine", "also fine"])
    rep.add("b", "..", ["could not run"])
    rep.add("c", "!!", ["one", "two"])
    assert rep.findings == 2


def test_empty_population_does_not_count_toward_the_exit_code():
    """PROJECT 041 PART 3's exit-code decision. `EMPTY` (`--`) is a check that
    ran against zero population — not a finding about the fleet, the same way
    `..` is not. A fresh machine's first `devman doctor` must exit `0`, not
    `1`, or every new machine would fail its own first health check for a
    reason that goes away the moment one repository registers."""
    rep = doctor.Report()
    rep.add("a", "ok", ["fine"])
    rep.add("b", doctor.EMPTY, ["nothing registered to check"])
    rep.add("c", "!!", ["one real finding"])
    assert rep.findings == 1


def test_a_check_with_no_lines_still_prints(capsys):
    rep = doctor.Report()
    rep.add("plane", "ok", [])
    rep.print()
    assert capsys.readouterr().out.strip() == "ok  plane"


def _git_repo(root: Path, trunk: str = "main") -> None:
    """A real git repository. project 041's C3 needs one — a reachability
    test has no meaning against a fake record (CONCEPT.md §3.5, D11)."""
    root.mkdir(parents=True, exist_ok=True)
    for args in (
        ["init", "-q", "-b", trunk],
        ["config", "user.email", "doctor-tests@example.com"],
        ["config", "user.name", "doctor tests"],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _commit(root: Path, rel: str, text: str = "x\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    subprocess.run(
        ["git", "-C", str(root), "add", "-A"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "add " + rel],
        check=True,
        capture_output=True,
    )


@needs_git
def test_link_drift_reports_a_view_on_trunk_as_ok(plane, tmp_path):
    """project 041: the input is the reverse index (every live symlink into
    the overlay), not `proj.links` — the registry field commit `37050e9`
    (2026-09-19) stopped populating, which is why this check used to read
    `ok  no registered project declares a link` no matter what the fleet
    held."""
    overlay = tmp_path / "overlay"
    _git_repo(overlay)
    _commit(overlay, "common/envrc", "use devenv\n")
    repo = plane.repos / "p"
    repo.mkdir(parents=True)
    (repo / ".envrc").symlink_to(overlay / "common/envrc")
    report = doctor.Report()

    doctor.check_link_drift(report, fleet=plane.repos, central_root=overlay)

    assert report.sections == [
        (
            "link drift",
            "ok",
            ["1 live views into the overlay are present and on main"],
        ),
        # C5 rides the same reverse-index walk and reports its own row, so a
        # hollow target is never misfiled under a check named for drift.
        ("empty surface", "ok", ["1 live view targets hold content"]),
    ]


@needs_git
def test_link_drift_fires_on_a_dangling_view(plane, tmp_path):
    """C2: a live view whose target does not exist on disk is a finding —
    the branch that could not fire before this project, because the input
    it read (`proj.links`) was always empty (project 041, CONCEPT.md §1.1)."""
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    repo = plane.repos / "p"
    repo.mkdir(parents=True)
    (repo / ".envrc").symlink_to(overlay / "common/envrc")
    report = doctor.Report()

    doctor.check_link_drift(report, fleet=plane.repos, central_root=overlay)

    assert report.sections[0][0:2] == ("link drift", "!!")
    assert "target does not exist" in report.sections[0][2][0]


@needs_git
def test_link_drift_fires_on_a_lane_only_view(plane, tmp_path):
    """C3, new in project 041: a view whose target exists but is not
    reachable from trunk — the condition behind the 2026-10-01 incidents
    this project was opened to answer."""
    overlay = tmp_path / "overlay"
    _git_repo(overlay)
    subprocess.run(
        ["git", "-C", str(overlay), "checkout", "-q", "-b", "m14-residue"],
        check=True,
        capture_output=True,
    )
    _commit(overlay, "common/envrc", "use devenv\n")
    repo = plane.repos / "p"
    repo.mkdir(parents=True)
    (repo / ".envrc").symlink_to(overlay / "common/envrc")
    report = doctor.Report()

    doctor.check_link_drift(report, fleet=plane.repos, central_root=overlay)

    assert report.sections[0][0:2] == ("link drift", "!!")
    assert "lane-only, not reachable from main" in report.sections[0][2][0]


@needs_git
def test_empty_surface_fires_on_a_hollow_target(plane, tmp_path):
    """C5 gets its own row, not a `link drift` line. A target holding no file
    and no symlink anywhere below it cannot be C3's "lane-only" — git never
    held it in any lane — but a live repository still links into it, so an
    agent reading there finds nothing. Measured live on `mnemonix`, whose
    central `agents/skills/my-ai/` is three levels of empty directory."""
    overlay = tmp_path / "overlay"
    _git_repo(overlay)
    (overlay / "projects/p/agents/skills/my-ai").mkdir(parents=True)
    repo = plane.repos / "p"
    repo.mkdir(parents=True)
    (repo / ".agents").symlink_to(overlay / "projects/p/agents")
    report = doctor.Report()

    doctor.check_link_drift(report, fleet=plane.repos, central_root=overlay)

    rows = {name: (status, lines) for name, status, lines in report.sections}
    assert rows["empty surface"][0] == "!!"
    assert "empty surface" in rows["empty surface"][1][0]
    # And it is NOT misfiled as drift: C3 must stay silent on a hollow target.
    assert rows["link drift"][0] == "ok"


@needs_git
def test_empty_surface_is_ok_when_the_target_holds_a_file(plane, tmp_path):
    overlay = tmp_path / "overlay"
    _git_repo(overlay)
    _commit(overlay, "projects/p/agents/skills/gitman/SKILL.md", "# gitman\n")
    repo = plane.repos / "p"
    repo.mkdir(parents=True)
    (repo / ".agents").symlink_to(overlay / "projects/p/agents")
    report = doctor.Report()

    doctor.check_link_drift(report, fleet=plane.repos, central_root=overlay)

    rows = {name: status for name, status, _ in report.sections}
    assert rows["empty surface"] == "ok"
    assert rows["link drift"] == "ok"


@needs_git
def test_link_drift_and_empty_surface_report_empty_not_ok_with_no_views(
    plane, tmp_path
):
    """Phase 1's rule, applied to this check: `ok` with a zero population is
    never a pass. A machine that has linked nothing and a broken reverse-index
    walk look identical from `ok`, and "ok with a zero population" is the exact
    sentence this check printed for twelve days while blind."""
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    (overlay / "gitman.toml").write_text('trunk = "main"\n')
    report = doctor.Report()

    doctor.check_link_drift(report, fleet=plane.repos, central_root=overlay)

    rows = {name: status for name, status, _ in report.sections}
    assert rows["link drift"] == doctor.EMPTY
    assert rows["empty surface"] == doctor.EMPTY


# ---------------------------------------------------------------------------
# check 2 — a queue name the machine does not declare (§15.4, corrected by S-9)


def test_an_undeclared_queue_name_is_a_finding(plane, tmp_path):
    """S-9: an undeclared name is **not** unlimited. It becomes a real queue at
    concurrency 1, shared by every DAG naming it — so a misspelt `light` does not
    run four wide and does not run free. It runs one at a time, beside anything
    else carrying the same misspelling, and nothing says so at run time."""
    plane.add("p", workflows={"check": "queue: lihgt\n" + ORDINARY})
    rep = doctor.Report()

    doctor.check_queue_names(rep, plane.reg, dagu_home(tmp_path))

    name, status, lines = rep.sections[0]
    assert status == "!!"
    assert "names queue 'lihgt'" in lines[0]


def test_a_child_queue_on_dag_enqueue_is_checked_too(plane, tmp_path):
    """`with.queue` is the only step-level queue Dagu 2.15.0 has (S-11), and it
    reaches the same scheduler, so a typo there costs the same."""
    text = (
        "steps:\n"
        "  - name: a\n"
        "    action: dag.enqueue\n"
        "    with: {dag: child, queue: hevy}\n"
    )
    plane.add("p", workflows={"stack": text})
    rep = doctor.Report()

    doctor.check_queue_names(rep, plane.reg, dagu_home(tmp_path))

    assert rep.sections[0][1] == "!!"
    assert "names queue 'hevy'" in rep.sections[0][2][0]


def test_declared_queue_names_pass(plane, tmp_path):
    plane.add("p", workflows={"check": "queue: heavy\n" + ORDINARY})
    rep = doctor.Report()

    doctor.check_queue_names(rep, plane.reg, dagu_home(tmp_path))

    assert rep.sections[0][1] == "ok"
    assert "heavy, light" in rep.sections[0][2][0]


def test_a_machine_with_no_queue_list_cannot_be_checked(plane, tmp_path):
    """`..` and not `!!`. The check needs the machine's declaration to compare
    against, and saying so is the honest answer — §15.7 forbids inventing one."""
    home = tmp_path / "dagu"
    home.mkdir()
    rep = doctor.Report()

    doctor.check_queue_names(rep, plane.reg, home)

    assert rep.sections[0][1] == ".."


def test_queue_names_reports_empty_rather_than_ok_with_nothing_projected(
    plane, tmp_path
):
    """PROJECT 041 PART 2/3. A declared queue list with zero projected files is
    trivially "every queue named is one of …", true of nothing. `EMPTY`, not
    `ok`, because this check already had test coverage for the populated case
    and the gap was only ever the zero-population branch."""
    rep = doctor.Report()

    doctor.check_queue_names(rep, plane.reg, dagu_home(tmp_path))

    name, status, lines = rep.sections[0]
    assert (name, status) == ("queue names", doctor.EMPTY)
    assert status != "ok"


def test_validate_reports_empty_rather_than_ok_with_nothing_projected(
    plane, monkeypatch
):
    """`check_load` shells out to a real `dagu validate` per file, excluded
    from the rest of this suite for that reason (module docstring). Zero
    files means the subprocess pool never runs, so this needs only a `dagu`
    that resolves, not one that works."""
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/dagu")
    rep = doctor.Report()

    doctor.check_load(rep, plane.reg, Path("/nonexistent-dagu-home"))

    name, status, lines = rep.sections[0]
    assert (name, status) == ("validate", doctor.EMPTY)
    assert status != "ok"


@needs_dagu
def test_validate_fires_on_a_workflow_dagu_validate_rejects(plane, tmp_path):
    """The `!!` branch, demonstrated against a real `dagu validate` — RESEARCH-
    check-efficacy.md flagged this as inferred-only, since exercising it needs
    a real binary and a deliberately broken workflow. `skipif` rather than a
    stub: a step that depends on a step that does not exist is real, rejected
    content, not a canned response.

    The home is warmed with one harmless `validate` call first — a brand new
    `--dagu-home` prints a one-time "creating example DAGs" line that would
    otherwise push `dagu`'s own error past the two lines `check_load` keeps
    (`doctor.py`'s own truncation, not a test artefact)."""
    home = tmp_path / "dagu"
    good = tmp_path / "warm.yaml"
    good.write_text("steps:\n  - name: a\n    run: echo hi\n")
    subprocess.run(
        ["dagu", "--dagu-home", str(home), "validate", str(good)],
        capture_output=True,
    )
    plane.add(
        "p",
        workflows={
            "check": "steps:\n  - name: a\n    run: echo hi\n    depends: [missing]\n"
        },
    )
    rep = doctor.Report()

    doctor.check_load(rep, plane.reg, home)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("validate", "!!")
    assert "Validation failed" in lines[0]


# ---------------------------------------------------------------------------
# check 3 — the bounded walk


def test_a_literal_directory_is_found_inside_a_registered_repository(plane):
    """The one real occurrence landed inside a project and was committed there
    (`STAGE_2_LOG.md` S15). It is the visible symptom of a trigger that passed
    the parameter and forgot the environment."""
    proj = plane.add("p")
    (proj.path / f"${{{PROJECT_DIR}}}").mkdir()

    found = doctor._literal_dirs(proj.path)

    assert [p.name for p in found] == [f"${{{PROJECT_DIR}}}"]


def test_the_walk_stops_at_its_stated_depth(plane):
    """§15.1 forbids scanning the filesystem for repositories. This walks inside
    a path the registry already names, and it stops."""
    proj = plane.add("p")
    deep = proj.path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / f"${{{PROJECT_DIR}}}").mkdir()

    assert doctor._literal_dirs(proj.path, depth=2) == []
    assert len(doctor._literal_dirs(proj.path, depth=4)) == 1


def test_the_walk_does_not_descend_into_generated_directories(plane):
    proj = plane.add("p")
    for name in (".git", ".devenv", ".direnv"):
        hidden = proj.path / name
        hidden.mkdir()
        (hidden / f"${{{PROJECT_DIR}}}").mkdir()

    assert doctor._literal_dirs(proj.path, depth=4) == []


def test_check_literal_itself_reports_a_finding(plane, tmp_path):
    """The three tests above call the private helper `_literal_dirs()`
    directly; none of them call `check_literal` itself, so the `rep.add(...,
    "!!", ...)` wiring around it was untested (RESEARCH-check-efficacy.md's
    `literal dir` row). This is the doctor-level test that was missing."""
    proj = plane.add("p")
    hit = proj.path / f"${{{PROJECT_DIR}}}"
    hit.mkdir()

    rep = doctor.Report()
    doctor.check_literal(rep, plane.reg, tmp_path / "dagu")

    name, status, lines = rep.sections[0]
    assert (name, status) == ("literal dir", "!!")
    assert str(hit) in lines[0]


# ---------------------------------------------------------------------------
# check 5 — the only thing that ever notices a deleted repository


def test_a_stale_entry_is_reported_without_prune(plane):
    plane.add("gone", workflows={"check": ORDINARY}, make_dir=False)
    rep = doctor.Report()

    doctor.check_stale(rep, plane.reg, prune=False)

    status, lines = rep.sections[0][1], rep.sections[0][2]
    assert status == "!!"
    assert "would pass, vacuously" in lines[0]
    assert "doctor --prune" in lines[-1]
    assert plane.reg.projects()["gone"]


def test_prune_removes_the_projection(plane):
    """Pruning is safe because the registry is derived (§9.3): an entry pruned
    wrongly, because a disk was unmounted, restores itself the next time that
    repository's shell is entered. It stays behind a flag because a diagnostic
    that deletes state by default is one a developer hesitates to run."""
    plane.add("gone", workflows={"check": ORDINARY}, make_dir=False)
    rep = doctor.Report()

    doctor.check_stale(rep, plane.reg, prune=True)

    assert "pruned" in rep.sections[0][2][0]
    assert plane.reg.projects() == {}


def test_a_live_entry_is_left_alone(plane):
    plane.add("here", workflows={"check": ORDINARY})
    rep = doctor.Report()

    doctor.check_stale(rep, plane.reg, prune=True)

    assert rep.sections[0][1] == "ok"
    assert plane.reg.projects()["here"]


def test_stale_entries_reports_empty_rather_than_ok_with_nothing_registered(plane):
    """PROJECT 041 PART 2/3. "every registered path is a directory" is
    vacuously true of zero registered paths — the same shape the regression
    this project fixes had."""
    rep = doctor.Report()

    doctor.check_stale(rep, plane.reg, prune=False)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("stale entries", doctor.EMPTY)
    assert status != "ok"
    assert rep.findings == 0


# ---------------------------------------------------------------------------
# check 6 — run output ageing (§9.2, D5) — had ZERO test coverage at any
# level before project 041 (RESEARCH-check-efficacy.md Part 3 #2)


def _age_a_run(proj_path: Path, workflow: str, *, days_old: int) -> None:
    run_dir = proj_path / ".devman" / ".runs" / "logs" / workflow / "dag-run_1"
    run_dir.mkdir(parents=True)
    old = time.time() - days_old * 86400
    os.utime(run_dir, (old, old))


def test_run_output_fires_on_a_project_whose_runs_stopped_ageing_out(plane):
    proj = plane.add("p", workflows={"check": ORDINARY})
    _age_a_run(proj.path, "check", days_old=30)
    rep = doctor.Report()

    doctor.check_ageing(rep, plane.reg, dagu_home(plane.root, retention=7))

    name, status, lines = rep.sections[0]
    assert (name, status) == ("run output", "!!")
    assert "newest 30 days old" in lines[0]


def test_run_output_passes_when_nothing_is_old(plane):
    proj = plane.add("p", workflows={"check": ORDINARY})
    _age_a_run(proj.path, "check", days_old=1)
    rep = doctor.Report()

    doctor.check_ageing(rep, plane.reg, dagu_home(plane.root, retention=7))

    assert rep.sections[0][1] == "ok"


def test_run_output_reports_empty_rather_than_ok_with_nothing_registered(plane):
    rep = doctor.Report()

    doctor.check_ageing(rep, plane.reg, dagu_home(plane.root, retention=7))

    name, status, lines = rep.sections[0]
    assert (name, status) == ("run output", doctor.EMPTY)
    assert status != "ok"
    assert rep.findings == 0


# ---------------------------------------------------------------------------
# check 4 — drift is a fact, not a fault


def test_a_shadowing_file_is_counted_and_not_faulted(plane, tmp_path):
    """§7.3 offers no partial override, so a shadowing file is the mechanism
    working. `doctor` counts it (§15.6) and reports `ok`.

    Both figures are given because the gap between them is the story: the group
    files are mostly comment, so a whole-file percentage measures documentation
    rather than duplication (`STAGE_2_LOG.md`, S14).
    """
    group_file = tmp_path / "group.yaml"
    group_file.write_text("# a comment\nsteps:\n  - name: s\n    run: echo hi\n")
    proj = plane.add("p", local=["check"], sources={"check": str(group_file)})
    own = proj.path / ".devman" / "workflows"
    own.mkdir(parents=True)
    (own / "check.yaml").write_text(
        "# a comment\nsteps:\n  - name: s\n    run: echo x\n"
    )
    rep = doctor.Report()

    doctor.check_drift(rep, plane.reg)

    status, lines = rep.sections[0][1], rep.sections[0][2]
    assert status == "ok"
    assert "shadows base" in lines[0]
    assert "executable lines unchanged" in lines[0]


def test_an_invented_local_workflow_has_nothing_to_diff(plane):
    plane.add("p", local=["mine"])
    rep = doctor.Report()

    doctor.check_drift(rep, plane.reg)

    assert "invented — no group version to diff" in rep.sections[0][2][0]


def test_only_lines_that_do_something_count_as_executable():
    assert doctor._executable(["# note", "", "  ", "  run: x", "a"]) == [
        "  run: x",
        "a",
    ]


def test_same_lines_counts_what_survives():
    assert doctor._same_lines(["a", "b", "c"], ["a", "x", "c"]) == (2, 3)
    assert doctor._same_lines([], ["a"]) == (0, 0)


def test_a_link_pointing_at_another_project_is_still_a_fault(plane):
    plane.add("devman", workflows={"b-check": ORDINARY})
    plane.add("devman-b", workflows={"check": ORDINARY}, link=False)
    plane.link("devman-b", "check", "../projects/devman/workflows/b-check.yaml")
    rep = doctor.Report()

    doctor.check_projection(rep, plane.reg)

    assert rep.sections[0][1] == "!!"
    assert "run the wrong file and report success" in rep.sections[0][2][-1]


def test_a_workflow_name_holding_a_dot_is_a_finding(plane):
    plane.add("p", workflows={"release.tagged": ORDINARY})
    rep = doctor.Report()

    doctor.check_dag_names(rep, plane.reg)

    assert rep.sections[0][1] == "!!"
    assert "cannot be a workflow name" in rep.sections[0][2][0]


def test_ordinary_workflow_names_pass_the_codec(plane):
    plane.add("loci.nvim", workflows={"check": ORDINARY, "maintain": ORDINARY})
    rep = doctor.Report()

    doctor.check_dag_names(rep, plane.reg)

    assert rep.sections[0][1] == "ok"


def test_projection_reports_empty_rather_than_ok_with_nothing_projected(plane):
    rep = doctor.Report()

    doctor.check_projection(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("projection", doctor.EMPTY)
    assert status != "ok"


def test_dag_names_reports_empty_rather_than_ok_with_nothing_registered(plane):
    rep = doctor.Report()

    doctor.check_dag_names(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("dag names", doctor.EMPTY)
    assert status != "ok"


# ---------------------------------------------------------------------------
# check — handlers, cross-repo, fan-out (§9.2, S8, S-8) — the predicates were
# tested at the `Workflow` level only; none of these three had a doctor-level
# test with a firing fixture before this project
# (RESEARCH-check-efficacy.md Part 2: "13 of 26 checks already have a
# doctor-level test ... handlers, cross-repo, fan-out" are three of the gap).

HANDLER_WORKFLOW = "handler_on:\n  success:\n    run: echo done\n" + ORDINARY

CROSS_REPO_HOLDING_WORKFLOW = """
working_dir: ${DEVMAN_PROJECT_DIR}
steps:
  - name: a
    action: dag.run
    with: {dag: child}
"""

UNBOUNDED_FANOUT_WORKFLOW = """
steps:
  - name: a
    action: dag.run
    with: {dag: child1}
  - name: b
    action: dag.run
    with: {dag: child2}
"""


def test_handlers_fires_on_a_workflow_that_replaces_the_exit_handler(plane):
    plane.add("p", workflows={"check": HANDLER_WORKFLOW})
    rep = doctor.Report()

    doctor.check_handlers(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("handlers", "!!")
    assert "defines handler_on (success)" in lines[0]


def test_handlers_passes_when_nothing_defines_one(plane):
    plane.add("p", workflows={"check": ORDINARY})
    rep = doctor.Report()

    doctor.check_handlers(rep, plane.reg)

    assert rep.sections[0][1] == "ok"


def test_handlers_reports_empty_rather_than_ok_with_nothing_projected(plane):
    rep = doctor.Report()

    doctor.check_handlers(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("handlers", doctor.EMPTY)
    assert status != "ok"


def test_cross_repo_fires_on_a_parent_holding_its_own_project_dir(plane):
    """S8: a `dag.run` parent that names `DEVMAN_PROJECT_DIR` for itself,
    rather than only in a child's `with.params`, is holding the wrong
    directory's name."""
    plane.add("p", workflows={"stack": CROSS_REPO_HOLDING_WORKFLOW})
    rep = doctor.Report()

    doctor.check_cross_repo(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("cross-repo", "!!")
    assert "holds DEVMAN_PROJECT_DIR in: working_dir" in lines[0]


def test_cross_repo_reports_empty_rather_than_ok_with_nothing_projected(plane):
    rep = doctor.Report()

    doctor.check_cross_repo(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("cross-repo", doctor.EMPTY)
    assert status != "ok"


def test_fanout_fires_on_two_children_with_no_stated_bound(plane):
    plane.add("p", workflows={"stack": UNBOUNDED_FANOUT_WORKFLOW})
    rep = doctor.Report()

    doctor.check_fanout(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("fan-out", "!!")
    assert "a dag.run child takes no queue slot" in lines[-1]


def test_fanout_reports_empty_rather_than_ok_with_nothing_projected(plane):
    rep = doctor.Report()

    doctor.check_fanout(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("fan-out", doctor.EMPTY)
    assert status != "ok"


# ---------------------------------------------------------------------------
# registry faults, and the schema (009 P2-3, and stage 3's schema 4)


def test_a_registry_fault_is_reported_with_its_metadata_path(plane):
    """The repair is one shell entry or `--prune`, so the developer has to know
    which repository to enter."""
    plane.add("good", workflows={"check": ORDINARY})
    entry = plane.root / "projects" / "broken"
    (entry / "workflows").mkdir(parents=True)
    (entry / "metadata.json").write_text("[]")

    rep = doctor.Report()
    doctor.check_faults(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("registry", "!!")
    assert "broken" in lines[0]
    assert str(entry / "metadata.json") in lines[1]


def test_the_other_checks_still_run_beside_a_fault(plane):
    """A fault must cost the entry, never the command. This is the whole point
    of naming them instead of crashing on them."""
    plane.add("good", workflows={"check": ORDINARY})
    entry = plane.root / "projects" / "broken"
    (entry / "workflows").mkdir(parents=True)
    (entry / "metadata.json").write_text("42")

    rep = doctor.Report()
    doctor.check_faults(rep, plane.reg)
    doctor.check_dag_names(rep, plane.reg)
    doctor.check_schema(rep, plane.reg)

    assert [status for _, status, _ in rep.sections] == ["!!", "ok", "ok"]


def test_a_clean_registry_says_so(plane):
    plane.add("good", workflows={"check": ORDINARY})

    rep = doctor.Report()
    doctor.check_faults(rep, plane.reg)

    assert rep.sections[0][1] == "ok"


def test_reload_reports_ok_with_no_markers(plane):
    rep = doctor.Report()
    doctor.check_reload(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("reload", "ok")


def test_reload_reports_pending_without_a_finding(plane):
    """Pending is expected transient state while an active run drains — it
    must not fail `doctor`'s exit code the way a genuine fault does."""
    plane.reg.state.mkdir(parents=True, exist_ok=True)
    (plane.reg.state / "reload.pending").write_text("2026-09-12T00:00:00Z\n")

    rep = doctor.Report()
    doctor.check_reload(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("reload", "..")
    assert "2026-09-12T00:00:00Z" in lines[0]
    assert rep.findings == 0


def test_reload_reports_blocked_as_a_finding_with_the_repair_action(plane):
    plane.reg.state.mkdir(parents=True, exist_ok=True)
    (plane.reg.state / "reload.blocked").write_text("2026-09-12T00:00:00Z\n")

    rep = doctor.Report()
    doctor.check_reload(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("reload", "!!")
    assert any("restart devman-dagu-reload.service" in line for line in lines)
    assert rep.findings == len(lines)


def test_reload_blocked_takes_priority_over_pending(plane):
    """A blocked reload reports both markers, with the blocked state first."""
    plane.reg.state.mkdir(parents=True, exist_ok=True)
    (plane.reg.state / "reload.pending").write_text("2026-09-12T00:00:00Z\n")
    (plane.reg.state / "reload.blocked").write_text("2026-09-12T00:05:00Z\n")

    rep = doctor.Report()
    doctor.check_reload(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("reload", "!!")
    assert "blocked since 2026-09-12T00:05:00Z" in lines[0]
    assert "pending since 2026-09-12T00:00:00Z" in lines[-1]


def test_an_entry_from_a_newer_devman_is_reported(plane):
    """Schema 4 changed what `plan` MEANS rather than adding a field, which is
    the shape of change a reader cannot detect by looking at the fields."""
    entry = plane.add("ahead", workflows={"check": ORDINARY}).entry
    raw = json.loads((entry / "metadata.json").read_text())
    raw["schema"] = 99
    (entry / "metadata.json").write_text(json.dumps(raw))

    rep = doctor.Report()
    doctor.check_schema(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("schema", "!!")
    assert "schema 99" in lines[0]


def test_schema_reports_empty_rather_than_ok_with_nothing_registered(plane):
    rep = doctor.Report()

    doctor.check_schema(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("schema", doctor.EMPTY)
    assert status != "ok"


def test_mode_reports_compatibility_with_no_generation_file(plane):
    plane.add("p", workflows={"check": ORDINARY})
    rep = doctor.Report()

    doctor.check_mode(rep, plane.reg)

    assert rep.sections[0] == ("mode", "ok", ["compatibility"])


def test_mode_reports_plane_when_a_generation_file_is_active(plane):
    plane.add("p", workflows={"check": ORDINARY})
    (plane.root / "generation.json").write_text('{"generation": 1}\n')
    rep = doctor.Report()

    doctor.check_mode(rep, plane.reg)

    assert rep.sections[0] == ("mode", "ok", ["plane"])


@pytest.mark.parametrize("mode", ["compatibility", "plane"])
def test_header_names_the_project_metadata_source(
    plane, tmp_path, capsys, monkeypatch, mode
):
    plane.add("active", workflows={"check": ORDINARY})
    state = tmp_path / "state"
    state_entry = state / "projects" / "stale-state"
    state_entry.mkdir(parents=True)
    (state_entry / "metadata.json").write_text(
        (plane.root / "projects" / "active" / "metadata.json")
        .read_text()
        .replace('"active"', '"stale-state"')
    )
    registry = Registry(plane.root, state)
    if mode == "plane":
        (plane.root / "generation.json").write_text('{"generation": 1}\n')

    # Main selects the source before printing. Stub checks so this test reads
    # no machine state and asserts the header from the actual command path.
    for name in dir(doctor):
        if name.startswith("check_") and name != "check_mode":
            monkeypatch.setattr(doctor, name, lambda *args, **kwargs: None)
    args = SimpleNamespace(dagu_home=tmp_path / "dagu", prune=False)
    assert doctor.main(args, registry) == 0

    lines = capsys.readouterr().out.splitlines()
    source = plane.root / "projects" if mode == "plane" else state_entry.parent
    workflow_count = 1 if mode == "plane" else 0
    assert lines[0] == f"devman doctor — 1 projects, {workflow_count} workflows"
    assert f"    projects   {source}" in lines
    selected = registry.for_active_generation() if mode == "plane" else registry
    assert sorted(selected.projects()) == (
        ["active"] if mode == "plane" else ["stale-state"]
    )


def test_plane_projection_records_must_match_active_generation(plane):
    project = plane.add("p", workflows={"check": ORDINARY})
    (plane.root / "generation.json").write_text('{"generation": 4}\n')
    (project.entry / "projection.json").write_text(
        '{"project": "p", "plane_generation": 3}\n'
    )
    report = doctor.Report()

    doctor.check_generation(report, plane.reg)

    assert report.sections[0][0:2] == ("generation", "!!")
    assert "!= active 4" in report.sections[0][2][0]


def test_plane_projection_records_can_match_active_generation(plane):
    project = plane.add("p", workflows={"check": ORDINARY})
    (plane.root / "generation.json").write_text('{"generation": 4}\n')
    (project.entry / "projection.json").write_text(
        '{"project": "p", "plane_generation": 4}\n'
    )
    report = doctor.Report()

    doctor.check_generation(report, plane.reg)

    assert report.sections == [
        ("generation", "ok", ["1 projections match generation 4"])
    ]


def test_plane_reads_projection_records_from_active_registry_first(plane):
    project = plane.add("p", workflows={"check": ORDINARY})
    state = plane.root.parent / "state"
    state_entry = state / "projects" / "p"
    state_entry.mkdir(parents=True)
    (state_entry / "metadata.json").write_text(
        (project.entry / "metadata.json").read_text()
    )
    registry = Registry(plane.root, state)
    (plane.root / "generation.json").write_text('{"generation": 4}\n')
    (plane.root / "projects" / "p" / "projection.json").write_text(
        '{"project": "p", "plane_generation": 4}\n'
    )
    (state_entry / "projection.json").write_text(
        '{"project": "p", "plane_generation": 3}\n'
    )
    report = doctor.Report()

    doctor.check_generation(report, registry)

    assert report.sections == [
        ("generation", "ok", ["1 projections match generation 4"])
    ]


def test_plane_registry_view_reads_projects_from_the_active_generation(plane):
    plane.add("active", workflows={"check": ORDINARY})
    state = plane.root.parent / "state"
    state_entry = state / "projects" / "stale-state"
    state_entry.mkdir(parents=True)
    (state_entry / "metadata.json").write_text(
        (plane.root / "projects" / "active" / "metadata.json")
        .read_text()
        .replace('"active"', '"stale-state"')
    )

    registry = Registry(plane.root, state).for_active_generation()

    assert sorted(registry.projects()) == ["active"]


# ---------------------------------------------------------------------------
# what the plane's only verb pays for (014)


def _dotfile(root, megabytes: int, *, name: str = "shellij", git: bool = True) -> None:
    """Give `<root>/<name>` a `.devenv` of about `megabytes`, in shell scripts."""
    dot = root / name / ".devenv"
    dot.mkdir(parents=True, exist_ok=True)
    block = b"x" * 1_000_000
    for i in range(megabytes):
        (dot / f"shell-{i:016x}.sh").write_bytes(block)
    if git:
        (root / name / ".git").mkdir(parents=True, exist_ok=True)


def _yaml_with_path_input(repo, target) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "devenv.yaml").write_text(
        yaml.safe_dump({"inputs": {"shellij": {"url": f"path:{target}"}}})
    )


def test_a_path_input_carrying_a_big_dotfile_is_a_finding(plane, tmp_path):
    """014: `validate_lock_file` re-hashes the whole `path:` target every run,
    `.gitignore` and all, so the taker pays for the target's own `.devenv`."""
    shared = tmp_path / "shared"
    _dotfile(shared, 60)
    taker = plane.add("taker", workflows={"check": ORDINARY}).path
    _yaml_with_path_input(taker, shared / "shellij")

    rep = doctor.Report()
    doctor.check_path_inputs(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("path inputs", "!!")
    assert "60 MB" in lines[0]
    assert "60 shell-*.sh" in lines[0]
    assert "every run of 1 projects" in lines[0]


def test_a_git_worktree_target_is_told_to_use_git_file(plane, tmp_path):
    """`git+file:` resolves through `git ls-files`, so the dotfile is excluded.
    Measured 802 ms -> 149 ms on the same input, so the remedy is named."""
    shared = tmp_path / "shared"
    _dotfile(shared, 60, git=True)
    taker = plane.add("taker", workflows={"check": ORDINARY}).path
    _yaml_with_path_input(taker, shared / "shellij")

    rep = doctor.Report()
    doctor.check_path_inputs(rep, plane.reg)

    assert "git+file://" in rep.sections[0][2][1]


def test_a_target_that_is_not_a_git_worktree_is_told_to_sweep(plane, tmp_path):
    """`git+file:` needs a git worktree. Without one the only remedy left is the
    stopgap, so the check must not name a fix that cannot be applied."""
    shared = tmp_path / "shared"
    _dotfile(shared, 60, git=False)
    taker = plane.add("taker", workflows={"check": ORDINARY}).path
    _yaml_with_path_input(taker, shared / "shellij")

    rep = doctor.Report()
    doctor.check_path_inputs(rep, plane.reg)

    line = rep.sections[0][2][1]
    assert "git+file://" not in line
    assert "delete shell-*.sh" in line


def test_a_small_dotfile_is_not_a_finding(plane, tmp_path):
    """Below the threshold the copy costs less than devenv's own 146 ms floor."""
    shared = tmp_path / "shared"
    _dotfile(shared, 2)
    taker = plane.add("taker", workflows={"check": ORDINARY}).path
    _yaml_with_path_input(taker, shared / "shellij")

    rep = doctor.Report()
    doctor.check_path_inputs(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("path inputs", "ok")
    assert "1 directories are path: inputs" in lines[0]


def test_every_taker_of_one_target_is_named(plane, tmp_path):
    """One oversized target is one finding, not one per taker: 51 repositories
    take `shellij`, and 51 identical lines would bury the rest of the report."""
    shared = tmp_path / "shared"
    _dotfile(shared, 60)
    for who in ("one", "two", "three"):
        repo = plane.add(who, workflows={"check": ORDINARY}).path
        _yaml_with_path_input(repo, shared / "shellij")

    rep = doctor.Report()
    doctor.check_path_inputs(rep, plane.reg)

    _, status, lines = rep.sections[0]
    assert status == "!!"
    assert len([line for line in lines if str(shared / "shellij") in line]) == 1
    assert "every run of 3 projects" in lines[0]
    assert "one, three, two" in lines[1]


def test_a_relative_path_input_resolves_against_the_repository(plane, tmp_path):
    """`path:./modules` and `path:../vendomat` are both live forms in this
    plane, so an unresolved target would silently check nothing."""
    taker = plane.add("taker", workflows={"check": ORDINARY}).path
    _dotfile(taker, 60, name="modules")
    (taker / "devenv.yaml").write_text(
        yaml.safe_dump({"inputs": {"mods": {"url": "path:./modules"}}})
    )

    rep = doctor.Report()
    doctor.check_path_inputs(rep, plane.reg)

    _, status, lines = rep.sections[0]
    assert status == "!!"
    assert str(taker / "modules") in lines[0]


def test_a_repository_with_no_devenv_yaml_is_not_an_error(plane):
    """The registry entry is the plane's; `devenv.yaml` is the repository's, and
    a repository may not have one."""
    plane.add("bare", workflows={"check": ORDINARY})

    rep = doctor.Report()
    doctor.check_path_inputs(rep, plane.reg)

    assert rep.sections[0][1] == "ok"


def test_path_inputs_reports_empty_rather_than_ok_with_nothing_registered(plane):
    rep = doctor.Report()

    doctor.check_path_inputs(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("path inputs", doctor.EMPTY)
    assert status != "ok"


def test_the_whole_dotfile_counts_not_only_the_shell_scripts(plane, tmp_path):
    """Nix copies the dotfile whole, so the venv and the eval cache are part of
    the bill even though only `shell-*.sh` is safe to delete. 014 measured the
    floor this creates: sweeping alone stops at 913 ms."""
    shared = tmp_path / "shared"
    dot = shared / "shellij" / ".devenv"
    (dot / "state" / "venv").mkdir(parents=True)
    (dot / "state" / "venv" / "big").write_bytes(b"x" * 60_000_000)
    taker = plane.add("taker", workflows={"check": ORDINARY}).path
    _yaml_with_path_input(taker, shared / "shellij")

    rep = doctor.Report()
    doctor.check_path_inputs(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("path inputs", "!!")
    assert "0 shell-*.sh" in lines[0]


# ---------------------------------------------------------------------------
# check — output ownership (015, §12 rule 3 as amended)


def test_a_project_declaring_nothing_is_reported_unaudited_not_clean(plane):
    """The check must not read silence as compliance. §12 rule 3 stopped being a
    refusal, so a workflow that declares nothing is simply unaudited."""
    plane.add("p", workflows={"check": ORDINARY})
    rep = doctor.Report()

    doctor.check_writes(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("writes", "ok")
    assert "unaudited, not proven silent" in lines[1]


def test_a_well_formed_declaration_is_counted_by_tier(plane):
    plane.add(
        "p",
        workflows={"format": ORDINARY, "regen": ORDINARY},
        writes={
            "format": {"tier": "insitu", "paths": ["**/*.py"]},
            "regen": {"tier": "lane", "paths": ["src/**"]},
        },
    )
    rep = doctor.Report()

    doctor.check_writes(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("writes", "ok")
    assert "1 insitu, 1 lane" in lines[0]


def test_a_local_workflow_writes_declaration_is_known(plane):
    """Local workflows belong to the project's complete projected set."""
    plane.add(
        "p",
        local=["mine"],
        writes={"mine": {"tier": "lane", "paths": ["src/**"]}},
    )
    rep = doctor.Report()

    doctor.check_writes(rep, plane.reg)

    assert rep.sections[0][1] == "ok"


def test_tier_free_outside_agent_surface_is_a_finding(plane):
    """The finding this check exists to make. A free-tier write lands in the
    working tree with nobody present, so claiming it for `src/**` is claiming to
    edit code unattended — which is what the lane exists to prevent."""
    plane.add(
        "p",
        workflows={"regen": ORDINARY},
        writes={"regen": {"tier": "free", "paths": ["src/**"]}},
    )
    rep = doctor.Report()

    doctor.check_writes(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("writes", "!!")
    assert "tier free over src/** — outside agent surface" in lines[0]


def test_tier_free_over_agent_surface_is_never_a_finding(plane):
    plane.add(
        "p",
        workflows={"notes": ORDINARY},
        writes={"notes": {"tier": "free", "paths": [".agents/**", "docs/**"]}},
    )
    rep = doctor.Report()

    doctor.check_writes(rep, plane.reg)

    assert rep.sections[0][1] == "ok"


def test_a_declaration_naming_no_projected_workflow_is_a_finding(plane):
    """Same shape as the trigger-target check: a claim about a workflow that
    does not exist audits nothing."""
    plane.add(
        "p",
        workflows={"check": ORDINARY},
        writes={"ghost": {"tier": "lane", "paths": ["src/**"]}},
    )
    rep = doctor.Report()

    doctor.check_writes(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("writes", "!!")
    assert "projects no such workflow" in lines[0]


def test_an_unknown_tier_is_a_finding(plane):
    """A registry entry can hold one even though the projection refuses it: an
    older devman wrote the entry, or somebody edited it (§9.3)."""
    plane.add(
        "p",
        workflows={"regen": ORDINARY},
        writes={"regen": {"tier": "trunk", "paths": ["src/**"]}},
    )
    rep = doctor.Report()

    doctor.check_writes(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("writes", "!!")
    assert "is not one of" in lines[0]


def test_writes_reports_empty_rather_than_ok_with_nothing_registered(plane):
    """PROJECT 041 PART 2/3. Distinct from `test_a_project_declaring_nothing_
    is_reported_unaudited_not_clean` above: that test registers one project
    that declares nothing (legitimately "unaudited"); this one registers
    none at all, which must not print the same "ok" sentence."""
    rep = doctor.Report()

    doctor.check_writes(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("writes", doctor.EMPTY)
    assert status != "ok"


# ---------------------------------------------------------------------------
# check — trigger target (S-3) — project 041's Part 2 priority #1
#
# RESEARCH-check-efficacy.md named this the closest living relative of the
# original `check_link_drift` defect: it trusts `proj.triggers`, a registry-
# projected field, rather than re-deriving its answer from the filesystem —
# and it had NO TEST ANYWHERE before this project.


def test_trigger_target_fires_on_a_tombstoned_group(plane):
    """A group whose workflow was deleted leaves its `triggers.toml` behind —
    the registry entry still carries a `triggers` block naming a workflow
    this project no longer projects. Every matching save then fires a
    `devman run` that refuses, silently, in a watcher log nobody opens
    (`check_trigger_targets`'s own docstring)."""
    plane.add(
        "p",
        workflows={},
        local=[],
        triggers={"group": "format", "map": {"**/*.py": "format"}},
    )
    rep = doctor.Report()

    doctor.check_trigger_targets(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("trigger target", "!!")
    assert "'format' is not projected" in lines[0]
    assert "this project projects: (nothing)" in lines[1]


def test_trigger_target_passes_when_the_workflow_is_still_projected(plane):
    plane.add(
        "p",
        workflows={"format": ORDINARY},
        triggers={"group": "format", "map": {"**/*.py": "format"}},
    )
    rep = doctor.Report()

    doctor.check_trigger_targets(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("trigger target", "ok")
    assert "1 triggers" in lines[0]


def test_trigger_target_reports_empty_rather_than_ok_with_nothing_registered(plane):
    """PROJECT 041 PART 2/3. Zero registered projects is zero triggers to
    check, and `ok  no registered project declares a trigger` was the exact
    sentence `check_link_drift` printed for twelve days while its real input
    was nonzero — this check must not say `ok` for the same empty shape."""
    rep = doctor.Report()

    doctor.check_trigger_targets(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("trigger target", doctor.EMPTY)
    assert status != "ok"
    assert rep.findings == 0


# ---------------------------------------------------------------------------
# check_duplicate_identity — two checkouts sharing a project name (O9, half 2
# of the duplicate-registration refusal). This reuses `cli._manifest_candidates`
# rather than re-deriving the comparison; the fixtures below are the same
# shape as `test_cli.py`'s `_write_manifest`/`test_link_all_blocks_duplicate_
# manifest_identities`, because the two are exercising one function.


def _write_project_manifest(root: Path, project: str) -> None:
    manifest = root / ".devman" / "project.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        f'schema = 1\nproject = "{project}"\ngroups = []\npolicy = "stable"\n'
    )


def test_duplicate_identity_fires_on_two_checkouts_sharing_a_project_name(tmp_path):
    """025 §6.4's hazard, from state already on disk: two direct children of
    the fleet root state the same `devman.project` in their own
    `.devman/project.toml`. Nothing about this reads the registry — both
    facts come from the checkouts themselves (041 D1)."""
    fleet = tmp_path / "fleet"
    fleet.mkdir()
    _write_project_manifest(fleet / "first-checkout", "flora")
    _write_project_manifest(fleet / "second-checkout", "flora")
    rep = doctor.Report()

    doctor.check_duplicate_identity(rep, fleet=fleet)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("duplicate name", "!!")
    assert any("duplicate manifest identity 'flora'" in line for line in lines)
    assert rep.findings == len(lines)


def test_duplicate_identity_is_silent_when_every_checkout_names_itself_once(tmp_path):
    fleet = tmp_path / "fleet"
    fleet.mkdir()
    _write_project_manifest(fleet / "first-checkout", "flora")
    _write_project_manifest(fleet / "second-checkout", "orchid")
    rep = doctor.Report()

    doctor.check_duplicate_identity(rep, fleet=fleet)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("duplicate name", "ok")
    assert "2 checkouts" in lines[0]
    assert rep.findings == 0


def test_duplicate_identity_reports_empty_rather_than_ok_with_no_manifest(tmp_path):
    """PROJECT 041 PART 2's rule, applied here: a fleet root that does not
    exist yet and a fleet root full of checkouts that carry no
    `.devman/project.toml` read identically through `ok` — `EMPTY` instead,
    so a machine with nothing to compare cannot be misread as a machine that
    compared everything and found it clean."""
    rep = doctor.Report()

    doctor.check_duplicate_identity(rep, fleet=tmp_path / "never-created")

    name, status, lines = rep.sections[0]
    assert (name, status) == ("duplicate name", doctor.EMPTY)
    assert rep.findings == 0

    fleet = tmp_path / "fleet-with-no-manifests"
    (fleet / "some-dir").mkdir(parents=True)
    rep2 = doctor.Report()

    doctor.check_duplicate_identity(rep2, fleet=fleet)

    name2, status2, _lines2 = rep2.sections[0]
    assert (name2, status2) == ("duplicate name", doctor.EMPTY)
    assert rep2.findings == 0


# ---------------------------------------------------------------------------
# check — what a repository's local libraries actually resolve to (016)


def fake_sources(monkeypatch, table: dict) -> None:
    """Stub `_source_state`, so these tests need no `git` binary.

    The check shells out to git for `(head, dirty)`. That is git's behaviour,
    not this check's logic, and `nix flake check` runs the suite in a sandbox
    with no git on PATH — the first version of these tests passed in the devenv
    shell and failed the gate for exactly that reason.
    """
    monkeypatch.setattr(
        doctor, "_source_state", lambda src: table.get(Path(src), (None, False))
    )


def lockfile(root, src, *, rev: str | None = None, name: str = "devenv.lock") -> None:
    locked = {"type": "git", "url": f"file://{src}"}
    if rev:
        locked["rev"] = rev
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps({"nodes": {"lib": {"locked": locked}}}))


def test_a_dirty_local_source_is_a_finding_with_its_consumer_count(
    plane, tmp_path, monkeypatch
):
    """The finding this check exists to make, and it is the opposite of the one
    expected: an unpinned `git+file:` input has no rev, so consumers resolve to
    the source's WORKING TREE. A dirty source is consumed as uncommitted work."""
    src = tmp_path / "lib"
    fake_sources(monkeypatch, {src: ("a" * 40, True)})
    for name in ("a", "b"):
        proj = plane.add(name)
        lockfile(Path(proj.path), src)
    rep = doctor.Report()

    doctor.check_local_sources(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("local sources", "!!")
    assert "uncommitted changes" in lines[0]
    assert "2 project(s)" in lines[0]


def test_a_clean_unpinned_source_is_not_a_finding(plane, tmp_path, monkeypatch):
    """Unpinned and clean is the normal, healthy fleet state — 91 of 93 inputs
    on this machine. It must not be reported, or the check is noise."""
    src = tmp_path / "lib"
    fake_sources(monkeypatch, {src: ("a" * 40, False)})
    proj = plane.add("a")
    lockfile(Path(proj.path), src)
    rep = doctor.Report()

    doctor.check_local_sources(rep, plane.reg)

    assert rep.sections[0][1] == "ok"


def test_a_pin_behind_its_source_is_a_finding(plane, tmp_path, monkeypatch):
    """The other half: a `flake.lock` pin DOES carry a rev, so it can go stale."""
    src = tmp_path / "lib"
    fake_sources(monkeypatch, {src: ("a" * 40, False)})
    proj = plane.add("a")
    lockfile(Path(proj.path), src, rev="0" * 40, name="flake.lock")
    rep = doctor.Report()

    doctor.check_local_sources(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("local sources", "!!")
    assert "pins lib at 00000000" in lines[0]


def test_a_pin_at_head_is_not_a_finding(plane, tmp_path, monkeypatch):
    src = tmp_path / "lib"
    head = "a" * 40
    fake_sources(monkeypatch, {src: (head, False)})
    proj = plane.add("a")
    lockfile(Path(proj.path), src, rev=head, name="flake.lock")
    rep = doctor.Report()

    doctor.check_local_sources(rep, plane.reg)

    assert rep.sections[0][1] == "ok"


def test_a_repository_with_no_local_inputs_says_so(plane):
    plane.add("a")
    rep = doctor.Report()

    doctor.check_local_sources(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("local sources", "ok")
    assert "0 local libraries" in lines[0]


def test_local_sources_reports_empty_rather_than_ok_with_nothing_registered(plane):
    """PROJECT 041 PART 2/3. Distinct from the test above: that one registers
    a project with no local inputs (legitimately "0 local libraries feed 0
    inputs"); this one registers no project at all."""
    rep = doctor.Report()

    doctor.check_local_sources(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("local sources", doctor.EMPTY)
    assert status != "ok"


# ---------------------------------------------------------------------------
# the ledger that nothing else prunes — `.devman-link-state.json`,
# project 041 open question O5. `check_stale` above prunes the *registry*;
# this is the file `Registry.unproject` never touches.
#
# Every test builds its own `fleet` and `central_root` under `tmp_path`. The
# live ledger's counts are changing while this project runs (D15's own
# incident: 456/84 to 450/82 inside three hours), so a test asserting a live
# count would pass today and fail tomorrow — the same reason `test_central.py`
# gives for never asserting against the live machine.

LIVE_ENTRY = {
    "canonical": "/home/andrew/.config/devman/projects/linkman/agents",
    "hash": "a" * 64,
}
OTHER_LIVE_ENTRY = {
    "canonical": "/home/andrew/.config/devman/projects/linkman/.local.gitignore",
    "hash": "c" * 64,
}
DEAD_ENTRY = {
    "canonical": "/home/andrew/.config/devman/projects/gone-project/agents",
    "hash": "b" * 64,
}


def _ledger_text(entries: dict, *, trailing_newline: bool = True) -> str:
    """The exact shape `devman_link.state.write_state` produces, confirmed
    against the live file: 2-space indent, sorted keys, trailing newline."""
    text = json.dumps(entries, indent=2, sort_keys=True)
    return text + "\n" if trailing_newline else text


def _write_ledger(
    central_root: Path, entries: dict, *, trailing_newline: bool = True
) -> Path:
    central_root.mkdir(parents=True, exist_ok=True)
    path = central_root / doctor.STATE_FILE
    path.write_text(_ledger_text(entries, trailing_newline=trailing_newline))
    return path


def test_ledger_reports_a_project_whose_repository_is_absent(tmp_path):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    (fleet / "linkman").mkdir(parents=True)
    _write_ledger(
        central_root,
        {"linkman:.agents": LIVE_ENTRY, "gone-project:.agents": DEAD_ENTRY},
    )
    rep = doctor.Report()

    doctor.check_ledger_stale(rep, prune=False, fleet=fleet, central_root=central_root)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("ledger", "!!")
    assert "2 entries, 2 projects" in lines[0]
    assert any("gone-project" in line and "1 entries" in line for line in lines)
    assert not any(line.startswith("linkman:") for line in lines)
    assert "doctor --prune" in lines[-1]


def test_ledger_does_not_report_a_project_whose_repository_exists(tmp_path):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    (fleet / "linkman").mkdir(parents=True)
    _write_ledger(central_root, {"linkman:.agents": LIVE_ENTRY})
    rep = doctor.Report()

    doctor.check_ledger_stale(rep, prune=False, fleet=fleet, central_root=central_root)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("ledger", "ok")
    assert "1 entries, 1 projects" in lines[0]


def test_prune_keeps_every_live_entry_byte_for_byte(tmp_path):
    """The two-sided-edit baseline is the `{canonical, hash}` pair, not just
    the key — a test that only counted entries would not catch a corrupted
    hash. Asserted against the parsed survivors directly."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    (fleet / "linkman").mkdir(parents=True)
    path = _write_ledger(
        central_root,
        {
            "linkman:.agents": LIVE_ENTRY,
            "linkman:.local.gitignore": OTHER_LIVE_ENTRY,
            "gone-project:.agents": DEAD_ENTRY,
        },
    )
    rep = doctor.Report()

    doctor.check_ledger_stale(rep, prune=True, fleet=fleet, central_root=central_root)

    survivors = json.loads(path.read_text())
    assert survivors == {
        "linkman:.agents": LIVE_ENTRY,
        "linkman:.local.gitignore": OTHER_LIVE_ENTRY,
    }


def test_prune_removes_exactly_the_dead_projects_entries_and_nothing_else(tmp_path):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    (fleet / "linkman").mkdir(parents=True)
    path = _write_ledger(
        central_root,
        {
            "linkman:.agents": LIVE_ENTRY,
            "gone-project:.agents": DEAD_ENTRY,
            "another-gone:.agents": DEAD_ENTRY,
        },
    )
    rep = doctor.Report()

    doctor.check_ledger_stale(rep, prune=True, fleet=fleet, central_root=central_root)

    survivors = json.loads(path.read_text())
    assert set(survivors) == {"linkman:.agents"}
    name, status, lines = rep.sections[0]
    assert status == "!!"
    assert any("pruned 1 entries" in line for line in lines if "gone-project" in line)
    assert any("pruned 1 entries" in line for line in lines if "another-gone" in line)


def test_without_prune_the_ledger_file_is_unmodified(tmp_path):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    (fleet / "linkman").mkdir(parents=True)
    path = _write_ledger(
        central_root,
        {"linkman:.agents": LIVE_ENTRY, "gone-project:.agents": DEAD_ENTRY},
    )
    before = path.read_bytes()
    rep = doctor.Report()

    doctor.check_ledger_stale(rep, prune=False, fleet=fleet, central_root=central_root)

    assert path.read_bytes() == before


def test_a_missing_ledger_file_is_not_an_error(tmp_path):
    """A fresh machine has made no link and has no ledger (project 033)."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    fleet.mkdir()
    central_root.mkdir()
    rep = doctor.Report()

    doctor.check_ledger_stale(rep, prune=True, fleet=fleet, central_root=central_root)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("ledger", "ok")
    assert not (central_root / doctor.STATE_FILE).exists()


def test_a_malformed_ledger_is_reported_and_left_alone(tmp_path):
    """A file that does not parse might still hold a real two-sided-edit
    baseline. Rewriting it would guess at content this check cannot read, so
    it reports and refuses rather than overwriting or crashing."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    central_root.mkdir()
    path = central_root / doctor.STATE_FILE
    path.write_text("{ not json")
    before = path.read_bytes()
    rep = doctor.Report()

    doctor.check_ledger_stale(rep, prune=True, fleet=fleet, central_root=central_root)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("ledger", "!!")
    assert "not valid JSON" in lines[0]
    assert path.read_bytes() == before


def test_a_ledger_that_is_a_json_list_is_reported_and_left_alone(tmp_path):
    """The shape, not only the syntax, must be right: a parseable file that
    is not an object (a list, say) is just as unreadable as a baseline."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    central_root.mkdir()
    path = central_root / doctor.STATE_FILE
    path.write_text("[1, 2, 3]\n")
    before = path.read_bytes()
    rep = doctor.Report()

    doctor.check_ledger_stale(rep, prune=True, fleet=fleet, central_root=central_root)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("ledger", "!!")
    assert "JSON object" in lines[0]
    assert path.read_bytes() == before


def test_prune_preserves_a_ledger_with_no_trailing_newline(tmp_path):
    """The write matches the file's own formatting, not an assumption. 033's
    reconciler always writes a trailing newline; this proves the check does
    not add one where the file on disk did not have it."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    (fleet / "linkman").mkdir(parents=True)
    path = _write_ledger(
        central_root,
        {"linkman:.agents": LIVE_ENTRY, "gone-project:.agents": DEAD_ENTRY},
        trailing_newline=False,
    )
    rep = doctor.Report()

    doctor.check_ledger_stale(rep, prune=True, fleet=fleet, central_root=central_root)

    assert not path.read_text().endswith("\n")
    assert json.loads(path.read_text()) == {"linkman:.agents": LIVE_ENTRY}


# ---------------------------------------------------------------------------
# universal law vs. selected tool skills (project 041, skill-surface work,
# step 4)


def _pool(central_root: Path, *names: str) -> Path:
    """A pool skill, real content so `.exists()` has something to find."""
    pool = central_root / "skills"
    for name in names:
        (pool / name).mkdir(parents=True, exist_ok=True)
        (pool / name / "SKILL.md").write_text(f"# {name}\n")
    return pool


def _surface(central_root: Path, project: str) -> Path:
    surface = central_root / "projects" / project / "agents" / "skills"
    surface.mkdir(parents=True, exist_ok=True)
    return surface


def _link(surface: Path, pool: Path, name: str) -> None:
    """A real relative link into the pool — 025 §7.2's shape."""
    (surface / name).symlink_to(
        os.path.relpath(pool / name, surface), target_is_directory=True
    )


def test_universal_skills_fires_on_a_surface_missing_writing(tmp_path):
    """The branch project 041 opened this check to reach: a live surface
    that never received the `writing` link, undetected by any convention
    for three weeks (RESEARCH-universal-skills.md §3)."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    pool = _pool(central_root, "writing")
    (fleet / "has-it").mkdir(parents=True)
    _link(_surface(central_root, "has-it"), pool, "writing")
    (fleet / "lacks-it").mkdir(parents=True)
    _surface(central_root, "lacks-it")  # no writing link at all
    rep = doctor.Report()

    doctor.check_universal_skills(rep, fleet=fleet, central_root=central_root)

    rows = {name: (status, lines) for name, status, lines in rep.sections}
    assert rows["universal skills"][0] == "!!"
    assert any(
        "lacks-it: missing writing" in line for line in rows["universal skills"][1]
    )
    assert not any(line.startswith("has-it") for line in rows["universal skills"][1])


def test_universal_skills_is_silent_when_every_live_surface_carries_it(tmp_path):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    pool = _pool(central_root, "writing")
    (fleet / "p").mkdir(parents=True)
    _link(_surface(central_root, "p"), pool, "writing")
    rep = doctor.Report()

    doctor.check_universal_skills(rep, fleet=fleet, central_root=central_root)

    rows = {name: status for name, status, _ in rep.sections}
    assert rows["universal skills"] == "ok"
    assert rows["universal pool"] == "ok"


def test_universal_skills_reports_empty_not_ok_with_no_live_surfaces(tmp_path):
    """Phase 1's rule, applied here: `ok` with a zero population is never a
    pass — the exact confusion that hid `check_link_drift`'s real gap for
    twelve days (its own docstring)."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    _pool(central_root, "writing")
    rep = doctor.Report()

    doctor.check_universal_skills(rep, fleet=fleet, central_root=central_root)

    rows = {name: status for name, status, _ in rep.sections}
    assert rows["universal skills"] == doctor.EMPTY
    assert rows["universal skills"] != "ok"


def test_universal_skills_ignores_a_surface_whose_repository_is_gone(tmp_path):
    """Liveness matches `check_ledger_stale`: `(fleet / name).is_dir()`,
    never the central overlay's own say-so. A central surface left behind
    for a repository the fleet no longer has is not counted — it is
    `check_ledger_stale`'s finding, not this check's."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    _pool(central_root, "writing")
    _surface(central_root, "gone")  # no writing link, and no fleet/gone dir
    rep = doctor.Report()

    doctor.check_universal_skills(rep, fleet=fleet, central_root=central_root)

    rows = {name: status for name, status, _ in rep.sections}
    assert rows["universal skills"] == doctor.EMPTY


def test_universal_skills_accepts_a_real_directory_copy_not_only_a_link(tmp_path):
    """025 §7.2 wants a link into the pool; this check asks a narrower
    question than §7.2 does — can an agent reading this surface find the
    skill right now — and a real copy answers that exactly as a link
    does, so it is accepted on equal terms (the check's own docstring)."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    _pool(central_root, "writing")
    (fleet / "p").mkdir(parents=True)
    surface = _surface(central_root, "p")
    (surface / "writing").mkdir()
    (surface / "writing" / "SKILL.md").write_text("# writing\n")
    rep = doctor.Report()

    doctor.check_universal_skills(rep, fleet=fleet, central_root=central_root)

    rows = {name: status for name, status, _ in rep.sections}
    assert rows["universal skills"] == "ok"


def test_universal_pool_fires_when_the_pool_itself_lacks_a_universal_skill(tmp_path):
    """Worse than any one surface's gap: nothing links to a pool skill that
    is not there, so every linking surface is dangling for the identical
    reason at once. Named here rather than left to be traced back from 47
    separate `check_link_drift` C2 findings."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    central_root.mkdir(parents=True)
    (fleet / "p").mkdir(parents=True)
    _surface(central_root, "p")  # no pool at all, nothing to link to
    rep = doctor.Report()

    doctor.check_universal_skills(rep, fleet=fleet, central_root=central_root)

    rows = {name: status for name, status, _ in rep.sections}
    assert rows["universal pool"] == "!!"


# ---------------------------------------------------------------------------
# check — `SHELL` in the running Dagu's own environment (009 P1-3, S13)
#
# Had no test anywhere (RESEARCH-check-efficacy.md: "the nix test checks
# `/proc` directly, not `doctor`'s output"). `_dagu_pids` matches on a
# process's own argv (named `dagu`, carrying `start-all`) and its
# `DAGU_HOME`/environment — real facts to construct without a real `dagu`
# binary: `subprocess.Popen`'s `executable=` runs this interpreter under a
# borrowed argv[0], so `/proc/<pid>/cmdline` and `/proc/<pid>/environ` are
# exactly what a real leaked-`SHELL` Dagu would leave. Nothing about Dagu's
# own behaviour is faked; this is a real process and a real `/proc` read.


def test_daemon_shell_fires_when_shell_leaks_into_a_running_dagu(tmp_path):
    home = tmp_path / "dagu_home"
    proc = subprocess.Popen(
        ["dagu", "-c", "import time; time.sleep(30)", "start-all"],
        executable=sys.executable,
        env={**os.environ, "DAGU_HOME": str(home), "SHELL": "/bin/doctor-test-shell"},
    )
    try:
        environ_path = Path(f"/proc/{proc.pid}/environ")
        for _ in range(100):
            if b"SHELL=/bin/doctor-test-shell" in environ_path.read_bytes():
                break
            time.sleep(0.05)
        else:
            pytest.fail("the fake dagu process never showed its SHELL in /proc")

        rep = doctor.Report()
        doctor.check_daemon_shell(rep, home)
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("daemon shell", "!!")
    assert any(
        f"pid {proc.pid}" in line and "SHELL=/bin/doctor-test-shell" in line
        for line in lines
    )


# ---------------------------------------------------------------------------
# check — the watcher (§8, stage 3)
#
# No unit-level test anywhere before this project: `nix/tests/dagu-
# service.nix:389-488` exercises the process-table branches in a VM, and only
# ever asserts the clean `"ok  watcher"` line (RESEARCH-check-efficacy.md).
# This fires the "supervisor alive, registry says watch something, nothing is
# actually watching it" branch — real `/proc` liveness (the state file names
# THIS test process's own pid, which is trivially alive) against a real,
# empty `running_watchers()` result (no watchexec was started, so there
# genuinely is none) — the one branch reachable without spawning watchexec.


def test_watcher_fires_when_the_supervisor_is_alive_but_nothing_is_running(plane):
    plane.add(
        "p",
        workflows={"format": ORDINARY},
        triggers={"group": "format", "map": {"**/*.py": "format"}},
    )
    entries = watch.watch_map(plane.reg)
    state = watch.WatchState(plane.reg)
    state.start(entries, ["watchexec", "--watch", str(plane.repos / "p")])

    rep = doctor.Report()
    doctor.check_watcher(rep, plane.reg)

    name, status, lines = rep.sections[0]
    assert (name, status) == ("watcher", "!!")
    assert any("is watching nothing" in line for line in lines)


# ---------------------------------------------------------------------------
# PART 2 — the rule enforced, not just satisfied (project 041, Phase 2)
#
# RESEARCH-check-efficacy.md's own recommendation: "one table-driven
# parametrised test ... a list of (check_name, fixture_fn) pairs ... so a new
# check added to main() without a corresponding fixture entry is itself a
# visible gap." `_checks_in_main()` reads the check list out of `main()`'s
# own source — never a hand-copied list — so the only thing a human can get
# wrong is forgetting to add the new check's entry to `FIRING_TESTS`, and
# THAT is what this test then fails on, by name, with a message that says
# exactly what to do next.
#
# **What this cannot catch, stated so nobody over-trusts it:** a fixture
# built against a wrong predicate proves nothing — it tests that *a* non-ok
# branch is reachable, not that the branch means what the check's docstring
# claims. It would NOT have caught the original defect this project exists to
# fix: `check_link_drift`'s own tests built their input by hand and never
# touched the different file (`modules/devenv.nix`) whose deletion emptied
# the real population path. That is why the empty-population guards
# (`EMPTY`, Part 2 of this project's Phase 1) are the primary defence and
# this table is secondary — it keeps the *next* check honest about having
# A firing test at all, not about that test's correctness.

INFORMATIONAL = {
    # `check_mode` and `check_drift` ("shadowing") print `ok` and nothing
    # else, by construction — each function's own docstring says so, and
    # RESEARCH-check-efficacy.md confirms neither has a reachable `!!`
    # branch. Opting out here is explicit and visible for exactly that
    # reason: a silent absence from FIRING_TESTS would look identical to a
    # forgotten entry, which is the loophole this guard exists to close.
    "check_mode": "no `!!` branch exists — a status line, not a fault detector (see check_mode's own docstring)",
    "check_drift": "no `!!` branch exists — drift is a fact, not a fault (see check_drift's own docstring)",
}

FIRING_TESTS = {
    "check_plane": "test_plane_reports_unreachable_as_a_loud_non_finding",
    "check_queues": "test_queues_reports_unreachable_as_a_loud_non_finding",
    "check_faults": "test_a_registry_fault_is_reported_with_its_metadata_path",
    "check_load": "test_validate_fires_on_a_workflow_dagu_validate_rejects",
    "check_queue_names": "test_an_undeclared_queue_name_is_a_finding",
    "check_literal": "test_check_literal_itself_reports_a_finding",
    "check_stale": "test_a_stale_entry_is_reported_without_prune",
    "check_ageing": "test_run_output_fires_on_a_project_whose_runs_stopped_ageing_out",
    "check_projection": "test_a_link_pointing_at_another_project_is_still_a_fault",
    "check_dag_names": "test_a_workflow_name_holding_a_dot_is_a_finding",
    "check_schema": "test_an_entry_from_a_newer_devman_is_reported",
    "check_generation": "test_plane_projection_records_must_match_active_generation",
    "check_handlers": "test_handlers_fires_on_a_workflow_that_replaces_the_exit_handler",
    "check_cross_repo": "test_cross_repo_fires_on_a_parent_holding_its_own_project_dir",
    "check_fanout": "test_fanout_fires_on_two_children_with_no_stated_bound",
    "check_writes": "test_tier_free_outside_agent_surface_is_a_finding",
    "check_trigger_targets": "test_trigger_target_fires_on_a_tombstoned_group",
    "check_duplicate_identity": "test_duplicate_identity_fires_on_two_checkouts_sharing_a_project_name",
    "check_link_drift": "test_link_drift_fires_on_a_dangling_view",
    "check_ledger_stale": "test_ledger_reports_a_project_whose_repository_is_absent",
    "check_universal_skills": "test_universal_skills_fires_on_a_surface_missing_writing",
    "check_local_sources": "test_a_dirty_local_source_is_a_finding_with_its_consumer_count",
    "check_path_inputs": "test_a_path_input_carrying_a_big_dotfile_is_a_finding",
    "check_daemon_shell": "test_daemon_shell_fires_when_shell_leaks_into_a_running_dagu",
    "check_reload": "test_reload_reports_blocked_as_a_finding_with_the_repair_action",
    "check_watcher": "test_watcher_fires_when_the_supervisor_is_alive_but_nothing_is_running",
}


def _checks_in_main() -> list[str]:
    """Every `check_*` function `doctor.main()` calls, read from its own
    source rather than hand-copied — the "source or projection, never a
    copy" rule (AGENTS.md P2), applied to this guard itself. A `check_*`
    call added anywhere in `main()`'s body is found here whether or not it
    sits behind an `if`, because this walks the parsed source rather than
    running it."""
    tree = ast.parse(inspect.getsource(doctor.main))
    names = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id.startswith("check_")
            and node.func.id not in names
        ):
            names.append(node.func.id)
    return names


def test_every_check_main_calls_is_accounted_for_at_all():
    """A canary for the guard itself: if `main()` stops calling any
    `check_*` function at all, or this parser stops finding them, the
    parametrised test below would silently collect zero cases rather than
    failing — pytest does not fail an empty parametrize by default."""
    assert len(_checks_in_main()) >= 20


@pytest.mark.parametrize("check_name", sorted(_checks_in_main()))
def test_every_check_main_calls_has_a_firing_test_or_is_informational(check_name):
    if check_name in INFORMATIONAL:
        return
    assert check_name in FIRING_TESTS, (
        f"{check_name} is called by doctor.main() and has no entry in "
        f"FIRING_TESTS (tests/unit/test_doctor.py). Add a test that makes "
        f"it report a non-ok status (a `!!` finding, or a loud `..`/`EMPTY`), "
        f'then add "{check_name}": "<your test\'s name>" to FIRING_TESTS — '
        f"or, if it is deliberately informational and has no reachable `!!` "
        f'branch, add "{check_name}": "<one-line reason>" to INFORMATIONAL '
        f"instead."
    )
    test_name = FIRING_TESTS[check_name]
    module = sys.modules[__name__]
    assert hasattr(module, test_name), (
        f"FIRING_TESTS[{check_name!r}] names {test_name!r}, which does not "
        f"exist in {__name__}. Fix the name, or write the test."
    )
