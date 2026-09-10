from __future__ import annotations

from pathlib import Path

import pytest

from devman.link import Declaration, LinkError, reconcile, resolve


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
