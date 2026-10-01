"""Lane 4 of the M14 devman cutover: the Phase A converter.

Three claims this file keeps true. First, every known view converts to the
Linkman schema's nested `target:` mapping (not a bare string — the
refactoring guide's inline example is wrong about this; `linkman.models.
config.LinkConfig` requires the mapping, confirmed against the real schema
before writing this converter). Second, the converter never writes the Nix
file it reads. Third, an unrecognised or inverted declaration is refused,
never guessed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tools.cutover.compare import Disagreement, compare_project
from tools.cutover.convert import (
    ConversionError,
    build_links_yaml,
    central_projects,
    convert_all,
    convert_declarations,
)

pytestmark = pytest.mark.unit


def write_central(
    overlay: Path, project: str, body: str = "{ config, ... }: { devman.link = { }; }\n"
) -> Path:
    path = overlay / "projects" / project / "devenv.local.nix"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


# ---------------------------------------------------------------------------
# convert_declarations


def test_central_view_targets_vars_central_with_repo_name_substituted(tmp_path: Path):
    overlay = tmp_path / "overlay"
    (overlay / "projects" / "demo" / "agents").mkdir(parents=True)

    links = convert_declarations(
        {".agents": {"canonical": "central", "path": "projects/demo/agents"}},
        overlay=overlay,
        project="demo",
    )

    assert links[".agents"] == {
        "target": "${vars.central}/projects/${repo.name}/agents/"
    }


def test_directory_views_get_a_trailing_slash_file_views_do_not(tmp_path: Path):
    overlay = tmp_path / "overlay"
    (overlay / "projects" / "demo").mkdir(parents=True)

    links = convert_declarations(
        {
            ".agents": {"canonical": "central", "path": "projects/demo/agents"},
            ".envrc": {"canonical": "central", "path": "common/envrc"},
        },
        overlay=overlay,
        project="demo",
    )

    assert links[".agents"]["target"].endswith("/")
    assert not links[".envrc"]["target"].endswith("/")


def test_external_view_targets_env_home_with_repo_name_substituted(tmp_path: Path):
    overlay = tmp_path / "overlay"
    (overlay / "projects" / "demo").mkdir(parents=True)

    links = convert_declarations(
        {".loci": {"canonical": "external", "path": "~/Notes/1_Projects/demo"}},
        overlay=overlay,
        project="demo",
    )

    assert links[".loci"] == {"target": "${env.HOME}/Notes/1_Projects/${repo.name}/"}


def test_bootstrap_declaration_is_synthesized_when_absent(tmp_path: Path):
    overlay = tmp_path / "overlay"
    (overlay / "projects" / "demo").mkdir(parents=True)

    links = convert_declarations({}, overlay=overlay, project="demo")

    assert links["devenv.local.nix"] == {
        "target": "${vars.central}/projects/${repo.name}/devenv.local.nix"
    }


def test_canonical_repo_is_refused(tmp_path: Path):
    overlay = tmp_path / "overlay"
    (overlay / "projects" / "demo").mkdir(parents=True)

    with pytest.raises(ConversionError, match='canonical="repo"'):
        convert_declarations(
            {".notes": {"canonical": "repo", "path": "notes"}},
            overlay=overlay,
            project="demo",
        )


def test_an_unrecognised_view_is_refused_not_guessed(tmp_path: Path):
    overlay = tmp_path / "overlay"
    (overlay / "projects" / "demo").mkdir(parents=True)

    with pytest.raises(ConversionError, match="unrecognised view"):
        convert_declarations(
            {".mystery": {"canonical": "central", "path": "projects/demo/mystery"}},
            overlay=overlay,
            project="demo",
        )


def test_a_project_literally_named_like_a_path_segment_is_not_mismatched(
    tmp_path: Path,
):
    """Whole-segment substitution: a project named `central` must not have an
    unrelated `central` segment elsewhere in the path rewritten by accident.
    """
    overlay = tmp_path / "overlay"
    (overlay / "projects" / "central").mkdir(parents=True)

    links = convert_declarations(
        {".envrc": {"canonical": "central", "path": "common/envrc"}},
        overlay=overlay,
        project="central",
    )

    assert links[".envrc"] == {"target": "${vars.central}/common/envrc"}


# ---------------------------------------------------------------------------
# build_links_yaml / the schema shape


def test_links_yaml_uses_the_nested_target_mapping_not_a_bare_string():
    document = build_links_yaml({".envrc": {"target": "${vars.central}/common/envrc"}})

    assert document["version"] == 1
    assert document["vars"] == {"central": "${env.HOME}/.config/devman"}
    assert document["links"][".envrc"] == {"target": "${vars.central}/common/envrc"}
    assert isinstance(document["links"][".envrc"], dict)


# ---------------------------------------------------------------------------
# convert_all — the preservation gate


def test_convert_all_writes_one_links_yaml_per_central_project(tmp_path: Path):
    overlay = tmp_path / "overlay"
    write_central(overlay, "alpha")
    write_central(overlay, "beta")

    converted = convert_all(overlay)

    assert sorted(converted) == ["alpha", "beta"]
    for project in converted:
        out = overlay / "projects" / project / "links.yaml"
        assert out.is_file()
        document = yaml.safe_load(out.read_text())
        assert "devenv.local.nix" in document["links"]


def test_dry_run_writes_nothing(tmp_path: Path):
    overlay = tmp_path / "overlay"
    write_central(overlay, "alpha")

    convert_all(overlay, dry_run=True)

    assert not (overlay / "projects" / "alpha" / "links.yaml").exists()


def test_nix_files_are_byte_identical_before_and_after(tmp_path: Path):
    overlay = tmp_path / "overlay"
    nix_file = write_central(overlay, "alpha")
    before = nix_file.read_bytes()

    convert_all(overlay)

    assert nix_file.read_bytes() == before


def test_a_moved_nix_file_fails_the_gate(tmp_path: Path, monkeypatch):
    overlay = tmp_path / "overlay"
    nix_file = write_central(overlay, "alpha")

    def mutating_evaluator(path: Path, project: str) -> dict[str, object]:
        path.write_text("{ } # mutated\n")
        return {}

    monkeypatch.setattr(
        "tools.cutover.convert.evaluate_central_file", mutating_evaluator
    )

    with pytest.raises(ConversionError, match="changed a Nix file"):
        convert_all(overlay)
    assert nix_file.read_text() == "{ } # mutated\n"


def test_central_projects_skips_directories_without_a_nix_file(tmp_path: Path):
    overlay = tmp_path / "overlay"
    write_central(overlay, "alpha")
    (overlay / "projects" / "not-a-project").mkdir(parents=True)

    found = central_projects(overlay)

    assert [name for name, _path in found] == ["alpha"]


# ---------------------------------------------------------------------------
# compare.py — the Phase A dry-run gate


def test_compare_project_reports_nothing_when_both_sides_agree(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        "tools.cutover.compare.devman_link_targets",
        lambda root, overlay, project: {".envrc": "/central/common/envrc"},
    )
    monkeypatch.setattr(
        "tools.cutover.compare.linkman_targets",
        lambda linkman_bin, root, overlay, project: {".envrc": "/central/common/envrc"},
    )

    disagreements = compare_project(Path("linkman"), tmp_path, tmp_path, "demo")

    assert disagreements == []


def test_compare_project_reports_a_value_mismatch(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "tools.cutover.compare.devman_link_targets",
        lambda root, overlay, project: {".envrc": "/old/target"},
    )
    monkeypatch.setattr(
        "tools.cutover.compare.linkman_targets",
        lambda linkman_bin, root, overlay, project: {".envrc": "/new/target"},
    )

    disagreements = compare_project(Path("linkman"), tmp_path, tmp_path, "demo")

    assert disagreements == [
        Disagreement("demo", ".envrc", "/old/target", "/new/target")
    ]


def test_compare_project_reports_a_key_present_on_only_one_side(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        "tools.cutover.compare.devman_link_targets",
        lambda root, overlay, project: {".envrc": "/x", ".agents": "/y"},
    )
    monkeypatch.setattr(
        "tools.cutover.compare.linkman_targets",
        lambda linkman_bin, root, overlay, project: {".envrc": "/x"},
    )

    disagreements = compare_project(Path("linkman"), tmp_path, tmp_path, "demo")

    assert disagreements == [Disagreement("demo", ".agents", "/y", None)]
