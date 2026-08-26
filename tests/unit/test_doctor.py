"""The decisions `doctor` makes itself.

Most of `doctor` is a loop over `Workflow` and `Registry`, and those are tested
where they live. What is here is the rest: the checks that read the machine's own
config, the bounded walk, and the report's own arithmetic.

**Nothing here mocks Dagu's HTTP API.** `check_plane` and `check_queues` read
what a running Dagu reports about itself (E5), and a stub of that API would test
the stub. They belong to `nix/tests/dagu-service.nix`, which runs a real one.
"""

from __future__ import annotations

import pytest
import yaml
from helpers import ORDINARY

from devman import doctor
from devman.workflow import PROJECT_DIR

pytestmark = pytest.mark.unit


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
# the report's own arithmetic


def test_only_findings_are_counted():
    """`..` is a check that could not run, and `ok` is a check that ran. Neither
    is a fault, and the exit code is the finding count."""
    rep = doctor.Report()
    rep.add("a", "ok", ["fine", "also fine"])
    rep.add("b", "..", ["could not run"])
    rep.add("c", "!!", ["one", "two"])
    assert rep.findings == 2


def test_a_check_with_no_lines_still_prints(capsys):
    rep = doctor.Report()
    rep.add("plane", "ok", [])
    rep.print()
    assert capsys.readouterr().out.strip() == "ok  plane"


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
