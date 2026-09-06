#!/usr/bin/env python3
"""Spike A: does a regenerated devman.nix defeat devenv's eval cache?"""
import subprocess, time, pathlib, sys

GEN = pathlib.Path("gen/devman.nix")

def regen(n, salt):
    lines = ["{ ... }:", "{", "  scripts = {"]
    for i in range(n):
        lines.append(f'    dm-asset-{i:02d}.exec = "echo asset {i:02d} {salt}";')
    lines += ["  };", "}"]
    GEN.write_text("\n".join(lines) + "\n")

def timed(label):
    t0 = time.monotonic()
    p = subprocess.run(["devenv", "shell", "--", "true"],
                       capture_output=True, text=True)
    dt = time.monotonic() - t0
    print(f"{label:<38} {dt:7.2f}s  rc={p.returncode}", flush=True)
    return dt

regen(20, "v1")
timed("1. cold (first eval)")
timed("2. warm, no change")
timed("3. warm, no change")
regen(20, "v1")                      # byte-identical rewrite, new mtime
timed("4. rewrite identical bytes")
regen(20, "v2")                      # same shape, changed content
timed("5. regen 20, content changed")
timed("6. warm after regen")
regen(21, "v3")                      # new script added
timed("7. regen 21, script added")
timed("8. warm after regen")
