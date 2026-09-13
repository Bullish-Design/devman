"""Tests for manifest-first project identity and central link validation."""

from __future__ import annotations

from pathlib import Path

import pytest

import devman_link.api
from devman import cli
from devman.identity import (
    IdentityError,
    LinkConfiguration,
    LinkConfigurationError,
    resolve_project_identity,
    validate_link_configuration,
)

pytestmark = pytest.mark.unit


def write_manifest(root: Path, project: str = "demo", **extra: object) -> None:
    manifest = root / ".devman/project.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    fields = {
        "schema": 1,
        "project": project,
        "groups": ["base"],
        "policy": "stable",
        **extra,
    }
    manifest.write_text(
        f"schema = {fields['schema']}\n"
        f"project = {fields['project']!r}\n"
        f'groups = ["base"]\n'
        f"policy = {fields['policy']!r}\n"
    )


def test_manifest_identity_is_used_without_project_argument(tmp_path: Path):
    write_manifest(tmp_path, "manifest-name")

    result = resolve_project_identity(tmp_path)

    assert result.project == "manifest-name"
    assert result.source == "manifest"


def test_matching_explicit_project_succeeds(tmp_path: Path):
    write_manifest(tmp_path, "demo")

    result = resolve_project_identity(tmp_path, "demo")

    assert result.project == "demo"
    assert result.source == "explicit"


def test_mismatching_explicit_project_refuses(tmp_path: Path):
    write_manifest(tmp_path, "manifest-name")

    with pytest.raises(IdentityError) as caught:
        resolve_project_identity(tmp_path, "cli-name")

    message = str(caught.value)
    assert str(tmp_path.resolve()) in message
    assert "manifest identity" in message
    assert "cli-name" in message
    assert "repair:" in message


def test_matching_manifest_and_nix_identities_succeed(tmp_path: Path):
    write_manifest(tmp_path, "demo")
    (tmp_path / "devenv.nix").write_text('{ devman = { project = "demo"; }; }\n')

    result = resolve_project_identity(tmp_path)

    assert result.project == "demo"
    assert result.compatibility == "demo"


def test_mismatching_manifest_and_nix_identities_refuse(tmp_path: Path):
    write_manifest(tmp_path, "manifest-name")
    (tmp_path / "devenv.nix").write_text(
        '{ devman = { project = "compatibility-name"; }; }\n'
    )

    with pytest.raises(IdentityError) as caught:
        resolve_project_identity(tmp_path)

    message = str(caught.value)
    assert "manifest identity" in message
    assert "compatibility identity" in message
    assert "compatibility-name" in message
    assert "repair:" in message


def test_manifest_free_compatibility_fallback_still_works(tmp_path: Path):
    (tmp_path / "devenv.nix").write_text(
        'let\n  projectName = "legacy";\nin\n{ devman = { project = projectName; }; }\n'
    )

    result = resolve_project_identity(tmp_path)

    assert result.project == "legacy"
    assert result.source == "compatibility"


def test_explicit_project_precedes_manifest_free_compatibility_value(tmp_path: Path):
    (tmp_path / "devenv.nix").write_text('{ devman = { project = "legacy"; }; }\n')

    result = resolve_project_identity(tmp_path, "explicit")

    assert result.project == "explicit"
    assert result.source == "explicit"


def test_directory_names_are_never_used_as_identity(tmp_path: Path):
    root = tmp_path / "directory-name"
    root.mkdir()

    with pytest.raises(IdentityError) as caught:
        resolve_project_identity(root)

    message = str(caught.value)
    assert "manifest-free compatibility repository" in message
    assert "repair:" in message


@pytest.mark.parametrize("project", ["", "../outside", "bad/name", "bad@name"])
def test_invalid_manifest_identity_names_field_and_repair(tmp_path: Path, project: str):
    write_manifest(tmp_path, project)

    with pytest.raises(IdentityError) as caught:
        resolve_project_identity(tmp_path)

    message = str(caught.value)
    assert "field 'project'" in message
    assert "repair:" in message


def test_unknown_manifest_field_names_field_and_repair(tmp_path: Path):
    write_manifest(tmp_path)
    manifest = tmp_path / ".devman/project.toml"
    manifest.write_text(manifest.read_text() + 'absolute_path = "/tmp/demo"\n')

    with pytest.raises(IdentityError) as caught:
        resolve_project_identity(tmp_path)

    assert "unknown field" in str(caught.value)
    assert "repair:" in str(caught.value)


def test_unsupported_manifest_schema_names_field_and_repair(tmp_path: Path):
    write_manifest(tmp_path)
    manifest = tmp_path / ".devman/project.toml"
    manifest.write_text(manifest.read_text().replace("schema = 1", "schema = 2"))

    with pytest.raises(IdentityError) as caught:
        resolve_project_identity(tmp_path)

    assert "field 'schema'" in str(caught.value)
    assert "repair:" in str(caught.value)


def test_multiple_compatibility_identities_refuse(tmp_path: Path):
    (tmp_path / "devenv.nix").write_text(
        '{ devman = { project = "one"; }; }\n{ devman = { project = "two"; }; }\n'
    )

    with pytest.raises(IdentityError, match="multiple values"):
        resolve_project_identity(tmp_path)


def test_central_link_configuration_is_validated_without_nix_process(
    tmp_path: Path,
):
    root = tmp_path / "repo"
    overlay = tmp_path / "overlay"
    root.mkdir()
    central = overlay / "projects/demo/devenv.local.nix"
    central.parent.mkdir(parents=True)
    central.write_text("{ config, ... }: { devman.link = { }; }\n")
    projects: list[str] = []

    def evaluate(_path: Path, project: str) -> object:
        projects.append(project)
        return {}

    result = validate_link_configuration(
        root,
        overlay,
        "demo",
        {
            "devenv.local.nix": {
                "canonical": "central",
                "path": "projects/demo/devenv.local.nix",
            }
        },
        evaluator=evaluate,
    )

    assert result.central_file == central
    assert "devenv.local.nix" in result.declarations
    assert projects == ["demo"]


def test_central_link_configuration_refuses_missing_bootstrap(tmp_path: Path):
    with pytest.raises(LinkConfigurationError, match="bootstrap central target"):
        validate_link_configuration(tmp_path, tmp_path / "overlay", "demo", {})


def test_public_link_boundary_uses_manifest_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    write_manifest(tmp_path, "manifest-name")
    overlay = tmp_path / "overlay"
    central = overlay / "projects/manifest-name/devenv.local.nix"
    args = cli.parser().parse_args(
        ["link", "status", "--root", str(tmp_path), "--overlay", str(overlay)]
    )
    seen: dict[str, object] = {}

    def configuration(root, overlay_root, project, declarations=None, **_kwargs):
        seen["project"] = project
        return LinkConfiguration(
            project=project,
            root=Path(root),
            overlay=Path(overlay_root),
            central_file=central,
            declarations={},
        )

    monkeypatch.setattr(devman_link.api, "validate_link_configuration", configuration)

    assert cli._link_command(args, object()) == 0
    assert seen["project"] == "manifest-name"
    assert capsys.readouterr().out.splitlines() == [f"central config {central}"]
