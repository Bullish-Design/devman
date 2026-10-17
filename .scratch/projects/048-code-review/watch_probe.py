"""Test a newly created workflow tree with the real watchexec watcher."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from devman.paths import Paths

from experiments import HERE, ROOT, make_plane


def wait_for(predicate, seconds: float = 12.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="watch-", dir=HERE) as temporary:
        root = Path(temporary)
        paths: Paths = make_plane(root)
        own = paths.workflows / "probe"
        (own / "check.yaml").unlink()
        own.rmdir()
        paths.workflows.rmdir()
        library_flow = paths.library / "workflows/check.yaml"
        library_flow.parent.mkdir()
        library_flow.write_text('queue: light\nsteps:\n  - name: old\n    run: "true"\n')
        paths.projects_toml.write_text(
            f'[probe]\npath = "{root / "project"}"\ntake = ["check"]\n'
        )
        env = {**os.environ}
        env.update({
            "DEVMAN_OVERLAY": str(paths.overlay),
            "DEVMAN_STATE": str(paths.state),
            "DEVMAN_DAGU_CONFIG": str(paths.dagu_config),
            "DEVMAN_BASH": str(ROOT / ".devenv/profile/bin/bash"),
            "DEVMAN_BIN": "/bin/true",
            "DEVMAN_GUARD": str(paths.guard),
            "PATH": str(ROOT / ".devenv/profile/bin") + os.pathsep + os.environ["PATH"],
        })
        # The Nix profile has bash under its own bin path.
        if not Path(env["DEVMAN_BASH"]).is_file():
            env["DEVMAN_BASH"] = "/run/current-system/sw/bin/bash"
        log = root / "watcher.txt"
        with log.open("w") as stream:
            # The review workspace itself sits under `.gitman`. The production
            # watcher ignores that name, so remove it only for this probe.
            program = (
                "from devman import watch; from devman.paths import Paths; "
                "watch.IGNORE = tuple(n for n in watch.IGNORE if n != '.gitman'); "
                "raise SystemExit(watch.watch(Paths.from_env(), '100ms'))"
            )
            proc = subprocess.Popen(
                [sys.executable, "-c", program],
                env=env,
                stderr=stream,
                stdout=subprocess.DEVNULL,
            )
            try:
                ready = wait_for(lambda: "watchexec ready" in log.read_text())
                initial = paths.records()["probe"]["workflows"]["check"]["origin"]
                own.mkdir(parents=True)
                (own / "check.yaml").write_text(
                    'queue: light\nsteps:\n  - name: new\n    run: "true"\n'
                )
                time.sleep(2)
                after_creation = paths.records()["probe"]["workflows"]["check"]["origin"]
                paths.projects_toml.write_text(
                    paths.projects_toml.read_text() + "\n# force overlay file event\n"
                )
                recovered = wait_for(
                    lambda: paths.records()["probe"]["workflows"]["check"]["origin"]
                    == "project"
                )
                print(json.dumps({
                    "ready": ready,
                    "initial_origin": initial,
                    "after_directory_creation": after_creation,
                    "after_manifest_edit": "project" if recovered else None,
                    "watcher_exit_before_stop": proc.poll(),
                    "watcher_log": log.read_text().splitlines()[-10:],
                }))
            finally:
                proc.terminate()
                proc.wait(timeout=15)


if __name__ == "__main__":
    main()
