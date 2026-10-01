"""Lane 6 of the M14 devman cutover: the Phase B byte-identity gate.

`linkman apply` itself is never run for real here — these are unit tests,
and the real gate runs against the live machine (see the Lane 6 commit
message for that evidence). What this file proves: the gate's own
bookkeeping is correct — population scoping, diffing, idempotence, and
mutation-scope detection — given a scripted `run_apply`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tools.cutover.gate import (
    GateFailureError,
    gate_project,
    linkman_population,
    mutating_action_count,
    top_level_digest,
)
from tools.cutover.snapshot import SnapshotEntry
from tools.cutover.snapshot import project_entries as real_project_entries

pytestmark = pytest.mark.unit


def write_manifest(root: Path, project: str) -> None:
    manifest = root / ".devman" / "project.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        f'schema = 1\nproject = "{project}"\ngroups = ["base"]\npolicy = "stable"\n'
    )


def fake_evaluator(_path: Path, _project: str) -> dict[str, object]:
    return {".envrc": {"canonical": "central", "path": "common/envrc"}}


def noop_apply_result(repo_root: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "command": "apply",
        "repo_root": str(repo_root),
        "applied": [
            {
                "link_rel": ".envrc",
                "actions": ["noop"],
                "previous_raw_target": None,
                "created_target_kind": None,
                "source": str(repo_root),
            }
        ],
        "refused": [],
        "failed": [],
        "sources": {},
    }


def make_project(root: Path, overlay: Path, project: str) -> None:
    root.mkdir(parents=True)
    write_manifest(root, project)
    (overlay / "projects" / project).mkdir(parents=True)
    (overlay / "common").mkdir(parents=True, exist_ok=True)
    (overlay / "common" / "envrc").write_text("# envrc\n")
    (root / ".envrc").symlink_to(overlay / "common" / "envrc")
    (overlay / "projects" / project / "devenv.local.nix").write_text(
        "{ config, ... }: { devman.link = { }; }\n"
    )


# ---------------------------------------------------------------------------
# small pure helpers


def test_linkman_population_excludes_git_exclude():
    entries = [
        SnapshotEntry("demo", ".envrc", "aa", "symlink", "overlay"),
        SnapshotEntry("demo", ".git/info/exclude", "bb", "file", "implicit"),
    ]
    assert [e.link_rel for e in linkman_population(entries)] == [".envrc"]


def test_mutating_action_count_counts_only_mutating_kinds():
    result = {
        "applied": [
            {"actions": ["noop"]},
            {"actions": ["create_target_dir", "create_link"]},
            {"actions": ["repoint_link"]},
        ]
    }
    assert mutating_action_count(result) == 3


def test_top_level_digest_excludes_named_entries(tmp_path: Path):
    (tmp_path / "managed").write_text("x")
    (tmp_path / "other.txt").write_text("y")

    digest = top_level_digest(tmp_path, exclude={"managed"})

    assert "managed" not in digest
    assert "other.txt" in digest


def test_top_level_digest_changes_when_file_content_changes(tmp_path: Path):
    target = tmp_path / "other.txt"
    target.write_text("y")
    before = top_level_digest(tmp_path, exclude=set())

    target.write_text("changed")
    after = top_level_digest(tmp_path, exclude=set())

    assert before != after


# ---------------------------------------------------------------------------
# gate_project — the orchestration


def test_gate_project_passes_cleanly_when_apply_is_a_true_noop(
    tmp_path: Path, monkeypatch
):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    make_project(root, overlay, "demo")
    monkeypatch.setattr(
        "tools.cutover.gate.project_entries",
        lambda project, root, overlay: real_project_entries(
            project, root, overlay=overlay, evaluator=fake_evaluator
        ),
    )
    monkeypatch.setattr(
        "tools.cutover.gate.run_apply",
        lambda linkman_bin, root, overlay, project: noop_apply_result(root),
    )

    diffs, population = gate_project(Path("linkman"), root, overlay, "demo")

    assert diffs == []
    assert population == 2


def test_gate_project_refuses_a_non_idempotent_second_apply(
    tmp_path: Path, monkeypatch
):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    make_project(root, overlay, "demo")
    monkeypatch.setattr(
        "tools.cutover.gate.project_entries",
        lambda project, root, overlay: real_project_entries(
            project, root, overlay=overlay, evaluator=fake_evaluator
        ),
    )

    calls = {"n": 0}

    def flaky_apply(linkman_bin, root, overlay, project):
        calls["n"] += 1
        if calls["n"] == 1:
            return noop_apply_result(root)
        result = noop_apply_result(root)
        result["applied"][0]["actions"] = ["repoint_link"]
        return result

    monkeypatch.setattr("tools.cutover.gate.run_apply", flaky_apply)

    with pytest.raises(GateFailureError, match="not idempotent"):
        gate_project(Path("linkman"), root, overlay, "demo")


def test_gate_project_refuses_a_mutation_outside_the_managed_set(
    tmp_path: Path, monkeypatch
):
    overlay = tmp_path / "overlay"
    root = tmp_path / "repo"
    make_project(root, overlay, "demo")
    (root / "untouched.txt").write_text("before")
    monkeypatch.setattr(
        "tools.cutover.gate.project_entries",
        lambda project, root, overlay: real_project_entries(
            project, root, overlay=overlay, evaluator=fake_evaluator
        ),
    )

    def mutating_apply(linkman_bin, root, overlay, project):
        (root / "untouched.txt").write_text("surprise")
        return noop_apply_result(root)

    monkeypatch.setattr("tools.cutover.gate.run_apply", mutating_apply)

    with pytest.raises(GateFailureError, match="outside the managed symlink set"):
        gate_project(Path("linkman"), root, overlay, "demo")
