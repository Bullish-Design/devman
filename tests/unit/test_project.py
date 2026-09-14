"""The producer's rendered bytes (009 stage 3, P1-1, P2-1, P2-2, P2-4).

**Nothing tested the projection's actual output before this file existed**, and
that gap is why P1-1, P1-3 and P2-1 survived a green suite for a whole stage.
`groups-validate` validates SOURCE group YAML, not the generated header; the VM
test built the projection by hand. The renderer was shell inside
`modules/devenv.nix` and therefore not reachable from a test at all.

Every case here asserts on the rendered string.
"""

from __future__ import annotations

import json

import pytest
import yaml

from devman import project
from devman.project import ProjectionError, render
from devman.workflow import PROJECT_DIR, SELF_DIR

pytestmark = pytest.mark.unit

ORDINARY = "steps:\n  - name: a\n    run: true\n"

CROSS_REPO = f"""params:
  - {SELF_DIR}: ""
steps:
  - name: a
    action: dag.run
    with:
      dag: child
      params:
        {PROJECT_DIR}: "${{{SELF_DIR}}}"
"""


def header_of(text: str) -> dict:
    """The generated header, parsed. The body follows it and is not read."""
    return yaml.safe_load(text)


def env_of(text: str) -> dict:
    """`name -> value` from the rendered `env:` block, whatever form it took."""
    env = header_of(text).get("env")
    if isinstance(env, dict):
        return env
    out = {}
    for item in env or []:
        if isinstance(item, dict):
            out.update(item)
    return out


# ---------------------------------------------------------------------------
# which directory variable — P1-1


def test_an_ordinary_workflow_gets_the_project_dir(tmp_path):
    text = render(tmp_path / "check.yaml", tmp_path, text=ORDINARY)
    assert env_of(text) == {PROJECT_DIR: str(tmp_path)}


def test_a_comment_naming_the_self_dir_does_not_change_the_variable(tmp_path):
    """**P1-1's live case.** The shell decided with `grep -q 'DEVMAN_SELF_DIR'`
    over the whole file, so a COMMENT mentioning the name flipped the emitted
    variable. `.devman/workflows/plane-report.yaml:23` is the real file it broke:
    it is an ordinary workflow whose comment explains the cross-repo rule, and it
    shipped `DEVMAN_SELF_DIR` — so its `working_dir` resolved from a name nothing
    sets, for a whole stage.
    """
    source = f"# {SELF_DIR} is what a cross-repo parent uses (§11)\n{ORDINARY}"

    text = render(tmp_path / "plane-report.yaml", tmp_path, text=source)

    assert env_of(text) == {PROJECT_DIR: str(tmp_path)}
    assert SELF_DIR not in env_of(text)


def test_a_dag_run_parent_gets_the_self_dir(tmp_path):
    """§11: a workflow that directs others targets no project, so it names its
    own directory and must not hold the name it passes to its children."""
    text = render(tmp_path / "stack.yaml", tmp_path, text=CROSS_REPO)
    assert env_of(text) == {SELF_DIR: str(tmp_path)}


# ---------------------------------------------------------------------------
# an existing env: block — refused, never merged and never silently dropped


def test_a_map_form_env_stating_the_right_value_emits_no_duplicate_key(tmp_path):
    source = f"env:\n  {PROJECT_DIR}: {tmp_path}\n{ORDINARY}"

    text = render(tmp_path / "check.yaml", tmp_path, text=source)

    assert "env:" not in text.split("steps:")[0].replace(
        f"env:\n  {PROJECT_DIR}", "", 1
    )
    assert yaml.safe_load(text)["env"] == {PROJECT_DIR: str(tmp_path)}


def test_a_list_form_env_stating_the_right_value_emits_no_duplicate_key(tmp_path):
    source = f"env:\n  - {PROJECT_DIR}: {tmp_path}\n{ORDINARY}"

    text = render(tmp_path / "check.yaml", tmp_path, text=source)

    assert env_of(text) == {PROJECT_DIR: str(tmp_path)}
    assert text.count(PROJECT_DIR) == 1


def test_an_env_block_stating_neither_name_is_refused(tmp_path):
    """**P1-1's severe case.** The shell emitted no header `env:` when the body
    had any `env:` at all, so such a workflow simply lost its directory variable
    and ran in a directory named literally `${DEVMAN_PROJECT_DIR}`.

    Refusing rather than merging is deliberate: merging means the projection
    edits the body, which breaks §7.2 and breaks the guard's tail-equality test.
    """
    source = f"env:\n  - LEVEL: debug\n{ORDINARY}"

    with pytest.raises(ProjectionError) as exc:
        render(tmp_path / "check.yaml", tmp_path, text=source)
    message = str(exc.value)
    assert "check.yaml" in message
    assert f"- {PROJECT_DIR}: {tmp_path}" in message


def test_an_env_block_assigning_a_reserved_name_another_value_is_refused(tmp_path):
    source = f"env:\n  - {PROJECT_DIR}: /somewhere/else\n{ORDINARY}"

    with pytest.raises(ProjectionError) as exc:
        render(tmp_path / "check.yaml", tmp_path, text=source)
    message = str(exc.value)
    assert "/somewhere/else" in message
    assert str(tmp_path) in message


def test_an_env_block_stating_the_other_reserved_name_is_refused(tmp_path):
    """§11's two names are not interchangeable. An ordinary workflow claiming
    `DEVMAN_SELF_DIR` would run with a name nothing else sets."""
    source = f"env:\n  - {SELF_DIR}: {tmp_path}\n{ORDINARY}"

    with pytest.raises(ProjectionError) as exc:
        render(tmp_path / "check.yaml", tmp_path, text=source)
    assert SELF_DIR in str(exc.value)
    assert PROJECT_DIR in str(exc.value)


# ---------------------------------------------------------------------------
# the header adds; it never overwrites


def test_a_body_with_its_own_working_dir_keeps_it(tmp_path):
    source = f"working_dir: /elsewhere\n{ORDINARY}"

    text = render(tmp_path / "check.yaml", tmp_path, text=source)

    assert yaml.safe_load(text)["working_dir"] == "/elsewhere"
    assert text.count("working_dir") == 1


def test_a_body_with_its_own_log_dir_keeps_it(tmp_path):
    source = f"log_dir: /var/log/mine\n{ORDINARY}"

    text = render(tmp_path / "check.yaml", tmp_path, text=source)

    assert yaml.safe_load(text)["log_dir"] == "/var/log/mine"


def test_presence_is_decided_from_the_document_not_from_a_grep(tmp_path):
    """`grep '^working_dir:'` misses a key that is not at the start of a line,
    and hits one inside a step's script. The parsed document does neither."""
    source = "steps:\n  - name: a\n    run: |\n      echo working_dir: no\n"

    text = render(tmp_path / "check.yaml", tmp_path, text=source)

    assert yaml.safe_load(text)["working_dir"] == str(tmp_path)


# ---------------------------------------------------------------------------
# the guard's dependency


def test_the_rendered_file_ends_with_the_source_body(tmp_path):
    """**THIS IS THE CASE THAT PROTECTS THE GUARD.**

    The shell-entry guard notices an edited override by comparing the tail of
    the projection against the source body, byte for byte
    (`modules/devenv.nix`). A renderer that reformatted, re-indented or
    re-emitted the body would break that test silently, and an edited workflow
    would stop reaching Dagu — which is `STAGE_7_LOG.md` S-5a, exactly.
    """
    source = f"# a comment\n{ORDINARY}\n\n# trailing\n"

    text = render(tmp_path / "check.yaml", tmp_path, text=source)

    assert text.endswith(source)


# ---------------------------------------------------------------------------
# encoding — P2-1
#
# The project-path domain was narrower than the public contract stated, with no
# refusal that explained the restriction. Everything here now round-trips; the
# three characters that do not are refused by the hook, by name.

HARD_PATHS = [
    pytest.param("with space", id="space"),
    pytest.param("colon: space", id="colon-space"),
    pytest.param("hash#mark", id="hash"),
    pytest.param('quote"mark', id="double-quote"),
    pytest.param("back\\slash", id="backslash"),
    pytest.param("new\nline", id="newline"),
    pytest.param("café-日本", id="non-ascii"),
    pytest.param("tab\there", id="tab"),
    pytest.param("- leading dash", id="leading-dash"),
    pytest.param("{brace}", id="brace"),
]


@pytest.mark.parametrize("name", HARD_PATHS)
def test_every_supported_path_round_trips_through_the_yaml(tmp_path, name):
    root = tmp_path / name

    text = render(root / "check.yaml", root, text=ORDINARY)

    doc = yaml.safe_load(text)
    assert doc["working_dir"] == str(root)
    assert doc["log_dir"] == str(root / ".devman" / ".runs" / "logs")
    assert doc["env"][0][PROJECT_DIR] == str(root)


@pytest.mark.parametrize("name", HARD_PATHS)
def test_every_supported_path_round_trips_through_the_metadata_json(tmp_path, name):
    root = tmp_path / name

    text = project.entry_text(
        project="p",
        root=root,
        groups=["base"],
        plan="/nix/store/plan.json",
        local=["check"],
        workflows={},
        triggers=None,
    )

    assert json.loads(text)["path"] == str(root)


def test_the_entry_holds_the_three_anchors_the_guard_slices(tmp_path):
    """The layout is a requirement, not a style. The forkless guard cuts on
    these three byte sequences (`modules/devenv.nix`), so a writer that
    reordered or re-indented would make the guard fire on every shell entry."""
    text = project.entry_text(
        project="p",
        root=tmp_path,
        groups=["base"],
        plan="/nix/store/plan.json",
        local=["a", "b"],
        workflows={},
        triggers=None,
    )

    assert '"path": "' in text
    assert '"plan": "' in text
    assert '"local": ["a", "b"]' in text
    assert json.loads(text)["local"] == ["a", "b"]


def test_the_entry_states_schema_four(tmp_path):
    text = project.entry_text(
        project="p",
        root=tmp_path,
        groups=[],
        plan="/nix/store/plan.json",
        local=[],
        workflows={},
        triggers=None,
    )
    assert json.loads(text)["schema"] == 4


# ---------------------------------------------------------------------------
# a source the plane cannot read


def test_a_source_that_is_not_loadable_is_refused(tmp_path):
    with pytest.raises(ProjectionError) as exc:
        render(tmp_path / "check.yaml", tmp_path, text="steps: [\n")
    assert "not loadable as YAML" in str(exc.value)


def test_a_source_that_is_not_a_mapping_is_refused(tmp_path):
    with pytest.raises(ProjectionError) as exc:
        render(tmp_path / "check.yaml", tmp_path, text="- a\n- b\n")
    assert "not a mapping" in str(exc.value)


# ---------------------------------------------------------------------------
# §7.3's last layer, for triggers (009 P3-3)


def write_local_triggers(root, text: str):
    (root / ".devman").mkdir(parents=True, exist_ok=True)
    (root / ".devman" / "triggers.toml").write_text(text)


def test_no_local_file_leaves_the_group_layer_alone(tmp_path):
    group = {"group": "format", "map": {"**/*.py": "format"}}
    assert project.resolve_triggers(group, tmp_path) == group


def test_an_ignore_list_narrows_the_group_map(tmp_path):
    """The case that forced the layer. A whole-file override cannot express
    'everything the group says, except this directory' — the repository would
    have to restate a map it does not own and keep it in step."""
    write_local_triggers(tmp_path, 'ignore = [".scratch/**"]\n')
    group = {"group": "format", "map": {"**/*.py": "format"}}

    out = project.resolve_triggers(group, tmp_path)

    assert out["map"] == {"**/*.py": "format"}
    assert out["ignore"] == [".scratch/**"]
    assert out["group"] == "format"
    assert out["source"] == "group+local"


def test_a_local_map_replaces_the_group_map_whole(tmp_path):
    """§7.3 shadows whole files, and this map does too."""
    write_local_triggers(tmp_path, '[map]\n"src/**/*.py" = "format"\n')
    group = {"group": "format", "map": {"**/*.py": "format"}}

    out = project.resolve_triggers(group, tmp_path)

    assert out["map"] == {"src/**/*.py": "format"}
    assert out["source"] == "local"


def test_an_ignore_with_no_group_map_declares_nothing(tmp_path):
    """A repository preparing for a group it has not taken. It fires nothing
    and hides nothing, so the entry records no trigger map at all."""
    write_local_triggers(tmp_path, 'ignore = [".scratch/**"]\n')
    assert project.resolve_triggers(None, tmp_path) is None


@pytest.mark.parametrize(
    ("text", "expect"),
    [
        pytest.param("ignore = [", "refusing to project", id="not-toml"),
        pytest.param('watch = ["x"]\n', "this file holds two keys", id="unknown-key"),
        pytest.param('ignore = "x"\n', "list of glob strings", id="ignore-not-a-list"),
        pytest.param("ignore = [1]\n", "list of glob strings", id="ignore-not-strings"),
        pytest.param('[map]\n"a" = 1\n', "<glob> = <workflow>", id="map-not-strings"),
    ],
)
def test_a_malformed_local_layer_is_refused(tmp_path, text, expect):
    """It decides what happens when a developer saves, so it is refused loudly
    rather than half-read."""
    write_local_triggers(tmp_path, text)

    with pytest.raises(ProjectionError) as exc:
        project.resolve_triggers({"group": "g", "map": {"**/*.py": "format"}}, tmp_path)
    assert expect in str(exc.value)


# ---------------------------------------------------------------------------
# Output ownership — writes.toml (015, §12 rule 3 as amended)


def write_local_writes(root, text: str) -> None:
    d = root / ".devman"
    d.mkdir(parents=True, exist_ok=True)
    (d / "writes.toml").write_text(text)


def test_a_project_with_no_layer_keeps_the_group_declaration(tmp_path):
    group = {"format": {"tier": "insitu", "paths": ["**/*.py"]}}
    assert project.resolve_writes(group, tmp_path) == group


def test_no_group_and_no_local_declares_nothing(tmp_path):
    """A declaration nobody made is absent, not an empty table — `doctor`
    reports "unaudited", and an empty table would read as "audited, nothing"."""
    assert project.resolve_writes(None, tmp_path) is None


def test_the_local_layer_merges_per_workflow_not_whole_file(tmp_path):
    """The one place this differs from §7.3 and from the trigger map: the unit
    is already a workflow, so overriding one must not drop the others."""
    write_local_writes(tmp_path, '[regen]\ntier = "lane"\npaths = ["src/**"]\n')
    group = {
        "format": {"tier": "insitu", "paths": ["**/*.py"]},
        "regen": {"tier": "lane", "paths": ["gen/**"]},
    }

    out = project.resolve_writes(group, tmp_path)

    assert out["format"] == {"tier": "insitu", "paths": ["**/*.py"]}
    assert out["regen"] == {"tier": "lane", "paths": ["src/**"]}


def test_free_path_is_agent_surface_only():
    assert project.free_path(".agents/skills/x.md")
    assert project.free_path("docs/index.md")
    assert project.free_path(".devman/notes.md")
    assert not project.free_path("src/devman/run.py")
    assert not project.free_path("**/*.py")


@pytest.mark.parametrize(
    ("text", "expect"),
    [
        pytest.param("[a]\ntier =", "refusing to project", id="not-toml"),
        pytest.param(
            '[a]\ntier = "trunk"\npaths = ["x"]\n',
            "there is no `trunk` tier",
            id="trunk-is-not-a-tier",
        ),
        pytest.param(
            '[a]\ntier = "trunk"\npaths = ["x"]\n', "a tier is one of", id="bad-tier"
        ),
        pytest.param('[a]\ntier = "lane"\n', "states no `paths`", id="no-paths"),
        pytest.param(
            '[a]\ntier = "lane"\npaths = []\n', "states no `paths`", id="empty-paths"
        ),
        pytest.param(
            '[a]\ntier = "lane"\npaths = ["x"]\nqueue = "light"\n',
            "this table holds",
            id="unknown-key",
        ),
    ],
)
def test_a_malformed_declaration_is_refused(tmp_path, text, expect):
    """A claim nobody can parse is worse than no claim: `doctor` would report it
    absent and the workflow would look compliant."""
    write_local_writes(tmp_path, text)

    with pytest.raises(ProjectionError) as exc:
        project.resolve_writes(None, tmp_path)
    assert expect in str(exc.value)
