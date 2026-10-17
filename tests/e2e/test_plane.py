"""End to end: a real Dagu 2.20.1 server, a compiled project, one emitted event.

The server listens on free loopback ports with its own DAGU_HOME and state
root. Nothing here touches the live Dagu on port 8080.
"""

import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import BASH, Plane
from typer.testing import CliRunner

from devman import doctor
from devman.cli import app
from devman.compile import compile
from devman.paths import Paths
from devman.router import Event, emit

pytestmark = pytest.mark.e2e

TERMINAL = {"succeeded", "failed", "aborted", "partially_succeeded"}


def free_ports(first: int = 18110) -> tuple[int, int]:
    """A free (http, grpc) pair, scanning up from 18110 / 51110."""
    for offset in range(200):
        pair = (first + offset, first + 33000 + offset)
        socks = []
        try:
            for port in pair:
                s = socket.socket()
                s.bind(("127.0.0.1", port))
                socks.append(s)
            return pair
        except OSError:
            continue
        finally:
            for s in socks:
                s.close()
    raise RuntimeError("no free loopback ports")


def api(port: int, path: str) -> dict | None:
    try:
        url = f"http://127.0.0.1:{port}/api/v1/{path}"
        with urllib.request.urlopen(url, timeout=3) as resp:
            return json.load(resp)
    except (urllib.error.URLError, OSError, ValueError):
        return None


def wait_for(fn, seconds: float = 30.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.2)
    return None


@pytest.fixture
def server(plane: Plane, monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    http, grpc = free_ports()
    state = plane.paths.state
    state.mkdir(parents=True, exist_ok=True)
    plane.paths.dagu_config.write_text(
        "host: 127.0.0.1\n"
        f"port: {http}\n"
        f"coordinator: {{host: 127.0.0.1, port: {grpc}}}\n"
        "auth: {mode: none}\n"
        "skip_examples: true\n"
        "dag_discovery: {recursive: true, symlinks: false}\n"
        f"paths: {{dags_dir: {state}/dags, base_config: {state}/base.yaml}}\n"
        "queues: {enabled: true, config: [{name: light, max_concurrency: 4},"
        " {name: normal, max_concurrency: 2}, {name: heavy, max_concurrency: 1}]}\n"
    )
    # A stand-in for `devenv`: it logs its arguments and exits with the code in
    # the file `devenv-exit`. The server and its children find it first.
    fake_bin = plane.root / "e2e-bin"
    fake_bin.mkdir()
    (fake_bin / "devenv").write_text(
        f'#!{BASH}\necho "$*" >> {plane.root}/devenv.log\n'
        f"exit $(cat {plane.root}/devenv-exit)\n"
    )
    (fake_bin / "devenv").chmod(0o755)
    (plane.root / "devenv-exit").write_text("0")
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    log = plane.root / "server.log"
    proc = None
    try:
        with log.open("w") as out:
            proc = subprocess.Popen(
                ["dagu", "--config", str(plane.paths.dagu_config), "start-all"],
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        assert wait_for(lambda: api(http, "dag-runs") is not None), log.read_text()
        yield http
    finally:
        if proc is not None:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    proc.wait(10)
                    break
                except subprocess.TimeoutExpired:
                    continue


def workflow(out: Path) -> str:
    return (
        "queue: light\nsteps:\n  - name: s\n    script: |\n"
        f'      printf \'%s|%s|%s\' "$DEVMAN_EVENT" "$DEVMAN_SUBJECT"'
        f' "$(date +%s.%N)" > {out}\n'
    )


def test_an_event_becomes_a_successful_run(plane: Plane, server: int):
    out, plain = plane.root / "check.out", plane.root / "plain.out"
    plane.library("check", workflow(out))
    plane.library("plain", workflow(plain))
    on = '[[alpha.on]]\nevent = "save"\nmatch = "**/*.py"\nrun = "check"\n'
    plane.add_project("alpha", '"check", "plain"', on)
    (plane.project_dir("alpha") / ".git").mkdir()  # the guard needs a marker
    assert compile(plane.paths) == 0

    began = time.time()
    outcome = emit(plane.paths, Event("save", "alpha", ("src/a.py",), "e2e"))
    assert outcome.code == 0, outcome.lines
    (match,) = outcome.record["matches"]

    def finished():
        run = api(server, f"dag-runs/alpha.check/{match['run_id']}")
        if run and run["dagRunDetails"]["statusLabel"] in TERMINAL:
            return run["dagRunDetails"]
        return None

    run = wait_for(finished)
    assert run is not None, "the run did not finish in 30 s"
    assert run["statusLabel"] == "succeeded"
    assert "devman.event=save" in run["labels"]
    event, subject, started = out.read_text().split("|")
    assert (event, subject) == ("save", "src/a.py")
    latency = float(started) - began
    print(f"event-to-step-start latency: {latency:.2f} s")
    assert latency < 30

    # A run the router did not start (a schedule, `dagu start`) reads the
    # declared defaults: both names are empty, not unset.
    file = plane.dag("alpha", "plain")
    subprocess.run(
        ["dagu", "--config", str(plane.paths.dagu_config), "start", str(file)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    event, subject, _ = plain.read_text().split("|")
    assert (event, subject) == ("", "")


def test_run_then_status_shows_the_result(plane: Plane, server: int):
    plane.library("check", workflow(plane.root / "check.out"))
    plane.add_project("alpha", '"check"')
    (plane.project_dir("alpha") / ".git").mkdir()
    assert compile(plane.paths) == 0
    runner = CliRunner()
    res = runner.invoke(app, ["run", "check", "--project", "alpha"], env=plane.env)
    assert res.exit_code == 0, res.output

    def succeeded():
        res = runner.invoke(app, ["status", "alpha", "--json"], env=plane.env)
        run = json.loads(res.output)["project"]["workflows"][0]["last_run"]
        return run if run and run["status"] in TERMINAL else None

    run = wait_for(succeeded)
    assert run is not None, "the run did not finish in 30 s"
    assert run["status"] == "succeeded"
    info = json.loads(
        runner.invoke(app, ["status", "alpha", "--json"], env=plane.env).output
    )
    assert info["project"]["dagu"] == "reachable"
    assert doctor.check_api(plane.paths) is None


def runs_of(server: int, dag: str) -> list[dict]:
    return (api(server, f"dag-runs?name={dag}&limit=20") or {}).get("dagRuns", [])


def settle(server: int, dag: str, run_id: str | None = None, known=()):
    """Wait for a run to finish. Return its details, or None after 30 s.

    With no `run_id`, any finished run whose ID is not in `known` counts. Dagu
    lists runs by start second, so "the newest" is not safe within one second.
    """

    def done():
        if run_id:
            got = api(server, f"dag-runs/{dag}/{run_id}")
            found = [got["dagRunDetails"]] if got else []
        else:
            found = [r for r in runs_of(server, dag) if r["dagRunId"] not in known]
        done = [r for r in found if r["statusLabel"] in TERMINAL]
        return done[0] if done else None

    return wait_for(done)


def events_of(plane: Plane, event: str) -> list[dict]:
    if not plane.paths.events.exists():
        return []
    lines = [json.loads(ln) for ln in plane.paths.events.read_text().splitlines()]
    return [ln for ln in lines if ln["event"] == event]


def library_plane(plane: Plane, on: str = "") -> Path:
    plane.seed()
    plane.add_project("alpha", '"check", "test"', on)
    project = plane.project_dir("alpha")
    (project / ".git").mkdir()
    assert compile(plane.paths) == 0
    return project


def stderr_of(server: int, dag: str, run_id: str) -> str:
    run = api(server, f"dag-runs/{dag}/{run_id}")["dagRunDetails"]
    return Path(run["nodes"][0]["stderr"]).read_text()


def run_cli(plane: Plane, workflow: str) -> str:
    res = CliRunner().invoke(
        app, ["run", workflow, "--project", "alpha"], env=plane.env
    )
    assert res.exit_code == 0, res.output
    return res.output.split("run=")[1].strip()


def test_a_library_check_runs_and_emits_done(plane: Plane, server: int):
    library_plane(plane)
    run_id = run_cli(plane, "check")
    run = settle(server, "alpha.check", run_id)
    assert run is not None and run["statusLabel"] == "succeeded"
    assert "devman.event=manual" in run["labels"]
    assert (plane.root / "devenv.log").read_text() == "tasks run -v base:check\n"
    (done,) = wait_for(lambda: events_of(plane, "done")) or [None]
    assert done["project"] == "alpha"
    assert done["subjects"] == ["check"]
    assert done["source"] == "dagu"


def test_a_failed_run_names_the_task_and_emits_failed(plane: Plane, server: int):
    library_plane(plane)
    (plane.root / "devenv-exit").write_text("1")
    run_id = run_cli(plane, "check")
    run = settle(server, "alpha.check", run_id)
    assert run is not None and run["statusLabel"] == "failed"
    assert "devman.task: task base:check failed" in stderr_of(
        server, "alpha.check", run_id
    )
    (failed,) = wait_for(lambda: events_of(plane, "failed")) or [None]
    assert failed["subjects"] == ["check"]
    assert not events_of(plane, "done")


def test_a_done_event_starts_the_next_workflow(plane: Plane, server: int):
    on = '[[alpha.on]]\nevent = "done"\nmatch = "check"\nrun = "test"\n'
    library_plane(plane, on)
    run_cli(plane, "check")
    assert wait_for(lambda: settle(server, "alpha.test")) is not None
    log = (plane.root / "devenv.log").read_text()
    assert log.splitlines()[0] == "tasks run -v base:check"
    assert "tasks run -v base:test" in log


def test_a_handler_problem_never_changes_the_run(plane: Plane, server: int):
    library_plane(plane)
    slow = plane.root / "slow-devman"
    slow.write_text(f"#!{BASH}\nsleep 10\nexit 1\n")
    slow.chmod(0o755)
    env = {**plane.env, "DEVMAN_BIN": str(slow)}
    assert compile(Paths.from_env(env), None, True) == 0
    began = time.monotonic()
    run_id = run_cli(plane, "check")
    run = settle(server, "alpha.check", run_id)
    assert run is not None and run["statusLabel"] == "succeeded"
    assert time.monotonic() - began < 8


def start(plane: Plane, project: str, workflow: str) -> None:
    """A run that does not pass the router, as a schedule does."""
    subprocess.run(
        ["dagu", "--config", str(plane.paths.dagu_config), "start"]
        + [str(plane.dag(project, workflow))],
        capture_output=True,
        timeout=60,
        check=False,
    )


def test_the_guard_fails_a_run_in_a_vanished_checkout(plane: Plane, server: int):
    project = library_plane(plane)
    plane.own("alpha", "plain", "queue: light\nsteps:\n  - run: echo ran\n")
    plane.paths.projects_toml.write_text(
        plane.paths.projects_toml.read_text().replace(
            'take = ["check", "test"]', 'take = ["check", "test", "plain"]'
        )
    )
    assert compile(plane.paths) == 0
    away = project.with_name("alpha-away")
    project.rename(away)
    for flow in ("check", "plain"):
        start(plane, "alpha", flow)
        run = settle(server, f"alpha.{flow}")
        assert run is not None and run["statusLabel"] == "failed", flow
        text = stderr_of(server, f"alpha.{flow}", run["dagRunId"])
        assert "gone (no .git, no .jj)" in text
    # M2: Dagu made an empty directory at the old path. It holds no marker.
    assert project.is_dir() and not (project / ".git").exists()
    assert not (plane.root / "devenv.log").exists()
    # The handler still reports the failure: it does not use the guard.
    assert wait_for(lambda: len(events_of(plane, "failed")) == 2)
    project.rmdir()
    away.rename(project)
    old = {r["dagRunId"] for r in runs_of(server, "alpha.plain")}
    start(plane, "alpha", "plain")
    run = settle(server, "alpha.plain", known=old)
    assert run is not None and run["statusLabel"] == "succeeded"
