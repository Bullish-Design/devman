import hashlib
from pathlib import Path

import pytest
import yaml

from devman.render import check_source, render

QUEUES = ["light", "heavy"]
SRC = Path("/o/library/workflows/check.yaml")


def make(text: str, project: str = "devman") -> str:
    return render(
        project,
        "check",
        Path("/work/devman"),
        Path("/s/runs/devman"),
        "library",
        SRC,
        text,
        "/g/guard.sh",
    )


def refusals(text: str) -> list[str]:
    return check_source(text, QUEUES, "devman/check")


def test_header_keys_are_added_when_absent() -> None:
    text = "queue: light\nsteps:\n  - name: s\n    run: echo hi\n"
    out = make(text)
    doc = yaml.safe_load(out)
    assert doc["working_dir"] == "/work/devman"
    assert doc["log_dir"] == "/s/runs/devman"
    assert doc["shell"] == "/g/guard.sh"
    assert doc["group"] == "devman"
    assert doc["labels"] == {"project": "devman"}
    assert doc["env"] == [{"DEVMAN_PROJECT_DIR": "/work/devman"}]
    assert doc["params"] == [{"DEVMAN_EVENT": ""}, {"DEVMAN_SUBJECT": ""}]
    assert doc["queue"] == "light"
    assert "name" not in doc
    # The guard owner is the compiled header (PLAN §A.8; Stage 7 measured that
    # a base `shell:` never reaches a step on Dagu 2.20.1). The packaged base
    # carries no top-level shell of its own.
    packaged = yaml.safe_load(
        Path(__file__)
        .resolve()
        .parent.parent.joinpath("src/devman/base.yaml")
        .read_text()
    )
    assert "shell" not in packaged


def test_the_header_comments_and_the_source_text() -> None:
    text = "# my comment\nsteps:\n  - name: s\n    run: echo hi\n"
    out = make(text)
    lines = out.splitlines()
    assert lines[0].startswith("# devman: compiled file. Do not edit.")
    assert lines[1] == "# devman: project=devman workflow=check origin=library"
    assert lines[2] == f"# devman: source={SRC}"
    assert (
        lines[3]
        == "# devman: source-sha256=" + hashlib.sha256(text.encode()).hexdigest()
    )
    assert out.endswith("# devman: source text follows\n" + text)


def test_a_source_without_a_final_newline_gets_one() -> None:
    assert make("steps: []").endswith("steps: []\n")


@pytest.mark.parametrize(
    ("key", "value"),
    [("group", '"mine"'), ("labels", "[a=b]")],
)
def test_the_source_wins_for_group_and_labels(key: str, value: str) -> None:
    out = make(f"{key}: {value}\nsteps: []\n")
    doc = yaml.safe_load(out)  # a duplicate key would raise or override
    assert out.count(f"\n{key}:") + out.startswith(f"{key}:") == 1
    assert doc[key] == yaml.safe_load(value)


def test_working_dir_is_refused_and_the_manifest_path_is_always_rendered() -> None:
    assert refusals('working_dir: "/elsewhere"\nqueue: light\nsteps: []\n') == [
        "devman/check: top-level working_dir is set by devman; "
        "the manifest sets the project directory"
    ]
    doc = yaml.safe_load(make("queue: light\nsteps: []\n"))
    assert doc["working_dir"] == "/work/devman"


def test_a_path_with_odd_characters_is_quoted() -> None:
    out = render(
        "p", "w", Path('/a b/"c"'), Path("/s"), "project", SRC, "steps: []\n", "/g"
    )
    assert yaml.safe_load(out)["working_dir"] == '/a b/"c"'


def test_a_leading_document_marker_is_dropped() -> None:
    out = make("# lead\n---\nsteps: []\n")
    assert len(list(yaml.safe_load_all(out))) == 1


def test_later_documents_stay() -> None:
    out = make("steps: []\n---\nname: sub\nsteps: []\n")
    assert len(list(yaml.safe_load_all(out))) == 2


@pytest.mark.parametrize(
    ("key", "advice"),
    [
        ("env", "use step env or params"),
        ("log_dir", "devman sets the log directory"),
        ("shell", "devman sets the checkout guard shell"),
    ],
)
def test_header_owned_keys_are_refused(key: str, advice: str) -> None:
    assert refusals(f"queue: light\n{key}: x\nsteps: []\n") == [
        f"devman/check: top-level {key} is set by devman; {advice}"
    ]


def test_handler_on_exit_is_refused_but_other_handlers_are_free() -> None:
    assert refusals("queue: light\nhandler_on:\n  exit:\n    run: x\n") == [
        "devman/check: handler_on.exit is set by devman; "
        "use handler_on.success or handler_on.failure"
    ]
    assert refusals("queue: light\nhandler_on:\n  success:\n    run: x\n") == []


def test_a_first_document_that_is_not_a_mapping_is_refused() -> None:
    expected = ["devman/check: the first document is not a mapping"]
    assert refusals("- a\n- b\n") == expected
    assert refusals("") == expected


def test_invalid_yaml_is_refused() -> None:
    [reason] = refusals("steps: [\n")
    assert reason.startswith("devman/check: invalid YAML: ")


@pytest.mark.parametrize(
    "params",
    [
        "[DEVMAN_EVENT, DEVMAN_SUBJECT]",
        '["DEVMAN_EVENT=", "DEVMAN_SUBJECT=x", "OTHER=1"]',
        '[{DEVMAN_EVENT: ""}, {DEVMAN_SUBJECT: ""}]',
        '{DEVMAN_EVENT: "", DEVMAN_SUBJECT: ""}',
        '"DEVMAN_EVENT= DEVMAN_SUBJECT="',
    ],
)
def test_params_that_declare_both_names_pass(params: str) -> None:
    assert refusals(f"queue: light\nparams: {params}\nsteps: []\n") == []


@pytest.mark.parametrize("params", ["[A=1]", "[DEVMAN_EVENT]", "[]", "{}"])
def test_params_that_miss_a_name_are_refused(params: str) -> None:
    assert refusals(f"queue: light\nparams: {params}\nsteps: []\n") == [
        "devman/check: params must declare DEVMAN_EVENT and DEVMAN_SUBJECT"
    ]


def test_a_source_with_params_keeps_them_and_the_header_adds_none() -> None:
    out = make(
        "queue: light\nparams:\n  - DEVMAN_EVENT: x\n  - DEVMAN_SUBJECT: y\nsteps: []\n"
    )
    assert out.count("\nparams:") + out.startswith("params:") == 1


def test_an_unconfigured_queue_is_refused() -> None:
    assert refusals("queue: undefinedq\nsteps: []\n") == [
        "devman/check: queue undefinedq is not configured; configured: light, heavy"
    ]
    assert refusals("queue: heavy\nsteps: []\n") == []


@pytest.mark.parametrize("queue", [None, "", "   ", "~", "[]", "{}", "1"])
def test_a_missing_or_non_string_queue_is_refused(queue: str | None) -> None:
    source = "steps: []\n" if queue is None else f"queue: {queue}\nsteps: []\n"
    assert refusals(source) == [
        "devman/check: queue must be a nonempty configured string"
    ]


def test_a_source_cannot_replace_the_packaged_devman_task_action() -> None:
    assert refusals(
        "queue: light\nactions:\n  devman.task:\n    command: echo replaced\n"
    ) == ["devman/check: action devman.task is reserved by the packaged base"]
