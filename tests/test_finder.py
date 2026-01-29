# tests/test_finder.py
"""Tests for DevmanFinder domain service."""
from pathlib import Path

from devman.domain.finder import DevmanFinder
from devman.domain.models import ProjectRoot


def test_finds_devman_from_root(tmp_path: Path) -> None:
    devman_dir = tmp_path / ".devman"
    devman_dir.mkdir()

    finder = DevmanFinder()
    result = finder.find(start_path=tmp_path)

    assert result.is_ok()
    assert result.unwrap().path == devman_dir


def test_finds_devman_from_nested_dir(tmp_path: Path) -> None:
    devman_dir = tmp_path / ".devman"
    devman_dir.mkdir()
    nested = tmp_path / "nested" / "deeper"
    nested.mkdir(parents=True)

    finder = DevmanFinder()
    result = finder.find(start_path=nested)

    assert result.is_ok()
    assert result.unwrap().path == devman_dir


def test_returns_error_when_not_found(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()

    finder = DevmanFinder()
    result = finder.find(start_path=nested)

    assert result.is_err()


def test_respects_projects_root_boundary(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    project = projects_root / "project"
    project.mkdir()
    (tmp_path / ".devman").mkdir()

    finder = DevmanFinder(projects_root=ProjectRoot(path=projects_root))
    result = finder.find(start_path=project)

    assert result.is_err()


def test_finds_within_projects_root(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    project = projects_root / "project"
    project.mkdir()
    devman_dir = projects_root / ".devman"
    devman_dir.mkdir()

    finder = DevmanFinder(projects_root=ProjectRoot(path=projects_root))
    result = finder.find(start_path=project)

    assert result.is_ok()
    assert result.unwrap().path == devman_dir
