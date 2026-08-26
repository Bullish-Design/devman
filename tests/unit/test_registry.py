"""Project resolution, the nested-checkout refusal, and the DAG link.

Every case builds a real registry under `tmp_path` (`tests/conftest.py`). No
test here reaches `~/.local/share/devman`, and none runs `git`.
"""

from __future__ import annotations

import json

import pytest
from helpers import ORDINARY, mark_checkout

from devman.registry import Registry, RegistryError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# reading the registry


def test_an_empty_registry_has_no_projects(tmp_path):
    assert Registry(tmp_path / "nothing").projects() == {}


def test_a_half_written_entry_is_skipped(plane):
    """The projection writes `metadata.json` last, precisely so an interrupted
    run leaves an entry that does not match (§9.3). A directory without one, and
    one holding invalid JSON, are both that state."""
    plane.add("good", workflows={"check": ORDINARY})
    (plane.root / "projects" / "no-metadata" / "workflows").mkdir(parents=True)
    half = plane.root / "projects" / "half"
    half.mkdir(parents=True)
    (half / "metadata.json").write_text("{not json")

    assert sorted(plane.reg.projects()) == ["good"]


def test_project_names_every_known_project_when_it_refuses(plane):
    plane.add("alpha")
    plane.add("beta")
    with pytest.raises(RegistryError) as exc:
        plane.reg.project("gamma")
    assert "no project named 'gamma'" in str(exc.value)
    assert "alpha, beta" in str(exc.value)


def test_workflow_names_merges_group_and_local(plane):
    proj = plane.add("p", workflows={"check": ORDINARY}, local=["own"])
    assert proj.workflow_names() == ["check", "own"]


def test_runs_dir_is_the_charters_path_shape(plane):
    proj = plane.add("p")
    assert proj.runs_dir == proj.path / ".devman" / ".runs"


def test_exists_is_false_when_the_repository_is_gone(plane):
    proj = plane.add("p", make_dir=False)
    assert proj.exists is False


# ---------------------------------------------------------------------------
# project_for() — the deepest registered path wins


def test_the_project_root_resolves_to_itself(plane):
    proj = plane.add("p")
    assert plane.reg.project_for(proj.path).name == "p"


def test_a_child_directory_resolves_to_its_project(plane):
    proj = plane.add("p")
    child = proj.path / "src" / "devman"
    child.mkdir(parents=True)
    assert plane.reg.project_for(child).name == "p"


def test_the_deepest_registered_project_wins(plane):
    """Identity is stated rather than inferred from a directory name (§9.1).
    This infers nothing — it compares against paths the repositories recorded."""
    outer = plane.add("outer")
    inner_path = outer.path / "vendor" / "inner"
    plane.add("inner", path=inner_path)
    assert plane.reg.project_for(inner_path).name == "inner"
    assert plane.reg.project_for(inner_path / "sub").name == "inner"


def test_a_directory_outside_every_project_is_refused(plane, tmp_path):
    plane.add("p")
    with pytest.raises(RegistryError) as exc:
        plane.reg.project_for(tmp_path / "elsewhere")
    assert "is not inside a registered repository" in str(exc.value)


# ---------------------------------------------------------------------------
# the nested-checkout refusal — a run that succeeds in the wrong tree


@pytest.mark.parametrize("worktree", [False, True], ids=["clone", "linked-worktree"])
def test_a_checkout_inside_a_registered_one_is_refused(plane, worktree):
    """`git worktree add .worktrees/feature` puts a whole other working tree under
    a registered path, and §9.1 refuses it a duplicate identity — so it never
    registers and "the deepest registered path" answers with the OUTER project.
    Measured: `devman run check` typed inside such a checkout enqueued a run
    against the parent checkout, with nothing said (`STAGE_5_LOG.md`, S3).

    `.git` is a **directory** in an ordinary clone and a **file** in a linked
    worktree, so `_checkout_between()` tests existence and not kind. Both ids
    below are that one contract.
    """
    outer = plane.add("outer")
    inner = mark_checkout(outer.path / ".worktrees" / "feature", worktree=worktree)

    with pytest.raises(RegistryError) as exc:
        plane.reg.project_for(inner)
    message = str(exc.value)
    assert "refusing to resolve 'outer'" in message
    assert str(inner) in message
    assert str(outer.path) in message


def test_the_refusal_names_the_outermost_checkout(plane):
    """The outermost one stands between the caller and the project the registry
    would answer with, so it is the one named."""
    outer = plane.add("outer")
    mid = mark_checkout(outer.path / "mid")
    deep = mark_checkout(mid / "deep")

    with pytest.raises(RegistryError) as exc:
        plane.reg.project_for(deep)
    assert str(mid) in str(exc.value)


def test_a_submodule_is_refused_for_the_same_reason(plane):
    """A submodule answers the `.git` test too, and that is intended: a run
    triggered inside one and executed in the parent checkout is the same
    ambiguity, and the plane makes it loud rather than guessing."""
    outer = plane.add("outer")
    sub = outer.path / "vendor" / "lib"
    sub.mkdir(parents=True)
    (sub / ".git").write_text("gitdir: ../../.git/modules/lib\n")

    with pytest.raises(RegistryError):
        plane.reg.project_for(sub)


def test_the_projects_own_dot_git_is_not_a_nested_checkout(plane):
    """Every registered repository has a `.git`. Only one strictly BELOW the
    registered root is a second checkout."""
    proj = mark_checkout(plane.repos / "p")
    plane.add("p", path=proj)
    assert plane.reg.project_for(proj).name == "p"
    src = proj / "src"
    src.mkdir()
    assert plane.reg.project_for(src).name == "p"


def test_an_explicit_project_bypasses_directory_resolution(plane):
    """`--project` states the target, which is what the refusal above asks for."""
    outer = plane.add("outer")
    mark_checkout(outer.path / "inner")
    assert plane.reg.project("outer").name == "outer"


# ---------------------------------------------------------------------------
# the projected file


def test_workflow_file_resolves_the_projected_yaml(plane):
    proj = plane.add("p", workflows={"check": ORDINARY})
    assert plane.reg.workflow_file(proj, "check").read_text() == ORDINARY


def test_an_unprojected_workflow_is_refused_with_the_list(plane):
    proj = plane.add("p", workflows={"check": ORDINARY})
    with pytest.raises(RegistryError) as exc:
        plane.reg.workflow_file(proj, "nope")
    assert "has no workflow named 'nope'" in str(exc.value)
    assert "it projects: check" in str(exc.value)


def test_projected_files_lists_every_project_and_workflow(plane):
    plane.add("a", workflows={"check": ORDINARY, "fmt": ORDINARY})
    plane.add("b", workflows={"check": ORDINARY})
    got = [(p.name, w) for p, w, _ in plane.reg.projected_files()]
    assert sorted(got) == [("a", "check"), ("a", "fmt"), ("b", "check")]


# ---------------------------------------------------------------------------
# the DAG link — a machine-global name that is not injective


def test_a_correct_link_is_no_fault(plane):
    proj = plane.add("p", workflows={"check": ORDINARY})
    assert plane.reg.dag_link_fault(proj, "check") is None


def test_a_missing_link_says_dagu_cannot_run_it_by_name(plane):
    proj = plane.add("p", workflows={"check": ORDINARY}, link=False)
    fault = plane.reg.dag_link_fault(proj, "check")
    assert "there is no dags/ link" in fault


def test_the_flat_dag_name_is_not_injective(plane):
    """`devman-b` + `check` and `devman` + `b-check` render one name.

    **Asserted through `dag_name()` and never against the string it returns
    today.** The identity codec is the next session's, and this test is its
    regression test: the collision is the fact, and the encoding that produces
    it is not.
    """
    devman = plane.add("devman", workflows={"b-check": ORDINARY})
    devman_b = plane.add("devman-b", workflows={"check": ORDINARY})
    assert plane.reg.dag_name(devman, "b-check") == plane.reg.dag_name(
        devman_b, "check"
    )


def test_the_second_projection_takes_the_first_ones_link(plane):
    """The measured case (`STAGE_5_LOG.md`, S6): `devman run check --project
    devman-b` executed devman's `b-check.yaml`, in devman-b's directory, and
    reported success, while `devman show` printed the file that did not run.

    `dag_link_fault` names the intruder — the link target is what the projection
    wrote, so comparing against it needs no second source.
    """
    devman = plane.add("devman", workflows={"b-check": ORDINARY})
    devman_b = plane.add("devman-b", workflows={"check": ORDINARY})
    # `devman-b`'s projection ran second, so `plane.add` above already pointed
    # the shared name at devman-b. Re-point it at devman's file to make devman
    # the last writer, which is the order S6 measured.
    plane.link("devman-b", "check", "../projects/devman/workflows/b-check.yaml")

    fault = plane.reg.dag_link_fault(devman_b, "check")
    assert fault == "../projects/devman/workflows/b-check.yaml"
    assert plane.reg.dag_link_fault(devman, "b-check") is None


# ---------------------------------------------------------------------------
# unproject() — `doctor --prune` only


def test_unproject_removes_this_projects_projection(plane):
    proj = plane.add("p", workflows={"check": ORDINARY})
    entry = plane.root / "projects" / "p"

    removed = plane.reg.unproject(proj)

    assert not (plane.root / "dags" / "p-check.yaml").is_symlink()
    assert not entry.exists()
    assert len(removed) == 3
    assert plane.reg.projects() == {}


def test_unproject_leaves_a_link_that_points_somewhere_else(plane):
    """`<project>-<workflow>` is ambiguous when one project name is a prefix of
    another, and the link target is not. Removing a link this project does not
    own would take the other project's DAG away with it."""
    devman = plane.add("devman", workflows={"b-check": ORDINARY})
    devman_b = plane.add("devman-b", workflows={"check": ORDINARY})
    plane.link("devman-b", "check", "../projects/devman/workflows/b-check.yaml")
    shared = plane.root / "dags" / "devman-b-check.yaml"

    plane.reg.unproject(devman_b)

    assert shared.is_symlink()
    assert plane.reg.workflow_file(devman, "b-check").exists()


def test_unproject_removes_metadata_last(plane, monkeypatch):
    """A prune interrupted half way must leave an entry `doctor` reports again,
    rather than a directory nothing owns."""
    proj = plane.add("p", workflows={"check": ORDINARY})
    meta = plane.root / "projects" / "p" / "metadata.json"
    seen = []

    real_unlink = type(meta).unlink

    def watched(self, *args, **kwargs):
        seen.append(self.name)
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(type(meta), "unlink", watched)
    plane.reg.unproject(proj)

    assert seen[-1] == "metadata.json"


def test_a_pruned_entry_is_reconstructable(plane):
    """§9.3: the registry is derived, so a wrongly pruned entry restores itself
    the next time that repository's shell is entered. This is that sentence as a
    round trip, and it is what makes `--prune` safe to offer at all."""
    proj = plane.add("p", workflows={"check": ORDINARY})
    before = json.loads((plane.root / "projects" / "p" / "metadata.json").read_text())

    plane.reg.unproject(proj)
    plane.add("p", workflows={"check": ORDINARY}, path=proj.path)

    after = json.loads((plane.root / "projects" / "p" / "metadata.json").read_text())
    assert after == before
    assert plane.reg.dag_link_fault(plane.reg.project("p"), "check") is None
