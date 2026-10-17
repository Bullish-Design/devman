import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from conftest import STEP, Plane

from devman import compile as compile_mod
from devman import dagu
from devman.compile import compile, fill_base
from devman.paths import Paths

SRC = Path(__file__).resolve().parent.parent / "src"


def two_projects(plane: Plane) -> None:
    plane.library("check")
    plane.add_project("alpha", '"check"')
    plane.add_project("beta", '"check"')


def snapshot(path: Path) -> tuple[bytes, int]:
    return path.read_bytes(), path.stat().st_mtime_ns


def editable_base(plane: Plane) -> Path:
    """Copy the packaged template before a test changes its bytes."""
    source = plane.paths.base_src
    target = plane.root / "test-base.yaml"
    shutil.copyfile(source, target)
    plane.paths = replace(plane.paths, base_src=target)
    return target


def test_compile_publishes_each_project(plane: Plane) -> None:
    two_projects(plane)
    assert compile(plane.paths) == 0
    for project in ("alpha", "beta"):
        assert yaml.safe_load(plane.dag(project, "check").read_text())["steps"]
        assert (plane.paths.runs / project).is_dir()
    record = plane.record()
    assert record["version"] == 2
    assert record["global"]["status"] == "ok"
    assert record["global"]["successful_input_sha256"]
    alpha = record["projects"]["alpha"]
    assert alpha["status"] == "ok"
    assert alpha["stale"] is False
    assert alpha["reasons"] == []
    assert alpha["workflows"]["check"]["dag"] == "alpha.check"
    assert alpha["workflows"]["check"]["origin"] == "library"
    assert alpha["workflows"]["check"]["file"] == str(plane.dag("alpha", "check"))
    assert alpha["workflows"]["check"]["source"] == str(
        plane.paths.library / "workflows" / "check.yaml"
    )


def test_a_project_workflow_replaces_the_library_file(plane: Plane) -> None:
    plane.library("check", STEP)
    plane.add_project("alpha", '"check"')
    plane.own(
        "alpha", "check", "queue: light\nsteps:\n  - name: mine\n    run: echo mine\n"
    )
    plane.own("alpha", "extra")  # a file with no `take` is in the set too
    assert compile(plane.paths) == 0
    workflows = plane.record()["projects"]["alpha"]["workflows"]
    assert workflows["check"]["origin"] == "project"
    assert workflows["extra"]["origin"] == "project"
    assert "mine" in plane.dag("alpha", "check").read_text()


def test_files_that_do_not_end_in_yaml_are_ignored(plane: Plane) -> None:
    plane.add_project("alpha")
    (plane.paths.workflows / "alpha").mkdir(parents=True)
    (plane.paths.workflows / "alpha" / "README.md").write_text("notes")
    assert compile(plane.paths) == 0
    assert plane.record()["projects"]["alpha"]["workflows"] == {}


def test_on_entries_are_recorded(plane: Plane) -> None:
    plane.library("check")
    on = '[[alpha.on]]\nevent = "land"\nmatch = "main"\nrun = "check"\n'
    plane.add_project("alpha", '"check"', on)
    assert compile(plane.paths) == 0
    assert plane.record()["projects"]["alpha"]["on"] == [
        {"event": "land", "match": ["main"], "exclude": [], "run": "check"}
    ]


# Each case: how to break project `alpha`, and the reason compile must record.
BROKEN_SOURCES = {
    "env": ("env:\n  - A: b\n" + STEP, "top-level env is set by devman"),
    "log_dir": ("log_dir: /x\n" + STEP, "top-level log_dir is set by devman"),
    "shell": ("shell: bash\n" + STEP, "top-level shell is set by devman"),
    "handler": (
        "handler_on:\n  exit:\n    run: x\n" + STEP,
        "handler_on.exit is set by devman",
    ),
    "queue": (
        STEP.replace("queue: light\n", "queue: undefinedq\n"),
        "queue undefinedq is not configured",
    ),
    "params": ("params: [A=1]\n" + STEP, "params must declare DEVMAN_EVENT"),
    "name": ("name: foo\n" + STEP, "entrypoint document must not define name"),
    "not-a-mapping": ("- a\n", "the first document is not a mapping"),
}


@pytest.mark.parametrize("case", sorted(BROKEN_SOURCES))
def test_a_refused_source_keeps_the_published_files_and_isolates_the_project(
    plane: Plane, case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    two_projects(plane)
    assert compile(plane.paths) == 0
    before = {p: snapshot(plane.dag(p, "check")) for p in ("alpha", "beta")}

    bad, reason = BROKEN_SOURCES[case]
    plane.own("alpha", "check", bad)  # alpha's own file replaces the library one
    plane.library("check", STEP + "# library edit\n")  # beta must still publish
    assert compile(plane.paths) == 1

    assert snapshot(plane.dag("alpha", "check")) == before["alpha"]
    assert plane.dag("beta", "check").read_text().endswith("# library edit\n")
    alpha = plane.record()["projects"]["alpha"]
    assert alpha["status"] == "refused"
    assert alpha["stale"] is True
    assert reason in " ".join(alpha["reasons"])
    assert "check" in alpha["workflows"]  # the last good compile stays described
    assert plane.record()["projects"]["beta"]["status"] == "ok"
    err = capsys.readouterr().err
    assert "devman: compile refused alpha: " in err
    assert reason in err


def test_a_project_refused_on_its_first_compile_is_not_stale(plane: Plane) -> None:
    plane.library("check", STEP.replace("queue: light\n", "queue: undefinedq\n"))
    plane.add_project("alpha", '"check"')
    assert compile(plane.paths) == 1
    alpha = plane.record()["projects"]["alpha"]
    assert (alpha["status"], alpha["stale"], alpha["on"], alpha["workflows"]) == (
        "refused",
        False,
        [],
        {},
    )
    assert not plane.dag("alpha", "check").exists()
    assert not (plane.paths.dags / "alpha").exists()


def test_an_unknown_take_name_refuses_the_project(plane: Plane) -> None:
    plane.add_project("alpha", '"check2"')
    assert compile(plane.paths) == 1
    assert plane.record()["projects"]["alpha"]["reasons"] == [
        "take names check2, which is neither in workflows/alpha/ nor in the library"
    ]


def test_an_on_entry_that_runs_an_unknown_workflow_refuses_the_project(
    plane: Plane,
) -> None:
    plane.library("check")
    on = '[[alpha.on]]\nevent = "land"\nmatch = "main"\nrun = "ghost"\n'
    plane.add_project("alpha", '"check"', on)
    assert compile(plane.paths) == 1
    assert plane.record()["projects"]["alpha"]["reasons"] == [
        "on entry runs ghost, which is not a workflow of this project"
    ]


def test_a_workflow_file_name_with_a_dot_refuses_the_project(plane: Plane) -> None:
    plane.add_project("alpha")
    plane.own("alpha", "a.b")
    assert compile(plane.paths) == 1
    assert plane.record()["projects"]["alpha"]["reasons"] == [
        "workflows/alpha/a.b.yaml: workflow name a.b must not contain a dot"
    ]


def test_a_manifest_error_refuses_only_its_project(plane: Plane) -> None:
    plane.library("check")
    plane.add_project("alpha", '"check"')
    plane.manifest(
        plane.paths.projects_toml.read_text() + '[typo]\npath = "/x"\ntkae = []\n'
    )
    assert compile(plane.paths) == 1
    projects = plane.record()["projects"]
    assert projects["typo"]["reasons"] == ["unknown key tkae"]
    assert projects["alpha"]["status"] == "ok"


def test_a_path_that_names_no_directory_refuses_and_creates_nothing(
    plane: Plane,
) -> None:
    plane.library("check")
    missing = plane.root / "typo-dir"
    plane.manifest(f'[alpha]\npath = "{missing}"\ntake = ["check"]\n')
    assert compile(plane.paths) == 1
    assert plane.record()["projects"]["alpha"]["reasons"] == [
        f"path {missing} is not a directory"
    ]
    assert not missing.exists()
    assert not (plane.paths.dags / "alpha").exists()


def test_a_broken_projects_toml_refuses_and_removes_nothing(plane: Plane) -> None:
    two_projects(plane)
    assert compile(plane.paths) == 0
    plane.manifest("[alpha\n")
    assert compile(plane.paths) == 1
    assert plane.dag("alpha", "check").exists()
    assert set(plane.record()["projects"]) == {"alpha", "beta"}


def test_a_removed_workflow_file_is_deleted(plane: Plane) -> None:
    plane.add_project("alpha")
    plane.own("alpha", "one")
    plane.own("alpha", "two")
    assert compile(plane.paths) == 0
    plane.own("alpha", "two").unlink()
    assert compile(plane.paths) == 0
    assert plane.dag("alpha", "one").exists()
    assert not plane.dag("alpha", "two").exists()


def test_a_removed_project_loses_its_dags_but_keeps_its_runs(plane: Plane) -> None:
    two_projects(plane)
    wiki = plane.paths.dags / "wiki"  # Dagu makes this; compile must leave it
    wiki.mkdir(parents=True)
    (wiki / "x.yaml").write_text("steps: []\n")
    assert compile(plane.paths) == 0
    plane.manifest(
        f'[alpha]\npath = "{plane.project_dir("alpha")}"\ntake = ["check"]\n'
    )
    assert compile(plane.paths) == 0
    assert not (plane.paths.dags / "beta").exists()
    assert (plane.paths.runs / "beta").is_dir()
    assert "beta" not in plane.record()["projects"]
    assert (wiki / "x.yaml").exists()


def test_a_partial_compile_removes_nothing(plane: Plane) -> None:
    two_projects(plane)
    assert compile(plane.paths) == 0
    plane.manifest(
        f'[alpha]\npath = "{plane.project_dir("alpha")}"\ntake = ["check"]\n'
    )
    assert compile(plane.paths, ["alpha"]) == 1
    assert plane.dag("beta", "check").exists()
    assert "beta" in plane.record()["projects"]
    assert plane.record()["global"]["status"] == "refused"


def test_a_partial_compile_leaves_the_others_alone(plane: Plane) -> None:
    two_projects(plane)
    assert compile(plane.paths) == 0
    beta = snapshot(plane.dag("beta", "check"))
    plane.library("check", STEP + "# edit\n")
    assert compile(plane.paths, ["alpha"]) == 1
    assert snapshot(plane.dag("beta", "check")) == beta
    assert plane.dag("alpha", "check").read_text().endswith("# edit\n")


def test_an_unknown_project_argument_is_a_usage_error(plane: Plane) -> None:
    two_projects(plane)
    assert compile(plane.paths, ["nope"]) == 2


def test_a_directory_without_a_table_is_refused_as_an_orphan(
    plane: Plane, capsys: pytest.CaptureFixture[str]
) -> None:
    plane.add_project("alpha")
    plane.own("ghost", "check")
    assert compile(plane.paths) == 1
    assert plane.record()["global"]["reasons"] == ["ghost"]
    assert "devman: compile refused ghost: " in capsys.readouterr().err
    assert not (plane.paths.dags / "ghost").exists()


def test_a_second_compile_writes_and_validates_nothing(
    plane: Plane, monkeypatch: pytest.MonkeyPatch
) -> None:
    two_projects(plane)
    assert compile(plane.paths) == 0
    files = [plane.dag(p, "check") for p in ("alpha", "beta")]
    before = [
        snapshot(f) for f in [*files, plane.paths.compile_json, plane.paths.base_out]
    ]
    calls: list[Path] = []
    monkeypatch.setattr(dagu, "validate", lambda config, file: calls.append(file))
    time.sleep(0.01)
    assert compile(plane.paths) == 0
    assert calls == []
    assert before == [
        snapshot(f) for f in [*files, plane.paths.compile_json, plane.paths.base_out]
    ]


def test_all_validates_every_file(
    plane: Plane, monkeypatch: pytest.MonkeyPatch
) -> None:
    two_projects(plane)
    assert compile(plane.paths) == 0
    calls: list[Path] = []
    monkeypatch.setattr(dagu, "validate", lambda config, file: calls.append(file))
    assert compile(plane.paths, None, validate_all=True) == 0
    assert len(calls) == 2


def test_a_changed_source_is_validated_and_republished(plane: Plane) -> None:
    two_projects(plane)
    assert compile(plane.paths) == 0
    plane.library("check", STEP + "# v2\n")
    assert compile(plane.paths) == 0
    assert plane.dag("alpha", "check").read_text().endswith("# v2\n")


def test_two_compiles_started_together_run_one_after_the_other(
    plane: Plane, monkeypatch: pytest.MonkeyPatch
) -> None:
    two_projects(plane)
    active, peak, codes = [0], [0], []
    real = compile_mod.fill_base

    def slow(paths: Paths):  # fill_base runs inside the lock
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        time.sleep(0.2)
        try:
            return real(paths)
        finally:
            active[0] -= 1

    monkeypatch.setattr(compile_mod, "fill_base", slow)
    threads = [
        threading.Thread(target=lambda: codes.append(compile(plane.paths)))
        for _ in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert codes == [0, 0]
    assert peak[0] == 1
    assert plane.dag("alpha", "check").exists()


def test_a_rendered_file_with_group_and_labels_validates(plane: Plane) -> None:
    plane.add_project("alpha")
    plane.own("alpha", "tagged", "group: g\nlabels:\n  - a=b\n" + STEP)
    plane.own("alpha", "plain")  # the header adds group and labels
    assert compile(plane.paths) == 0


def test_base_yaml_is_filled_and_written_to_the_state_directory(plane: Plane) -> None:
    plane.add_project("alpha")
    assert compile(plane.paths) == 0
    base = yaml.safe_load(plane.paths.base_out.read_text())
    assert base["handler_on"]["exit"]["shell"] == plane.env["DEVMAN_BASH"]
    assert "@bash@" not in plane.paths.base_out.read_text()
    assert plane.env["DEVMAN_BIN"] in plane.paths.base_out.read_text()


def test_a_changed_base_yaml_is_written_and_every_file_is_validated(
    plane: Plane, monkeypatch: pytest.MonkeyPatch
) -> None:
    two_projects(plane)
    assert compile(plane.paths) == 0
    source = editable_base(plane)
    source.write_text(source.read_text() + "# changed template\n")
    calls: list[Path] = []
    monkeypatch.setattr(dagu, "validate", lambda config, file: calls.append(file))
    assert compile(plane.paths) == 0
    assert "hist_retention_days: 7" in plane.paths.base_out.read_text()
    assert len(calls) == 3


def test_a_missing_base_yaml_refuses_the_run(
    plane: Plane, capsys: pytest.CaptureFixture[str]
) -> None:
    two_projects(plane)
    original_source = editable_base(plane)
    plane.paths.base_src.unlink()
    assert compile(plane.paths) == 1
    assert "compile refused: cannot read" in capsys.readouterr().err
    assert original_source.exists() is False


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("x: '@nope@'\n", "unknown token @nope@"),
        ("- a\n", "base.yaml is not a mapping"),
        ("a: [\n", "invalid YAML"),
    ],
)
def test_a_bad_base_yaml_refuses_the_run_and_writes_nothing(
    plane: Plane, capsys: pytest.CaptureFixture[str], text: str, reason: str
) -> None:
    two_projects(plane)
    editable_base(plane)
    plane.paths.base_src.write_text(text)
    assert compile(plane.paths) == 1
    assert reason in capsys.readouterr().err
    assert not plane.paths.base_out.exists()
    assert not plane.dag("alpha", "check").exists()


def test_a_bad_packaged_base_keeps_the_active_base_and_dags(
    plane: Plane, capsys: pytest.CaptureFixture[str]
) -> None:
    plane.add_project("alpha")
    plane.own("alpha", "check")
    assert compile(plane.paths) == 0
    active = plane.paths.base_out.read_bytes()
    published = plane.dag("alpha", "check").read_bytes()
    source = editable_base(plane)
    source.write_text(source.read_text().replace("handler_on:\n", "removed_handler:\n"))

    assert compile(plane.paths) == 1
    assert "required handler_on.exit is missing" in capsys.readouterr().err
    assert plane.paths.base_out.read_bytes() == active
    assert plane.dag("alpha", "check").read_bytes() == published


def test_a_token_with_no_value_refuses_the_run(plane: Plane) -> None:
    two_projects(plane)
    editable_base(plane)
    plane.paths.base_src.write_text("x: '@devman@'\n")
    assert fill_base(replace(plane.paths, bin=None))[1] == (
        f"{plane.paths.base_src}: @devman@ has no value; set DEVMAN_BIN"
    )


def test_a_missing_guard_file_refuses_the_whole_compile(
    plane: Plane, capsys: pytest.CaptureFixture[str]
) -> None:
    two_projects(plane)
    paths = replace(plane.paths, guard=str(plane.root / "nope.sh"))
    assert compile(paths) == 1
    assert "cannot read" in capsys.readouterr().err
    assert not plane.dag("alpha", "check").exists()


def test_the_state_directory_token_is_filled(plane: Plane) -> None:
    plane.add_project("alpha")
    source = editable_base(plane)
    source.write_text(
        source.read_text().replace("@stateDir@/handler.log", "@stateDir@/custom.log")
    )
    assert compile(plane.paths) == 0
    base = yaml.safe_load(plane.paths.base_out.read_text())
    assert f"{plane.paths.state}/custom.log" in base["handler_on"]["exit"]["command"]


def test_compile_needs_the_dagu_config(plane: Plane) -> None:
    env = {k: v for k, v in plane.env.items() if k != "DEVMAN_DAGU_CONFIG"}
    assert compile(Paths.from_env(env)) == 1


def test_the_cli_runs_compile(plane: Plane) -> None:
    two_projects(plane)
    run = subprocess.run(
        [sys.executable, "-m", "devman", "compile"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **plane.env, "PYTHONPATH": str(SRC)},
    )
    assert run.returncode == 0, run.stderr
    assert (
        json.loads(plane.paths.compile_json.read_text())["projects"]["alpha"]["status"]
        == "ok"
    )
    bad = subprocess.run(
        [sys.executable, "-m", "devman", "compile", "nope"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **plane.env, "PYTHONPATH": str(SRC)},
    )
    assert bad.returncode == 2
