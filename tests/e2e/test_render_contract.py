"""Check queue validation with the installed Dagu binary."""

from __future__ import annotations

import pytest
from conftest import Plane

from devman.compile import compile

pytestmark = pytest.mark.e2e


def test_configured_queue_compiles_with_real_dagu(plane: Plane) -> None:
    plane.library("check", "queue: light\nsteps:\n  - run: echo valid\n")
    plane.add_project("alpha", '"check"')

    assert compile(plane.paths) == 0

    compiled = plane.dag("alpha", "check").read_text()
    assert "queue: light" in compiled
