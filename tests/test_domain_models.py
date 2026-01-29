# tests/test_domain_models.py
from pathlib import Path

from devman.domain.errors import PathNotFoundError
from devman.domain.models import DevmanDirectory, ProjectRoot, ValidationResult


def test_project_root_validates_existing_directory(tmp_path: Path):
    result = ProjectRoot.create(tmp_path)
    assert result.is_ok()
    assert result.unwrap().path == tmp_path.resolve()


def test_project_root_rejects_missing_path(tmp_path: Path):
    missing = tmp_path / "nonexistent"
    result = ProjectRoot.create(missing)
    assert result.is_err()
    assert isinstance(result.unwrap_err(), PathNotFoundError)


def test_devman_directory_validates_name(tmp_path: Path):
    devman_dir = tmp_path / ".devman"
    devman_dir.mkdir()

    result = DevmanDirectory.create(devman_dir)
    assert result.is_ok()


def test_devman_directory_rejects_wrong_name(tmp_path: Path):
    wrong_name = tmp_path / ".notdevman"
    wrong_name.mkdir()

    result = DevmanDirectory.create(wrong_name)
    assert result.is_err()


def test_validation_result_tracks_multiple_issues():
    vr = ValidationResult()
    vr.add_error("Missing type field", location="project_name")
    vr.add_warning("Deprecated syntax", location="use_docker")

    assert not vr.is_valid
    assert len(vr.errors) == 1
    assert len(vr.warnings) == 1
    assert vr.errors[0].location == "project_name"
