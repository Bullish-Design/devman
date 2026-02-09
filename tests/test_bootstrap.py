from datetime import datetime
from pathlib import Path
import subprocess
import tomli

from devman.bootstrap import bootstrap_file_type, get_current_devman_version


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


def test_bootstrap_file_type_writes_timezone_aware_created_at(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("devman.bootstrap.Path.home", lambda: tmp_path)

    template_path = (
        tmp_path / ".devman-store" / "devman" / ".devman" / ".templates" / "file-type"
    )
    template_path.mkdir(parents=True)

    def fake_run_checked_subprocess(command, **kwargs):
        target_path = tmp_path / ".devman-store" / "pyproject.toml"
        config_path = target_path / ".devman" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("[devman]\nversion = \"0.1.0\"\n", encoding="utf-8")
        return subprocess.CompletedProcess(list(command), 0, "", "")

    monkeypatch.setattr("devman.bootstrap.run_checked_subprocess", fake_run_checked_subprocess)

    bootstrap_file_type("pyproject.toml", template_version="v1.2.3")

    config = tomli.loads(
        (
            tmp_path
            / ".devman-store"
            / "pyproject.toml"
            / ".devman"
            / "config.toml"
        ).read_text(encoding="utf-8")
    )
    created_at = config["template"]["created_at"]
    assert datetime.fromisoformat(created_at).tzinfo is not None


def test_bootstrap_file_type_prefers_dedicated_seed_template(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("devman.bootstrap.Path.home", lambda: tmp_path)

    dedicated_template = (
        tmp_path / ".devman-store" / "devman" / ".devman" / ".templates" / "devenv.nix"
    )
    dedicated_template.mkdir(parents=True)

    calls: list[list[str]] = []

    def fake_run_checked_subprocess(command, **kwargs):
        calls.append(list(command))
        target_path = tmp_path / ".devman-store" / "devenv.nix"
        config_path = target_path / ".devman" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("[devman]\nversion = \"0.1.0\"\n", encoding="utf-8")
        return subprocess.CompletedProcess(list(command), 0, "", "")

    monkeypatch.setattr("devman.bootstrap.run_checked_subprocess", fake_run_checked_subprocess)

    bootstrap_file_type("devenv.nix", template_version="v1.2.3")

    assert calls
    assert calls[0][-2] == str(dedicated_template)
    assert calls[0][-1] == str(tmp_path / ".devman-store")
