from pathlib import Path

from devman.domain.errors import PathNotDirectoryError, PathNotFoundError


def test_path_not_found_error_args_and_message():
    error = PathNotFoundError(path=Path("/tmp/missing"))
    assert error.args == ("Path does not exist: /tmp/missing",)
    assert str(error) == "Path does not exist: /tmp/missing"


def test_path_not_directory_error_args_and_message():
    error = PathNotDirectoryError(path=Path("/tmp/file.txt"))
    assert error.args == ("Path is not a directory: /tmp/file.txt",)
    assert str(error) == "Path is not a directory: /tmp/file.txt"
