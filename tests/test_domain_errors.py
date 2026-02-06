# tests/test_domain_errors.py
from pathlib import Path

from devman.domain.errors import PathNotFoundError, PathNotDirectoryError


def test_path_not_found_error_message():
    error = PathNotFoundError(message="", path=Path("/tmp/missing"))
    assert "/tmp/missing" in str(error)


def test_path_not_directory_error_message():
    error = PathNotDirectoryError(message="", path=Path("/tmp/file.txt"))
    assert "/tmp/file.txt" in str(error)
    assert "not a directory" in str(error)
