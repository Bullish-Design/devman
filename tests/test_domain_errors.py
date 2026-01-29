# tests/test_domain_errors.py
from pathlib import Path

from devman.domain.errors import PathNotFoundError, ValidationError


def test_path_not_found_error_message():
    error = PathNotFoundError(message="", path=Path("/tmp/missing"))
    assert "/tmp/missing" in str(error)


def test_validation_error_combines_messages():
    error = ValidationError(
        message="",
        errors=["Missing field 'type'"],
        warnings=["Deprecated syntax"],
    )
    assert "Missing field" in str(error)
    assert "Deprecated" in str(error)
