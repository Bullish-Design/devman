"""Shared fixtures: a temporary plane (overlay, state, Dagu config, projects)."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from devman.paths import Paths

FIXTURES = Path(__file__).parent / "fixtures"
FAKES = Path(__file__).parent / "fakes"
ROOT = Path(__file__).resolve().parent.parent
BASH = shutil.which("bash") or "/bin/bash"
STEP = "queue: light\nsteps:\n  - name: s\n    run: echo hi\n"


@dataclass
class Plane:
    root: Path
    paths: Paths
    env: dict[str, str]

    def project_dir(self, name: str) -> Path:
        path = self.root / "work" / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def manifest(self, text: str) -> None:
        self.paths.overlay.mkdir(parents=True, exist_ok=True)
        self.paths.projects_toml.write_text(text)

    def add_project(self, name: str, take: str = "", on: str = "") -> None:
        body = f'[{name}]\npath = "{self.project_dir(name)}"\ntake = [{take}]\n{on}'
        old = self.paths.projects_toml
        self.manifest((old.read_text() if old.exists() else "") + body)

    def library(self, name: str, text: str = STEP) -> None:
        file = self.paths.library / "workflows" / f"{name}.yaml"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def seed(self) -> None:
        """Copy the seed library workflows into the overlay library."""
        shutil.copytree(
            FIXTURES / "library" / "workflows",
            self.paths.library / "workflows",
            dirs_exist_ok=True,
        )

    def own(self, project: str, name: str, text: str = STEP) -> Path:
        file = self.paths.workflows / project / f"{name}.yaml"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return file

    def record(self) -> dict:
        return json.loads(self.paths.compile_json.read_text())

    def dag(self, project: str, name: str) -> Path:
        return self.paths.dags / project / f"{project}.{name}.yaml"


def standin(root: Path, env: dict[str, str]) -> Path:
    """The checkout guard (tokens filled) and a `devman` that runs the source."""
    guard = root / "guard.sh"
    guard.write_text((ROOT / "dagu" / "guard.sh").read_text().replace("@bash@", BASH))
    guard.chmod(0o755)
    exports = "".join(f"export {k}={shlex.quote(v)}\n" for k, v in env.items())
    devman = root / "devman"
    devman.write_text(
        f"#!{BASH}\n{exports}export PYTHONPATH={ROOT / 'src'}\n"
        f'exec {sys.executable} -m devman "$@"\n'
    )
    devman.chmod(0o755)
    return guard


@pytest.fixture
def plane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Plane:
    overlay, state = tmp_path / "overlay", tmp_path / "state"
    config = tmp_path / "dagu.yaml"
    # `skip_examples` matters: Dagu otherwise writes example DAGs into dags_dir.
    config.write_text(
        "auth: {mode: none}\n"
        "skip_examples: true\n"
        f"paths: {{dags_dir: {state}/dags, base_config: {state}/base.yaml}}\n"
        'queues: {enabled: true, config: [{"name": "light", "max_concurrency": 4},'
        ' {"name": "normal", "max_concurrency": 2},'
        ' {"name": "heavy", "max_concurrency": 1}]}\n'
    )
    monkeypatch.setenv("DAGU_HOME", str(tmp_path / "dagu-home"))
    env = {
        "DEVMAN_OVERLAY": str(overlay),
        "DEVMAN_STATE": str(state),
        "DEVMAN_DAGU_CONFIG": str(config),
        "DEVMAN_BASH": BASH,
        "DEVMAN_BIN": str(tmp_path / "devman"),
        "DEVMAN_GUARD": str(tmp_path / "guard.sh"),
        "DAGU_HOME": str(tmp_path / "dagu-home"),
    }
    standin(tmp_path, env)
    paths = Paths.from_env(env)
    paths.library.mkdir(parents=True)
    shutil.copy(FIXTURES / "library" / "base.yaml", paths.base_src)
    return Plane(tmp_path, paths, env)


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
