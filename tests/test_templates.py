# tests/test_templates.py
from pathlib import Path
import pytest

from devman.domain.templates import TemplateReference, TemplateValidator


def test_template_reference_from_file_path(tmp_path: Path):
    template_dir = tmp_path / "template"
    template_dir.mkdir()

    ref = TemplateReference.from_string(str(template_dir))

    assert ref.source_type == "file"
    assert ref.location == str(template_dir)


def test_template_reference_from_git_https():
    ref = TemplateReference.from_string("https://github.com/user/repo.git")

    assert ref.source_type == "git"
    assert ref.location == "https://github.com/user/repo.git"


def test_template_reference_from_git_ssh():
    ref = TemplateReference.from_string("git@github.com:user/repo.git")

    assert ref.source_type == "git"


def test_template_reference_from_gh_shorthand():
    ref = TemplateReference.from_string("gh:user/repo")

    assert ref.source_type == "git"
    assert ref.location == "gh:user/repo"


def test_template_reference_invalid_file_path():
    with pytest.raises(ValueError, match="does not exist"):
        TemplateReference(source_type="file", location="/nonexistent/path")


def test_template_reference_resolve_file_path(tmp_path: Path):
    template_dir = tmp_path / "template"
    template_dir.mkdir()

    ref = TemplateReference(source_type="file", location=str(template_dir))
    resolved = ref.resolve_path()

    assert resolved.exists()
    assert resolved.is_dir()


def test_template_validator_valid_structure():
    fixture = Path("tests/fixtures")

    result = TemplateValidator.validate(fixture)

    assert result.is_valid


def test_template_validator_missing_copier_yaml(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = TemplateValidator.validate(empty_dir)

    assert not result.is_valid
    assert any("copier.yaml" in e.message for e in result.errors)


def test_template_validator_malformed_yaml(tmp_path: Path):
    template_dir = tmp_path / "template"
    template_dir.mkdir()

    copier_file = template_dir / "copier.yaml"
    copier_file.write_text("""
invalid yaml content [[[
    """)

    result = TemplateValidator.validate(template_dir)

    assert not result.is_valid


# --- Result-based API tests ---


def test_template_reference_create_returns_result(tmp_path: Path):
    template_dir = tmp_path / "template"
    template_dir.mkdir()

    result = TemplateReference.create("file", str(template_dir))

    assert result.is_ok()
    assert result.unwrap().source_type == "file"


def test_template_reference_create_handles_missing_path():
    result = TemplateReference.create("file", "/nonexistent/path")

    assert result.is_err()
    from devman.domain.errors import PathNotFoundError

    assert isinstance(result.unwrap_err(), PathNotFoundError)


def test_template_reference_create_handles_invalid_git_url():
    result = TemplateReference.create("git", "not-a-url")

    assert result.is_err()
    from devman.domain.errors import InvalidGitUrlError

    assert isinstance(result.unwrap_err(), InvalidGitUrlError)


def test_template_validator_returns_structured_result():
    fixture = Path("tests/fixtures")
    result = TemplateValidator.validate(fixture)

    from devman.domain.models import ValidationResult

    assert isinstance(result, ValidationResult)
    assert result.is_valid


def test_template_validator_validate_reference():
    fixture = Path("tests/fixtures")
    ref = TemplateReference(source_type="file", location=str(fixture))

    result = TemplateValidator.validate_reference(ref)

    assert result.is_valid
