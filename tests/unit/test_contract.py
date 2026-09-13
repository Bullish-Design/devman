"""Tests for the portable project and plane contract records."""

from __future__ import annotations

import pytest

from devman.contract import (
    CONTRACT_SCHEMA,
    ContractError,
    PlaneGeneration,
    ProjectionRecord,
    ProjectManifest,
    digest_blobs,
    digest_bytes,
)

pytestmark = pytest.mark.unit


def manifest() -> ProjectManifest:
    return ProjectManifest(
        schema=CONTRACT_SCHEMA,
        project="demo",
        groups=("base", "python"),
        policy="stable",
    )


def generation() -> PlaneGeneration:
    digest = digest_bytes(b"input")
    return PlaneGeneration(
        generation=7,
        devman_runtime="v0.6.0",
        renderer_digest=digest,
        policy_digest=digest,
        dagu_digest=digest,
        toolchain_digest=digest,
    )


def test_manifest_round_trips_toml_and_has_a_path_free_digest():
    original = manifest()

    parsed = ProjectManifest.from_text(original.to_toml())

    assert parsed == original
    assert parsed.digest.startswith("sha256:")
    assert "/" not in original.to_toml()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project", "../outside"),
        ("groups", ["base", "../outside"]),
        ("policy", "/tmp/policy"),
    ],
)
def test_manifest_rejects_path_values(field, value):
    raw = manifest().to_mapping()
    raw[field] = value

    with pytest.raises(ContractError, match=f"field '{field}'"):
        ProjectManifest.from_mapping(raw)


def test_manifest_rejects_unknown_fields_and_unsupported_schema():
    raw = manifest().to_mapping()
    raw["absolute_path"] = "/tmp/demo"
    with pytest.raises(ContractError, match="unknown field"):
        ProjectManifest.from_mapping(raw)

    raw = manifest().to_mapping()
    raw["schema"] = CONTRACT_SCHEMA + 1
    with pytest.raises(ContractError, match="unsupported"):
        ProjectManifest.from_mapping(raw)


def test_manifest_rejects_duplicate_groups():
    raw = manifest().to_mapping()
    raw["groups"] = ["base", "base"]

    with pytest.raises(ContractError, match="duplicate"):
        ProjectManifest.from_mapping(raw)


def test_named_blob_digest_is_order_independent_and_path_safe():
    first = digest_blobs({"b.yaml": b"b", "a.yaml": b"a"})
    second = digest_blobs({"a.yaml": b"a", "b.yaml": b"b"})

    assert first == second
    with pytest.raises(ContractError, match="relative path"):
        digest_blobs({"../a.yaml": b"a"})


def test_generation_digest_changes_when_a_renderer_changes():
    old = generation()
    new = PlaneGeneration(
        **{
            **old.to_mapping(),
            "renderer_digest": digest_bytes(b"new renderer"),
        }
    )

    assert old.digest != new.digest
    assert old.renderer_digest != new.renderer_digest


def test_projection_record_matches_all_relevant_generation_inputs():
    plane = generation()
    project = manifest()
    source = digest_bytes(b"workflow")
    record = ProjectionRecord(
        project=project.project,
        manifest_digest=project.digest,
        policy_digest=plane.policy_digest,
        plane_generation=plane.generation,
        renderer_digest=plane.renderer_digest,
        source_digest=source,
    )

    assert record.matches(plane, project, source_digest=source)
    assert not record.matches(
        PlaneGeneration(
            **{
                **plane.to_mapping(),
                "renderer_digest": digest_bytes(b"new renderer"),
            }
        ),
        project,
        source_digest=source,
    )
    assert not record.matches(plane, project, source_digest=digest_bytes(b"new"))


def test_projection_record_round_trips_without_a_machine_path():
    plane = generation()
    project = manifest()
    record = ProjectionRecord(
        project=project.project,
        manifest_digest=project.digest,
        policy_digest=plane.policy_digest,
        plane_generation=plane.generation,
        renderer_digest=plane.renderer_digest,
        source_digest=digest_bytes(b"workflow"),
        overlay_digest=digest_bytes(b"overlay"),
    )

    parsed = ProjectionRecord.from_mapping(record.to_mapping())

    assert parsed == record
    assert "/" not in str(record.to_mapping())
