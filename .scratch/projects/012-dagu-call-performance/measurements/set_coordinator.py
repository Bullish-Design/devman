#!/usr/bin/env python3
"""Set `coordinator.enabled` in a Dagu config file. Used by coordinator_cost.sh.

The key is absent from the plane's own `config.yaml`, so it takes the documented
default of true. Writing it explicitly is what makes the two measurements a
comparison rather than a guess about what the default is.

Usage: set_coordinator.py CONFIG true|false
"""
from __future__ import annotations

import sys


def main() -> int:
    path, want = sys.argv[1], sys.argv[2]
    out: list[str] = []
    inside = False
    for line in open(path).read().splitlines():
        if line.startswith("coordinator:"):
            out += [line, f"  enabled: {want}"]
            inside = True
            continue
        if inside and line.startswith("  enabled:"):
            continue
        if inside and line and not line.startswith(" "):
            inside = False
        out.append(line)
    open(path, "w").write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
