from __future__ import annotations

from pathlib import Path

import pytest

from devman.link import Declaration, LinkError, _project_from_nix, reconcile, resolve


def central_decl(path: str = "common/envrc") -> dict[str, str]:
    return {"canonical": "central", "path": path}


def test_absent_view_links_to_existing_canonical(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    canonical = overlay / "common/envrc"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("use devenv\n")

    result = reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )

    assert result[0].state == "link"
    assert (root / ".envrc").is_symlink()
    assert (root / ".envrc").resolve() == canonical.resolve()
    assert (overlay / ".devman-link-state.json").is_file()


def test_absent_view_and_canonical_create_an_empty_file(tmp_path: Path):
    root = tmp_path / "repo"
    result = reconcile(
        {".envrc": central_decl()},
        overlay=tmp_path / "overlay",
        root=root,
        project="demo",
    )

    assert result[0].state == "create"
    assert (root / ".envrc").is_symlink()
    assert (root / ".envrc").read_text() == ""


def test_correct_link_is_a_noop(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    canonical = overlay / "common/envrc"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("use devenv\n")

    first = reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )
    before = (root / ".envrc").lstat()
    second = reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )

    assert first[0].state == "link"
    assert second[0].state == "ok"
    assert (root / ".envrc").lstat().st_ino == before.st_ino


def test_wrong_link_is_repointed(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    wanted = overlay / "common/envrc"
    wrong = overlay / "wrong"
    wanted.parent.mkdir(parents=True)
    wanted.write_text("wanted\n")
    wrong.write_text("wrong\n")
    (root / ".envrc").parent.mkdir(parents=True)
    (root / ".envrc").symlink_to(wrong)

    result = reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )

    assert result[0].state == "repoint"
    assert (root / ".envrc").resolve() == wanted.resolve()


def test_real_view_is_promoted_before_linking(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    canonical = overlay / "common/envrc"
    canonical.parent.mkdir(parents=True)
    (root / ".envrc").parent.mkdir(parents=True)
    (root / ".envrc").write_text("edited locally\n")

    result = reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )

    assert result[0].state == "promote"
    assert canonical.read_text() == "edited locally\n"
    assert (root / ".envrc").is_symlink()
    assert (root / ".envrc.devman-promoted").read_text() == "edited locally\n"


def test_real_directory_is_promoted_without_deleting_the_view(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    view = root / ".devman/workflows"
    view.mkdir(parents=True)
    (view / "check.yaml").write_text("steps: []\n")

    result = reconcile(
        {".devman/workflows": {"canonical": "central"}},
        overlay=overlay,
        root=root,
        project="demo",
    )

    canonical = overlay / "projects/demo/repo/.devman/workflows"
    assert result[0].state == "promote"
    assert (canonical / "check.yaml").read_text() == "steps: []\n"
    assert view.is_symlink()
    assert (root / ".devman/workflows.devman-promoted/check.yaml").read_text() == (
        "steps: []\n"
    )


def test_first_reconcile_creates_a_shared_canonical_ancestor_as_a_directory(
    tmp_path: Path,
):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"

    result = reconcile(
        {
            ".agents": {"canonical": "central", "path": "projects/demo/agents"},
            ".claude/skills": {
                "canonical": "central",
                "path": "projects/demo/agents/skills",
            },
        },
        overlay=overlay,
        root=root,
        project="demo",
    )

    assert [item.state for item in result] == ["create", "create"]
    assert (overlay / "projects/demo/agents").is_dir()
    assert (overlay / "projects/demo/agents/skills").is_dir()
    assert (root / ".agents").is_symlink()
    assert (root / ".claude/skills").is_symlink()


def test_promotion_refuses_when_canonical_changed_since_link(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    canonical = overlay / "common/envrc"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("original\n")
    reconcile({".envrc": central_decl()}, overlay=overlay, root=root, project="demo")
    canonical.write_text("central edit\n")
    (root / ".envrc").unlink()
    (root / ".envrc").write_text("local edit\n")

    with pytest.raises(LinkError, match="canonical changed"):
        reconcile(
            {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
        )

    assert (root / ".envrc").read_text() == "local edit\n"


def test_repo_canonical_exposes_a_relative_overlay_view(tmp_path: Path):
    root = tmp_path / "repo"
    (root / ".devman/workflows").mkdir(parents=True)
    (root / ".devman/workflows/check.yaml").write_text("steps: []\n")

    result = reconcile(
        {".devman/workflows": {"canonical": "repo"}},
        overlay=tmp_path / "overlay",
        root=root,
        project="demo",
    )
    link = tmp_path / "overlay/projects/demo/repo/.devman/workflows"

    assert result[0].state == "link"
    assert link.is_symlink()
    assert link.resolve() == (root / ".devman/workflows").resolve()


def test_declaration_cannot_escape_overlay(tmp_path: Path):
    with pytest.raises(LinkError, match="relative"):
        resolve(
            # The public declaration reader is intentionally used here through
            # reconcile in normal operation; this call checks the resolved side.
            Declaration.read(".envrc", {"path": "/tmp/envrc"}),
            overlay=tmp_path / "overlay",
            root=tmp_path / "repo",
            project="demo",
        )


@pytest.mark.parametrize("canonical", ["repo", "external"])
def test_templates_are_restricted_to_central_canonical_content(
    tmp_path: Path, canonical: str
):
    declaration = {"canonical": canonical, "template": "template-name"}

    with pytest.raises(LinkError, match="only for canonical=\"central\""):
        Declaration.read(".envrc", declaration)


def test_central_path_cannot_escape_through_a_symlinked_directory(tmp_path: Path):
    overlay = tmp_path / "overlay"
    outside = tmp_path / "outside"
    overlay.mkdir()
    outside.mkdir()
    (overlay / "common").symlink_to(outside, target_is_directory=True)

    with pytest.raises(LinkError, match="escapes"):
        resolve(
            Declaration.read(".envrc", central_decl("common/envrc")),
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
            Declaration.read("config/envrc", central_decl()),
            overlay=tmp_path / "overlay",
            root=root,
            project="demo",
        )


def test_wrong_link_to_an_absent_canonical_is_repaired_deterministically(
    tmp_path: Path,
):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    wrong = tmp_path / "wrong"
    wrong.write_text("not the canonical file\n")
    (root / ".envrc").parent.mkdir(parents=True)
    (root / ".envrc").symlink_to(wrong)

    result = reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )

    canonical = overlay / "common/envrc"
    assert result[0].state == "repoint"
    assert canonical.read_text() == ""
    assert (root / ".envrc").resolve() == canonical.resolve()


def test_a_dangling_correct_link_creates_its_canonical_target(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    canonical = overlay / "common/envrc"
    root.mkdir()
    (root / ".envrc").symlink_to(canonical)

    result = reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )

    assert result[0].state == "create"
    assert canonical.is_file()
    assert (root / ".envrc").resolve() == canonical.resolve()


def test_reconcile_writes_exclusions_for_normal_git_repositories(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    exclude = root / ".git/info/exclude"
    exclude.parent.mkdir(parents=True)
    exclude.write_text("# existing\n")
    canonical = overlay / "common/envrc"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("use devenv\n")

    reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )

    assert exclude.read_text().splitlines() == [
        "# existing",
        ".devman/.runs/",
        ".envrc",
    ]
    assert exclude.is_symlink()
    assert exclude.resolve() == (overlay / "projects/demo/.local.gitignore").resolve()
    assert not (root / ".gitignore").exists()


def test_reconcile_writes_exclusions_to_a_linked_worktree_common_git_dir(
    tmp_path: Path,
):
    overlay = tmp_path / "overlay"
    root = tmp_path / "worktree"
    common_git = tmp_path / "main/.git"
    worktree_git = common_git / "worktrees/feature"
    (common_git / "info").mkdir(parents=True)
    (worktree_git).mkdir(parents=True)
    (worktree_git / "commondir").write_text("../..\n")
    (common_git / "info/exclude").write_text("")
    root.mkdir()
    (root / ".git").write_text(f"gitdir: {worktree_git}\n")
    canonical = overlay / "common/envrc"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("use devenv\n")

    reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )

    assert (common_git / "info/exclude").read_text().splitlines() == [
        ".devman/.runs/",
        ".envrc",
    ]
    assert (common_git / "info/exclude").is_symlink()
    assert (common_git / "info/exclude").resolve() == (
        overlay / "projects/demo/.local.gitignore"
    ).resolve()


def test_reconcile_promotes_changed_exclude_after_the_central_file_was_linked(
    tmp_path: Path,
):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    exclude = root / ".git/info/exclude"
    exclude.parent.mkdir(parents=True)
    exclude.write_text("# existing\n")

    reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )
    exclude.unlink()
    exclude.write_text("# edited locally\n")

    result = reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )

    assert result[0].state == "ok"
    assert (overlay / "projects/demo/.local.gitignore").read_text().startswith(
        "# edited locally\n"
    )
    assert exclude.is_symlink()


def test_reconcile_refuses_two_sided_local_gitignore_edits(tmp_path: Path):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    exclude = root / ".git/info/exclude"
    exclude.parent.mkdir(parents=True)
    exclude.write_text("# existing\n")

    reconcile(
        {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
    )
    (overlay / "projects/demo/.local.gitignore").write_text("# central edit\n")
    exclude.unlink()
    exclude.write_text("# local edit\n")

    with pytest.raises(LinkError, match="both changed"):
        reconcile(
            {".envrc": central_decl()}, overlay=overlay, root=root, project="demo"
        )


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        (
            'let\n  projectName = "devman";\nin\n{ devman = { project = projectName; }; }\n',
            "devman",
        ),
        ('{ devman.project = "literal"; }\n', "literal"),
    ],
)
def test_project_identity_reads_supported_explicit_forms(
    tmp_path: Path, contents: str, expected: str
):
    (tmp_path / "devenv.nix").write_text(contents)

    assert _project_from_nix(tmp_path) == expected


def test_project_identity_refuses_missing_identity(tmp_path: Path):
    (tmp_path / "devenv.nix").write_text("{ name = \"directory-name\"; }\n")

    with pytest.raises(LinkError, match="cannot determine project identity"):
        _project_from_nix(tmp_path)


def test_project_identity_refuses_ambiguous_identity(tmp_path: Path):
    (tmp_path / "devenv.nix").write_text(
        '{ devman = { project = "one"; }; }\n'
        '{ devman = { project = "two"; }; }\n'
    )

    with pytest.raises(LinkError, match="ambiguous project identity"):
        _project_from_nix(tmp_path)


def test_external_canonical_is_created_as_a_directory(tmp_path: Path):
    root = tmp_path / "repo"
    external = tmp_path / "Notes" / "1_Projects" / "demo"

    result = reconcile(
        {".loci": {"canonical": "external", "path": str(external)}},
        overlay=tmp_path / "overlay",
        root=root,
        project="demo",
    )

    assert result[0].state == "create"
    assert external.is_dir()
    assert (root / ".loci").is_symlink()
    assert (root / ".loci").resolve() == external.resolve()


def test_external_path_must_be_absolute_after_expansion(tmp_path: Path):
    with pytest.raises(LinkError, match="must be absolute"):
        reconcile(
            {".loci": {"canonical": "external", "path": "Notes/${project}"}},
            overlay=tmp_path / "overlay",
            root=tmp_path / "repo",
            project="demo",
        )


def test_external_path_cannot_resolve_inside_project_or_overlay(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    for path in (root / "notes", overlay / "notes"):
        with pytest.raises(LinkError, match="inside the"):
            reconcile(
                {".loci": {"canonical": "external", "path": str(path)}},
                overlay=overlay,
                root=root,
                project="demo",
            )


def test_new_project_devenv_local_file_bootstraps_default_links(tmp_path: Path):
    result = reconcile(
        {
            "devenv.local.nix": {
                "canonical": "central",
                "path": "projects/demo/devenv.local.nix",
            }
        },
        overlay=tmp_path / "overlay",
        root=tmp_path / "repo",
        project="demo",
    )

    assert result[0].state == "create"
    local = tmp_path / "overlay/projects/demo/devenv.local.nix"
    assert '".envrc"' in local.read_text()
    assert '".loci"' in local.read_text()
    assert '".agents"' in local.read_text()
    assert '".claude/skills"' in local.read_text()
