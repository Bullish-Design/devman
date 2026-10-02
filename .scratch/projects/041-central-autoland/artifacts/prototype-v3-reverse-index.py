#!/usr/bin/env python3
"""Prototype v3 — the reverse index: the VIEW side is the authority.

Walk the fleet, find every symlink that points into the central overlay, then
assert of each target: (1) it exists, (2) it is committed on trunk.
No registry, no ledger, no declaration file is trusted.
"""
import os, re, subprocess, sys, time
from pathlib import Path

CENTRAL = (Path.home() / ".config/devman").resolve()
FLEET   = Path.home() / "Documents/Projects"
SKIP    = {".git", ".jj", ".devenv", ".direnv", ".venv", "node_modules",
           "__pycache__", ".worktrees", ".archive", ".runs"}

def git(*a):
    return subprocess.run(["git", "-C", str(CENTRAL), *a], capture_output=True, text=True).stdout

def trunk():
    m = re.search(r'trunk\s*=\s*"([^"]+)"', (CENTRAL / "gitman.toml").read_text())
    return m.group(1) if m else "main"

def views():
    """Every fleet symlink whose raw target lands inside the central overlay."""
    out = []
    for repo in sorted(p for p in FLEET.iterdir() if p.is_dir() and p.name not in SKIP):
        for cur, dirs, files in os.walk(repo, followlinks=False):
            depth = len(Path(cur).relative_to(repo).parts)
            dirs[:] = [] if depth >= 2 else [d for d in dirs if d not in SKIP]
            for name in list(dirs) + files:
                p = Path(cur) / name
                if not p.is_symlink():
                    continue
                raw = os.readlink(p)
                t = Path(raw) if os.path.isabs(raw) else (Path(cur) / raw)
                try:
                    t = Path(os.path.normpath(t))
                except ValueError:
                    continue
                if str(t) == str(CENTRAL) or str(t).startswith(str(CENTRAL) + "/"):
                    out.append((repo.name, str(p.relative_to(repo)), str(t)))
            # .git/info/exclude lives below the walk's pruned .git
        g = repo / ".git"
        ex = (g / "info" / "exclude") if g.is_dir() else None
        if ex and ex.is_symlink():
            raw = os.readlink(ex)
            t = Path(os.path.normpath(raw if os.path.isabs(raw) else ex.parent / raw))
            if str(t).startswith(str(CENTRAL) + "/"):
                out.append((repo.name, ".git/info/exclude", str(t)))
    return out

def main():
    t0 = time.time(); tr = trunk(); cs = str(CENTRAL)
    v = views()
    repos = sorted({r for r, _, _ in v})
    tracked = set(git("ls-tree", "-r", "--name-only", tr).split("\n"))

    missing, lane_only = [], []
    for repo, rel, t in v:
        if not os.path.exists(t):
            missing.append((repo, rel, t)); continue
        trel = t[len(cs) + 1:]
        if os.path.isdir(t):
            on_trunk = any(x == trel or x.startswith(trel + "/") for x in tracked)
        else:
            on_trunk = trel in tracked
        if not on_trunk:
            lane_only.append((repo, rel, trel))

    print(f"reverse index — {len(v)} live views into the overlay, across {len(repos)} repositories")
    print(f"\nV1  dangling view (target absent)      : {len(missing)}")
    for r, rel, t in missing: print(f"      !! {r}/{rel} -> {t}")
    print(f"\nV2  target exists but is NOT on {tr}   : {len(lane_only)}")
    for r, rel, t in lane_only: print(f"      !! {r}/{rel} -> {t}")
    print(f"\nelapsed {time.time()-t0:.2f}s")
    return 1 if (missing or lane_only) else 0

sys.exit(main())
