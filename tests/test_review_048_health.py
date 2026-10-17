"""Public command regressions for review findings F2 to F4."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import yaml
from conftest import Plane
from typer.testing import CliRunner

from devman.cli import app
from devman.paths import Paths

runner = CliRunner()


def invoke(plane: Plane, *args: str):
    return runner.invoke(app, list(args), env=plane.env)


def good_compile(plane: Plane) -> Path:
    plane.library("check", "queue: light\nsteps:\n  - name: s\n    run: echo ok\n")
    plane.add_project("alpha", '"check"')
    assert invoke(plane, "compile").exit_code == 0
    return plane.dag("alpha", "check")


def assert_red_health(plane: Plane, reason: str) -> None:
    status = invoke(plane, "status", "alpha")
    doctor = invoke(plane, "doctor")
    assert status.exit_code == 1, status.output
    assert reason in status.output
    assert doctor.exit_code == 1, doctor.output
    assert "FAIL compile clean:" in doctor.output
    assert reason in doctor.output


def test_bad_packaged_base_keeps_last_good_base_and_reports_red_health(
    plane: Plane, monkeypatch
):
    dag = good_compile(plane)
    old_dag = dag.read_bytes()
    old_base = plane.paths.base_out.read_bytes()
    broken = plane.root / "broken-base.yaml"
    broken.write_text("queue: [\n")
    custom = replace(plane.paths, base_src=broken)
    monkeypatch.setattr(
        Paths,
        "from_env",
        classmethod(lambda cls, env=None: custom),
    )

    result = invoke(plane, "compile")

    assert result.exit_code == 1
    assert dag.read_bytes() == old_dag
    assert plane.paths.base_out.read_bytes() == old_base
    assert_red_health(plane, "base")


def test_bad_manifest_keeps_last_good_dag_and_reports_red_health(plane: Plane):
    dag = good_compile(plane)
    old_dag = dag.read_bytes()
    plane.paths.projects_toml.write_text("[alpha\n")

    result = invoke(plane, "compile")

    assert result.exit_code == 1
    assert dag.read_bytes() == old_dag
    assert_red_health(plane, "projects.toml")


def test_changed_workflow_is_stale_until_full_compile_succeeds(plane: Plane):
    dag = good_compile(plane)
    source = plane.paths.library / "workflows" / "check.yaml"
    source.write_text("queue: light\nsteps:\n  - name: s\n    run: echo changed\n")

    status = invoke(plane, "status", "alpha")
    doctor = invoke(plane, "doctor")

    assert status.exit_code == 1, status.output
    assert "stale" in status.output.lower()
    assert doctor.exit_code == 1, doctor.output
    assert "FAIL compile clean:" in doctor.output
    assert "stale" in doctor.output.lower()
    assert dag.read_text().endswith("echo ok\n")

    compiled = invoke(plane, "compile")
    assert compiled.exit_code == 0, compiled.output
    assert invoke(plane, "status", "alpha").exit_code == 0


def test_partial_compile_does_not_clear_global_staleness(plane: Plane):
    good_compile(plane)
    source = plane.paths.library / "workflows" / "check.yaml"
    source.write_text("queue: light\nsteps:\n  - name: s\n    run: echo changed\n")

    partial = invoke(plane, "compile", "alpha")

    assert partial.exit_code == 1, partial.output
    state = plane.record()
    assert state["global"]["status"] == "refused"
    assert state["global"]["successful_input_sha256"]
    assert invoke(plane, "status", "alpha").exit_code == 1


def test_no_change_full_compile_preserves_compile_json_bytes(plane: Plane):
    good_compile(plane)
    before = plane.paths.compile_json.read_bytes()

    compiled = invoke(plane, "compile")

    assert compiled.exit_code == 0, compiled.output
    assert plane.paths.compile_json.read_bytes() == before


def test_version_one_state_requires_a_full_compile(plane: Plane):
    good_compile(plane)
    state = plane.record()
    state["version"] = 1
    state.pop("global")
    plane.paths.compile_json.write_text(json.dumps(state))

    status = invoke(plane, "status", "alpha", "--json")
    doctor = invoke(plane, "doctor")

    assert status.exit_code == 1
    assert "full compile is required" in status.output
    assert doctor.exit_code == 1
    assert "compile.json version 2" in doctor.output


def test_new_project_workflow_directory_makes_global_health_stale(plane: Plane):
    good_compile(plane)
    (plane.paths.workflows / "orphan").mkdir(parents=True)

    status = invoke(plane, "status", "alpha")
    compiled = invoke(plane, "compile")

    assert status.exit_code == 1
    assert "inputs changed" in status.output
    assert compiled.exit_code == 1
    assert "orphan" in plane.record()["global"]["reasons"]


def test_base_queue_must_be_configured_before_publication(plane: Plane, monkeypatch):
    dag = good_compile(plane)
    old_dag = dag.read_bytes()
    old_base = plane.paths.base_out.read_bytes()
    template = yaml.safe_load(plane.paths.base_src.read_text())
    template["queue"] = "ghost"
    broken = plane.root / "bad-queue-base.yaml"
    broken.write_text(yaml.safe_dump(template))
    custom = replace(plane.paths, base_src=broken)
    monkeypatch.setattr(
        Paths,
        "from_env",
        classmethod(lambda cls, env=None: custom),
    )

    result = invoke(plane, "compile")

    assert result.exit_code == 1
    assert dag.read_bytes() == old_dag
    assert plane.paths.base_out.read_bytes() == old_base
    assert_red_health(plane, "queue")
