# tests/test_domain_finder.py
from pathlib import Path

from devman.domain.errors import DevmanNotFoundError
from devman.domain.finder import DevmanFinder
from devman.domain.models import ProjectRoot


def test_finder_locates_devman_in_current_directory(tmp_path: Path):
    devman_dir = tmp_path / ".devman"
    devman_dir.mkdir()

    finder = DevmanFinder()
    result = finder.find(start_path=tmp_path)

    assert result.is_ok()
    assert result.unwrap().path == devman_dir


def test_finder_traverses_upward(tmp_path: Path):
    devman_dir = tmp_path / ".devman"
    devman_dir.mkdir()
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)

    finder = DevmanFinder()
    result = finder.find(start_path=nested)

    assert result.is_ok()
    assert result.unwrap().path == devman_dir


def test_finder_returns_error_when_not_found(tmp_path: Path):
    finder = DevmanFinder()
    result = finder.find(start_path=tmp_path)

    assert result.is_err()
    assert isinstance(result.unwrap_err(), DevmanNotFoundError)


def test_finder_respects_projects_root_boundary(tmp_path: Path):
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    project = projects_root / "myproject"
    project.mkdir()

    # .devman exists outside projects root
    (tmp_path / ".devman").mkdir()

    finder = DevmanFinder(projects_root=ProjectRoot(path=projects_root))
    result = finder.find(start_path=project)

    assert result.is_err()


def test_finder_finds_within_projects_root(tmp_path: Path):
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    devman_dir = projects_root / ".devman"
    devman_dir.mkdir()
    project = projects_root / "myproject"
    project.mkdir()

    finder = DevmanFinder(projects_root=ProjectRoot(path=projects_root))
    result = finder.find(start_path=project)

    assert result.is_ok()
    assert result.unwrap().path == devman_dir


def test_finder_handles_symlinks(tmp_path: Path):
    """Ensure finder resolves symlinks correctly."""
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    devman_dir = real_dir / ".devman"
    devman_dir.mkdir()

    link_dir = tmp_path / "link"
    link_dir.symlink_to(real_dir)

    finder = DevmanFinder()
    result = finder.find(start_path=link_dir)

    assert result.is_ok()
    # Should resolve to actual .devman location
    assert result.unwrap().path.resolve() == devman_dir.resolve()


def test_finder_handles_circular_symlinks(tmp_path: Path):
    """Ensure finder doesn't infinite loop on circular symlinks."""
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    dir_b = tmp_path / "b"
    dir_b.mkdir()

    # Create circular symlinks
    (dir_a / "link_b").symlink_to(dir_b)
    (dir_b / "link_a").symlink_to(dir_a)

    finder = DevmanFinder()
    result = finder.find(start_path=dir_a / "link_b")

    # Should eventually hit filesystem root and return error
    assert result.is_err()
