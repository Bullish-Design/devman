from pathlib import Path

from devman.bootstrap import get_current_devman_version


def test_get_current_devman_version_returns_unversioned_when_store_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("devman.bootstrap.Path.home", lambda: tmp_path)

    assert get_current_devman_version() == "unversioned"


def test_get_current_devman_version_returns_unversioned_when_git_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    devman_path = tmp_path / ".devman-store" / "devman"
    devman_path.mkdir(parents=True)
    monkeypatch.setattr("devman.bootstrap.Path.home", lambda: tmp_path)

    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr("devman.bootstrap.subprocess.run", raise_file_not_found)

    assert get_current_devman_version() == "unversioned"
