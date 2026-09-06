"""No imports at all: read the CLI's own --help. Works on any CLI, Typer or not."""
import re, subprocess, sys, os

ENV = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}

def run(argv):
    p = subprocess.run(argv, capture_output=True, text=True, env=ENV)
    return p.stdout + p.stderr

def strip(t):                      # drop rich box-drawing, keep content
    return "\n".join(re.sub(r"^[│┃|]\s?|\s*[│┃|]\s*$", "", ln).rstrip()
                     for ln in t.splitlines())

def parse(bin_, path=()):
    t = strip(run([bin_, *path, "--help"]))
    usage = re.search(r"Usage:\s*\S+((?:\s+\S+)*)", t)
    usage = usage.group(1).strip() if usage else ""
    # a group's help lists subcommands under a Commands section
    sec = re.search(r"^\s*Commands:?\s*$\n(.*?)(?:\n\s*\n|\Z)", t, re.M | re.S)
    subs = []
    if sec:
        subs = [m.group(1) for m in
                re.finditer(r"^\s{1,4}([a-z][a-z0-9-]*)\s", sec.group(1), re.M)]
        subs = [s for s in subs if s != "help"]
    pos = re.findall(r"[\{\[]([a-z][a-z0-9_-]*)[\}\]]", usage)
    opts = sorted(set(re.findall(r"(--[a-z][a-z0-9-]+)", t)))
    return {"kind": "group" if subs else "leaf", "children": sorted(subs),
            "positional": pos, "options": opts, "usage": usage}

def tree(bin_, path=(), out=None, depth=0):
    out = out if out is not None else {}
    node = parse(bin_, path)
    if path:
        out[" ".join(path)] = node
    if node["kind"] == "group" and depth < 3:
        for c in node["children"]:
            tree(bin_, (*path, c), out, depth + 1)
    return out

for b in sys.argv[1:]:
    t = tree(b)
    groups = [k for k, v in t.items() if v["kind"] == "group"]
    print(f"{b:<10} nodes={len(t):<3} groups={groups}")
    for probe in ["layer", "version", "remote", "remote add", "update"]:
        if probe in t:
            v = t[probe]
            print(f"    {probe:<12} {v['kind']:<6} pos={v['positional']} opts={v['options'][:4]}")
