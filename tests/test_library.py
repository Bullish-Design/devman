"""The seed library compiles, and its actions all exist (PLAN Stage 7)."""

import shutil

import yaml
from conftest import FIXTURES, Plane

from devman import doctor
from devman.compile import compile

TAKEN = '"check", "test", "format", "release"'


def test_the_seed_library_compiles_for_a_project(plane: Plane):
    plane.seed()
    plane.add_project("alpha", TAKEN)
    (plane.project_dir("alpha") / ".git").mkdir()
    assert compile(plane.paths) == 0
    flows = plane.record()["projects"]["alpha"]["workflows"]
    assert sorted(flows) == ["check", "format", "release", "test"]
    assert doctor.check_actions(plane.paths) is None


def test_the_compiled_file_runs_the_guard_and_the_action(plane: Plane):
    plane.seed()
    plane.add_project("alpha", '"check"')
    assert compile(plane.paths) == 0
    doc = yaml.safe_load(plane.dag("alpha", "check").read_text())
    assert doc["shell"] == plane.env["DEVMAN_GUARD"]
    assert doc["steps"] == [{"action": "devman.task", "with": {"task": "base:check"}}]
    base = yaml.safe_load(plane.paths.base_out.read_text())
    assert "setsid -f" in base["handler_on"]["exit"]["command"]
    assert plane.env["DEVMAN_BIN"] in base["handler_on"]["exit"]["command"]
    assert base["hist_retention_days"] == 7
    assert "queue" not in base


def test_overlay_base_cannot_change_required_behavior(plane: Plane):
    plane.seed()
    plane.add_project("alpha", '"check"')
    editable = plane.paths.library / "base.yaml"
    editable.parent.mkdir(parents=True, exist_ok=True)
    editable.write_text("{}\n")

    assert compile(plane.paths) == 0
    base = yaml.safe_load(plane.paths.base_out.read_text())
    assert "exit" in base["handler_on"]
    assert "devman.task" in base["actions"]
    assert "queue" not in base


def test_release_runs_the_test_first(plane: Plane):
    plane.seed()
    doc = yaml.safe_load((plane.paths.library / "workflows/release.yaml").read_text())
    assert [s["with"]["task"] for s in doc["steps"]] == ["base:test", "release:build"]
    assert doc["type"] == "chain"


def test_the_agent_example_commits_before_it_removes_the_work_tree():
    text = (FIXTURES / "library/examples/agent-task.yaml").read_text()
    doc = yaml.safe_load(text)
    actions = [s.get("action", "run") for s in doc["steps"]]
    assert actions == [
        "git.worktree.add",
        "harness.run",
        "run",
        "human.task",
        "git.worktree.remove",
    ]
    commit = doc["steps"][2]["run"]
    assert "git commit" in commit
    assert "exit 1" in commit  # an agent that changed nothing must fail
    assert "max-budget-usd" in doc["steps"][1]["with"]
    assert "force" not in doc["steps"][4]["with"]


def test_the_agent_example_compiles_as_a_project_workflow(plane: Plane):
    text = (FIXTURES / "library/examples/agent-task.yaml").read_text()
    plane.seed()
    plane.add_project("alpha", '"check"')
    plane.own("alpha", "agent-task", text)
    assert compile(plane.paths) == 0
    assert "agent-task" in plane.record()["projects"]["alpha"]["workflows"]


def test_compile_never_takes_the_examples(plane: Plane):
    plane.seed()
    shutil.copytree(FIXTURES / "library/examples", plane.paths.library / "examples")
    plane.add_project("alpha", '"agent-task"')
    assert compile(plane.paths) != 0
