"""Lane 7 of the M14 devman cutover: Phase C, devman calls Linkman.

Proves the concept §14 flow (`devman.linking.reconcile_with_linkman`) end to
end against real `links.yaml` declarations, the missing-`links.yaml`
assertion fires as a refusal, and `devman_link` stays importable behind the
flag — the three things the Lane 7 gate names.

`DEVMAN_LINK_ENGINE=linkman devman link reconcile` was also run against a
real live project (see the Lane 7 commit message); this file is the
scripted, fixture-based proof.

`linkman` needs `pydantic`, which lives in the `cutover` extra
(`pyproject.toml`), not in the base dependency list `base:unit` and
`base:test` hand their hermetic interpreter — see that file's comment for
why. This module is skipped there and runs for real in the dev venv
(`uv sync --extra cutover`, then `pytest tests/unit/test_linking.py`).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import devman_link

pytest.importorskip("linkman")

from devman.linking import LinkingError, reconcile_with_linkman  # noqa: E402

pytestmark = pytest.mark.unit


def write_manifest(root: Path, project: str) -> None:
    manifest = root / ".devman" / "project.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        f'schema = 1\nproject = "{project}"\ngroups = ["base"]\npolicy = "stable"\n'
    )


def write_links_yaml(overlay: Path, project: str, envrc_target: Path) -> Path:
    central = overlay / "projects" / project
    central.mkdir(parents=True, exist_ok=True)
    bootstrap_target = central / "devenv.local.nix"
    path = central / "links.yaml"
    path.write_text(
        "version: 1\n"
        "links:\n"
        f'  ".envrc":\n    target: "{envrc_target}"\n'
        f'  "devenv.local.nix":\n    target: "{bootstrap_target}"\n'
    )
    return path


def make_project(root: Path, overlay: Path, project: str) -> Path:
    root.mkdir(parents=True)
    write_manifest(root, project)
    (root / ".git").mkdir()
    envrc_target = overlay / "common" / "envrc"
    envrc_target.parent.mkdir(parents=True, exist_ok=True)
    envrc_target.write_text("# envrc\n")
    return write_links_yaml(overlay, project, envrc_target)


# ---------------------------------------------------------------------------
# devman_link stays importable behind the flag


def test_devman_link_still_imports():
    assert devman_link.run is not None


# ---------------------------------------------------------------------------
# the missing-links.yaml assertion


def test_missing_links_yaml_is_refused(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    write_manifest(root, "demo")

    with pytest.raises(LinkingError, match="no links.yaml"):
        reconcile_with_linkman(root, overlay=overlay, project=None)


def test_missing_links_yaml_creates_no_central_directory_content(tmp_path: Path):
    """A refusal must not half-create the thing it is refusing over."""
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    write_manifest(root, "demo")

    with pytest.raises(LinkingError):
        reconcile_with_linkman(root, overlay=overlay, project=None)

    central = overlay / "projects" / "demo"
    assert list(central.iterdir()) == [] if central.exists() else True


# ---------------------------------------------------------------------------
# the six-step flow, end to end


def test_reconcile_creates_the_declared_links(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    make_project(root, overlay, "demo")

    result = reconcile_with_linkman(root, overlay=overlay, project=None)

    assert result.identity.project == "demo"
    assert (root / ".envrc").is_symlink()
    assert os.readlink(root / ".envrc") == str(overlay / "common" / "envrc")
    assert (root / "devenv.local.nix").is_symlink()
    assert not result.apply_result.failed
    assert not result.apply_result.refused


def test_bootstrap_is_written_before_the_link_is_made(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    make_project(root, overlay, "demo")
    bootstrap_target = overlay / "projects" / "demo" / "devenv.local.nix"
    assert not bootstrap_target.exists()

    reconcile_with_linkman(root, overlay=overlay, project=None)

    assert bootstrap_target.is_file()
    assert "devman.link" in bootstrap_target.read_text()
    assert os.readlink(root / "devenv.local.nix") == str(bootstrap_target)


def test_bootstrap_is_never_overwritten_once_present(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    make_project(root, overlay, "demo")
    bootstrap_target = overlay / "projects" / "demo" / "devenv.local.nix"
    bootstrap_target.parent.mkdir(parents=True, exist_ok=True)
    bootstrap_target.write_text("# a hand-authored bootstrap\n")

    reconcile_with_linkman(root, overlay=overlay, project=None)

    assert bootstrap_target.read_text() == "# a hand-authored bootstrap\n"


def test_reconcile_projects_the_git_exclude(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    make_project(root, overlay, "demo")

    reconcile_with_linkman(root, overlay=overlay, project=None)

    exclude = root / ".git" / "info" / "exclude"
    assert exclude.is_symlink()
    canonical = overlay / "projects" / "demo" / ".local.gitignore"
    assert canonical.is_file()
    assert ".envrc" in canonical.read_text()


def test_reconcile_is_idempotent(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    make_project(root, overlay, "demo")

    reconcile_with_linkman(root, overlay=overlay, project=None)
    second = reconcile_with_linkman(root, overlay=overlay, project=None)

    assert all(applied.actions == ["noop"] for applied in second.apply_result.applied)
