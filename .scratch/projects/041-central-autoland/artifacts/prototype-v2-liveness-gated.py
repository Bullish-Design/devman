#!/usr/bin/env python3
"""Prototype v2 — the same three assertions, scoped to LIVE repositories."""
import json, os, re, subprocess, sys, time
from pathlib import Path

CENTRAL = Path.home() / ".config/devman"
FLEET   = Path.home() / "Documents/Projects"
HOME    = str(Path.home())

def git(*a):
    return subprocess.run(["git", "-C", str(CENTRAL), *a], capture_output=True, text=True).stdout

def trunk():
    m = re.search(r'trunk\s*=\s*"([^"]+)"', (CENTRAL / "gitman.toml").read_text())
    return m.group(1) if m else "main"

def live(project):
    """A project is live when its repository directory exists."""
    return (FLEET / project).is_dir()

def from_links_yaml():
    out = []
    for f in sorted(CENTRAL.glob("projects/*/links.yaml")):
        p = f.parent.name
        vars_, section, cur = {}, None, None
        for line in f.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#"): continue
            if not line.startswith((" ", "\t")):
                section = line.split(":", 1)[0].strip(); continue
            ind, body = len(line) - len(line.lstrip()), line.strip()
            if section == "vars" and ":" in body:
                k, v = body.split(":", 1); vars_[k.strip()] = v.strip()
            elif section == "links":
                if ind == 2 and body.endswith(":"): cur = body[:-1].strip()
                elif cur and body.startswith("target:"):
                    val = body.split(":", 1)[1].strip()
                    for _ in range(5):
                        val = val.replace("${env.HOME}", HOME).replace("${repo.name}", p)
                        val = re.sub(r"\$\{vars\.(\w+)\}", lambda m: vars_.get(m.group(1), m.group(0)), val)
                    out.append((p, cur, val.rstrip("/"), "links.yaml"))
    return out

def from_ledger():
    s = CENTRAL / ".devman-link-state.json"
    if not s.is_file(): return []
    d = json.load(s.open())
    return [(k.split(":", 1)[0], k.split(":", 1)[1], v["canonical"].rstrip("/"), "ledger")
            for k, v in d.items()]

def main():
    t0 = time.time(); tr = trunk(); cs = str(CENTRAL)
    decls = from_links_yaml() + from_ledger()
    seen, uniq = set(), []
    for p, r, t, src in decls:
        if (p, r, t) in seen: continue
        seen.add((p, r, t)); uniq.append((p, r, t, src))
    livedecls = [d for d in uniq if live(d[0])]
    dead = sorted({d[0] for d in uniq if not live(d[0])})

    a1 = [d for d in livedecls if not os.path.lexists(d[2])]
    tracked = set(git("ls-tree", "-r", "--name-only", tr).split("\n"))
    a2 = []
    for p, r, t, src in livedecls:
        if not t.startswith(cs + "/"): continue
        rel = t[len(cs) + 1:]
        if os.path.isdir(t):
            if not any(x == rel or x.startswith(rel + "/") for x in tracked): a2.append((p, r, rel, src))
        elif rel not in tracked: a2.append((p, r, rel, src))
    a3 = [x for x in git("ls-files", "-i", "-c", "--exclude-standard").split("\n") if x]

    print(f"declarations: {len(uniq)} unique  ({len(livedecls)} live, {len(uniq)-len(livedecls)} for absent repos)")
    print(f"dead projects skipped ({len(dead)}): {', '.join(dead)}")
    print(f"\nA1  declared target missing from disk : {len(a1)}")
    for p, r, t, src in a1: print(f"      !! {p}:{r} -> {t}   [{src}]")
    print(f"\nA2  declared target not on {tr}        : {len(a2)}")
    for p, r, rel, src in a2: print(f"      !! {p}:{r} -> {rel}   [{src}]")
    print(f"\nA3  tracked and also ignored          : {len(a3)}")
    for x in a3[:10]: print(f"      !! {x}")
    print(f"\nelapsed {time.time()-t0:.2f}s")
    return 1 if (a1 or a2 or a3) else 0

sys.exit(main())
