#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Parse a file-type template TOML config and print key=value pairs for shell consumption."""

import sys
import tomllib

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: parse-config.py <config.toml>", file=sys.stderr)
        sys.exit(1)

    config_path = sys.argv[1]
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)

    section = cfg["file_type_template"]
    print(f"file_type={section['file_type']}")
    print(f"description={section.get('description', '')}")

if __name__ == "__main__":
    main()
