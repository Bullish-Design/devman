"""Command-level regressions for compile state validation (project 048).

Every case uses the isolated `Plane`. Corruption cases start from a successful
full compile when prior files matter, so byte comparisons are meaningful. The
commands run through the public CLI. A nonzero exit is a refusal: the runner
must hold no exception other than the SystemExit that Typer raises.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import Plane
from typer.testing import CliRunner

from devman import watch
from devman.cli import app

runner = CliRunner()

CHECK = "queue: light\nsteps:\n  - name: s\n    run: echo hi\n"
ON_SAVE = (
    '[[alpha.on]]\nevent = "save"\nmatch = "**/*.py"\nexclude = []\nrun = "check"\n'
)


def invoke(plane: Plane, *args: str):
    """Run one command as the service does. Refuse, never crash."""
    result = runner.invoke(app, list(args), env=plane.env)
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"{args} raised {result.exception!r}\n{result.output}"
    )
    return result


def good_compile(plane: Plane, on: str = ON_SAVE) -> Path:
    """One successful full compile with a save entry. Return the DAG file."""
    plane.library("check", CHECK)
    plane.add_project("alpha", '"check"', on)
    result = invoke(plane, "compile")
    assert result.exit_code == 0, result.output
    return plane.dag("alpha", "check")


def record(plane: Plane) -> dict:
    return json.loads(plane.paths.compile_json.read_text())


def rewrite(plane: Plane, doc: dict) -> None:
    plane.paths.compile_json.write_text(json.dumps(doc, indent=2) + "\n")


def published_bytes(plane: Plane) -> dict[Path, bytes]:
    """The bytes compile owns besides state: base and every published DAG."""
    files = {}
    if plane.paths.base_out.exists():
        files[plane.paths.base_out] = plane.paths.base_out.read_bytes()
    if plane.paths.dags.exists():
        for file in sorted(plane.paths.dags.rglob("*.yaml")):
            files[file] = file.read_bytes()
    return files


def last_event(plane: Plane) -> dict:
    return json.loads(plane.paths.events.read_text().splitlines()[-1])


def assert_state_error(plane: Plane, result, code: int, field: str) -> None:
    assert result.exit_code == code, result.output
    assert field in result.output, result.output
    assert "ok   compile clean" not in result.output


def test_missing_state_is_an_initial_condition(plane: Plane, fake: Path):
    """No compile.json: a full compile starts fresh; readers name it."""
    good_compile(plane)
    plane.paths.compile_json.unlink()
    fresh = invoke(plane, "compile")
    assert fresh.exit_code == 0, fresh.output
    assert record(plane)["version"] == 2
    assert record(plane)["global"]["status"] == "ok"

    plane.paths.compile_json.unlink()

    status = invoke(plane, "status")
    doctor = invoke(plane, "doctor")
    show = invoke(plane, "show", "check", "--project", "alpha")

    assert status.exit_code == 2, status.output
    assert "is missing; run devman compile" in status.output
    assert doctor.exit_code == 1, doctor.output
    assert "FAIL compile clean:" in doctor.output
    assert "is missing; run devman compile" in doctor.output
    assert show.exit_code == 2, show.output


def test_broken_json_refuses_every_command_and_changes_nothing(
    plane: Plane, fake: Path
):
    good_compile(plane)
    before = published_bytes(plane)
    plane.paths.compile_json.write_text("{ not json\n")

    compile_result = invoke(plane, "compile")
    status = invoke(plane, "status")
    doctor = invoke(plane, "doctor")

    assert compile_result.exit_code == 1, compile_result.output
    assert "compile.json" in compile_result.output
    assert_state_error(plane, status, 2, "invalid JSON")
    assert doctor.exit_code == 1, doctor.output
    assert "FAIL compile clean:" in doctor.output
    assert "invalid JSON" in doctor.output
    assert plane.paths.compile_json.read_text() == "{ not json\n", (
        "a refused compile must not replace malformed state"
    )
    assert published_bytes(plane) == before, "a refused compile must write nothing"


@pytest.mark.parametrize("text", ["[]", "[1]", "42", '"x"'])
def test_truthy_non_mapping_state_refuses_cleanly(plane: Plane, fake: Path, text: str):
    """`[]` and `[1]` share one wrong type. `[1]` proves the guard."""
    good_compile(plane)
    before = published_bytes(plane)
    plane.paths.compile_json.write_text(text)

    compile_result = invoke(plane, "compile")
    status = invoke(plane, "status")
    show = invoke(plane, "show", "check", "--project", "alpha")
    doctor = invoke(plane, "doctor")
    emit = invoke(plane, "emit", "save", "--project", "alpha", "--subject", "a.py")
    run = invoke(plane, "run", "check", "--project", "alpha")

    assert compile_result.exit_code == 1, compile_result.output
    assert published_bytes(plane) == before, "a refused compile must write nothing"
    assert plane.paths.compile_json.read_text() == text, (
        "a refused compile must not replace malformed state"
    )
    assert_state_error(plane, status, 2, "the top-level document must be a mapping")
    assert_state_error(plane, show, 2, "the top-level document must be a mapping")
    assert doctor.exit_code == 1, doctor.output
    assert "FAIL compile clean:" in doctor.output
    assert "the top-level document must be a mapping" in doctor.output
    assert emit.exit_code == 2, emit.output
    assert last_event(plane)["refusal"].startswith("compile.json")
    assert run.exit_code == 2, run.output
    assert not (plane.root / "dagu.log").exists(), "no enqueue may happen"


def test_string_global_reasons_cannot_report_green(plane: Plane, fake: Path):
    good_compile(plane)
    doc = record(plane)
    doc["global"]["reasons"] = "chmod -R 000 ~/"
    rewrite(plane, doc)

    status = invoke(plane, "status")
    doctor = invoke(plane, "doctor")

    assert_state_error(plane, status, 2, "global.reasons must be a list of strings")
    assert "ok compile" not in status.output
    assert doctor.exit_code == 1, doctor.output
    assert "FAIL compile clean:" in doctor.output
    assert "global.reasons must be a list of strings" in doctor.output


def test_malformed_global_fields_are_named(plane: Plane, fake: Path):
    good_compile(plane)
    good = json.loads(json.dumps(record(plane)))

    doc = json.loads(json.dumps(good))
    del doc["global"]["at"]
    rewrite(plane, doc)
    assert_state_error(plane, invoke(plane, "status"), 2, "global.at is required")
    doctor = invoke(plane, "doctor")
    assert "FAIL compile clean:" in doctor.output
    assert "global.at is required" in doctor.output

    doc = json.loads(json.dumps(good))
    doc["global"]["successful_input_sha256"] = 42
    rewrite(plane, doc)
    assert_state_error(
        plane, invoke(plane, "status"), 2, "global.successful_input_sha256"
    )
    doctor = invoke(plane, "doctor")
    assert "FAIL compile clean:" in doctor.output
    assert (
        "global.successful_input_sha256 must be a 64-character lowercase"
        " sha256 string or null" in doctor.output
    )


def test_boolean_version_is_not_a_valid_state_version(plane: Plane, fake: Path):
    good_compile(plane)
    doc = record(plane)
    doc["version"] = True
    rewrite(plane, doc)
    assert_state_error(
        plane, invoke(plane, "status"), 2, "version must be integer 1 or 2"
    )
    doctor = invoke(plane, "doctor")
    assert "FAIL compile clean:" in doctor.output
    assert "version must be integer 1 or 2" in doctor.output


def test_null_project_record_does_not_raise_anywhere(plane: Plane, fake: Path):
    good_compile(plane)
    doc = record(plane)
    doc["projects"]["alpha"] = None
    rewrite(plane, doc)

    status = invoke(plane, "status")
    show = invoke(plane, "show", "check", "--project", "alpha")
    emit = invoke(plane, "emit", "save", "--project", "alpha", "--subject", "a.py")
    doctor = invoke(plane, "doctor")

    assert_state_error(plane, status, 2, "projects.alpha must be a mapping")
    assert_state_error(plane, show, 2, "projects.alpha must be a mapping")
    assert_state_error(plane, emit, 2, "projects.alpha must be a mapping")
    assert last_event(plane)["refusal"].startswith("compile.json")
    assert not (plane.root / "dagu.log").exists(), "no enqueue may happen"
    assert doctor.exit_code == 1, doctor.output
    assert "FAIL compile clean:" in doctor.output
    assert "projects.alpha must be a mapping" in doctor.output
    assert watch.save_projects(plane.paths) == {}
    targets = watch.targets(plane.paths)
    assert plane.paths.overlay in targets.shallow, "the overlay stays watched"
    assert watch.classify(
        plane.paths, [str(plane.paths.overlay / "projects.toml")]
    ) == (
        True,
        {},
    )


def test_null_workflow_record_does_not_raise_anywhere(plane: Plane, fake: Path):
    good_compile(plane)
    doc = record(plane)
    doc["projects"]["alpha"]["workflows"]["check"] = None
    rewrite(plane, doc)

    status = invoke(plane, "status")
    show = invoke(plane, "show", "check", "--project", "alpha")
    emit = invoke(plane, "emit", "save", "--project", "alpha", "--subject", "a.py")
    doctor = invoke(plane, "doctor")

    assert_state_error(
        plane, status, 2, "projects.alpha.workflows.check must be a mapping"
    )
    assert_state_error(
        plane, show, 2, "projects.alpha.workflows.check must be a mapping"
    )
    assert_state_error(
        plane, emit, 2, "projects.alpha.workflows.check must be a mapping"
    )
    assert not (plane.root / "dagu.log").exists(), "no enqueue may happen"
    assert doctor.exit_code == 1, doctor.output
    assert "FAIL compile clean:" in doctor.output
    assert "projects.alpha.workflows.check must be a mapping" in doctor.output


def test_nested_project_record_fields_are_validated(plane: Plane, fake: Path):
    good_compile(plane)
    good = record(plane)
    doc = json.loads(json.dumps(good))
    doc["projects"]["alpha"]["on"][0]["match"] = "main"
    rewrite(plane, doc)
    assert_state_error(plane, invoke(plane, "status"), 2, "projects.alpha.on[0].match")

    good["projects"]["alpha"]["workflows"]["check"]["sha256"] = "short"
    rewrite(plane, good)
    assert_state_error(
        plane,
        invoke(plane, "status"),
        2,
        "projects.alpha.workflows.check.sha256 must be a 64-character lowercase"
        " sha256 string",
    )


def test_a_green_project_needs_a_real_path(plane: Plane, fake: Path):
    good_compile(plane)
    doc = record(plane)
    doc["projects"]["alpha"]["path"] = None
    rewrite(plane, doc)
    assert_state_error(
        plane,
        invoke(plane, "status"),
        2,
        "projects.alpha.path must be a nonempty string when status is ok",
    )


def test_valid_version_one_state_upgrades_through_a_full_compile(
    plane: Plane, fake: Path
):
    good_compile(plane)
    dag_file = plane.dag("alpha", "check")
    old_dag = dag_file.read_bytes()
    old_digest = record(plane)["projects"]["alpha"]["workflows"]["check"]["sha256"]
    doc = record(plane)
    doc["version"] = 1
    doc.pop("global")
    doc["devman"] = "0.9.0"
    doc["orphans"] = []
    rewrite(plane, doc)

    assert_state_error(
        plane, invoke(plane, "status", "alpha"), 1, "full compile is required"
    )
    doctor = invoke(plane, "doctor")
    assert "FAIL compile clean:" in doctor.output

    result = invoke(plane, "compile")
    assert result.exit_code == 0, result.output
    upgraded = record(plane)
    assert upgraded["version"] == 2
    assert upgraded["global"]["status"] == "ok"
    assert upgraded["global"]["successful_input_sha256"]
    assert upgraded["projects"]["alpha"]["status"] == "ok"
    # Version 1 records survive the upgrade: same file, same digest.
    assert dag_file.read_bytes() == old_dag
    assert upgraded["projects"]["alpha"]["workflows"]["check"]["sha256"] == old_digest
    assert invoke(plane, "status", "alpha").exit_code == 0


def test_a_refused_full_compile_recovery_cycle(plane: Plane, fake: Path):
    """A global refusal stays visible; a full green compile clears it."""
    good_compile(plane)
    first = record(plane)["global"]["successful_input_sha256"]
    source = plane.paths.library / "workflows" / "check.yaml"

    source.write_text(CHECK.replace("queue: light", "queue: ghost"))
    refused = invoke(plane, "compile")
    assert refused.exit_code == 1, refused.output
    assert "alpha" in record(plane)["global"]["reasons"]
    assert record(plane)["global"]["successful_input_sha256"] == first
    assert_state_error(plane, invoke(plane, "status", "alpha"), 1, "refused")
    assert "FAIL compile clean" in invoke(plane, "doctor").output

    source.write_text(CHECK.replace("echo hi", "echo changed"))
    recovered = invoke(plane, "compile")
    assert recovered.exit_code == 0, recovered.output
    state = record(plane)
    assert state["global"]["status"] == "ok"
    assert state["global"]["reasons"] == []
    assert state["global"]["successful_input_sha256"] != first
    assert invoke(plane, "status", "alpha").exit_code == 0
    assert "ok   compile clean" in invoke(plane, "doctor").output

    before = plane.paths.compile_json.read_bytes()
    assert invoke(plane, "compile").exit_code == 0
    assert plane.paths.compile_json.read_bytes() == before


def test_emit_refuses_before_enqueue_on_a_missing_state_file(plane: Plane, fake: Path):
    good_compile(plane)
    plane.paths.compile_json.unlink()

    result = invoke(plane, "emit", "save", "--project", "alpha", "--subject", "a.py")

    assert result.exit_code == 2, result.output
    assert "is missing; run devman compile" in last_event(plane)["refusal"]
    assert not (plane.root / "dagu.log").exists(), "no enqueue may happen"
