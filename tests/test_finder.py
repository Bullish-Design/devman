from pathlib import Path

from devman.cli import DevmanFinder


def test_finds_devman_from_root(tmp_path: Path) -> None:
    devman_dir = tmp_path / ".devman"
    devman_dir.mkdir()

    finder = DevmanFinder()

    assert finder.find(start_path=tmp_path) == devman_dir


def test_finds_devman_from_nested_dir(tmp_path: Path) -> None:
    devman_dir = tmp_path / ".devman"
    devman_dir.mkdir()
    nested = tmp_path / "nested" / "deeper"
    nested.mkdir(parents=True)

    finder = DevmanFinder()

    assert finder.find(start_path=nested) == devman_dir


def test_returns_none_when_not_found(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()

    finder = DevmanFinder()

    assert finder.find(start_path=nested) is None


def test_respects_projects_root_boundary(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    project = projects_root / "project"
    project.mkdir()
    (tmp_path / ".devman").mkdir()

    finder = DevmanFinder(projects_root=projects_root)

    assert finder.find(start_path=project) is None


def test_finds_within_projects_root(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    project = projects_root / "project"
    project.mkdir()
    devman_dir = projects_root / ".devman"
    devman_dir.mkdir()

    finder = DevmanFinder(projects_root=projects_root)

    assert finder.find(start_path=project) == devman_dir
