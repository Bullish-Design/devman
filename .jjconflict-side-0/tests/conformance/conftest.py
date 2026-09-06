"""One throwaway Dagu home for the whole conformance run.

`dagu` writes to its home and **seeds five example DAGs on first use** unless
`skip_examples: true`. `flake.nix`'s `groups-validate` sets `HOME` and
`DAGU_HOME` into `$TMPDIR` for that reason; this does the same with
`tmp_path_factory`, and states `skip_examples` as well so the seeding does not
happen at all.

**`dagu validate` only.** It reads a file and exits. `dagu dry` does not — it
creates `log_dir`, which reproduces S15's literally-named directory and is the
whole reason the bounded reader exists (S1). Nothing here runs it.

The config key spelling is measured, not guessed: Dagu 2.15.0 refuses a
camelCase config outright — "config file uses legacy camelCase keys; migrate to
snake_case: skipexamples -> skip_examples" — before it looks at any DAG.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dagu"


@dataclass
class Dagu:
    """The pinned binary, aimed at a home nothing else shares."""

    binary: str
    home: Path

    def validate(self, path: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.binary, "--dagu-home", str(self.home), "validate", str(path)],
            capture_output=True,
            text=True,
            env=self._env(),
        )

    def ls(self, dags: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.binary, "--dagu-home", str(self.home), "ls"],
            capture_output=True,
            text=True,
            env=self._env(dags),
        )

    def enqueue(self, dags: Path, name: str) -> subprocess.CompletedProcess:
        """Queue one run. **This does not start anything**: no scheduler runs in
        these tests, so the item sits in the queue directory and is read back
        from there. `dagu dry` would execute and create `log_dir` (S1)."""
        return subprocess.run(
            [self.binary, "--dagu-home", str(self.home), "enqueue", name],
            capture_output=True,
            text=True,
            env=self._env(dags),
        )

    def status(self, dags: Path, name: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.binary, "--dagu-home", str(self.home), "status", name],
            capture_output=True,
            text=True,
            env=self._env(dags),
        )

    def _env(self, dags: Path | None = None) -> dict:
        """Never the ambient environment. `HOME` and `DAGU_HOME` are stated
        because an unset one makes `dagu` build a fresh home and seed five
        example DAGs (S2)."""
        env = {
            **os.environ,
            "HOME": str(self.home.parent),
            "DAGU_HOME": str(self.home),
        }
        if dags is not None:
            env["DAGU_DAGS_DIR"] = str(dags)
        return env


@pytest.fixture(scope="session")
def dagu(tmp_path_factory: pytest.TempPathFactory) -> Dagu:
    binary = shutil.which("dagu")
    if binary is None:
        pytest.skip("dagu is not on PATH — this layer measures the pinned binary")
    root = tmp_path_factory.mktemp("dagu-conformance")
    home = root / "dagu"
    home.mkdir()
    (home / "config.yaml").write_text("skip_examples: true\nauth:\n  mode: none\n")
    return Dagu(binary=binary, home=home)


@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIXTURES
