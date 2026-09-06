"""The fixtures. Everything they build lives in `tests/helpers.py`.

**No test in this suite may touch the installed plane.** `plane` is a registry
root under `tmp_path`, and `no_ambient_plane` removes the variables that would
let a stray inherited value reach `run.resolve()` or `run.child_env()` — the
same three names those functions clear, for the same reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import Plane

from devman.registry import Registry
from devman.workflow import PROJECT_DIR, SELF_DIR


@pytest.fixture
def plane(tmp_path: Path) -> Plane:
    return Plane(root=tmp_path / "registry", repos=tmp_path / "repos")


@pytest.fixture
def reg(plane: Plane) -> Registry:
    return plane.reg


@pytest.fixture(autouse=True)
def no_ambient_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the plane's own variables for every test.

    A developer running the suite from inside a triggered run would otherwise
    inherit `DEVMAN_PROJECT_DIR`, and the tests of `child_env()` would pass for
    the wrong reason. `DAGU_HOME` goes for the reason `run.command()` states
    `--dagu-home` rather than inheriting one (S2).
    """
    for name in (PROJECT_DIR, SELF_DIR, "DAGU_HOME"):
        monkeypatch.delenv(name, raising=False)
