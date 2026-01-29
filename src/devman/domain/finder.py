# src/devman/domain/finder.py
from __future__ import annotations

from pathlib import Path

from result import Err, Result

from devman.domain.errors import DevmanNotFoundError
from devman.domain.models import DevmanDirectory, ProjectRoot


class DevmanFinder:
    """Domain service for locating .devman configuration directories."""

    def __init__(self, projects_root: ProjectRoot | None = None) -> None:
        """
        Initialize finder with optional boundary.

        Args:
            projects_root: Stop searching when reaching this directory
        """
        self.projects_root = projects_root

    def find(
        self, start_path: Path | None = None
    ) -> Result[DevmanDirectory, DevmanNotFoundError]:
        """
        Locate nearest .devman directory by traversing up from start_path.

        Args:
            start_path: Starting point for search (defaults to cwd)

        Returns:
            Ok(DevmanDirectory) if found, Err(DevmanNotFoundError) otherwise
        """
        current = (start_path or Path.cwd()).resolve()
        search_root = current

        projects_root_path = self.projects_root.path if self.projects_root else None

        while True:
            candidate = current / ".devman"

            if candidate.is_dir():
                return DevmanDirectory.create(candidate)

            # Check boundary condition
            if projects_root_path is not None and current == projects_root_path:
                return Err(
                    DevmanNotFoundError(
                        message=f"No .devman found within projects root: {projects_root_path}",
                        search_root=search_root,
                    )
                )

            # Check filesystem root
            if current.parent == current:
                return Err(
                    DevmanNotFoundError(
                        message=f"No .devman found in tree: {search_root}",
                        search_root=search_root,
                    )
                )

            current = current.parent
