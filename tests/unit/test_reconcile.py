"""Central Devman resolution tests used by the machine-plane renderer."""

from __future__ import annotations

import json

import pytest

from devman.contract import PlaneGeneration, ProjectManifest, digest_bytes
from devman.reconcile import (
    ReconcileError,
    bundle_from_json,
    render_project,
    renderer_digest,
    resolve_policy,
)

WORKFLOW = """steps:
  - name: check
    command: echo ok
"""


def _manifest(root, project="fixture", groups=("base",)):
    devman = root / ".devman"
    devman.mkdir(parents=True, exist_ok=True)
    (devman / "project.toml").write_text(
        "schema = 1\n"
        f'project = "{project}"\n'
        f"groups = [{', '.join(json.dumps(group) for group in groups)}]\n"
        'policy = "stable"\n'
    )


def _generation(policy_digest, number=7):
    return PlaneGeneration(
        generation=number,
        devman_runtime="test-runtime",
        renderer_digest=renderer_digest(),
        policy_digest=policy_digest,
        dagu_digest=digest_bytes(b"dagu"),
        toolchain_digest=digest_bytes(b"toolchain"),
    )


def _policy_root(tmp_path):
    root = tmp_path / "policy"
    group = root / "groups" / "base" / "workflows"
    group.mkdir(parents=True)
    (group / "check.yaml").write_text(WORKFLOW)
    return root


def test_policy_resolution_is_ordered_and_has_one_machine_digest(tmp_path):
    policy_root = _policy_root(tmp_path)
    extra = policy_root / "groups" / "extra" / "workflows"
    extra.mkdir(parents=True)
    (extra / "other.yaml").write_text(WORKFLOW)

    first = tmp_path / "first"
    second = tmp_path / "second"
    _manifest(first, groups=("base",))
    _manifest(second, groups=("extra",))

    first_policy = resolve_policy(ProjectManifest.from_root(first), policy_root)
    second_policy = resolve_policy(ProjectManifest.from_root(second), policy_root)

    assert first_policy.digest == second_policy.digest
    assert set(first_policy.workflows) == {"check"}
    assert set(second_policy.workflows) == {"other"}


def test_render_project_resolves_overlay_and_emits_metadata(tmp_path):
    policy_root = _policy_root(tmp_path)
    project_root = tmp_path / "project"
    _manifest(project_root)
    overlay = tmp_path / "overlay" / "projects" / "fixture" / "workflows"
    overlay.mkdir(parents=True)
    (overlay / "check.yaml").write_text("# overlay\n" + WORKFLOW)
    (overlay / "local.yaml").write_text(WORKFLOW)

    policy = resolve_policy(ProjectManifest.from_root(project_root), policy_root)
    bundle = render_project(
        project_root,
        policy_root=policy_root,
        overlay_root=tmp_path / "overlay",
        generation=_generation(policy.digest),
    )

    projected = bundle.files["projects/fixture/workflows/check.yaml"].decode()
    metadata = json.loads(bundle.files["projects/fixture/metadata.json"])
    assert projected.endswith("# overlay\n" + WORKFLOW)
    assert "projects/fixture/workflows/check.yaml" in projected
    assert f"#   {project_root}" not in projected
    assert set(bundle.sources) == {"check", "local"}
    assert metadata["local"] == ["check", "local"]
    assert bundle.record.overlay_digest is not None
    assert bundle.links["dags/fixture.check.yaml"].endswith("check.yaml")


def test_renderer_bundle_round_trips_without_losing_bytes(tmp_path):
    policy_root = _policy_root(tmp_path)
    project_root = tmp_path / "project"
    _manifest(project_root)
    policy = resolve_policy(ProjectManifest.from_root(project_root), policy_root)
    bundle = render_project(
        project_root,
        policy_root=policy_root,
        overlay_root=tmp_path / "overlay",
        generation=_generation(policy.digest),
    )

    restored = bundle_from_json(bundle.to_json())

    assert restored.record == bundle.record
    assert restored.files == bundle.files
    assert restored.links == bundle.links


def test_renderer_rejects_a_generation_from_another_policy(tmp_path):
    policy_root = _policy_root(tmp_path)
    project_root = tmp_path / "project"
    _manifest(project_root)
    with pytest.raises(ReconcileError, match="does not match policy"):
        render_project(
            project_root,
            policy_root=policy_root,
            overlay_root=tmp_path / "overlay",
            generation=_generation(digest_bytes(b"other")),
        )
