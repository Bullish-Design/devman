"""The independent link adapter (038 Stage 16).

Two claims this file exists to keep true. First, the component is independent:
it imports no Devman plane module, and a normal operation reads no compatibility
registry entry, no `metadata.json`, and no `generation.json`. Second, the safety
behaviour did not weaken when the adapter moved: every root check, promotion
rule, conflict refusal and exclude-file rule still refuses what it refused.

`tests/unit/test_link.py` covers the older `devman.link` implementation and is
not changed by this file.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import devman_link
from devman_link import (
    Declaration,
    IdentityError,
    LinkConfigurationError,
    LinkError,
    reconcile,
    resolve,
    status,
)
from devman_link.cli import main as link_cli
from devman_link.excludes import git_exclude_path
from devman_link.state import STATE_FILE

pytestmark = pytest.mark.unit

PACKAGE_ROOT = Path(devman_link.__file__).resolve().parent
SOURCE_ROOT = PACKAGE_ROOT.parent


def central(path: str = "common/envrc") -> dict[str, str]:
    return {"canonical": "central", "path": path}


def bootstrap(project: str = "demo") -> dict[str, str]:
    return {"canonical": "central", "path": f"projects/{project}/devenv.local.nix"}


def write_manifest(root: Path, project: str = "demo") -> None:
    manifest = root / ".devman/project.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        f'schema = 1\nproject = "{project}"\ngroups = ["base"]\npolicy = "stable"\n'
    )


def write_central_file(overlay: Path, project: str, body: str) -> Path:
    path = overlay / "projects" / project / "devenv.local.nix"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


DEFAULT_CENTRAL = """{ config, ... }:

{
  devman.link = {
    ".envrc" = { canonical = "central"; path = "common/envrc"; };
    ".agents" = {
      canonical = "central";
      path = "projects/${config.devman.project}/agents";
    };
  };
}
"""


# ---------------------------------------------------------------------------
# Independence. These are the claims the extraction was for.


def test_component_imports_no_devman_plane_module():
    """A stray `import devman` would couple the component back to the plane.

    `nix/link-adapter.nix` builds this package without `devman` on the path, so
    such an import fails that build. This says the same thing in the fast loop,
    where a developer sees it in a second rather than in a Nix build.
    """
    offenders = []
    for source in sorted(PACKAGE_ROOT.rglob("*.py")):
        text = source.read_text()
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("import devman.", "from devman.")) or stripped in {
                "import devman"
            }:
                offenders.append(f"{source.name}:{number}: {stripped}")
    assert offenders == []


def test_component_names_no_registry_or_generation_file():
    """Normal operation must not depend on a machine-plane file.

    Docstrings are excluded, because this file and `api.py` both have to name
    the files the component does not read in order to say that it does not.
    """
    forbidden = ("metadata.json", "generation.json", "/dags/")
    offenders = []
    for source in sorted(PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(source.read_text())
        documentation = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(
                node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
            )
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        offenders.extend(
            f"{source.name}:{node.lineno}: {name}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in documentation
            for name in forbidden
            if name in node.value
        )
    assert offenders == []


def test_status_needs_no_compatibility_registry_entry(tmp_path: Path):
    """The failure Stage 15 recorded: a real repository the registry never saw."""
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    write_manifest(root, "unregistered")
    write_central_file(overlay, "unregistered", DEFAULT_CENTRAL)

    outcome = devman_link.run(
        "status", root=root, overlay=overlay, evaluator=lambda _path, _project: {}
    )

    assert outcome.project == "unregistered"
    assert outcome.identity.source == "manifest"
    assert outcome.central_file == overlay / "projects/unregistered/devenv.local.nix"


def test_status_writes_nothing(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    write_manifest(root)
    write_central_file(overlay, "demo", DEFAULT_CENTRAL)
    before = {
        path.relative_to(tmp_path): path.lstat().st_mtime_ns
        for path in sorted(tmp_path.rglob("*"))
    }

    outcome = devman_link.run(
        "status",
        root=root,
        overlay=overlay,
        evaluator=lambda _path, _project: {".envrc": central()},
    )

    after = {
        path.relative_to(tmp_path): path.lstat().st_mtime_ns
        for path in sorted(tmp_path.rglob("*"))
    }
    assert outcome.exit_code == 1
    assert before == after
    assert not (overlay / STATE_FILE).exists()


def test_reconcile_touches_no_dag_or_generation_file(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    plane = tmp_path / "plane"
    (plane / "dags").mkdir(parents=True)
    (plane / "dags/demo.check.yaml").write_text("steps: []\n")
    (plane / "generation.json").write_text('{"generation": 2}\n')
    root.mkdir()
    before = {
        path: path.read_bytes() for path in sorted(plane.rglob("*")) if path.is_file()
    }

    reconcile({".envrc": central()}, overlay=overlay, root=root, project="demo")

    after = {
        path: path.read_bytes() for path in sorted(plane.rglob("*")) if path.is_file()
    }
    assert before == after


# ---------------------------------------------------------------------------
# Identity. One resolver, manifest first, never the directory name.


def test_manifest_identity_without_project_argument(tmp_path: Path):
    write_manifest(tmp_path, "manifest-name")

    result = devman_link.resolve_project_identity(tmp_path)

    assert (result.project, result.source) == ("manifest-name", "manifest")


def test_matching_explicit_identity_is_accepted(tmp_path: Path):
    write_manifest(tmp_path, "demo")

    assert devman_link.resolve_project_identity(tmp_path, "demo").source == "explicit"


def test_mismatching_explicit_identity_names_both_and_a_repair(tmp_path: Path):
    write_manifest(tmp_path, "manifest-name")

    with pytest.raises(IdentityError) as caught:
        devman_link.resolve_project_identity(tmp_path, "other-name")

    message = str(caught.value)
    assert str(tmp_path.resolve()) in message
    assert "manifest-name" in message
    assert "other-name" in message
    assert "repair:" in message


def test_matching_manifest_and_nix_identities_agree(tmp_path: Path):
    write_manifest(tmp_path, "demo")
    (tmp_path / "devenv.nix").write_text('{ devman = { project = "demo"; }; }\n')

    result = devman_link.resolve_project_identity(tmp_path)

    assert result.compatibility == "demo"


def test_mismatching_manifest_and_nix_identities_refuse(tmp_path: Path):
    write_manifest(tmp_path, "manifest-name")
    (tmp_path / "devenv.nix").write_text('{ devman = { project = "old-name"; }; }\n')

    with pytest.raises(IdentityError) as caught:
        devman_link.resolve_project_identity(tmp_path)

    message = str(caught.value)
    assert "manifest identity" in message
    assert "compatibility identity" in message
    assert "repair:" in message


def test_manifest_free_compatibility_fallback(tmp_path: Path):
    (tmp_path / "devenv.nix").write_text('{ devman.project = "legacy"; }\n')

    result = devman_link.resolve_project_identity(tmp_path)

    assert (result.project, result.source) == ("legacy", "compatibility")


def test_directory_name_is_never_an_identity(tmp_path: Path):
    root = tmp_path / "looks-like-a-project"
    root.mkdir()

    with pytest.raises(IdentityError) as caught:
        devman_link.resolve_project_identity(root)

    message = str(caught.value)
    # The refusal names the root as the place that lacks an identity, and
    # proposes the manifest or --project. It never proposes the directory name.
    assert "is absent and no literal devman.project exists" in message
    assert "manifest-free compatibility repository" in message
    assert "repair:" in message


@pytest.mark.parametrize("project", ["", "..", "bad/name", "bad@name", "-flag"])
def test_invalid_identities_are_refused_with_the_field_named(
    tmp_path: Path, project: str
):
    write_manifest(tmp_path, project)

    with pytest.raises(IdentityError) as caught:
        devman_link.resolve_project_identity(tmp_path)

    assert "field 'project'" in str(caught.value)
    assert "repair:" in str(caught.value)


# ---------------------------------------------------------------------------
# The central configuration.


def test_central_declarations_are_evaluated_with_the_selected_identity(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    write_central_file(overlay, "demo", DEFAULT_CENTRAL)
    seen: list[tuple[Path, str]] = []

    def evaluate(path: Path, project: str) -> object:
        seen.append((path, project))
        return {".envrc": central()}

    configuration = devman_link.validate_link_configuration(
        root, overlay, "demo", evaluator=evaluate
    )

    assert seen == [(overlay / "projects/demo/devenv.local.nix", "demo")]
    assert set(configuration.declarations) == {".envrc", "devenv.local.nix"}


@pytest.mark.skipif(
    shutil.which("nix-instantiate") is None, reason="needs a Nix evaluator"
)
def test_the_real_central_nix_file_evaluates_to_its_link_block(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    write_central_file(overlay, "demo", DEFAULT_CENTRAL)

    configuration = devman_link.validate_link_configuration(root, overlay, "demo")

    assert configuration.declarations[".agents"]["path"] == "projects/demo/agents"


def test_missing_central_file_is_refused_with_a_repair(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()

    with pytest.raises(LinkConfigurationError) as caught:
        devman_link.validate_link_configuration(root, tmp_path / "overlay", "demo")

    assert "bootstrap central target does not exist" in str(caught.value)
    assert "repair:" in str(caught.value)


def test_missing_repository_root_is_refused(tmp_path: Path):
    with pytest.raises(LinkConfigurationError, match="repository root does not exist"):
        devman_link.validate_link_configuration(
            tmp_path / "absent", tmp_path / "overlay", "demo"
        )


def test_unknown_central_field_is_refused_with_a_repair(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    write_central_file(overlay, "demo", DEFAULT_CENTRAL)

    with pytest.raises(LinkConfigurationError) as caught:
        devman_link.validate_link_configuration(
            root,
            overlay,
            "demo",
            evaluator=lambda _path, _project: {".envrc": {"target": "elsewhere"}},
        )

    assert "unknown field" in str(caught.value)
    assert "repair:" in str(caught.value)


def test_bootstrap_link_must_point_at_the_central_project_file(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    write_central_file(overlay, "demo", DEFAULT_CENTRAL)

    with pytest.raises(LinkConfigurationError, match="bootstrap link points to"):
        devman_link.validate_link_configuration(
            root,
            overlay,
            "demo",
            evaluator=lambda _path, _project: {
                "devenv.local.nix": {"canonical": "central", "path": "common/other.nix"}
            },
        )


# ---------------------------------------------------------------------------
# Path safety. Every one of these must stay a refusal.


def test_central_path_cannot_be_absolute(tmp_path: Path):
    with pytest.raises(LinkError, match="relative"):
        resolve(
            Declaration.read(".envrc", {"path": "/tmp/envrc"}),
            overlay=tmp_path / "overlay",
            root=tmp_path / "repo",
            project="demo",
        )


def test_central_path_cannot_traverse_out_of_the_overlay(tmp_path: Path):
    with pytest.raises(LinkError, match="relative"):
        Declaration.read(".envrc", central("../outside/envrc"))


def test_central_path_cannot_escape_through_a_symlinked_parent(tmp_path: Path):
    overlay = tmp_path / "overlay"
    outside = tmp_path / "outside"
    overlay.mkdir()
    outside.mkdir()
    (overlay / "common").symlink_to(outside, target_is_directory=True)

    with pytest.raises(LinkError, match="escapes"):
        resolve(
            Declaration.read(".envrc", central()),
            overlay=overlay,
            root=tmp_path / "repo",
            project="demo",
        )


def test_view_cannot_escape_through_a_symlinked_parent(tmp_path: Path):
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "config").symlink_to(outside, target_is_directory=True)

    with pytest.raises(LinkError, match="view .* escapes"):
        resolve(
            Declaration.read("config/envrc", central()),
            overlay=tmp_path / "overlay",
            root=root,
            project="demo",
        )


def test_external_path_must_be_absolute_after_expansion(tmp_path: Path):
    with pytest.raises(LinkError, match="must be absolute"):
        reconcile(
            {".loci": {"canonical": "external", "path": "Notes/${project}"}},
            overlay=tmp_path / "overlay",
            root=tmp_path / "repo",
            project="demo",
        )


@pytest.mark.parametrize("inside", ["repo", "overlay"])
def test_external_path_cannot_resolve_inside_the_repository_or_overlay(
    tmp_path: Path, inside: str
):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"

    with pytest.raises(LinkError, match="inside the"):
        reconcile(
            {".loci": {"canonical": "external", "path": str(tmp_path / inside / "n")}},
            overlay=overlay,
            root=root,
            project="demo",
        )


def test_a_declaration_that_is_not_an_attribute_set_is_refused():
    with pytest.raises(LinkError, match="must be an attribute set"):
        Declaration.read(".envrc", "common/envrc")


def test_an_unknown_canonical_kind_is_refused():
    with pytest.raises(LinkError, match="use central, repo, or external"):
        Declaration.read(".envrc", {"canonical": "machine"})


@pytest.mark.parametrize("canonical", ["repo", "external"])
def test_templates_are_restricted_to_central_declarations(canonical: str):
    with pytest.raises(LinkError, match='only for canonical="central"'):
        Declaration.read(".envrc", {"canonical": canonical, "template": "some-name"})


def test_an_empty_view_is_refused():
    with pytest.raises(LinkError, match="must name a path"):
        Declaration.read("", central())


# ---------------------------------------------------------------------------
# The five states.


def test_absent_view_links_to_an_existing_canonical(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    canonical = overlay / "common/envrc"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("use devenv\n")

    result = reconcile({".envrc": central()}, overlay=overlay, root=root, project="d")

    assert result[0].state == "link"
    assert (root / ".envrc").resolve() == canonical.resolve()
    assert (overlay / STATE_FILE).is_file()


def test_absent_view_and_canonical_create_the_canonical_side_first(tmp_path: Path):
    root = tmp_path / "repo"

    result = reconcile(
        {".envrc": central()}, overlay=tmp_path / "overlay", root=root, project="d"
    )

    assert result[0].state == "create"
    assert (root / ".envrc").is_symlink()
    assert (root / ".envrc").read_text() == ""


def test_a_correct_link_is_a_no_op(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    reconcile({".envrc": central()}, overlay=overlay, root=root, project="d")
    before = (root / ".envrc").lstat().st_ino

    second = reconcile({".envrc": central()}, overlay=overlay, root=root, project="d")

    assert second[0].state == "ok"
    assert (root / ".envrc").lstat().st_ino == before


def test_a_wrong_link_is_repointed(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    wanted = overlay / "common/envrc"
    wanted.parent.mkdir(parents=True)
    wanted.write_text("wanted\n")
    (overlay / "wrong").write_text("wrong\n")
    root.mkdir()
    (root / ".envrc").symlink_to(overlay / "wrong")

    result = reconcile({".envrc": central()}, overlay=overlay, root=root, project="d")

    assert result[0].state == "repoint"
    assert (root / ".envrc").resolve() == wanted.resolve()


def test_a_dangling_correct_link_creates_its_canonical_target(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".envrc").symlink_to(overlay / "common/envrc")

    result = reconcile({".envrc": central()}, overlay=overlay, root=root, project="d")

    assert result[0].state == "create"
    assert (overlay / "common/envrc").is_file()
    assert (root / ".envrc").resolve() == (overlay / "common/envrc").resolve()


def test_a_real_file_is_promoted_and_backed_up(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".envrc").write_text("edited locally\n")

    result = reconcile({".envrc": central()}, overlay=overlay, root=root, project="d")

    assert result[0].state == "promote"
    assert (overlay / "common/envrc").read_text() == "edited locally\n"
    assert (root / ".envrc.devman-promoted").read_text() == "edited locally\n"
    assert (root / ".envrc").is_symlink()


def test_a_real_directory_is_promoted_without_deleting_the_view(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    (root / ".devman/workflows").mkdir(parents=True)
    (root / ".devman/workflows/check.yaml").write_text("steps: []\n")

    result = reconcile(
        {".devman/workflows": {"canonical": "central"}},
        overlay=overlay,
        root=root,
        project="demo",
    )

    canonical = overlay / "projects/demo/repo/.devman/workflows"
    assert result[0].state == "promote"
    assert (canonical / "check.yaml").read_text() == "steps: []\n"
    assert (root / ".devman/workflows.devman-promoted/check.yaml").is_file()


def test_promotion_refuses_when_the_canonical_side_also_changed(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    canonical = overlay / "common/envrc"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("original\n")
    reconcile({".envrc": central()}, overlay=overlay, root=root, project="d")
    canonical.write_text("central edit\n")
    (root / ".envrc").unlink()
    (root / ".envrc").write_text("local edit\n")

    with pytest.raises(LinkError, match="canonical changed"):
        reconcile({".envrc": central()}, overlay=overlay, root=root, project="d")

    assert (root / ".envrc").read_text() == "local edit\n"
    assert canonical.read_text() == "central edit\n"


def test_a_repo_canonical_exposes_the_repository_through_the_overlay(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    (root / ".devman/workflows").mkdir(parents=True)

    result = reconcile(
        {".devman/workflows": {"canonical": "repo"}},
        overlay=overlay,
        root=root,
        project="demo",
    )

    view = overlay / "projects/demo/repo/.devman/workflows"
    assert result[0].state == "link"
    assert view.resolve() == (root / ".devman/workflows").resolve()


def test_a_shared_canonical_ancestor_is_created_as_a_directory(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"

    result = reconcile(
        {
            ".agents": central("projects/demo/agents"),
            ".claude/skills": central("projects/demo/agents/skills"),
        },
        overlay=overlay,
        root=root,
        project="demo",
    )

    assert [item.state for item in result] == ["create", "create"]
    assert (overlay / "projects/demo/agents/skills").is_dir()


def test_an_external_canonical_is_created_as_a_directory(tmp_path: Path):
    root = tmp_path / "repo"
    external = tmp_path / "Notes/1_Projects/demo"

    result = reconcile(
        {".loci": {"canonical": "external", "path": str(external)}},
        overlay=tmp_path / "overlay",
        root=root,
        project="demo",
    )

    assert result[0].state == "create"
    assert external.is_dir()
    assert (root / ".loci").resolve() == external.resolve()


def test_the_bootstrap_central_file_carries_the_standard_link_block(tmp_path: Path):
    result = reconcile(
        {"devenv.local.nix": bootstrap()},
        overlay=tmp_path / "overlay",
        root=tmp_path / "repo",
        project="demo",
    )
    body = (tmp_path / "overlay/projects/demo/devenv.local.nix").read_text()

    assert result[0].state == "create"
    assert (tmp_path / "repo/devenv.local.nix").is_symlink()
    for view in ('".envrc"', '".loci"', '".agents"', '".claude/skills"'):
        assert view in body


def test_a_created_bootstrap_link_is_never_left_dangling(tmp_path: Path):
    """Nix reads `devenv.local.nix` before any hook, so a dangling one is fatal."""
    root = tmp_path / "repo"

    reconcile(
        {"devenv.local.nix": bootstrap()},
        overlay=tmp_path / "overlay",
        root=root,
        project="demo",
    )

    assert (root / "devenv.local.nix").is_symlink()
    assert (root / "devenv.local.nix").resolve().is_file()


# ---------------------------------------------------------------------------
# Git exclude ownership.


def test_a_normal_checkout_gets_a_central_exclude_file(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    exclude = root / ".git/info/exclude"
    exclude.parent.mkdir(parents=True)
    exclude.write_text("# existing\n")

    reconcile({".envrc": central()}, overlay=overlay, root=root, project="demo")

    assert exclude.is_symlink()
    assert exclude.resolve() == (overlay / "projects/demo/.local.gitignore").resolve()
    assert exclude.read_text().splitlines() == [
        "# existing",
        ".devman/.runs/",
        ".envrc",
    ]


def test_a_linked_worktree_uses_its_common_git_directory(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "worktree"
    common = tmp_path / "main/.git"
    worktree_git = common / "worktrees/feature"
    (common / "info").mkdir(parents=True)
    worktree_git.mkdir(parents=True)
    (worktree_git / "commondir").write_text("../..\n")
    (common / "info/exclude").write_text("")
    root.mkdir()
    (root / ".git").write_text(f"gitdir: {worktree_git}\n")

    reconcile({".envrc": central()}, overlay=overlay, root=root, project="demo")

    assert (common / "info/exclude").is_symlink()
    assert (common / "info/exclude").read_text().splitlines() == [
        ".devman/.runs/",
        ".envrc",
    ]


def test_a_repository_without_a_git_marker_gets_no_exclude_link(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()

    reconcile(
        {".envrc": central()}, overlay=tmp_path / "overlay", root=root, project="d"
    )

    assert git_exclude_path(root) is None
    assert not (tmp_path / "overlay/projects/d/.local.gitignore").exists()


def test_a_two_sided_exclude_edit_is_refused(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    exclude = root / ".git/info/exclude"
    exclude.parent.mkdir(parents=True)
    exclude.write_text("# existing\n")
    reconcile({".envrc": central()}, overlay=overlay, root=root, project="demo")
    (overlay / "projects/demo/.local.gitignore").write_text("# central edit\n")
    exclude.unlink()
    exclude.write_text("# local edit\n")

    with pytest.raises(LinkError, match="both changed"):
        reconcile({".envrc": central()}, overlay=overlay, root=root, project="demo")


def test_an_edited_exclude_is_promoted_after_the_central_file_was_linked(
    tmp_path: Path,
):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    exclude = root / ".git/info/exclude"
    exclude.parent.mkdir(parents=True)
    exclude.write_text("# existing\n")
    reconcile({".envrc": central()}, overlay=overlay, root=root, project="demo")
    exclude.unlink()
    exclude.write_text("# edited locally\n")

    result = reconcile(
        {".envrc": central()}, overlay=overlay, root=root, project="demo"
    )

    assert result[0].state == "ok"
    assert (
        (overlay / "projects/demo/.local.gitignore")
        .read_text()
        .startswith("# edited locally\n")
    )


# ---------------------------------------------------------------------------
# The state record.


def test_the_state_record_is_written_atomically(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"

    reconcile({".envrc": central()}, overlay=overlay, root=root, project="demo")

    record = json.loads((overlay / STATE_FILE).read_text())
    assert set(record["demo:.envrc"]) == {"canonical", "hash"}
    assert not list(overlay.glob(f".{STATE_FILE}.new"))


def test_an_unreadable_state_record_is_treated_as_no_baseline(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    overlay.mkdir()
    (overlay / STATE_FILE).write_text("{ not json\n")

    result = reconcile(
        {".envrc": central()}, overlay=overlay, root=root, project="demo"
    )

    assert result[0].state == "create"


# ---------------------------------------------------------------------------
# The command.


def _cli_environment() -> dict[str, str]:
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        f"{SOURCE_ROOT}{os.pathsep}{existing}" if existing else str(SOURCE_ROOT)
    )
    return environment


def test_the_command_runs_as_a_real_subprocess_without_a_registry(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    write_manifest(root, "subprocess-demo")
    write_central_file(
        overlay,
        "subprocess-demo",
        "{ config, ... }:\n\n{\n  devman.link = {\n"
        '    ".envrc" = { canonical = "central"; path = "common/envrc"; };\n'
        "  };\n}\n",
    )
    if shutil.which("nix-instantiate") is None:
        pytest.skip("needs a Nix evaluator")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "devman_link.cli",
            "status",
            "--root",
            str(root),
            "--overlay",
            str(overlay),
        ],
        capture_output=True,
        text=True,
        env=_cli_environment(),
        check=False,
    )

    assert result.returncode == 1, result.stderr
    assert f"central config {overlay}/projects/subprocess-demo" in result.stdout
    assert "create  subprocess-demo:.envrc" in result.stdout


def test_the_command_refuses_a_retired_registry_flag(
    capsys: pytest.CaptureFixture[str],
):
    code = link_cli(["status", "--registry", "/tmp/registry"])

    assert code == 2
    assert "does not read" in capsys.readouterr().err


def test_the_command_refuses_an_unknown_operation():
    with pytest.raises(LinkError, match="unknown link operation"):
        devman_link.run("apply", root=".", overlay=".")


def test_status_reports_drift_as_exit_one_and_no_drift_as_zero(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    write_manifest(root)
    write_central_file(overlay, "demo", DEFAULT_CENTRAL)
    declarations = {".envrc": central()}

    drifted = devman_link.run(
        "status", root=root, overlay=overlay, evaluator=lambda *_: declarations
    )
    devman_link.run(
        "reconcile", root=root, overlay=overlay, evaluator=lambda *_: declarations
    )
    settled = devman_link.run(
        "status", root=root, overlay=overlay, evaluator=lambda *_: declarations
    )

    assert drifted.exit_code == 1
    assert settled.exit_code == 0
    assert {result.state for result in settled.results} == {"ok"}


def test_every_declared_state_name_is_one_the_component_states():
    assert set(devman_link.STATES) == {"ok", "repoint", "promote", "link", "create"}


def test_status_helper_returns_one_result_per_view(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()

    results = status(
        {".envrc": central(), ".agents": central("projects/demo/agents")},
        overlay=tmp_path / "overlay",
        root=root,
        project="demo",
    )

    assert [result.link.declaration.view for result in results] == [".envrc", ".agents"]
