"""The seed library compiles, and its actions all exist (PLAN Stage 7)."""

import yaml
from conftest import Plane

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


def test_release_runs_the_test_first(plane: Plane):
    plane.seed()
    doc = yaml.safe_load((plane.paths.library / "workflows/release.yaml").read_text())
    assert [s["with"]["task"] for s in doc["steps"]] == ["base:test", "release:build"]
    assert doc["type"] == "chain"
