# tests/test_domain_models.py
from devman.domain.models import ValidationResult


def test_validation_result_tracks_multiple_issues():
    vr = ValidationResult()
    vr.add_error("Missing type field", location="project_name")
    vr.add_warning("Deprecated syntax", location="use_docker")

    assert not vr.is_valid
    assert len(vr.errors) == 1
    assert len(vr.warnings) == 1
    assert vr.errors[0].location == "project_name"


def test_validation_result_is_valid_with_no_errors():
    vr = ValidationResult()
    vr.add_warning("Minor issue")

    assert vr.is_valid
    assert len(vr.errors) == 0
    assert len(vr.warnings) == 1
