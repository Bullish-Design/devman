import os
import subprocess
import sys
from pathlib import Path

from devman import __version__

SRC = Path(__file__).resolve().parent.parent / "src"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "devman", *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(SRC)},
    )


def test_version_prints_the_version() -> None:
    result = run("--version")
    assert result.returncode == 0
    assert result.stdout.strip() == f"devman {__version__}"
    assert __version__ == "0.9.0"


def test_unknown_command_exits_2() -> None:
    result = run("no-such-command")
    assert result.returncode == 2
