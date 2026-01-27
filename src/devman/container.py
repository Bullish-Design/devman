# src/devman/container.py
"""Container operations for testing."""

from __future__ import annotations

import subprocess
from pathlib import Path


def create_container(name: str, devman_dir: Path) -> None:
    """Create and start a nixos-container."""
    subprocess.run(
        [
            "nixos-container",
            "create",
            name,
            "--config-file",
            str(devman_dir / "devenv.nix"),
        ],
        check=True,
    )
    subprocess.run(["nixos-container", "start", name], check=True)


def run_container_tests(name: str, devman_dir: Path) -> None:
    """Run tests inside the container."""
    subprocess.run(
        [
            "nixos-container",
            "run",
            name,
            "--",
            "bash",
            "-c",
            "cd /mnt/project/.devman && just test",
        ],
        check=True,
    )


def cleanup_container(name: str) -> None:
    """Stop and destroy a container."""
    subprocess.run(["nixos-container", "stop", name], check=False)
    subprocess.run(["nixos-container", "destroy", name], check=True)


def list_devman_containers() -> list[str]:
    """List all devman-* containers."""
    result = subprocess.run(
        ["nixos-container", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith("devman-")
    ]
