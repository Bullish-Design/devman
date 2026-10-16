import hashlib
import shutil
import subprocess
import time

import pytest
import rest
from conftest import Plane
from typer.testing import CliRunner

from devman import dagu, doctor
from devman.cli import app
from devman.compile import compile

ACTION_FLOW = "steps:\n  - action: devman.task\n    with: {task: base:check}\n"
BASE = (
    "queue: light\nactions:\n  devman.task:\n    input_schema: {type: object}\n"
    "    template: {run: x}\n"
)


def setup(plane: Plane) -> None:
    plane.paths.base_src.write_text(BASE)
    plane.library("check", ACTION_FLOW)
    plane.add_project("alpha", '"check"')
    (plane.project_dir("alpha") / ".git").mkdir()
    assert compile(plane.paths) == 0


def findings(plane: Plane) -> dict[str, str | None]:
    return {n: c(plane.paths) for n, c in doctor.CHECKS}


def test_a_healthy_plane_passes_the_file_checks(plane: Plane):
    setup(plane)
    got = findings(plane)
    for name in ("compile clean", "dags match compile", "checkouts", "library actions"):
        assert got[name] is None, name


def test_compile_clean_fails_on_a_refused_project(plane: Plane):
    setup(plane)
    plane.own("alpha", "check", "env: {A: b}\nsteps: []\n")
    assert compile(plane.paths) == 1
    assert "alpha" in findings(plane)["compile clean"]


def test_compile_clean_fails_without_compile_json(plane: Plane):
    assert "devman compile" in findings(plane)["compile clean"]


def test_dags_fail_on_an_edited_a_missing_and_a_stray_file(plane: Plane):
    setup(plane)
    file = plane.dag("alpha", "check")
    file.write_text(file.read_text() + "# edit\n")
    assert "changed since compile" in findings(plane)["dags match compile"]
    file.unlink()
    assert "is missing" in findings(plane)["dags match compile"]
    stray = plane.paths.dags / "alpha" / "alpha.stray.yaml"
    stray.write_text("steps: []\n")
    assert (
        "alpha.stray.yaml is not in compile.json"
        in findings(plane)["dags match compile"]
    )


def test_dags_pass_with_the_recorded_hash(plane: Plane):
    setup(plane)
    digest = plane.record()["projects"]["alpha"]["workflows"]["check"]["sha256"]
    assert (
        hashlib.sha256(plane.dag("alpha", "check").read_bytes()).hexdigest() == digest
    )


def test_checkouts_fail_when_the_markers_are_gone(plane: Plane):
    setup(plane)
    shutil.rmtree(plane.project_dir("alpha") / ".git")
    assert "alpha" in findings(plane)["checkouts"]
    (plane.project_dir("alpha") / ".jj").mkdir()
    assert findings(plane)["checkouts"] is None


def test_actions_fail_for_a_name_that_base_does_not_define(plane: Plane):
    setup(plane)
    plane.library("bad", "steps:\n  - action: devman.nope\n")
    msg = findings(plane)["library actions"]
    assert "bad.yaml names action devman.nope" in msg
    assert "check.yaml" not in msg


def test_actions_find_a_name_in_a_later_document(plane: Plane):
    setup(plane)
    plane.library("two", "steps: []\n---\nname: sub\nsteps:\n  - action: x.y\n")
    assert "x.y" in findings(plane)["library actions"]


def test_the_api_check_passes_and_fails(plane: Plane):
    setup(plane)
    with rest.serve([]) as port:
        plane.paths.dagu_config.write_text(f"host: 127.0.0.1\nport: {port}\n")
        assert findings(plane)["Dagu answers"] is None
    assert "does not answer" in findings(plane)["Dagu answers"]


def test_the_version_check(plane: Plane, monkeypatch: pytest.MonkeyPatch):
    setup(plane)
    monkeypatch.setattr(dagu, "version", lambda: "2.20.1")
    paths = plane.paths.__class__.from_env(
        {**plane.env, "DEVMAN_DAGU_VERSION": "2.20.1"}
    )
    assert doctor.check_version(paths) is None
    monkeypatch.setattr(dagu, "version", lambda: "2.15.0")
    assert "2.15.0" in doctor.check_version(paths)
    assert doctor.check_version(plane.paths) is None  # no expected version set


def test_the_watcher_and_budget_checks(plane: Plane, monkeypatch: pytest.MonkeyPatch):
    setup(plane)
    state = plane.paths.state
    assert "no watcher" in findings(plane)["watcher runs"]
    # A process that is named watchexec and carries our --project-origin.
    # bash reads stdin, so it stays alive and never re-executes.
    proc = subprocess.Popen(
        ["watchexec", "-c", "read x", f"--project-origin={state}"],
        executable=shutil.which("bash"),
        stdin=subprocess.PIPE,
    )
    try:
        for _ in range(50):  # the child needs a moment to start
            if doctor.watcher_pids(plane.paths):
                break
            time.sleep(0.1)
        assert doctor.watcher_pids(plane.paths) == [proc.pid]
        assert findings(plane)["watcher runs"] is None
        monkeypatch.setattr(doctor, "inotify_watches", lambda pid: 10**9)
        assert "inotify watches" in findings(plane)["watch budget"]
        monkeypatch.setattr(doctor, "inotify_watches", lambda pid: 1)
        assert findings(plane)["watch budget"] is None
    finally:
        proc.kill()
        proc.wait()


def test_inotify_watches_counts_a_real_watcher(plane: Plane):
    script = (
        "import ctypes,os,sys;libc=ctypes.CDLL(None);fd=libc.inotify_init();"
        f"[libc.inotify_add_watch(fd,{str(plane.root)!r}.encode(),0x100)];"
        "print(os.getpid(),flush=True);sys.stdin.read()"
    )
    proc = subprocess.Popen(
        ["python3", "-c", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        pid = int(proc.stdout.readline())
        assert doctor.inotify_watches(pid) == 1
    finally:
        proc.kill()
        proc.wait()


def test_doctor_exit_code_and_lines(plane: Plane):
    setup(plane)
    res = CliRunner().invoke(app, ["doctor"], env=plane.env)
    assert res.exit_code == 1
    assert "FAIL watcher runs" in res.output
    assert "ok   compile clean" in res.output
    assert "ok   library actions" in res.output
