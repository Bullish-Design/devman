import json
import os
from pathlib import Path

import rest
from conftest import Plane
from typer.testing import CliRunner

from devman.cli import app
from devman.compile import compile
from devman.router import Event, emit

ON = '[[alpha.on]]\nevent = "land"\nmatch = "main"\nrun = "check"\n'


def setup(plane: Plane, port: int | None) -> None:
    plane.library("check", "queue: heavy\nschedule: '0 3 * * *'\nsteps:\n  - run: x\n")
    plane.library("test")
    plane.add_project("alpha", '"check", "test"', ON)
    assert compile(plane.paths) == 0
    if port:
        plane.paths.dagu_config.write_text(
            f"host: 127.0.0.1\nport: {port}\nqueues: "
            "{enabled: true, config: [{name: light, max_concurrency: 1},"
            " {name: heavy, max_concurrency: 1}]}\n"
        )


def cli(plane: Plane, *args: str, cwd: Path | None = None):
    old = Path.cwd()
    os.chdir(cwd or plane.root)
    try:
        return CliRunner().invoke(app, list(args), env=plane.env)
    finally:
        os.chdir(old)


def test_status_json_has_the_documented_shape(plane: Plane):
    with rest.serve([rest.run("alpha.check", "failed")]) as port:
        setup(plane, port)
        res = cli(plane, "status", "alpha", "--json")
    assert res.exit_code == 0
    info = json.loads(res.output)
    assert info["project"] == "alpha"
    assert info["dagu"] == "reachable"
    assert info["compile"]["status"] == "ok"
    check, test = info["workflows"]
    assert check["origin"] == "library"
    assert check["queue"] == "heavy"
    assert check["schedule"] == "0 3 * * *"
    assert check["triggers"] == [{"event": "land", "match": ["main"], "exclude": []}]
    assert check["last_run"]["status"] == "failed"
    assert check["last_run"]["run_id"] == "r1"
    assert test["last_run"] is None
    assert test["queue"] == "light"  # the base default


def test_status_text_from_the_project_directory(plane: Plane):
    with rest.serve([rest.run("alpha.check")]) as port:
        setup(plane, port)
        res = cli(plane, "status", cwd=plane.project_dir("alpha"))
    assert res.exit_code == 0
    assert "alpha" in res.output
    assert "check  library  queue=heavy" in res.output
    assert "last run: succeeded" in res.output
    assert "triggers: land main" in res.output


def test_status_with_dagu_down_still_exits_0(plane: Plane):
    setup(plane, 1)  # nothing listens on port 1
    res = cli(plane, "status", "alpha")
    assert res.exit_code == 0
    assert "Dagu unreachable" in res.output
    info = json.loads(cli(plane, "status", "alpha", "--json").output)
    assert info["dagu"] == "unreachable"
    assert info["workflows"][0]["last_run"] is None


def test_status_without_a_project_lists_every_project(plane: Plane):
    setup(plane, None)
    res = cli(plane, "status")
    assert res.exit_code == 0
    assert res.output.startswith("alpha")
    assert "workflows: 2" in res.output
    listing = json.loads(cli(plane, "status", "--json").output)
    assert [p["project"] for p in listing] == ["alpha"]


def test_status_shows_a_stale_refusal(plane: Plane):
    setup(plane, 1)
    plane.own("alpha", "check", "env: {A: b}\nsteps: []\n")
    assert compile(plane.paths) == 1
    out = cli(plane, "status", "alpha").output
    assert "stale" in out
    assert "top-level env is set by devman" in out


def test_status_unknown_project_exits_2(plane: Plane):
    setup(plane, None)
    assert cli(plane, "status", "nope").exit_code == 2


def test_show_prints_both_paths_and_the_file(plane: Plane):
    setup(plane, None)
    res = cli(plane, "show", "check", "--project", "alpha")
    assert res.exit_code == 0
    lines = res.output.splitlines()
    assert lines[0] == f"# compiled: {plane.dag('alpha', 'check')}"
    assert lines[1] == f"# source: {plane.paths.library / 'workflows/check.yaml'}"
    assert plane.dag("alpha", "check").read_text() in res.output


def test_show_unknown_workflow_exits_2(plane: Plane):
    setup(plane, None)
    assert cli(plane, "show", "nope", "--project", "alpha").exit_code == 2


def test_run_is_a_manual_event_with_an_implicit_match(plane: Plane, fake: Path):
    setup(plane, None)
    res = cli(plane, "run", "test", "K=v", cwd=plane.project_dir("alpha"))
    assert res.exit_code == 0
    argv = fake.read_text().split("\x1f")
    assert "devman.event=manual" in argv
    assert "DEVMAN_EVENT=manual" in argv
    assert "DEVMAN_SUBJECT=test" in argv
    assert "K=v" in argv
    assert str(plane.dag("alpha", "test")) in argv
    line = json.loads(plane.paths.events.read_text().splitlines()[-1])
    assert line["source"] == "manual"
    assert line["matches"][0]["workflow"] == "test"  # no `on` entry names it


def test_run_unknown_workflow_exits_2(plane: Plane, fake: Path):
    setup(plane, None)
    res = cli(plane, "run", "nope", "--project", "alpha")
    assert res.exit_code == 2
    assert "no workflow nope" in res.output
    assert not fake.exists()


def test_run_on_a_stale_project_warns_and_runs_the_old_file(plane: Plane, fake: Path):
    setup(plane, None)
    plane.own("alpha", "check", "env: {A: b}\nsteps: []\n")
    assert compile(plane.paths) == 1
    res = cli(plane, "run", "test", "--project", "alpha")
    assert res.exit_code == 0
    assert "stale" in res.output
    assert fake.exists()


def test_run_refuses_a_reserved_field(plane: Plane, fake: Path):
    setup(plane, None)
    assert cli(plane, "run", "test", "DEVMAN_X=1", "--project", "alpha").exit_code == 2


def test_emit_still_ignores_the_implicit_path(plane: Plane, fake: Path):
    setup(plane, None)
    out = emit(plane.paths, Event("manual", "alpha", ("test",)))
    assert out.record["matches"] == []
