"""The bounded Dagu reader (`src/devman/workflow.py`).

Every table here was measured against the pinned Dagu 2.15.0 and recorded in
`.scratch/projects/007-standard-workflows/STAGE_7_LOG.md`. The tests assert the
measurement; they do not re-derive it. `tests/conformance/test_dagu_yaml.py`
holds the other half — that Dagu itself still agrees.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from devman.workflow import PROJECT_DIR, SELF_DIR, Workflow

pytestmark = pytest.mark.unit


def _read(text: str) -> Workflow:
    """A `Workflow` over YAML text, with no file behind it.

    `Workflow.read()` is exercised separately below. Everything that reads the
    document takes the same path whether the text came from a file or not, so
    the rest of this module states the YAML inline and stays legible.
    """
    text = textwrap.dedent(text)
    return Workflow(path=Path("inline.yaml"), text=text, doc=yaml.safe_load(text) or {})


# ---------------------------------------------------------------------------
# reading a file at all


def test_read_missing_file_is_a_finding_not_a_crash(tmp_path):
    """§10 check 1's failure must arrive as text. A projected file that fails to
    load is a `doctor` finding, never an exception (workflow.py's docstring)."""
    result = Workflow.read(tmp_path / "nothing.yaml")
    assert result.doc is None
    assert result.error.startswith("cannot read:")


def test_read_invalid_yaml_is_a_finding(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("steps: [\n")
    result = Workflow.read(path)
    assert result.doc is None
    assert "not loadable as YAML" in result.error


def test_read_non_mapping_document_is_a_finding(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- a\n- b\n")
    result = Workflow.read(path)
    assert result.doc is None
    assert result.error == "the document is not a mapping"


def test_read_empty_file_is_an_empty_mapping(tmp_path):
    """An empty file loads as `None`, and every reader below expects a dict."""
    path = tmp_path / "empty.yaml"
    path.write_text("")
    result = Workflow.read(path)
    assert result.error is None
    assert result.doc == {}


# ---------------------------------------------------------------------------
# params() — five spellings (S-10)

PARAM_FORMS = [
    pytest.param(
        """
        params:
          - A: x
          - B: y
        """,
        {"A": "x", "B": "y"},
        id="legacy-list",
    ),
    pytest.param("params: {A: x, B: y}", {"A": "x", "B": "y"}, id="legacy-map"),
    pytest.param('params: "A=x B=y"', {"A": "x", "B": "y"}, id="string"),
    pytest.param("params: [A=x, B=y]", {"A": "x", "B": "y"}, id="inline-list"),
    pytest.param(
        """
        params:
          - name: A
            type: string
            default: x
        """,
        {"A": "x"},
        id="typed",
    ),
    pytest.param(
        """
        params:
          - name: A
            type: string
        """,
        {"A": ""},
        id="typed-no-default",
    ),
    pytest.param(
        """
        params:
          - name: A
            enum: [x, y]
            default: y
        """,
        {"A": "y"},
        id="typed-enum",
    ),
    pytest.param(
        """
        params:
          - Z: q
          - name: A
            type: string
            default: x
        """,
        {"Z": "q", "A": "x"},
        id="mixed-spellings",
    ),
]


@pytest.mark.parametrize(("text", "expected"), PARAM_FORMS)
def test_params_reads_every_spelling(text, expected):
    """S-10: Dagu 2.15.0 accepts five spellings, and the fifth — the inline typed
    definition — was read as three parameters that do not exist.

    **A list item holding a `name` key defines the parameter that key names.**
    Dagu's own rule: `- name: FOO` alone is refused with "must define at least
    one field in addition to name", so a list-form parameter cannot be called
    `name` and the key's presence decides the reading with no heuristic.
    """
    assert _read(text).params() == expected


def test_params_absent_is_empty():
    assert _read("steps: []").params() == {}


def test_positional_params_are_not_returned():
    """A positional parameter has no name, and devman fills parameters by name."""
    assert _read('params: "one two"').params() == {}
    assert _read("params: [one, two]").params() == {}


@pytest.mark.parametrize(
    ("written", "expected"),
    [("5", "5"), ("true", "true"), ("false", "false"), ("null", "")],
)
def test_params_defaults_become_the_string_dagu_would_pass(written, expected):
    """`_scalar()`. Dagu keeps a default scalar — an object or array default is
    refused at validation (S-10) — so a string is always the honest rendering.
    A YAML boolean must not arrive as Python's `True`."""
    assert _read(f"params: {{A: {written}}}").params() == {"A": expected}


def test_params_string_form_strips_quotes():
    assert _read("params: ['A=\"x y\"']").params() == {"A": "x y"}


# ---------------------------------------------------------------------------
# holds_project_dir() — §11's rule, mechanically

TYPED_PROJECT_DIR = f"""
params:
  - name: {PROJECT_DIR}
    type: string
    default: /tmp
"""


def test_typed_param_holding_the_project_dir_is_seen():
    """The regression S-10's fix closed. Read as a plain mapping, this file
    yields `name`, `type` and `default` and loses the real parameter — so §11's
    first branch never fired and the developer was told to add a parameter the
    file already had."""
    assert _read(TYPED_PROJECT_DIR).holds_project_dir() == ["params"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(f"params:\n  - {PROJECT_DIR}: /tmp", ["params"], id="params"),
        pytest.param(f"env:\n  {PROJECT_DIR}: /tmp", ["env"], id="env-map"),
        pytest.param(f"env:\n  - {PROJECT_DIR}: /tmp", ["env"], id="env-list-map"),
        pytest.param(f"env:\n  - {PROJECT_DIR}=/tmp", ["env"], id="env-list-string"),
        pytest.param(
            f"working_dir: ${{{PROJECT_DIR}}}", ["working_dir"], id="working_dir"
        ),
        pytest.param(f"log_dir: ${{{PROJECT_DIR}}}/x", ["log_dir"], id="log_dir"),
    ],
)
def test_holds_project_dir_finds_the_four_places(text, expected):
    assert _read(text).holds_project_dir() == expected


def test_a_parent_directing_a_child_does_not_hold_the_name():
    """S8 (`STAGE_2_LOG.md`): the rule that forbade mentioning `DEVMAN_PROJECT_DIR`
    at all reported the only correct cross-repo workflow in this repository as
    broken. Inside a step's `with.params` the name is how a parent directs a
    child."""
    text = f"""
    params:
      - {SELF_DIR}: /tmp
    steps:
      - name: a
        action: dag.run
        with:
          dag: child
          params: {{{PROJECT_DIR}: /elsewhere}}
    """
    assert _read(text).holds_project_dir() == []


# ---------------------------------------------------------------------------
# steps() — the loader and the validator disagree, and devman follows the validator


def test_steps_reads_the_sequence_form():
    text = """
    steps:
      - name: a
        run: echo a
      - name: b
        run: echo b
    """
    assert [s["name"] for s in _read(text).steps()] == ["a", "b"]


def test_mapping_form_steps_are_deliberately_unread():
    """S-8: `dagu dry` RUNS a mapping-form `steps:` and `dagu validate` REFUSES
    it — "entrypoint document steps must be a non-empty sequence". Reading it
    here would make devman more permissive than the validator §10 check 1 runs
    over every projected file, so the file stays invalid and `doctor` is what
    says so."""
    text = """
    steps:
      a:
        run: echo a
    """
    assert _read(text).steps() == []


def test_non_mapping_step_entries_are_skipped():
    assert _read("steps: [ok-name, {name: a, run: echo}]").steps() == [
        {"name": "a", "run": "echo"}
    ]


# ---------------------------------------------------------------------------
# unbounded_fanout() — eight shapes (S-8)

CHILD = "    action: dag.run\n    with: {dag: child}\n"
TWO_CHILDREN = f"steps:\n  - name: a\n{CHILD}  - name: b\n{CHILD}"

FANOUT_SHAPES = [
    pytest.param(
        TWO_CHILDREN,
        ["2 dag.run steps, and neither type: chain nor max_active_steps"],
        id="two-children-no-type",
    ),
    pytest.param("type: chain\n" + TWO_CHILDREN, [], id="two-children-chain"),
    pytest.param("max_active_steps: 4\n" + TWO_CHILDREN, [], id="max-active-steps"),
    pytest.param(
        """
        steps:
          - name: f
            action: dag.run
            with: {dag: "${ITEM.dag}"}
            parallel:
              items:
                - {dag: one}
                - {dag: two}
        """,
        ["step 'f' fans out with no parallel.max_concurrent"],
        id="parallel-unbounded",
    ),
    pytest.param(
        """
        steps:
          - name: f
            action: dag.run
            with: {dag: "${ITEM.dag}"}
            parallel:
              items:
                - {dag: one}
                - {dag: two}
              max_concurrent: 2
        """,
        [],
        id="parallel-bounded",
    ),
    pytest.param(
        """
        steps:
          - name: f
            action: dag.run
            with: {dag: "${ITEM}"}
            parallel: [a, b, c]
        """,
        ["step 'f' fans out with no parallel.max_concurrent"],
        id="parallel-list-shorthand",
    ),
    pytest.param(f"steps:\n  - name: a\n{CHILD}", [], id="one-child"),
    pytest.param(
        """
        steps:
          a:
            action: dag.run
            with: {dag: one}
          b:
            action: dag.run
            with: {dag: two}
        """,
        [],
        id="mapping-form-steps",
    ),
]


@pytest.mark.parametrize(("text", "expected"), FANOUT_SHAPES)
def test_unbounded_fanout_reports_only_an_unstated_bound(text, expected):
    """S-8: a `dag.run` child takes no slot in any queue. The parent executes it
    in place, so a queue name in the child throttles nothing and the only bound
    is one the parent states — `type: chain`, `max_active_steps`, or
    `parallel.max_concurrent`.

    Two rows carry their own measurement:

    * `max_active_steps: 4` is **never** a finding. The author said 4, and §15.7
      forbids devman deciding 4 is too many.
    * mapping-form `steps:` reports nothing because `steps()` reads none of it,
      by design — see `test_mapping_form_steps_are_deliberately_unread`. The file
      is already a §10 check 1 finding, and devman does not become more
      permissive than the validator to say so twice.
    """
    assert _read(text).unbounded_fanout() == expected


def test_a_stated_bound_of_one_is_still_a_stated_bound():
    """§15.7, as a value rather than as prose."""
    assert _read("max_active_steps: 1\n" + TWO_CHILDREN).unbounded_fanout() == []


def test_child_runs_and_triggers_other_dags():
    doc = _read(TWO_CHILDREN)
    assert len(doc.child_runs()) == 2
    assert doc.triggers_other_dags() is True
    plain = _read("steps:\n  - name: a\n    run: echo hi")
    assert plain.child_runs() == []
    assert plain.triggers_other_dags() is False


def test_dag_enqueue_is_not_a_dag_run():
    """S-8: `dag.enqueue` is the path that DOES admit through the queue, so it is
    not a fan-out finding — and it is not a substitute for `dag.run` either,
    because it never reports the child's result."""
    text = "steps:\n  - name: a\n    action: dag.enqueue\n    with: {dag: child}\n"
    assert _read(text).child_runs() == []
    assert _read(text).unbounded_fanout() == []


# ---------------------------------------------------------------------------
# handlers() — base.yaml is inherited whole-field (§9.2)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("steps: []", [], id="absent"),
        pytest.param("handler_on:\n  success:\n    run: echo", ["success"], id="one"),
        pytest.param(
            "handler_on:\n  success: {run: echo}\n  exit: {run: echo}",
            ["exit", "success"],
            id="two-sorted",
        ),
        pytest.param("handler_on: {}", [], id="empty-mapping"),
    ],
)
def test_handlers_reports_every_event_defined(text, expected):
    """Any key counts. `handler_on` is one field, so defining `success` alone
    still replaces the machine's whole block, exit handler included — and the
    run then appends no line to `.devman/.runs/metadata.jsonl`
    (`STAGE_4_LOG.md`, S3)."""
    assert _read(text).handlers() == expected


# ---------------------------------------------------------------------------
# queues() — every queue name a file can hold on the pin (S-9, S-11)


def test_queues_reads_the_dags_own_queue():
    assert _read("queue: light\nsteps: []").queues() == ["light"]


def test_queues_reads_a_child_queue_on_dag_enqueue():
    """`with.queue` is the only step-level queue Dagu 2.15.0 has, and it exists
    on `dag.enqueue` alone (S-11). It matters to `doctor` check 2 for S-9's
    reason: an undeclared name is not unlimited, it is concurrency 1 shared with
    every other DAG carrying the same misspelling."""
    text = """
    queue: light
    steps:
      - name: a
        action: dag.enqueue
        with: {dag: child, queue: heavy}
    """
    assert _read(text).queues() == ["light", "heavy"]


def test_queues_ignores_a_step_level_queue_key():
    """S-11, measured: `steps[].queue` does not exist on the pin. `dagu validate`
    refuses the file — "'spec.step' has invalid keys: queue" — so such a file is
    a §10 check 1 finding and never runs. Reporting its queue name as well would
    be devman reading a field Dagu does not have."""
    text = "steps:\n  - name: a\n    queue: heavy\n    run: echo hi\n"
    assert _read(text).queues() == []


def test_queues_absent_is_empty():
    """S-9: a DAG naming no queue still gets one — a queue named after itself, at
    concurrency 1. That is Dagu's fallback and not a name in the file, so
    `queues()` reports nothing and `doctor` check 2 has nothing to check."""
    assert _read("steps: []").queues() == []
