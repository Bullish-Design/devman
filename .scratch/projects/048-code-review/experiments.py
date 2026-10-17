"""Isolated review probes. Run with `uv run python experiments.py`."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from devman import doctor, status
from devman.compile import compile
from devman.manifest import load
from devman.paths import Paths
from devman.router import Event, emit, find_project

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASH = shutil.which("bash") or "/bin/bash"


def make_plane(root: Path) -> Paths:
    overlay = root / "overlay"
    state = root / "state"
    config = root / "dagu.yaml"
    project = root / "project"
    project.mkdir()
    (project / ".git").mkdir()
    config.write_text(
        "auth: {mode: none}\n"
        "skip_examples: true\n"
        f"paths: {{dags_dir: {state}/dags, base_config: {state}/base.yaml}}\n"
        "queues: {enabled: true, config: [{name: light, max_concurrency: 1}]}\n"
    )
    guard = root / "guard.sh"
    guard.write_text((ROOT / "dagu/guard.sh").read_text().replace("@bash@", BASH))
    guard.chmod(0o755)
    env = {
        "DEVMAN_OVERLAY": str(overlay),
        "DEVMAN_STATE": str(state),
        "DEVMAN_DAGU_CONFIG": str(config),
        "DEVMAN_BASH": BASH,
        "DEVMAN_BIN": "/bin/true",
        "DEVMAN_GUARD": str(guard),
    }
    paths = Paths.from_env(env)
    paths.library.mkdir(parents=True)
    shutil.copy(ROOT / "tests/fixtures/library/base.yaml", paths.base_src)
    paths.projects_toml.write_text(f'[probe]\npath = "{project}"\n')
    flow = paths.workflows / "probe" / "check.yaml"
    flow.parent.mkdir(parents=True)
    flow.write_text('queue: light\nsteps:\n  - name: check\n    run: "true"\n')
    os.environ["DAGU_HOME"] = str(root / "dagu-home")
    return paths


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="probe-", dir=HERE) as temporary:
        root = Path(temporary)
        paths = make_plane(root)
        assert compile(paths) == 0

        # The value is a harmless sentinel. The event log stores arbitrary
        # fields with permissions granted by the process umask.
        emit(paths, Event("tick", "probe", fields={"TOKEN": "example-only"}))
        print(json.dumps({
            "case": "event-fields",
            "log_mode": oct(paths.events.stat().st_mode & 0o777),
            "value_in_log": "example-only" in paths.events.read_text(),
        }))

        # A source may replace working_dir. The header guard still checks the
        # manifest path, so this test uses a different, missing directory.
        wrong = root / "wrong-directory"
        output = root / "step-output"
        flow = paths.workflows / "probe" / "check.yaml"
        flow.write_text(
            f'working_dir: "{wrong}"\nqueue: light\nsteps:\n'
            f'  - name: check\n    run: "pwd > {output}"\n'
        )
        working_compile = compile(paths)
        run = subprocess.run(
            ["dagu", "--config", str(paths.dagu_config), "start", str(paths.dags / "probe/probe.check.yaml")],
            capture_output=True,
            text=True,
            check=False,
        )
        print(json.dumps({
            "case": "source-working-dir",
            "compile_exit": working_compile,
            "run_exit": run.returncode,
            "wrong_dir_created": wrong.is_dir(),
            "step_pwd": output.read_text().strip() if output.exists() else None,
            "run_tail": run.stdout.splitlines()[-5:] + run.stderr.splitlines()[-5:],
        }))

        # Dagu accepts a queue that config does not define. The compiler only
        # checks each workflow source, not the base queue.
        base = paths.base_src.read_text()
        paths.base_src.write_text(base.replace("queue: light", "queue: ghost", 1))
        base_compile = compile(paths)
        print(json.dumps({
            "case": "base-queue",
            "compile_exit": base_compile,
            "base_queue": paths.base_out.read_text().split("queue: ")[1].splitlines()[0],
            "doctor_compile": doctor.check_compile(paths),
        }))

        paths.base_src.write_text("{}\n")
        empty_base = compile(paths)
        run_without_handler = subprocess.run(
            ["dagu", "--config", str(paths.dagu_config), "start", str(paths.dags / "probe/probe.check.yaml")],
            capture_output=True,
            text=True,
            check=False,
        )
        print(json.dumps({
            "case": "base-removes-handler",
            "compile_exit": empty_base,
            "base_has_handler": "handler_on" in paths.base_out.read_text(),
            "run_exit": run_without_handler.returncode,
            "run_has_exit_handler": "onExit" in run_without_handler.stdout,
            "doctor_compile": doctor.check_compile(paths),
        }))

        # Use a library workflow so no orphan source directory can mask the
        # lost TOML refusal in doctor.
        flow.unlink()
        flow.parent.rmdir()
        paths.workflows.rmdir()
        library_flow = paths.library / "workflows/check.yaml"
        library_flow.parent.mkdir()
        library_flow.write_text('queue: light\nsteps:\n  - name: check\n    run: "true"\n')
        paths.projects_toml.write_text(
            f'[probe]\npath = "{root / "project"}"\ntake = ["check"]\n'
        )
        paths.base_src.write_text(base)
        assert compile(paths) == 0

        # A TOML parse error returns failure but leaves the last green state.
        paths.projects_toml.write_text("[probe\n")
        bad_manifest = compile(paths)
        code, shown = status.status(paths, "probe", False, root / "project")
        print(json.dumps({
            "case": "invalid-manifest",
            "compile_exit": bad_manifest,
            "record_status": paths.records()["probe"]["status"],
            "doctor_compile": doctor.check_compile(paths),
            "status_exit": code,
            "status_first_line": shown.splitlines()[0],
        }))

        # A base syntax error returns before the compile record changes.
        paths.projects_toml.write_text(f'[probe]\npath = "{root / "project"}"\n')
        paths.base_src.write_text("queue: [\n")
        bad_base = compile(paths)
        print(json.dumps({
            "case": "invalid-base",
            "compile_exit": bad_base,
            "record_status": paths.records()["probe"]["status"],
            "doctor_compile": doctor.check_compile(paths),
        }))

        # The manifest compares lexical paths. A symlink can register the same
        # checkout twice and make current-directory routing ambiguous.
        alias = root / "alias"
        alias.symlink_to(root / "project", target_is_directory=True)
        paths.projects_toml.write_text(
            f'[probe]\npath = "{root / "project"}"\n'
            f'[alias]\npath = "{alias}"\n'
        )
        doc = load(paths.projects_toml)
        paths.base_src.write_text(base)
        duplicate_compile = compile(paths)
        print(json.dumps({
            "case": "duplicate-symlink",
            "accepted_projects": sorted(doc.projects),
            "errors": doc.errors,
            "compile_exit": duplicate_compile,
            "project_from_real_checkout": find_project(paths.records(), root / "project"),
        }))


if __name__ == "__main__":
    main()
