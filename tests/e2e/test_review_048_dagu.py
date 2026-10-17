"""Real Dagu checks for review findings F1 and F2."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import Plane
from typer.testing import CliRunner

from devman.cli import app
from devman.paths import Paths

runner = CliRunner()

pytestmark = pytest.mark.e2e


def wait_for_done(plane: Plane) -> dict:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if plane.paths.events.exists():
            events = [
                json.loads(line) for line in plane.paths.events.read_text().splitlines()
            ]
            done = [event for event in events if event["event"] == "done"]
            if done:
                return done[-1]
        time.sleep(0.1)
    raise AssertionError("Dagu did not emit a done event")


def run_dag(plane: Plane, dag: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["dagu", "--config", str(plane.paths.dagu_config), "start", str(dag)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_working_dir_override_is_refused_and_last_dag_runs_in_manifest_path(
    plane: Plane,
):
    project = plane.project_dir("alpha")
    (project / ".git").mkdir()
    output = plane.root / "pwd.txt"
    plane.library(
        "check",
        f"queue: light\nsteps:\n  - name: s\n    script: 'pwd > {output}'\n",
    )
    plane.add_project("alpha", '"check"')
    compiled = runner.invoke(app, ["compile"], env=plane.env)
    assert compiled.exit_code == 0, compiled.output
    dag = plane.dag("alpha", "check")
    old_dag = dag.read_bytes()

    wrong = plane.root / "wrong-workdir"
    plane.library(
        "check",
        f"working_dir: {wrong}\nqueue: light\nsteps:\n"
        f"  - name: s\n    script: 'pwd > {output}'\n",
    )
    refused = runner.invoke(app, ["compile"], env=plane.env)

    assert refused.exit_code == 1
    assert dag.read_bytes() == old_dag
    run = run_dag(plane, dag)
    assert run.returncode == 0, run.stdout + run.stderr
    assert output.read_text().strip() == str(project)
    assert not wrong.exists()
    assert wait_for_done(plane)["project"] == "alpha"


def test_bad_base_refusal_keeps_real_dagu_exit_handler(plane: Plane, monkeypatch):
    project = plane.project_dir("alpha")
    (project / ".git").mkdir()
    plane.library("check", "queue: light\nsteps:\n  - name: s\n    run: echo ok\n")
    plane.add_project("alpha", '"check"')
    assert runner.invoke(app, ["compile"], env=plane.env).exit_code == 0
    dag = plane.dag("alpha", "check")
    old_dag = dag.read_bytes()
    old_base = plane.paths.base_out.read_bytes()

    broken = plane.root / "bad-base.yaml"
    broken.write_text("{}\n")
    custom = replace(plane.paths, base_src=broken)
    monkeypatch.setattr(
        Paths,
        "from_env",
        classmethod(lambda cls, env=None: custom),
    )
    refused = runner.invoke(app, ["compile"], env=plane.env)

    assert refused.exit_code == 1
    assert dag.read_bytes() == old_dag
    assert plane.paths.base_out.read_bytes() == old_base

    run = run_dag(plane, dag)
    assert run.returncode == 0, run.stdout + run.stderr
    assert wait_for_done(plane)["subjects"] == ["check"]
