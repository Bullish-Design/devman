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
# publication — identity first, then validate, then publish (P1-5, P2-2)


def plan_for(tmp_path, workflows=None):
    return project.Plan(
        path="/nix/store/plan.json",
        project="p",
        groups=["base"],
        workflows=workflows or {},
        triggers=None,
        renderer="/nix/store/renderer",
    )


def test_apply_publishes_a_file_a_link_and_an_entry(tmp_path):
    root = tmp_path / "repo"
    (root / ".devman" / "workflows").mkdir(parents=True)
    (root / ".devman" / "workflows" / "check.yaml").write_text(ORDINARY)
    registry = tmp_path / "registry"

    project.apply(plan_for(tmp_path), root, registry, ["check"], dagu="true")

    projected = registry / "projects" / "p" / "workflows" / "check.yaml"
    assert projected.read_text().endswith(ORDINARY)
    link = registry / "dags" / "p.check.yaml"
    assert link.is_symlink()
    entry = json.loads((registry / "projects" / "p" / "metadata.json").read_text())
    assert entry["path"] == str(root)
    assert entry["local"] == ["check"]
    assert entry["plan"] == "/nix/store/plan.json"


def test_an_invalid_project_identity_is_refused_before_any_path_is_built(tmp_path):
    """Stage 5's grammar, before path construction. `bad@project` used to
    register, and `projects/$proj` used to be built from whatever it said."""
    plan = plan_for(tmp_path)
    plan.project = "bad@project"
    registry = tmp_path / "registry"

    with pytest.raises(ProjectionError):
        project.apply(plan, tmp_path / "repo", registry, [], dagu="true")
    assert not (registry / "projects" / "bad@project").exists()


def test_a_workflow_name_holding_a_dot_is_refused(tmp_path):
    root = tmp_path / "repo"
    (root / ".devman" / "workflows").mkdir(parents=True)
    (root / ".devman" / "workflows" / "release.tagged.yaml").write_text(ORDINARY)
    registry = tmp_path / "registry"

    with pytest.raises(ProjectionError) as exc:
        project.apply(
            plan_for(tmp_path), root, registry, ["release.tagged"], dagu="true"
        )
    assert "injective" in str(exc.value)


def test_a_file_dagu_refuses_is_not_published(tmp_path):
    """**P2-2, closed at publication rather than at enqueue.** Validating at
    enqueue moves the refusal to whoever triggers the workflow next; validating
    here moves it to the author, at shell entry, and makes every published link
    known valid."""
    root = tmp_path / "repo"
    (root / ".devman" / "workflows").mkdir(parents=True)
    (root / ".devman" / "workflows" / "check.yaml").write_text(ORDINARY)
    registry = tmp_path / "registry"

    with pytest.raises(ProjectionError) as exc:
        project.apply(plan_for(tmp_path), root, registry, ["check"], dagu="false")

    message = str(exc.value)
    assert "check.yaml" in message
    assert not (registry / "projects" / "p" / "workflows" / "check.yaml").exists()
    assert not (registry / "dags" / "p.check.yaml").exists()


def test_a_local_override_shadows_the_group_file(tmp_path):
    """§7.3's last layer, whole-file. The repository's own copy wins."""
    root = tmp_path / "repo"
    (root / ".devman" / "workflows").mkdir(parents=True)
    (root / ".devman" / "workflows" / "check.yaml").write_text("# mine\n" + ORDINARY)
    group = tmp_path / "group-check.yaml"
    group.write_text("# the group's\n" + ORDINARY)
    registry = tmp_path / "registry"
    plan = plan_for(
        tmp_path,
        {"check": {"group": "base", "shadows": [], "source": str(group)}},
    )

    project.apply(plan, root, registry, ["check"], dagu="true")

    projected = registry / "projects" / "p" / "workflows" / "check.yaml"
    assert "# mine" in projected.read_text()
    assert "# the group's" not in projected.read_text()


def test_the_entry_is_written_last(tmp_path):
    """An interrupted projection must leave an entry that does not match, so the
    next shell entry retries it (§9.3). The refusal above is that state: files
    published, no entry."""
    root = tmp_path / "repo"
    (root / ".devman" / "workflows").mkdir(parents=True)
    (root / ".devman" / "workflows" / "check.yaml").write_text(ORDINARY)
    registry = tmp_path / "registry"

    with pytest.raises(ProjectionError):
        project.apply(plan_for(tmp_path), root, registry, ["check"], dagu="false")

    assert not (registry / "projects" / "p" / "metadata.json").exists()


def test_a_stale_link_and_file_are_swept(tmp_path):
    """The registry is derived, so the projection is rebuilt rather than
    patched — including the pre-codec `<project>-<workflow>` shape, which is
    what makes the codec migrate itself (S-12)."""
    root = tmp_path / "repo"
    (root / ".devman" / "workflows").mkdir(parents=True)
    (root / ".devman" / "workflows" / "check.yaml").write_text(ORDINARY)
    registry = tmp_path / "registry"
    workflows = registry / "projects" / "p" / "workflows"
    dags = registry / "dags"
    workflows.mkdir(parents=True)
    dags.mkdir(parents=True)
    (workflows / "gone.yaml").write_text("stale\n")
    (dags / "p-gone.yaml").symlink_to("../projects/p/workflows/gone.yaml")
    (dags / "p.gone.yaml").symlink_to("../projects/p/workflows/gone.yaml")

    project.apply(plan_for(tmp_path), root, registry, ["check"], dagu="true")

    assert not (workflows / "gone.yaml").exists()
    assert not (dags / "p-gone.yaml").is_symlink()
    assert not (dags / "p.gone.yaml").is_symlink()
    assert (dags / "p.check.yaml").is_symlink()


# ---------------------------------------------------------------------------
# validating only what changed — the cost control, and its limit
#
# `dagu validate` costs 71 ms per workflow (STAGE_9_LOG.md S-3). It is paid when
# bytes change and skipped when they do not. **Rule 5 applies to the skip
# itself**: these cases are what stop it becoming "never validate".


def test_an_unchanged_file_is_not_revalidated(tmp_path):
    """Second projection, same bytes, same plan: no fork. `false` as the
    validator makes any validation a failure, so passing proves the skip."""
    root = tmp_path / "repo"
    (root / ".devman" / "workflows").mkdir(parents=True)
    (root / ".devman" / "workflows" / "check.yaml").write_text(ORDINARY)
    registry = tmp_path / "registry"

    project.apply(plan_for(tmp_path), root, registry, ["check"], dagu="true")
    project.apply(plan_for(tmp_path), root, registry, ["check"], dagu="false")

    assert (registry / "projects" / "p" / "workflows" / "check.yaml").exists()


def test_a_changed_file_is_revalidated(tmp_path):
    """The whole point of the skip is that it does not cover an edit."""
    root = tmp_path / "repo"
    (root / ".devman" / "workflows").mkdir(parents=True)
    source = root / ".devman" / "workflows" / "check.yaml"
    source.write_text(ORDINARY)
    registry = tmp_path / "registry"

    project.apply(plan_for(tmp_path), root, registry, ["check"], dagu="true")
    source.write_text("# edited\n" + ORDINARY)

    with pytest.raises(ProjectionError):
        project.apply(plan_for(tmp_path), root, registry, ["check"], dagu="false")


def test_a_new_plan_revalidates_everything(tmp_path):
    """A new plan path means a new renderer, and the renderer wraps the Dagu
    that validates. Unchanged bytes prove nothing against a new validator."""
    root = tmp_path / "repo"
    (root / ".devman" / "workflows").mkdir(parents=True)
    (root / ".devman" / "workflows" / "check.yaml").write_text(ORDINARY)
    registry = tmp_path / "registry"

    project.apply(plan_for(tmp_path), root, registry, ["check"], dagu="true")
    newer = plan_for(tmp_path)
    newer.path = "/nix/store/a-newer-plan.json"

    with pytest.raises(ProjectionError):
        project.apply(newer, root, registry, ["check"], dagu="false")


def test_a_refusal_leaves_the_previous_projection_intact(tmp_path):
    """**"Publish nothing" means the whole projection, not the failed file.**

    Measured while writing stage 3: with the sweep first, adding an `env:` block
    to one override refused correctly and left the repository with NONE of its
    ten workflows published — so a typo would have stopped that repository's
    nightly `maintain` until somebody noticed. The registry is now untouched
    until every file has rendered and every changed file has validated.
    """
    root = tmp_path / "repo"
    (root / ".devman" / "workflows").mkdir(parents=True)
    good = root / ".devman" / "workflows" / "good.yaml"
    bad = root / ".devman" / "workflows" / "bad.yaml"
    good.write_text(ORDINARY)
    bad.write_text(ORDINARY)
    registry = tmp_path / "registry"
    project.apply(plan_for(tmp_path), root, registry, ["good", "bad"], dagu="true")
    before = (registry / "projects" / "p" / "workflows" / "good.yaml").read_text()

    bad.write_text(f"env:\n  - LEVEL: debug\n{ORDINARY}")
    with pytest.raises(ProjectionError):
        project.apply(plan_for(tmp_path), root, registry, ["good", "bad"], dagu="true")

    projected = registry / "projects" / "p" / "workflows"
    assert projected.joinpath("good.yaml").read_text() == before
    assert projected.joinpath("bad.yaml").exists()
    assert (registry / "dags" / "p.good.yaml").is_symlink()
