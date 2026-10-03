"""Central Devman resolution tests used by the machine-plane renderer."""

from __future__ import annotations

import json
import shutil

import pytest

from devman.project import ProjectionError
from devman.reconcile import (
    ReconcileError,
    bundle_from_json,
    compatibility_apply,
    inspect_project,
    render_project,
    renderer_digest,
    resolve_policy,
)
from devman_contract import PlaneGeneration, ProjectManifest, digest_blobs, digest_bytes

WORKFLOW = """steps:
  - name: check
    command: echo ok
"""

# `compatibility_apply` validates every rendered workflow by running the
# `dagu` binary named in its `dagu=` argument (`_validate_compatibility`).
# Tests below pass the coreutils `true`/`false` in that slot instead of a
# real `dagu`, so they measure the registration path and not the Dagu
# binary — but `subprocess.run` still has to find `true`/`false` ON PATH
# (it execs them directly; a shell builtin would not need this). A
# PATH-stripped run must SKIP these, not fail with a bare
# `FileNotFoundError` — same idiom as `needs_git` and `needs_nix` in
# `tests/unit/test_central.py`.
needs_true_false = pytest.mark.skipif(
    shutil.which("true") is None or shutil.which("false") is None,
    reason="needs the coreutils true/false binaries on PATH",
)


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


def test_inspection_returns_identity_without_rendered_files(tmp_path):
    policy_root = _policy_root(tmp_path)
    project_root = tmp_path / "project"
    _manifest(project_root)
    policy = resolve_policy(ProjectManifest.from_root(project_root), policy_root)

    inspection = inspect_project(
        project_root,
        policy_root=policy_root,
        overlay_root=tmp_path / "overlay",
        generation=_generation(policy.digest),
    )

    assert inspection.project == "fixture"
    assert inspection.record.source_digest == digest_blobs(
        {"workflows/check.yaml": WORKFLOW.encode()}
    )
    assert inspection.sources == {"check": "groups/base/workflows/check.yaml"}


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


@needs_true_false
def test_compatibility_apply_publishes_the_canonical_render(tmp_path):
    policy_root = _policy_root(tmp_path)
    project_root = tmp_path / "project"
    _manifest(project_root)
    registry = tmp_path / "registry"
    state = tmp_path / "state"

    compatibility_apply(
        project_root,
        policy_root=policy_root,
        overlay_root=tmp_path / "overlay",
        registry=registry,
        state=state,
        plan="/nix/store/compatibility-plan.json",
        dagu="true",
    )

    projected = registry / "projects" / "fixture" / "workflows" / "check.yaml"
    assert projected.read_text().endswith(WORKFLOW)
    assert (registry / "dags" / "fixture.check.yaml").is_symlink()
    metadata = json.loads(
        (state / "projects" / "fixture" / "metadata.json").read_text()
    )
    assert metadata["plan"] == "/nix/store/compatibility-plan.json"


@needs_true_false
def test_compatibility_apply_validates_before_publishing(tmp_path):
    policy_root = _policy_root(tmp_path)
    project_root = tmp_path / "project"
    _manifest(project_root)
    registry = tmp_path / "registry"
    state = tmp_path / "state"

    with pytest.raises(ProjectionError, match="refusing to publish"):
        compatibility_apply(
            project_root,
            policy_root=policy_root,
            overlay_root=tmp_path / "overlay",
            registry=registry,
            state=state,
            plan="compatibility-plan",
            dagu="false",
        )

    assert not (registry / "projects" / "fixture" / "workflows" / "check.yaml").exists()
    assert not (registry / "dags" / "fixture.check.yaml").exists()
    assert not (state / "projects" / "fixture" / "metadata.json").exists()


def test_compatibility_apply_refuses_shared_authored_and_generated_roots(tmp_path):
    policy_root = _policy_root(tmp_path)
    project_root = tmp_path / "project"
    _manifest(project_root)
    shared = tmp_path / "shared"

    with pytest.raises(ReconcileError, match="must be different roots"):
        compatibility_apply(
            project_root,
            policy_root=policy_root,
            overlay_root=shared,
            registry=shared,
            state=tmp_path / "state",
            plan="compatibility-plan",
            dagu="true",
        )

    assert not (shared / "projects").exists()


@needs_true_false
def test_compatibility_apply_skips_unchanged_validation(tmp_path):
    policy_root = _policy_root(tmp_path)
    project_root = tmp_path / "project"
    _manifest(project_root)
    registry = tmp_path / "registry"
    state = tmp_path / "state"
    kwargs = {
        "policy_root": policy_root,
        "overlay_root": tmp_path / "overlay",
        "registry": registry,
        "state": state,
        "plan": "compatibility-plan",
    }

    compatibility_apply(project_root, dagu="true", **kwargs)
    compatibility_apply(project_root, dagu="false", **kwargs)

    assert (registry / "projects" / "fixture" / "workflows" / "check.yaml").exists()


# ---------------------------------------------------------------------------
# the duplicate-registration refusal (025 CONCEPT.md §10 item 2; devman
# project 041, O9). All four fixtures below share one registry/state pair and
# one project name ("fixture"), because the refusal is about two CHECKOUTS
# colliding on one name — never against the live registry, which changes
# hourly on this machine.


def _apply_kwargs(tmp_path, policy_root):
    return {
        "policy_root": policy_root,
        "overlay_root": tmp_path / "overlay",
        "registry": tmp_path / "registry",
        "state": tmp_path / "state",
        "plan": "compatibility-plan",
        "dagu": "true",
    }


@needs_true_false
def test_compatibility_apply_refuses_a_second_checkout_with_the_same_name(tmp_path):
    policy_root = _policy_root(tmp_path)
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _manifest(first_root)
    _manifest(second_root)
    kwargs = _apply_kwargs(tmp_path, policy_root)

    compatibility_apply(first_root, **kwargs)
    metadata_path = kwargs["state"] / "projects" / "fixture" / "metadata.json"
    before = metadata_path.read_bytes()

    with pytest.raises(
        ReconcileError, match="refusing to register 'fixture'"
    ) as excinfo:
        compatibility_apply(second_root, **kwargs)

    message = str(excinfo.value)
    # The refusal names both paths and the recovery command, so the operator
    # does not have to guess either.
    assert str(first_root) in message
    assert str(second_root) in message
    assert "devman project apply" in message

    # The surviving checkout's entry is untouched — bytes, not just presence,
    # because a refusal that still rewrites the file with the same JSON would
    # hide a bug the "unchanged" claim exists to catch.
    assert metadata_path.read_bytes() == before


@needs_true_false
def test_compatibility_apply_does_not_refuse_a_moved_checkout(tmp_path):
    """The one test that prevents a fleet outage.

    A recorded path that no longer exists means the project moved, not that
    it collided. Refusing here would mean every rename or relocation of a
    repository registers once and then refuses itself forever after — on
    every one of the fleet's live shell entries.
    """

    policy_root = _policy_root(tmp_path)
    old_root = tmp_path / "old-location"
    new_root = tmp_path / "new-location"
    _manifest(old_root)
    kwargs = _apply_kwargs(tmp_path, policy_root)

    compatibility_apply(old_root, **kwargs)

    # The checkout moved: the old directory is gone before the new one ever
    # registers under the same project name.
    shutil.rmtree(old_root)
    _manifest(new_root)

    compatibility_apply(new_root, **kwargs)  # must not raise

    metadata = json.loads(
        (kwargs["state"] / "projects" / "fixture" / "metadata.json").read_text()
    )
    assert metadata["path"] == str(new_root)


@needs_true_false
def test_compatibility_apply_does_not_refuse_the_same_checkout_re_entering(tmp_path):
    policy_root = _policy_root(tmp_path)
    project_root = tmp_path / "project"
    _manifest(project_root)
    kwargs = _apply_kwargs(tmp_path, policy_root)

    compatibility_apply(project_root, **kwargs)
    compatibility_apply(project_root, **kwargs)  # ordinary shell re-entry

    metadata = json.loads(
        (kwargs["state"] / "projects" / "fixture" / "metadata.json").read_text()
    )
    assert metadata["path"] == str(project_root)


@needs_true_false
def test_compatibility_apply_does_not_refuse_a_first_registration(tmp_path):
    policy_root = _policy_root(tmp_path)
    project_root = tmp_path / "project"
    _manifest(project_root)
    kwargs = _apply_kwargs(tmp_path, policy_root)

    compatibility_apply(project_root, **kwargs)  # no prior entry; must not raise

    assert (kwargs["state"] / "projects" / "fixture" / "metadata.json").exists()


@needs_true_false
def test_compatibility_apply_refusal_is_a_reconcile_error_not_a_crash(tmp_path):
    """Shell entry is not broken: the refusal is one caught exception type.

    `devman project apply` (the only caller, invoked by the devenv guard)
    catches exactly `ReconcileError` — a `ProjectionError` subclass — around
    this call and turns it into a clean stderr line and exit code 1. Nothing
    about the refusal is an uncaught exception, a `SystemExit`, or an
    `os._exit`: it is a plain, catchable return path out of a function that
    writes a registry entry, same as every other refusal in this module.
    """

    policy_root = _policy_root(tmp_path)
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _manifest(first_root)
    _manifest(second_root)
    kwargs = _apply_kwargs(tmp_path, policy_root)

    compatibility_apply(first_root, **kwargs)

    try:
        compatibility_apply(second_root, **kwargs)
    except ReconcileError:
        pass
    else:
        pytest.fail("expected the duplicate-registration refusal to fire")
