#!/usr/bin/env python3
"""Redo of 009 P3-3: what fraction of watcher fires cannot change a file?

Method: every line of ~/.local/share/devman/watch/fired.jsonl.
A fire is "wasted" if its path is excluded from this repository's formatter,
i.e. matches the local trigger layer's ignore list.
"""
import json, os, collections
from pathlib import PurePath
LOG = os.path.expanduser("~/.local/share/devman/watch/fired.jsonl")
REPO = "/home/andrew/Documents/Projects/devman"
IGNORE = [".scratch/**"]

fires = []
for line in open(LOG):
    line = line.strip()
    if line:
        fires.append(json.loads(line))
print(f"fires recorded: {len(fires)}")
print("span:", fires[0]["at"], "->", fires[-1]["at"])
print()

wasted = []
useful = []
for f in fires:
    p = f.get("path", "")
    rel = os.path.relpath(p, f.get("project_path") or REPO)
    if any(PurePath(rel).full_match(g) for g in IGNORE):
        wasted.append((f["at"], rel))
    else:
        useful.append((f["at"], rel))

print(f"fires on .scratch/** (excluded from Ruff, cannot change a file): {len(wasted)}")
print(f"fires on formattable paths:                                      {len(useful)}")
print(f"wasted fraction: {len(wasted)/len(fires):.1%}")
print()
print("=== wasted fires by day ===")
c = collections.Counter(a[:10] for a, _ in wasted)
for d in sorted(c): print(" ", d, c[d])
print()
print("=== top wasted paths ===")
for rel, n in collections.Counter(r for _, r in wasted).most_common(10):
    print(f"  {n:4}  {rel}")
print()
print("=== all fires by day ===")
c = collections.Counter(f["at"][:10] for f in fires)
for d in sorted(c): print(" ", d, c[d])
print()
print("=== fires by project/workflow ===")
print(collections.Counter((f.get("project"), f.get("workflow")) for f in fires).most_common())
