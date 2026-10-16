import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from conftest import Plane

from devman import watch
from devman.compile import compile

SRC = Path(__file__).resolve().parent.parent / "src"
SAVE = (
    '[[{p}.on]]\nevent = "save"\nmatch = "**/*.py"\nexclude = [".scratch/**"]\n'
    'run = "check"\n'
)


def record(plane: Plane) -> None:
    plane.library("check")
    plane.add_project("alpha", '"check"', SAVE.format(p="alpha"))
    plane.add_project("beta", '"check"')  # no save entry
    assert compile(plane.paths) == 0


def test_the_watch_set_holds_save_projects_and_the_overlay(plane: Plane):
    record(plane)
    got = watch.targets(plane.paths)
    assert got.deep == tuple(
        sorted([plane.project_dir("alpha"), plane.paths.library])
    )  # no workflows/ yet, so it is not listed; beta has no save entry
    assert got.shallow == (plane.paths.overlay,)
    plane.own("alpha", "extra")
    assert plane.paths.workflows in watch.targets(plane.paths).deep
    assert got.count() == 4


def test_the_command_line_holds_the_fixed_ignore_list(plane: Plane):
    record(plane)
    argv = watch.command(plane.paths, watch.targets(plane.paths), "300ms")
    assert argv[:3] == [
        "watchexec",
        "--only-emit-events",
        "--emit-events-to=json-stdio",
    ]
    assert f"--project-origin={plane.paths.state}" in argv
    assert argv[argv.index("--debounce") + 1] == "300ms"
    ignored = {argv[i + 1] for i, a in enumerate(argv) if a == "--ignore"}
    names = ".git .jj .devenv .direnv .venv node_modules __pycache__ .gitman"
    names += " .worktrees .devman"
    assert ignored == {f"**/{n}" for n in names.split()} | {
        f"**/{n}/**" for n in names.split()
    }
    watched = [argv[i + 1] for i, a in enumerate(argv) if a == "--watch"]
    assert str(plane.project_dir("alpha")) in watched
    assert str(plane.project_dir("beta")) not in watched
    shallow = [argv[i + 1] for i, a in enumerate(argv) if a == "--watch-non-recursive"]
    assert str(plane.paths.overlay) in shallow


def test_event_paths_skip_reads_deletes_and_directories():
    def event(kind: str, filetype: str = "file") -> str:
        tags = [
            {"kind": "source", "source": "filesystem"},
            {"kind": "fs", "simple": kind},
            {"kind": "path", "absolute": "/p/a.py", "filetype": filetype},
        ]
        return json.dumps({"tags": tags})

    assert watch.event_paths(event("modify")) == ["/p/a.py"]
    assert watch.event_paths(event("create")) == ["/p/a.py"]
    assert watch.event_paths(event("access")) == []
    assert watch.event_paths(event("remove")) == []
    assert watch.event_paths(event("create", "dir")) == []
    assert watch.event_paths("not json") == []
    assert watch.event_paths("{}") == []


def test_classify_groups_by_project_and_sends_overlay_paths_to_compile(plane: Plane):
    record(plane)
    alpha = plane.project_dir("alpha")
    overlay = plane.paths.projects_toml
    found = [
        str(alpha / "a.py"),
        str(alpha / "src" / "b.py"),
        str(alpha / "a.py"),
        str(plane.project_dir("beta") / "c.py"),  # no save entry
        str(plane.paths.state / "watch" / "canary"),
        "/elsewhere/d.py",
    ]
    assert watch.classify(plane.paths, found) == (
        False,
        {"alpha": sorted({str(alpha / "a.py"), str(alpha / "src" / "b.py")})},
    )
    assert watch.classify(plane.paths, [str(overlay)]) == (True, {})


def test_durations():
    assert watch.seconds("300ms") == 0.3
    assert watch.seconds("2s") == 2
    assert watch.seconds("1m") == 60
    assert watch.seconds("250") == 0.25
    with pytest.raises(ValueError):
        watch.seconds("soon")


# --- real watchexec, a temporary tree, a fake dagu -----------------------------


class Service:
    """`devman watch` as a child process, with its stderr collected."""

    def __init__(self, plane: Plane):
        env = {**os.environ, **plane.env, "PYTHONPATH": str(SRC)}
        self.plane = plane
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "devman", "watch", "--debounce", "100ms"],
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        self.lines: list[str] = []
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        for line in self.proc.stderr:
            self.lines.append(line.rstrip())

    def count(self, text: str) -> int:
        return sum(text in ln for ln in self.lines)

    def wait_for(self, check: Callable[[], object], seconds: float = 20.0):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = check()
            if value:
                return value
            time.sleep(0.05)
        raise AssertionError("timeout; log:\n" + "\n".join(self.lines))

    def saves(self) -> list[dict]:
        if not self.plane.paths.events.exists():
            return []
        text = self.plane.paths.events.read_text()
        return [json.loads(ln) for ln in text.splitlines() if ln]

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


@pytest.fixture
def service(plane: Plane, fake: Path) -> Iterator[Service]:
    record(plane)
    svc = Service(plane)
    try:
        svc.wait_for(lambda: svc.count("watchexec ready"))
        yield svc
    finally:
        svc.stop()


def test_a_save_gives_one_event_and_ignored_paths_give_none(service: Service):
    plane, alpha = service.plane, service.plane.project_dir("alpha")
    assert service.count("watchexec starting, 4 paths") == 1
    for name in (
        ".git",
        ".worktrees/w",
        "node_modules/x",
        "src/__pycache__",
        ".devman",
    ):
        (alpha / name).mkdir(parents=True, exist_ok=True)
        (alpha / name / "f.py").write_text("x = 1\n")
    time.sleep(0.5)
    started = time.monotonic()
    (alpha / "src").mkdir(exist_ok=True)
    (alpha / "src" / "a.py").write_text("x = 1\n")
    (alpha / "src" / "a.py").write_text("x = 2\n")
    service.wait_for(lambda: service.saves())
    assert time.monotonic() - started < 2
    time.sleep(0.7)
    (line,) = service.saves()
    assert line["event"] == "save" and line["source"] == "watcher"
    assert line["project"] == "alpha"
    assert line["subjects"] == ["src/a.py"]
    assert [m["result"] for m in line["matches"]] == ["enqueued"]
    assert plane.paths.events.read_text().count("\n") == 1


def test_an_overlay_edit_compiles_and_restarts_only_on_a_path_change(
    service: Service,
):
    plane = service.plane
    # A changed workflow is a compile and no change of the watch set.
    plane.library("check", "steps:\n  - name: s\n    run: echo changed\n")
    service.wait_for(lambda: "changed" in plane.dag("alpha", "check").read_text())
    time.sleep(1)
    assert service.count("watchexec starting") == 1
    # A new project with a save entry grows the set and restarts watchexec.
    plane.add_project("gamma", '"check"', SAVE.format(p="gamma"))
    service.wait_for(lambda: service.count("watchexec starting") == 2)
    assert service.count("watchexec starting, 5 paths") == 1
    service.wait_for(lambda: service.count("watchexec ready") == 2)
    (plane.project_dir("gamma") / "g.py").write_text("x = 1\n")
    service.wait_for(lambda: [s for s in service.saves() if s["project"] == "gamma"])
    assert service.proc.poll() is None


def child_of(parent: int) -> int:
    """The pid of a child process; the build sandbox has no pgrep."""
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
        except OSError:
            continue
        if int(fields[1]) == parent:
            return int(stat.parent.name)
    raise AssertionError("no child process")


def test_the_watcher_exits_with_the_exit_code_of_watchexec(plane: Plane, fake: Path):
    record(plane)
    svc = Service(plane)
    try:
        svc.wait_for(lambda: svc.count("watchexec ready"))
        pid = child_of(svc.proc.pid)
        os.kill(pid, 9)
        assert svc.proc.wait(15) == 1
        assert svc.count("watchexec exited") == 1
    finally:
        svc.stop()
