from pathlib import Path

from devman.config import DevmanConfig


def test_default_config(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("DEVMAN_PROJECTS_ROOT", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    config = DevmanConfig()

    assert config.projects_root is None


def test_loads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("DEVMAN_PROJECTS_ROOT", "/tmp/projects")

    config = DevmanConfig()

    assert config.projects_root == Path("/tmp/projects")


def test_converts_string_to_path(monkeypatch, tmp_path) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv("DEVMAN_PROJECTS_ROOT", str(projects_root))

    config = DevmanConfig()

    assert isinstance(config.projects_root, Path)
