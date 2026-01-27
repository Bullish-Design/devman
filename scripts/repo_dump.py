#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pydantic>=2.0.0",
# ]
# ///

from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

default_patterns = [
    "*.pyc",
    ".ruff_cache*",
    ".envrc",
    "__pycache__",
    ".git",
    ".gitignore",
    "*.log",
    "*.tmp",
    ".devenv*",
    "*.venv*",
    "*.env",
    ".git*",
    "*.lock",
    ".tmuxp*",
    "src/scripts/repo_dump.py",
    "src/archive*",
    ".agents/*",
    ".pytest_cache/*",
    "devenv*",
    "src/examples*",
    "buf.gen*",
    "*.hidden*",
    "*.db",
]


class FileCombinerConfig(BaseModel):
    """Configuration for file combining operation."""

    input_dir: Path
    output_dir: Path
    ignore_patterns: List[str] = Field(default_factory=List[Optional[str]])

    @field_validator("input_dir", "output_dir")
    def validate_paths(cls, v):
        return Path(v)

    @field_validator("input_dir")
    def input_dir_must_exist(cls, v):
        if not v.exists() or not v.is_dir():
            raise ValueError(f"Input directory {v} does not exist or is not a directory")
        return v


class FileCombiner:
    """Combines multiple files into a single output file with headers."""

    def __init__(self, config: FileCombinerConfig):
        self.config = config
        self.repo_name = config.input_dir.name

    def should_ignore_file(self, file_path: Path) -> bool:
        """Check if file matches any ignore pattern."""
        relative_path = file_path.relative_to(self.config.input_dir)

        for pattern in self.config.ignore_patterns:
            if fnmatch.fnmatch(str(relative_path), pattern):
                return True
            if fnmatch.fnmatch(file_path.name, pattern):
                return True

        return False

    def get_files_to_process(self) -> List[Path]:
        """Get all files that should be included in the combined output."""
        files = []

        for file_path in self.config.input_dir.rglob("*"):
            if file_path.is_file() and not self.should_ignore_file(file_path):
                files.append(file_path)

        return sorted(files)

    def create_file_header(self, file_path: Path) -> str:
        """Create a header comment for a file section."""
        relative_path = file_path.relative_to(self.config.input_dir)
        header = f"""
{"=" * 80}
FILE: {relative_path}

{"=" * 80}

"""
        return header

    def combine_files(self, version: Optional[int] = None) -> None:
        """Combine all non-ignored files into a single output file."""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        if version is not None and version > 0:
            output_file = self.config.output_dir / f"{version:02d}_{self.repo_name}_full_llms.txt"
        else:
            output_file = self.config.output_dir / f"{self.repo_name}_full_llms.txt"

        files_to_process = self.get_files_to_process()

        if not files_to_process:
            print("No files found to process.")
            return

        with output_file.open("w", encoding="utf-8") as outfile:
            outfile.write(f"Combined repository contents for: {self.repo_name}\n")
            outfile.write(f"Total files: {len(files_to_process)}\n")
            outfile.write(f"{'=' * 80}\n\n")

            for file_path in files_to_process:
                try:
                    outfile.write(self.create_file_header(file_path))

                    # Try to read file as text
                    with file_path.open("r", encoding="utf-8") as infile:
                        content = infile.read()
                        outfile.write(content)

                    # Ensure there's a newline after each file
                    if not content.endswith("\n"):
                        outfile.write("\n")
                    outfile.write("\n")

                except UnicodeDecodeError:
                    outfile.write(f"[BINARY FILE - SKIPPED]\n\n")
                except Exception as e:
                    outfile.write(f"[ERROR READING FILE: {e}]\n\n")

        print(f"    Combined {len(files_to_process)} files into {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Combine repository files into a single text file for LLM consumption")
    parser.add_argument("input_dir", help="Input directory path")
    parser.add_argument("output_dir", help="Output directory path")
    parser.add_argument("--ver", nargs="?", default=0, help="Version num to include in output file name")
    parser.add_argument("--ignore", nargs="*", default=[], help="Additional ignore patterns (supports wildcards)")

    args = parser.parse_args()

    # print(f"\n\nArguments: {args}\n")
    # print(f"    input: {args.input_dir}")
    # print(f"   output: {args.output_dir}")
    # print(f"   ignore: {args.ignore}\n\n")

    print(f"\nCombining files from {args.input_dir} into {args.output_dir}...")
    ignore_list = default_patterns + args.ignore

    try:
        config = FileCombinerConfig(
            input_dir=Path(args.input_dir),
            output_dir=Path(args.output_dir),
            ignore_patterns=ignore_list,
        )

        combiner = FileCombiner(config)
        combiner.combine_files(int(args.ver))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
