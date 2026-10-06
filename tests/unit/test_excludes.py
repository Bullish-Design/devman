"""Tests for `devman.excludes` (Lane 4 of the Linkman cutover, project 044).

`devman.excludes` reimplements Linkman's `links.yaml` declaration contract —
layer reading, interpolation, the external/internal scope rule — without
importing `linkman`. These tests build every repository and overlay under
`tmp_path`. No test reads or writes `~/.config/devman`, and no test names a
real checkout.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

from devman.excludes import (
    RUN_DIRECTORY,
    ExcludeError,
    ensure_git_exclude,
    exclude_entries,
)
from devman_link.errors import LinkError
from devman_link.paths import local_gitignore_key, local_gitignore_path
from devman_link.state import State, content_hash

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper.


def write_layer(
    path: Path,
    links: Mapping[str, str],
    *,
    variables: Mapping[str, str] | None = None,
) -> None:
    """Write one `links.yaml` declaration layer. Keep the given link order."""
    document: dict[str, object] = {}
    if variables is not None:
        document["vars"] = dict(variables)
    document["links"] = {name: {"target": target} for name, target in links.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False))


def make_project(
    tmp_path: Path,
    overlay_links: Mapping[str, str] | None = None,
    *,
    project: str = "demo",
    repo_links: Mapping[str, str] | None = None,
    variables: Mapping[str, str] | None = None,
) -> tuple[Path, Path]:
    """Build a temporary repository and overlay for one project.

    Creates `<root>/.git/` as a directory. Writes the overlay layer when
    `overlay_links` is given, and the repo layer when `repo_links` is given.
    Returns the repository root and the overlay root.
    """
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    (root / ".git").mkdir(parents=True)
    if overlay_links is not None:
        write_layer(
            overlay / "projects" / project / "links.yaml",
            overlay_links,
            variables=variables,
        )
    if repo_links is not None:
        write_layer(root / "links.yaml", repo_links)
    return root, overlay


# ---------------------------------------------------------------------------
# Scope and order.


def test_external_target_adds_its_name_internal_target_adds_nothing(tmp_path: Path):
    """An internal target must not leak into Git's exclude file."""
    root, overlay = make_project(
        tmp_path,
        {"external": str(tmp_path / "elsewhere"), "internal": "${repo.root}/vendor"},
    )

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY, "external"]


def test_run_directory_is_first_when_no_link_is_declared(tmp_path: Path):
    """`RUN_DIRECTORY` must appear even for a project with an empty layer."""
    root, overlay = make_project(tmp_path, {})

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY]


def test_run_directory_is_first_when_both_layers_are_absent(tmp_path: Path):
    """A project with no `links.yaml` at all still owns its run directory."""
    root, overlay = make_project(tmp_path)

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY]


def test_entry_order_is_declaration_order_repo_before_overlay_not_sorted(
    tmp_path: Path,
):
    """A stray `sorted()` would put 'alpha' before 'zee'. It must not."""
    root, overlay = make_project(
        tmp_path,
        {"alpha": str(tmp_path / "ext-alpha")},
        repo_links={"zee": str(tmp_path / "ext-zee")},
    )

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY, "zee", "alpha"]


def test_duplicate_entry_is_removed_without_reordering(tmp_path: Path):
    """A link literally named `RUN_DIRECTORY` must not duplicate the entry."""
    root, overlay = make_project(
        tmp_path,
        {
            "zzz": str(tmp_path / "ext-zzz"),
            RUN_DIRECTORY: str(tmp_path / "ext-run"),
        },
    )

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY, "zzz"]


def test_target_equal_to_repo_root_counts_as_external(tmp_path: Path):
    """A link pointed straight at the repository root is still external."""
    root, overlay = make_project(tmp_path, {"selflink": "${repo.root}"})

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY, "selflink"]


def test_symlinked_parent_inside_the_repo_makes_a_target_external(tmp_path: Path):
    """A symlinked directory under the repo can carry a target back out."""
    root, overlay = make_project(tmp_path, {"escapee": "${repo.root}/jump/file.txt"})
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "jump").symlink_to(outside, target_is_directory=True)

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY, "escapee"]


def test_target_outside_the_repo_that_symlinks_back_inside_is_internal(
    tmp_path: Path,
):
    """The mirror case: an outside path that loops back in through a link."""
    outside = tmp_path / "outside"
    outside.mkdir()
    root, overlay = make_project(
        tmp_path, {"loopback": str(outside / "back" / "vendor")}
    )
    (outside / "back").symlink_to(root, target_is_directory=True)

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY]


# ---------------------------------------------------------------------------
# Interpolation.


def test_env_token_resolves_from_the_injected_environ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The real process environment must never supply this value."""
    monkeypatch.delenv("DEVMAN_TEST_TOKEN", raising=False)
    root, overlay = make_project(tmp_path, {"fromenv": "${env.DEVMAN_TEST_TOKEN}"})

    entries = exclude_entries(
        root,
        overlay,
        "demo",
        environ={"DEVMAN_TEST_TOKEN": str(tmp_path / "elsewhere")},
    )

    assert entries == [RUN_DIRECTORY, "fromenv"]


def test_repo_root_token_resolves_to_the_repository_root(tmp_path: Path):
    """A path built from `${repo.root}` must land under the repository."""
    root, overlay = make_project(tmp_path, {"inside": "${repo.root}/vendor/data"})

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY]


def test_repo_name_token_resolves_to_the_given_project_name(tmp_path: Path):
    """A symlink named after the project proves the exact value used."""
    root, overlay = make_project(
        tmp_path,
        {"escapee": "${repo.root}/${repo.name}/vendor"},
        project="escape-marker",
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape-marker").symlink_to(outside, target_is_directory=True)

    entries = exclude_entries(root, overlay, "escape-marker")

    assert entries == [RUN_DIRECTORY, "escapee"]


def test_repo_parent_token_resolves_to_the_repository_roots_parent(tmp_path: Path):
    """A symlink placed at the parent proves the exact value used."""
    root, overlay = make_project(
        tmp_path, {"loopback": "${repo.parent}/parent-marker/vendor"}
    )
    (tmp_path / "parent-marker").symlink_to(root, target_is_directory=True)

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY]


def test_nested_variable_chain_resolves_through_repo_name(tmp_path: Path):
    """A variable may reference another variable, which references `repo.name`."""
    root, overlay = make_project(
        tmp_path,
        {"escapee": "${repo.root}/${vars.outer}/vendor"},
        variables={"inner": "${repo.name}", "outer": "${vars.inner}-escape"},
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "demo-escape").symlink_to(outside, target_is_directory=True)

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY, "escapee"]


def test_unset_environment_variable_refuses_naming_the_variable(tmp_path: Path):
    """The refusal must name the environment variable it could not find."""
    root, overlay = make_project(tmp_path, {"fromenv": "${env.DEVMAN_TEST_MISSING}"})

    with pytest.raises(ExcludeError, match="DEVMAN_TEST_MISSING"):
        exclude_entries(root, overlay, "demo", environ={})


def test_unknown_repo_name_refuses(tmp_path: Path):
    """`${repo.*}` has exactly three names. A fourth one must refuse."""
    root, overlay = make_project(tmp_path, {"outside": "${repo.nickname}"})

    with pytest.raises(ExcludeError, match="nickname"):
        exclude_entries(root, overlay, "demo")


def test_unknown_vars_name_refuses(tmp_path: Path):
    """A link may not reference a variable nobody declared."""
    root, overlay = make_project(tmp_path, {"outside": "${vars.missing}"})

    with pytest.raises(ExcludeError, match="missing"):
        exclude_entries(root, overlay, "demo")


def test_variable_cycle_refuses_showing_the_cycle(tmp_path: Path):
    """The message must show the exact cycle, joined with `->`."""
    root, overlay = make_project(
        tmp_path, {}, variables={"a": "${vars.b}", "b": "${vars.a}"}
    )

    with pytest.raises(ExcludeError, match=r"a -> b -> a"):
        exclude_entries(root, overlay, "demo")


def test_variable_depth_limit_refuses(tmp_path: Path):
    """A chain longer than the depth limit must refuse, not recurse forever."""
    variables = {f"v{i}": f"${{vars.v{i + 1}}}" for i in range(59)}
    variables["v59"] = "end"
    root, overlay = make_project(tmp_path, {}, variables=variables)

    with pytest.raises(ExcludeError, match="depth"):
        exclude_entries(root, overlay, "demo")


def test_token_without_a_namespace_separator_refuses(tmp_path: Path):
    """`${bad}` names no namespace at all."""
    root, overlay = make_project(tmp_path, {"outside": "${bad}"})

    with pytest.raises(ExcludeError, match=re.escape("${bad}")):
        exclude_entries(root, overlay, "demo")


def test_token_with_an_unknown_namespace_refuses_naming_the_namespace(tmp_path: Path):
    """`${nope.x}` names a namespace that does not exist."""
    root, overlay = make_project(tmp_path, {"outside": "${nope.x}"})

    with pytest.raises(ExcludeError, match="nope"):
        exclude_entries(root, overlay, "demo")


def test_unclosed_token_refuses(tmp_path: Path):
    """A token with no closing brace must refuse, not scan past the string."""
    root, overlay = make_project(tmp_path, {"outside": "${env.HOME"})

    with pytest.raises(ExcludeError, match="unclosed"):
        exclude_entries(root, overlay, "demo")


def test_nul_byte_in_a_target_refuses(tmp_path: Path):
    """A NUL byte in a target must refuse at the layer-reading step."""
    root, overlay = make_project(tmp_path, {})
    layer = overlay / "projects" / "demo" / "links.yaml"
    layer.write_text('links:\n  outside:\n    target: "value\\0suffix"\n')

    with pytest.raises(ExcludeError, match="NUL"):
        exclude_entries(root, overlay, "demo")


# ---------------------------------------------------------------------------
# Declaration layers and refusals.


def test_link_name_declared_in_both_layers_refuses_naming_both_files(tmp_path: Path):
    """A name claimed by both layers is ambiguous. The message must say which."""
    root, overlay = make_project(
        tmp_path,
        {"shared": str(tmp_path / "overlay-target")},
        repo_links={"shared": str(tmp_path / "repo-target")},
    )
    repo_layer = (root / "links.yaml").resolve()
    overlay_layer = (overlay / "projects" / "demo" / "links.yaml").resolve()

    with pytest.raises(ExcludeError) as caught:
        exclude_entries(root, overlay, "demo")

    message = str(caught.value)
    assert str(repo_layer) in message
    assert str(overlay_layer) in message


def test_variable_name_declared_in_both_layers_refuses_naming_both_files(
    tmp_path: Path,
):
    """The same rule applies to a variable name, in its own namespace."""
    root, overlay = make_project(tmp_path)
    repo_layer = (root / "links.yaml").resolve()
    overlay_layer = (overlay / "projects" / "demo" / "links.yaml").resolve()
    write_layer(repo_layer, {}, variables={"shared": "one"})
    write_layer(overlay_layer, {}, variables={"shared": "two"})

    with pytest.raises(ExcludeError) as caught:
        exclude_entries(root, overlay, "demo")

    message = str(caught.value)
    assert str(repo_layer) in message
    assert str(overlay_layer) in message


def test_a_link_name_and_a_variable_name_may_be_the_same_string(tmp_path: Path):
    """Linkman has no cross-namespace rule. Nobody should re-add one here."""
    root, overlay = make_project(
        tmp_path,
        {"shared": str(tmp_path / "outside")},
        variables={"shared": "unused"},
    )

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY, "shared"]


def test_version_2_refuses(tmp_path: Path):
    """Only version 1 of the declaration grammar exists today."""
    root, overlay = make_project(tmp_path)
    layer = overlay / "projects" / "demo" / "links.yaml"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text("version: 2\nlinks: {}\n")

    with pytest.raises(ExcludeError, match="version"):
        exclude_entries(root, overlay, "demo")


def test_version_true_refuses_naming_a_boolean(tmp_path: Path):
    """YAML's `true` is a boolean, not the integer 1. The message must say so."""
    root, overlay = make_project(tmp_path)
    layer = overlay / "projects" / "demo" / "links.yaml"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text("version: true\nlinks: {}\n")

    with pytest.raises(ExcludeError, match="boolean"):
        exclude_entries(root, overlay, "demo")


def test_unknown_top_level_key_refuses(tmp_path: Path):
    """Only `version`, `vars` and `links` are declaration keys."""
    root, overlay = make_project(tmp_path)
    layer = overlay / "projects" / "demo" / "links.yaml"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text("links: {}\nextra: 1\n")

    with pytest.raises(ExcludeError, match="extra"):
        exclude_entries(root, overlay, "demo")


def test_unknown_key_inside_a_link_entry_refuses_naming_the_link(tmp_path: Path):
    """Only `target` is a key inside one link entry."""
    root, overlay = make_project(tmp_path)
    layer = overlay / "projects" / "demo" / "links.yaml"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text('links:\n  outside:\n    target: "x"\n    mode: "640"\n')

    with pytest.raises(ExcludeError, match="outside"):
        exclude_entries(root, overlay, "demo")


def test_bare_links_key_with_nothing_after_it_is_valid(tmp_path: Path):
    """A bare `links:` parses to `None`. Treat that as no links at all."""
    root, overlay = make_project(tmp_path)
    layer = overlay / "projects" / "demo" / "links.yaml"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text("links:\n")

    entries = exclude_entries(root, overlay, "demo")

    assert entries == [RUN_DIRECTORY]


@pytest.mark.parametrize("name", [".", "..", "a/../b", "/abs", "~/x", "links.yaml"])
def test_invalid_link_names_refuse(tmp_path: Path, name: str):
    """Every name Linkman could not use either must refuse here too."""
    root, overlay = make_project(tmp_path)
    layer = overlay / "projects" / "demo" / "links.yaml"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text(f'links:\n  "{name}":\n    target: "x"\n')

    with pytest.raises(ExcludeError):
        exclude_entries(root, overlay, "demo")


def test_invalid_yaml_refuses_naming_the_file(tmp_path: Path):
    """A YAML parse failure must name the file that failed to parse."""
    root, overlay = make_project(tmp_path)
    layer = overlay / "projects" / "demo" / "links.yaml"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text("links: [unterminated\n")

    with pytest.raises(ExcludeError) as caught:
        exclude_entries(root, overlay, "demo")

    assert str(layer.resolve()) in str(caught.value)


def test_empty_target_refuses_naming_the_link(tmp_path: Path):
    """An empty target string is not a usable path."""
    root, overlay = make_project(tmp_path)
    layer = overlay / "projects" / "demo" / "links.yaml"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text('links:\n  outside:\n    target: ""\n')

    with pytest.raises(ExcludeError, match="outside"):
        exclude_entries(root, overlay, "demo")


def test_whitespace_only_target_refuses_naming_the_link(tmp_path: Path):
    """A target made only of spaces is not a usable path either."""
    root, overlay = make_project(tmp_path)
    layer = overlay / "projects" / "demo" / "links.yaml"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text('links:\n  outside:\n    target: "   "\n')

    with pytest.raises(ExcludeError, match="outside"):
        exclude_entries(root, overlay, "demo")


# ---------------------------------------------------------------------------
# Byte preservation through `ensure_git_exclude`.


def test_ensure_git_exclude_leaves_bytes_untouched_when_nothing_is_missing(
    tmp_path: Path,
):
    """Every computed entry already present must mean zero bytes change."""
    root, overlay = make_project(
        tmp_path,
        {"b_link": str(tmp_path / "ext-b"), "a_link": str(tmp_path / "ext-a")},
    )
    canonical = local_gitignore_path(overlay.resolve(), "demo")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text(
        "# hand-authored header\n"
        "\n"
        "a_link\n"
        "# keep me\n"
        "custom-pattern\n"
        "b_link\n"
        f"{RUN_DIRECTORY}\n"
    )
    exclude = root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True)
    exclude.symlink_to(canonical)
    key = local_gitignore_key("demo")
    state: State = {key: {"canonical": str(canonical), "hash": content_hash(canonical)}}
    before_canonical = canonical.read_bytes()
    before_exclude = exclude.read_bytes()

    changed = ensure_git_exclude(root, overlay, "demo", state)

    assert canonical.read_bytes() == before_canonical
    assert exclude.read_bytes() == before_exclude
    assert changed is False
    lines = canonical.read_text().splitlines()
    assert lines[0] == "# hand-authored header"
    assert lines[1] == ""
    assert lines[3] == "# keep me"
    assert lines[4] == "custom-pattern"


def test_no_trailing_newline_keeps_exact_bytes_when_nothing_is_missing(
    tmp_path: Path,
):
    """A central file with no trailing newline must not gain one for no reason."""
    root, overlay = make_project(tmp_path, {"only": str(tmp_path / "outside")})
    canonical = local_gitignore_path(overlay.resolve(), "demo")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_bytes(f"{RUN_DIRECTORY}\nonly".encode())
    exclude = root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True)
    exclude.symlink_to(canonical)
    key = local_gitignore_key("demo")
    state: State = {key: {"canonical": str(canonical), "hash": content_hash(canonical)}}
    before = canonical.read_bytes()

    changed = ensure_git_exclude(root, overlay, "demo", state)

    assert canonical.read_bytes() == before
    assert changed is False


def test_no_trailing_newline_gets_one_inserted_before_an_appended_entry(
    tmp_path: Path,
):
    """A missing entry must not land glued onto the previous line's text."""
    root, overlay = make_project(tmp_path, {"only": str(tmp_path / "outside")})
    canonical = local_gitignore_path(overlay.resolve(), "demo")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_bytes(b"# header")
    exclude = root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True)
    exclude.symlink_to(canonical)
    key = local_gitignore_key("demo")
    state: State = {key: {"canonical": str(canonical), "hash": content_hash(canonical)}}

    ensure_git_exclude(root, overlay, "demo", state)

    assert canonical.read_bytes() == f"# header\n{RUN_DIRECTORY}\nonly\n".encode()


def test_missing_entry_is_appended_at_the_end_without_moving_existing_lines(
    tmp_path: Path,
):
    """An append must never rewrite or reorder a line that was already there."""
    root, overlay = make_project(
        tmp_path,
        {"first": str(tmp_path / "ext-first"), "second": str(tmp_path / "ext-second")},
    )
    canonical = local_gitignore_path(overlay.resolve(), "demo")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("# header\nfirst\n")
    exclude = root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True)
    exclude.symlink_to(canonical)
    key = local_gitignore_key("demo")
    state: State = {key: {"canonical": str(canonical), "hash": content_hash(canonical)}}

    ensure_git_exclude(root, overlay, "demo", state)

    assert canonical.read_text().splitlines() == [
        "# header",
        "first",
        RUN_DIRECTORY,
        "second",
    ]


def test_ensure_git_exclude_called_twice_is_idempotent(tmp_path: Path):
    """The second call on an unchanged tree must report and change nothing."""
    root, overlay = make_project(tmp_path, {"only": str(tmp_path / "outside")})
    state: State = {}

    first = ensure_git_exclude(root, overlay, "demo", state)
    canonical = local_gitignore_path(overlay.resolve(), "demo")
    before = canonical.read_bytes()
    second = ensure_git_exclude(root, overlay, "demo", state)

    assert first is True
    assert second is False
    assert canonical.read_bytes() == before


# ---------------------------------------------------------------------------
# Preserved behaviour from the old projection.


def test_promotion_refuses_without_a_recorded_baseline(tmp_path: Path):
    """A real exclude file that differs from the central one, with no ledger
    entry, must refuse rather than guess which side is right."""
    root, overlay = make_project(tmp_path, {"only": str(tmp_path / "outside")})
    canonical = local_gitignore_path(overlay.resolve(), "demo")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("# central\n")
    exclude = root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True)
    exclude.write_text("# local, different\n")
    state: State = {}
    before_canonical = canonical.read_bytes()
    before_exclude = exclude.read_bytes()

    with pytest.raises(LinkError, match="differ without a recorded baseline"):
        ensure_git_exclude(root, overlay, "demo", state)

    assert canonical.read_bytes() == before_canonical
    assert exclude.read_bytes() == before_exclude


def test_promotion_refuses_when_both_sides_changed(tmp_path: Path):
    """A recorded baseline that matches neither side means both sides moved."""
    root, overlay = make_project(tmp_path, {"only": str(tmp_path / "outside")})
    canonical = local_gitignore_path(overlay.resolve(), "demo")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("# central, edited\n")
    exclude = root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True)
    exclude.write_text("# local, edited\n")
    key = local_gitignore_key("demo")
    state: State = {key: {"canonical": str(canonical), "hash": "0" * 64}}

    with pytest.raises(LinkError, match="both changed"):
        ensure_git_exclude(root, overlay, "demo", state)


def test_repository_without_a_git_marker_gets_no_exclude_link(tmp_path: Path):
    """A gitman or jj workspace must not get a second exclude file."""
    root = tmp_path / "repo"
    root.mkdir()
    overlay = tmp_path / "overlay"
    state: State = {}

    changed = ensure_git_exclude(root, overlay, "demo", state)

    assert changed is False
    assert not (overlay / "projects" / "demo" / ".local.gitignore").exists()


def test_linked_worktree_uses_its_common_git_directory(tmp_path: Path):
    """A linked worktree's exclude file must project onto the common one."""
    overlay = tmp_path / "overlay"
    root = tmp_path / "worktree"
    common = tmp_path / "main" / ".git"
    worktree_git = common / "worktrees" / "feature"
    (common / "info").mkdir(parents=True)
    worktree_git.mkdir(parents=True)
    (worktree_git / "commondir").write_text("../..\n")
    root.mkdir()
    (root / ".git").write_text(f"gitdir: {worktree_git}\n")
    write_layer(
        overlay / "projects" / "demo" / "links.yaml",
        {"only": str(tmp_path / "outside")},
    )
    state: State = {}

    ensure_git_exclude(root, overlay, "demo", state)

    exclude = common / "info" / "exclude"
    assert exclude.is_symlink()
    assert (
        exclude.resolve() == local_gitignore_path(overlay.resolve(), "demo").resolve()
    )
