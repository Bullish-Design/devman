#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=7.4.0",
#     "pytest-cov>=4.1.0",
#     "typer>=0.12.0",
#     "rich>=13.0.0",
#     "pydantic>=2.5.0",
# ]
# ///

# scripts/run_tests.py
"""Test runner script for devman library."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Run pytest with coverage and formatting."""
    repo_root = Path(__file__).resolve().parent.parent
    test_dir = repo_root / "tests"
    src_dir = repo_root / "src"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_dir),
        f"--cov={src_dir / 'devman'}",
        "--cov-report=term-missing",
        "--cov-report=html",
        "-v",
        "--tb=short",
    ]

    print("Running tests with coverage...")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n✅ All tests passed!")
        print("📊 Coverage report: htmlcov/index.html")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
