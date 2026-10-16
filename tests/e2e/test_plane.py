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
from conftest import Plane
from typer.testing import CliRunner

from devman import doctor
from devman.cli import app
from devman.compile import compile
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
def server(plane: Plane) -> Iterator[int]:
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
        "queues: {enabled: true, config: [{name: light, max_concurrency: 4}]}\n"
    )
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
    assert compile(plane.paths) == 0
    runner = CliRunner()
    res = runner.invoke(app, ["run", "check", "--project", "alpha"], env=plane.env)
    assert res.exit_code == 0, res.output

    def succeeded():
        res = runner.invoke(app, ["status", "alpha", "--json"], env=plane.env)
        run = json.loads(res.output)["workflows"][0]["last_run"]
        return run if run and run["status"] in TERMINAL else None

    run = wait_for(succeeded)
    assert run is not None, "the run did not finish in 30 s"
    assert run["status"] == "succeeded"
    info = json.loads(
        runner.invoke(app, ["status", "alpha", "--json"], env=plane.env).output
    )
    assert info["dagu"] == "reachable"
    assert doctor.check_api(plane.paths) is None
