from __future__ import annotations

import pytest
import yaml
from conftest import Plane

from devman.compile import compile


def test_working_dir_refusal_keeps_the_last_compiled_file(plane: Plane, fake) -> None:
    plane.library("check")
    plane.add_project("alpha", '"check"')
    assert compile(plane.paths) == 0
    dag = plane.dag("alpha", "check")
    before = dag.read_bytes()
    assert yaml.safe_load(dag.read_text())["working_dir"] == str(
        plane.project_dir("alpha")
    )

    plane.own(
        "alpha",
        "check",
        'queue: light\nworking_dir: "/wrong"\nsteps:\n  - run: echo wrong\n',
    )
    assert compile(plane.paths) == 1

    assert dag.read_bytes() == before
    record = plane.record()["projects"]["alpha"]
    assert record["status"] == "refused"
    assert record["stale"] is True
    assert "top-level working_dir is set by devman" in " ".join(record["reasons"])


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("steps: []\n", "queue must be a nonempty configured string"),
        ("queue: ghost\nsteps: []\n", "queue ghost is not configured"),
    ],
)
def test_queue_refusal_keeps_the_last_compiled_file(
    plane: Plane, fake, source: str, reason: str
) -> None:
    plane.library("check")
    plane.add_project("alpha", '"check"')
    assert compile(plane.paths) == 0
    dag = plane.dag("alpha", "check")
    before = dag.read_bytes()

    plane.own("alpha", "check", source)
    assert compile(plane.paths) == 1

    assert dag.read_bytes() == before
    record = plane.record()["projects"]["alpha"]
    assert record["status"] == "refused"
    assert record["stale"] is True
    assert reason in " ".join(record["reasons"])
