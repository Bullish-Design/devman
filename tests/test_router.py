import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import Plane

from devman import dagu
from devman.compile import compile
from devman.router import Event, emit, find_project

FAKES = Path(__file__).parent / "fakes"
SRC = Path(__file__).resolve().parent.parent / "src"
ON = (
    '[[{p}.on]]\nevent = "save"\nmatch = "**/*.py"\nexclude = [".scratch/**"]\n'
    'run = "check"\n'
)


@pytest.fixture
def fake(plane: Plane, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = plane.root / "dagu.log"
    # The build sandbox has no /usr/bin/env, so the copy names bash directly.
    bin_dir = plane.root / "fake-bin"
    bin_dir.mkdir()
    body = (FAKES / "dagu").read_text().split("\n", 1)[1]
    script = bin_dir / "dagu"
    script.write_text(f"#!{shutil.which('bash')}\n{body}")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_DAGU_LOG", str(log))
    monkeypatch.delenv("FAKE_DAGU_EXIT", raising=False)
    return log


def calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [ln.split("\x1f")[:-1] for ln in log.read_text().splitlines()]


def events(plane: Plane) -> list[dict]:
    return [json.loads(ln) for ln in plane.paths.events.read_text().splitlines()]


def setup(plane: Plane, name: str = "alpha") -> None:
    plane.library("check")
    plane.add_project(name, '"check"', ON.format(p=name))
    assert compile(plane.paths) == 0


def test_a_match_enqueues_with_the_exact_command_line(plane: Plane, fake: Path):
    setup(plane)
    out = emit(
        plane.paths, Event("save", "alpha", ("src/a.py",), "watcher", {"K": "v"})
    )
    assert out.code == 0
    (argv,) = calls(fake)
    run_id = argv[argv.index("--run-id") + 1]
    assert argv == [
        "--config", str(plane.paths.dagu_config),
        "enqueue",
        "--run-id", run_id,
        "--labels", "devman.event=save",
        str(plane.dag("alpha", "check")),
        "--",
        "DEVMAN_EVENT=save", "DEVMAN_SUBJECT=src/a.py", "K=v",
    ]  # fmt: skip
    assert "--name" not in argv
    assert "--default-working-dir" not in argv
    assert out.lines == [f"enqueued alpha.check run={run_id}"]


def test_the_event_line_has_the_documented_shape(plane: Plane, fake: Path):
    setup(plane)
    emit(plane.paths, Event("save", "alpha", ("src/a.py",), "watcher", {"K": "v"}))
    (line,) = events(plane)
    run_id = calls(fake)[0][4]
    assert list(line) == [
        "at", "event", "project", "source", "subjects",
        "fields", "stale", "matches", "refusal",
    ]  # fmt: skip
    assert line["at"].endswith("+00:00")
    assert line | {"at": ""} == {
        "at": "",
        "event": "save",
        "project": "alpha",
        "source": "watcher",
        "subjects": ["src/a.py"],
        "fields": {"K": "v"},
        "stale": False,
        "matches": [
            {
                "workflow": "check",
                "dag": "alpha.check",
                "run_id": run_id,
                "result": "enqueued",
            }
        ],
        "refusal": None,
    }


def test_many_subjects_give_one_enqueue(plane: Plane, fake: Path):
    setup(plane)
    emit(plane.paths, Event("save", "alpha", ("a.py", "b.py", "c.py")))
    (argv,) = calls(fake)
    assert argv[-2:] == ["DEVMAN_EVENT=save", "DEVMAN_SUBJECT=a.py"]


def test_the_subject_is_the_first_one_that_matches(plane: Plane, fake: Path):
    setup(plane)
    emit(plane.paths, Event("save", "alpha", ("README.md", ".scratch/x.py", "b.py")))
    assert calls(fake)[0][-1] == "DEVMAN_SUBJECT=b.py"


def test_exclude_and_other_events_match_nothing(plane: Plane, fake: Path):
    setup(plane)
    out = emit(plane.paths, Event("save", "alpha", (".scratch/x.py", "doc.md")))
    assert out.code == 0 and out.lines == []
    assert emit(plane.paths, Event("land", "alpha", ("a.py",))).code == 0
    assert calls(fake) == []
    assert [e["matches"] for e in events(plane)] == [[], []]
    assert events(plane)[0]["refusal"] is None


def test_an_absolute_subject_becomes_relative(plane: Plane, fake: Path):
    setup(plane)
    root = plane.project_dir("alpha")
    out = emit(plane.paths, Event("save", "alpha", (str(root / "src" / "a.py"),)))
    assert out.record["subjects"] == ["src/a.py"]
    assert calls(fake)[0][-1] == "DEVMAN_SUBJECT=src/a.py"


def test_no_subject_matches_only_a_double_star(plane: Plane, fake: Path):
    plane.library("check")
    on = '[[alpha.on]]\nevent = "tick"\nmatch = "**"\nrun = "check"\n'
    plane.add_project("alpha", '"check"', on)
    compile(plane.paths)
    assert emit(plane.paths, Event("tick", "alpha")).code == 0
    assert calls(fake)[0][-1] == "DEVMAN_SUBJECT="
    assert emit(plane.paths, Event("save", "alpha")).lines == []


def test_two_entries_for_one_workflow_enqueue_once(plane: Plane, fake: Path):
    plane.library("check")
    on = (
        ON.format(p="alpha")
        + '[[alpha.on]]\nevent = "save"\nmatch = "*"\nrun = "check"\n'
    )
    plane.add_project("alpha", '"check"', on)
    compile(plane.paths)
    emit(plane.paths, Event("save", "alpha", ("a.py",)))
    assert len(calls(fake)) == 1


def test_the_project_comes_from_the_deepest_parent_of_cwd(plane: Plane, fake: Path):
    setup(plane, "alpha")
    inner = plane.project_dir("alpha") / "inner"
    inner.mkdir()
    plane.library("check")
    text = plane.paths.projects_toml.read_text()
    plane.manifest(text + f'[inner]\npath = "{inner}"\ntake = ["check"]\n')
    compile(plane.paths)
    records = plane.record()["projects"]
    assert find_project(records, inner / "sub") == "inner"
    assert find_project(records, plane.project_dir("alpha")) == "alpha"
    assert find_project(records, plane.root) is None
    out = emit(
        plane.paths, Event("save", None, ("a.py",), cwd=plane.project_dir("alpha"))
    )
    assert out.record["project"] == "alpha"


def test_no_project_is_a_refusal(plane: Plane, fake: Path):
    setup(plane)
    out = emit(plane.paths, Event("save", None, ("a.py",), cwd=plane.root))
    assert out.code == 2
    assert out.record["refusal"] == "no project contains the current directory"
    assert out.record["project"] is None and out.record["matches"] == []
    assert events(plane)[-1]["refusal"] == out.record["refusal"]
    out = emit(plane.paths, Event("save", "nope", ("a.py",)))
    assert out.code == 2 and out.record["refusal"] == "unknown project nope"
    assert calls(fake) == []


def test_a_missing_compile_json_is_a_refusal(plane: Plane, fake: Path):
    out = emit(plane.paths, Event("save", "alpha", ("a.py",)))
    assert out.code == 2 and "cannot read" in out.record["refusal"]


def test_a_vanished_checkout_is_refused(plane: Plane, fake: Path):
    setup(plane)
    plane.project_dir("alpha").rmdir()
    out = emit(plane.paths, Event("save", "alpha", ("a.py",)))
    assert out.code == 2
    assert out.record["refusal"].endswith("is not a directory")
    assert calls(fake) == []


def test_a_failed_enqueue_still_writes_its_event(
    plane: Plane, fake: Path, monkeypatch: pytest.MonkeyPatch
):
    setup(plane)
    monkeypatch.setenv("FAKE_DAGU_EXIT", "1")
    out = emit(plane.paths, Event("save", "alpha", ("a.py",)))
    assert out.code == 1
    (line,) = events(plane)
    (match,) = line["matches"]
    assert match["result"] == "failed" and "fake dagu failure" in match["error"]
    assert out.lines[0].startswith("failed alpha.check: ")


def test_a_missing_compiled_file_fails_the_match(plane: Plane, fake: Path):
    setup(plane)
    plane.dag("alpha", "check").unlink()
    out = emit(plane.paths, Event("save", "alpha", ("a.py",)))
    assert out.code == 1 and "missing" in out.record["matches"][0]["error"]
    assert calls(fake) == []


def test_a_stale_project_routes_on_its_old_entries(plane: Plane, fake: Path):
    setup(plane)
    plane.own("alpha", "check", "env: {A: b}\nsteps:\n  - name: s\n    run: x\n")
    assert compile(plane.paths) == 1
    out = emit(plane.paths, Event("save", "alpha", ("a.py",)))
    assert out.code == 0 and out.record["stale"] is True
    assert len(calls(fake)) == 1


def test_no_dagu_config_refuses_a_match(plane: Plane, fake: Path):
    setup(plane)
    paths = type(plane.paths).from_env(
        {k: v for k, v in plane.env.items() if k != "DEVMAN_DAGU_CONFIG"}
    )
    out = emit(paths, Event("save", "alpha", ("a.py",)))
    assert out.code == 2 and "DEVMAN_DAGU_CONFIG" in out.record["refusal"]


def test_dagu_enqueue_reports_the_error_text(plane: Plane, fake: Path, monkeypatch):
    monkeypatch.setenv("FAKE_DAGU_EXIT", "1")
    err = dagu.enqueue(Path("c.yaml"), Path("/x.yaml"), "id", "save", [])
    assert err == "Error: fake dagu failure"


def run_cli(plane: Plane, *args: str, cwd: Path | None = None):
    env = {**os.environ, **plane.env, "PYTHONPATH": str(SRC)}
    return subprocess.run(
        [sys.executable, "-m", "devman", "emit", *args],
        capture_output=True, text=True, check=False, env=env, cwd=cwd,
    )  # fmt: skip


def test_cli_emit_grammar_and_exit_codes(plane: Plane, fake: Path):
    setup(plane)
    ok = run_cli(plane, "save", "--project", "alpha", "--subject", "a.py", "K=v")
    assert ok.returncode == 0 and ok.stdout.startswith("enqueued alpha.check run=")
    in_dir = run_cli(plane, "save", "--subject", "a.py", cwd=plane.project_dir("alpha"))
    assert in_dir.returncode == 0
    for bad in (
        ["Save"],
        ["save", "DEVMAN_X=1"],
        ["save", "novalue"],
        ["save", "1a=b"],
    ):
        result = run_cli(plane, *bad, "--project", "alpha")
        assert result.returncode == 2, bad
    nowhere = run_cli(plane, "save", cwd=plane.root)
    assert nowhere.returncode == 2 and "no project" in nowhere.stderr
    assert len(calls(fake)) == 2
    assert len(events(plane)) == 3  # usage errors write no line
