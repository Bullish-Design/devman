"""The devman/Dagu semantic boundary, stated in both directions.

For every fixture in `tests/fixtures/dagu/` this layer asserts two things:

    Dagu accepts / refuses it     <- `dagu validate`, against the pinned binary
    devman extracts X             <- `Workflow.read()` and the bounded helpers

**The reason this layer exists is drift.** A Dagu pin bump must run these before
it is accepted. Every unit test of `workflow.py` asserts a measurement of Dagu
2.15.0's behaviour; nothing but this file notices when the binary underneath
those measurements changes.

`nix/dagu.nix` holds the pin. `flake.nix`'s `python-tests` check puts it on
`PATH`, so `nix flake check` runs this layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from devman.workflow import PROJECT_DIR, Workflow

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Case:
    """One fixture, and both halves of what it pins.

    `refusal` is a substring of Dagu's own message, kept short enough to survive
    a reworded error and specific enough to prove which rule fired. `warning` is
    the same for a file Dagu accepts and complains about.

    The `None` defaults mean "this fixture pins nothing about that helper", not
    "expect an empty answer".
    """

    fixture: str
    valid: bool
    refusal: str = ""
    warning: str = ""
    params: dict[str, str] | None = None
    steps: int | None = None
    queues: list[str] | None = None
    handlers: list[str] | None = None
    fanout: list[str] | None = None
    holds: list[str] | None = field(default=None)


CASES = [
    # -- params: five spellings, and the three forms Dagu refuses (S-10) ------
    Case("params-legacy-list", True, params={"A": "x", "B": "y"}),
    Case("params-legacy-map", True, params={"A": "x", "B": "y"}),
    Case("params-string", True, params={"A": "x", "B": "y"}),
    Case("params-inline-list", True, params={"A": "x", "B": "y"}),
    Case("params-typed", True, params={"A": "x"}),
    Case("params-typed-nodefault", True, params={"A": ""}),
    Case("params-typed-enum", True, params={"A": "y"}),
    Case("params-mixed", True, params={"Z": "q", "A": "x"}),
    Case(
        "params-typed-name-only",
        False,
        refusal="must define at least one field in addition to name",
    ),
    Case(
        "params-typed-object-default",
        False,
        refusal="inline parameter definitions must use object form with name",
    ),
    Case(
        "param-schema-key", False, refusal="'spec.dag' has invalid keys: param_schema"
    ),
    # -- steps: the loader and the validator disagree (S-8) ------------------
    Case("steps-list", True, steps=2),
    Case(
        "steps-map",
        False,
        refusal="entrypoint document steps must be a non-empty sequence",
        steps=0,
    ),
    Case(
        "step-command", True, warning="steps[0].command is deprecated; use run", steps=1
    ),
    Case("top-level-name", False, refusal="entrypoint document must not define name"),
    # -- env: both spellings hold DEVMAN_PROJECT_DIR -------------------------
    Case("env-map", True, holds=["env"]),
    Case("env-list", True, holds=["env"]),
    Case("env-list-strings", True, holds=["env"]),
    # -- queues (S-9, S-11) --------------------------------------------------
    Case("queues", True, queues=["light", "heavy"]),
    Case(
        "step-queue",
        False,
        refusal="'spec.step' has invalid keys: queue",
        queues=[],
    ),
    Case(
        "dagrun-with-queue",
        False,
        refusal="dag.run does not support with.queue",
        queues=["heavy"],
    ),
    # -- handlers (§9.2) -----------------------------------------------------
    Case("handler", True, handlers=["success"]),
    # -- fan-out: eight shapes, all valid to Dagu (S-8) ----------------------
    Case("fanout-chain", True, fanout=[]),
    Case(
        "fanout-unbounded",
        True,
        fanout=["2 dag.run steps, and neither type: chain nor max_active_steps"],
    ),
    Case("fanout-max-active-steps", True, fanout=[]),
    Case("parallel-bounded", True, fanout=[]),
    Case(
        "parallel-unbounded",
        True,
        fanout=["step 'f' fans out with no parallel.max_concurrent"],
    ),
    Case(
        "parallel-list",
        True,
        fanout=["step 'f' fans out with no parallel.max_concurrent"],
    ),
    Case("dag-enqueue", True, fanout=[]),
    Case("cross-repo-holds-project-dir", True, holds=["params"], fanout=[]),
    # -- the DAG name, which comes from the file's base name (S1) ------------
    Case("name.dots_and_underscores", True, steps=1),
    Case(
        "name-with@at",
        False,
        refusal="name must only contain alphanumeric characters, dashes, dots, and underscores",
        steps=1,
    ),
]

IDS = [case.fixture for case in CASES]


def path_of(fixtures: Path, case: Case) -> Path:
    return fixtures / f"{case.fixture}.yaml"


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_dagu_still_agrees(case: Case, dagu, fixtures: Path):
    """Half one: what the pinned binary does with the file.

    A failure here is a **pin bump**, not a devman regression — Dagu changed its
    mind about a file devman reads. Read the message before changing the case:
    S-9's lesson was that a wrong sentence gets copied faithfully into every
    layer that documents it, and this file is the only place that measures.
    """
    result = dagu.validate(path_of(fixtures, case))
    output = result.stdout + result.stderr

    if case.valid:
        assert result.returncode == 0, output
    else:
        assert result.returncode != 0, "Dagu now accepts a file it refused"
        assert case.refusal in output, output

    if case.warning:
        assert case.warning in output, output


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_devman_extracts_what_it_claims(case: Case, fixtures: Path):
    """Half two: what devman's bounded reader takes out of the same bytes.

    **devman reads a file Dagu refuses, and that is deliberate.** §10 check 1
    runs `dagu validate` over every projected file, so an invalid file is already
    a finding; the reader's job is to tolerate it rather than to re-implement the
    schema (`workflow.py`). The refused fixtures below therefore still state what
    comes out.
    """
    wf = Workflow.read(path_of(fixtures, case))
    assert wf.error is None, wf.error

    if case.params is not None:
        assert wf.params() == case.params
    if case.steps is not None:
        assert len(wf.steps()) == case.steps
    if case.queues is not None:
        assert wf.queues() == case.queues
    if case.handlers is not None:
        assert wf.handlers() == case.handlers
    if case.fanout is not None:
        assert wf.unbounded_fanout() == case.fanout
    if case.holds is not None:
        assert wf.holds_project_dir() == case.holds


def test_every_fixture_is_in_the_table(fixtures: Path):
    """A fixture nobody asserts against is a file nobody reads (§12 rule 7)."""
    on_disk = {p.stem for p in fixtures.glob("*.yaml")}
    assert on_disk == set(IDS)


def test_a_typed_project_dir_is_valid_to_dagu_and_refused_by_devman(dagu, fixtures):
    """The two halves disagreeing on purpose, which is what §11 is.

    `cross-repo-holds-project-dir.yaml` is a perfectly good Dagu file. Nothing
    but devman would ever say the parent drags every child into its own
    directory — the children would run, succeed, and do the work in the wrong
    place (S-10, `run.resolve()`).
    """
    case = next(c for c in CASES if c.fixture == "cross-repo-holds-project-dir")
    assert dagu.validate(path_of(fixtures, case)).returncode == 0

    wf = Workflow.read(path_of(fixtures, case))
    assert wf.triggers_other_dags()
    assert wf.holds_project_dir() == ["params"]
    assert PROJECT_DIR in wf.params()


def test_a_dotted_and_underscored_dag_name_resolves(dagu, fixtures, tmp_path):
    """`dagu ls` finds a DAG whose file name holds dots and underscores.

    This one is for the session after this one. `<project>-<workflow>` is not
    injective (S6), and whatever encoding replaces it may use a dot or an
    underscore — but not an `@`, which `name-with@at` above pins.

    `ls` reads. `dry` would create `log_dir`, so it is not used here (S1).
    """
    dags = tmp_path / "dags"
    dags.mkdir()
    (dags / "a.b_c-d.yaml").write_text((fixtures / "steps-list.yaml").read_text())

    result = dagu.ls(dags)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "a.b_c-d" in result.stdout
