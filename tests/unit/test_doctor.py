"""The decisions `doctor` makes itself.

Most of `doctor` is a loop over `Workflow` and `Registry`, and those are tested
where they live. What is here is the rest: the checks that read the machine's own
config, the bounded walk, and the report's own arithmetic.

**Nothing here mocks Dagu's HTTP API.** `check_plane` and `check_queues` read
what a running Dagu reports about itself (E5), and a stub of that API would test
the stub. They belong to `nix/tests/dagu-service.nix`, which runs a real one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from helpers import ORDINARY

from devman import doctor
from devman.link import reconcile
from devman.registry import Registry
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


def test_link_drift_reports_the_reconciler_state(plane, tmp_path):
    overlay = tmp_path / "overlay"
    canonical = overlay / "common/envrc"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("use devenv\n")
    repo = plane.repos / "p"
    plane.add(
        "p",
        links={".envrc": {"canonical": "central", "path": "common/envrc"}},
        overlay=str(overlay),
    )
    reconcile(
        {".envrc": {"canonical": "central", "path": "common/envrc"}},
        overlay=overlay,
        root=repo,
        project="p",
    )
    report = doctor.Report()

    doctor.check_link_drift(report, plane.reg)

    assert report.sections == [("link drift", "ok", ["1 declared links are correct"])]


def test_link_drift_names_a_real_view_as_promote(plane, tmp_path):
    overlay = tmp_path / "overlay"
    repo = plane.repos / "p"
    repo.mkdir(parents=True)
    (repo / ".envrc").write_text("local\n")
    plane.add(
        "p",
        links={".envrc": {"canonical": "central", "path": "common/envrc"}},
        overlay=str(overlay),
    )
    report = doctor.Report()

    doctor.check_link_drift(report, plane.reg)

    assert report.sections[0][0:2] == ("link drift", "!!")
    assert report.sections[0][2] == ["p:.envrc: promote"]


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


# ---------------------------------------------------------------------------
# the codec (§9.2, S-12)


def test_an_unmigrated_projection_is_a_note_and_not_a_fault(plane):
    """Reporting it `!!` would have made every repository on the machine a fault
    for as long as the migration took — 53 of them, none of them broken."""
    plane.add("p", workflows={"check": ORDINARY}, link=False, legacy=True)
    rep = doctor.Report()

    doctor.check_projection(rep, plane.reg)

    status, lines = rep.sections[0][1], rep.sections[0][2]
    assert status == "ok"
    assert "still project under the pre-codec name" in lines[1]
    assert "migrates itself the next time its shell is entered" in lines[2]


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
    """A reload service that timed out leaves both markers behind — `blocked`
    is the one that still matters, and it must not hide behind `pending`."""
    plane.reg.state.mkdir(parents=True, exist_ok=True)
    (plane.reg.state / "reload.pending").write_text("2026-09-12T00:00:00Z\n")
    (plane.reg.state / "reload.blocked").write_text("2026-09-12T00:05:00Z\n")

    rep = doctor.Report()
    doctor.check_reload(rep, plane.reg)

    assert rep.sections[0][1] == "!!"


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
