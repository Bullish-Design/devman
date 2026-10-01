"""Lane 2 of the M14 devman cutover: snapshot and restore.

Two claims this file keeps true. First, two consecutive snapshots of an
unchanged tree are byte-identical — the manifest holds no wall-clock field.
Second, `restore.py` recreates a raw symlink target exactly, by bytes, and
refuses on a kind mismatch unless `--force` is given.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from tools.cutover.restore import RestoreRefusedError, restore
from tools.cutover.snapshot import (
    path_kind,
    project_entries,
    raw_target_hex,
    take_snapshot,
    write_snapshot,
)

pytestmark = pytest.mark.unit


def write_manifest(root: Path, project: str) -> None:
    manifest = root / ".devman" / "project.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        f'schema = 1\nproject = "{project}"\ngroups = ["base"]\npolicy = "stable"\n'
    )


def fake_evaluator(_path: Path, _project: str) -> dict[str, object]:
    return {
        ".envrc": {"canonical": "central", "path": "common/envrc"},
        ".agents": {"canonical": "central", "path": "projects/${project}/agents"},
    }


def make_project(root: Path, overlay: Path, project: str) -> None:
    root.mkdir(parents=True)
    write_manifest(root, project)
    (overlay / "projects" / project).mkdir(parents=True)
    (overlay / "common" / "envrc").parent.mkdir(parents=True, exist_ok=True)
    (overlay / "common" / "envrc").write_text("# envrc\n")
    (overlay / "projects" / project / "agents").mkdir()
    (root / ".envrc").symlink_to(overlay / "common" / "envrc")
    (root / ".agents").symlink_to(overlay / "projects" / project / "agents")
    central = overlay / "projects" / project / "devenv.local.nix"
    central.write_text("{ config, ... }: { devman.link = { }; }\n")


# ---------------------------------------------------------------------------
# path_kind / raw_target_hex


def test_path_kind_classifies_without_exists(tmp_path: Path):
    """A broken symlink must classify as `symlink`, never `missing` (Trap 1)."""
    broken = tmp_path / "broken"
    broken.symlink_to(tmp_path / "nowhere")
    real = tmp_path / "real"
    real.write_text("x")
    missing = tmp_path / "absent"

    assert path_kind(broken) == "symlink"
    assert path_kind(real) == "file"
    assert path_kind(missing) == "missing"
    assert path_kind(tmp_path) == "dir"


def test_raw_target_hex_is_the_literal_bytes(tmp_path: Path):
    link = tmp_path / "link"
    link.symlink_to("../relative/target")
    assert bytes.fromhex(raw_target_hex(link)) == b"../relative/target"
    assert raw_target_hex(tmp_path / "absent") is None


# ---------------------------------------------------------------------------
# project_entries


def test_project_entries_covers_declared_links(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    make_project(root, overlay, "demo")

    entries = project_entries("demo", root, overlay=overlay, evaluator=fake_evaluator)

    by_view = {entry.link_rel: entry for entry in entries}
    assert by_view[".envrc"].kind == "symlink"
    assert by_view[".envrc"].declared_in == "overlay"
    assert (
        bytes.fromhex(by_view[".envrc"].raw_target_hex)
        == str(overlay / "common" / "envrc").encode()
    )
    assert "devenv.local.nix" in by_view
    assert entries == sorted(entries, key=lambda entry: entry.link_rel)


def test_project_entries_refuses_canonical_repo(tmp_path: Path):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    make_project(root, overlay, "demo")

    def evaluator(_path: Path, _project: str) -> dict[str, object]:
        return {".notes": {"canonical": "repo", "path": "notes"}}

    with pytest.raises(RuntimeError, match='canonical="repo"'):
        project_entries("demo", root, overlay=overlay, evaluator=evaluator)


# ---------------------------------------------------------------------------
# take_snapshot — the byte-identity gate


def test_two_consecutive_snapshots_are_byte_identical(tmp_path: Path):
    projects_root = tmp_path / "projects"
    overlay = tmp_path / "overlay"
    make_project(projects_root / "demo", overlay, "demo")

    first = take_snapshot(projects_root, overlay=overlay, evaluator=fake_evaluator)
    second = take_snapshot(projects_root, overlay=overlay, evaluator=fake_evaluator)

    out_a = tmp_path / "snap-a.json"
    out_b = tmp_path / "snap-b.json"
    write_snapshot(out_a, first)
    write_snapshot(out_b, second)

    assert out_a.read_bytes() == out_b.read_bytes()
    assert "captured_at" not in json.loads(out_a.read_text())


def test_take_snapshot_sweeps_every_manifest_backed_project(tmp_path: Path):
    projects_root = tmp_path / "projects"
    overlay = tmp_path / "overlay"
    make_project(projects_root / "alpha", overlay, "alpha")
    make_project(projects_root / "beta", overlay, "beta")
    (projects_root / "no-manifest").mkdir(parents=True)

    snapshot = take_snapshot(projects_root, overlay=overlay, evaluator=fake_evaluator)

    projects = {entry["project"] for entry in snapshot["entries"]}
    assert projects == {"alpha", "beta"}


# ---------------------------------------------------------------------------
# restore.py


def test_restore_recreates_the_recorded_raw_target(tmp_path: Path):
    projects_root = tmp_path / "projects"
    overlay = tmp_path / "overlay"
    make_project(projects_root / "demo", overlay, "demo")

    before = take_snapshot(projects_root, overlay=overlay, evaluator=fake_evaluator)

    envrc = projects_root / "demo" / ".envrc"
    envrc.unlink()
    envrc.symlink_to("/somewhere/else")

    changed = restore(before, projects_root=projects_root)

    assert "demo:.envrc" in changed
    assert os.readlink(envrc) == str(overlay / "common" / "envrc")


def test_restore_is_a_noop_on_an_already_matching_tree(tmp_path: Path):
    projects_root = tmp_path / "projects"
    overlay = tmp_path / "overlay"
    make_project(projects_root / "demo", overlay, "demo")

    before = take_snapshot(projects_root, overlay=overlay, evaluator=fake_evaluator)
    changed = restore(before, projects_root=projects_root)

    assert changed == []


def test_restore_refuses_on_a_kind_mismatch_without_force(tmp_path: Path):
    projects_root = tmp_path / "projects"
    overlay = tmp_path / "overlay"
    make_project(projects_root / "demo", overlay, "demo")

    before = take_snapshot(projects_root, overlay=overlay, evaluator=fake_evaluator)

    envrc = projects_root / "demo" / ".envrc"
    envrc.unlink()
    envrc.write_text("real content now")

    with pytest.raises(RestoreRefusedError):
        restore(before, projects_root=projects_root)

    assert envrc.read_text() == "real content now"

    changed = restore(before, projects_root=projects_root, force=True)
    assert "demo:.envrc" in changed
    assert os.readlink(envrc) == str(overlay / "common" / "envrc")
