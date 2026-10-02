#!/usr/bin/env python3
"""Prototype: the failing-capable verify for ~/.config/devman.

Three independent assertions, all read-only, all over the tracked declaration set:
  A1  every declared central target exists on disk
  A2  every declared central target is committed on trunk (not lane-only)
  A3  no tracked path is also matched by the repository's own ignore rules
"""
import os, re, subprocess, sys, time
from pathlib import Path

CENTRAL = Path(os.environ.get("DEVMAN_OVERLAY", str(Path.home() / ".config/devman")))
HOME = str(Path.home())

def git(*args):
    return subprocess.run(["git", "-C", str(CENTRAL), *args],
                          capture_output=True, text=True).stdout

def trunk():
    t = (CENTRAL / "gitman.toml").read_text()
    m = re.search(r'trunk\s*=\s*"([^"]+)"', t)
    return m.group(1) if m else "main"

def targets():
    """(project, link_rel, absolute target) for every tracked links.yaml."""
    out = []
    for f in sorted(CENTRAL.glob("projects/*/links.yaml")):
        project = f.parent.name
        vars_ = {}
        cur = None
        section = None
        for line in f.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if not line.startswith((" ", "\t")):
                section = line.split(":", 1)[0].strip()
                continue
            indent = len(line) - len(line.lstrip())
            body = line.strip()
            if section == "vars" and ":" in body:
                k, v = body.split(":", 1)
                vars_[k.strip()] = v.strip()
            elif section == "links":
                if indent == 2 and body.endswith(":"):
                    cur = body[:-1].strip()
                elif cur and body.startswith("target:"):
                    out.append((project, cur, body.split(":", 1)[1].strip()))
        resolved = []
        for project, rel, raw in [t for t in out if t[0] == project]:
            pass
    # second pass: resolve
    final = []
    for f in sorted(CENTRAL.glob("projects/*/links.yaml")):
        project = f.parent.name
        vars_, section, cur = {}, None, None
        for line in f.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if not line.startswith((" ", "\t")):
                section = line.split(":", 1)[0].strip(); continue
            indent = len(line) - len(line.lstrip()); body = line.strip()
            if section == "vars" and ":" in body:
                k, v = body.split(":", 1); vars_[k.strip()] = v.strip()
            elif section == "links":
                if indent == 2 and body.endswith(":"):
                    cur = body[:-1].strip()
                elif cur and body.startswith("target:"):
                    raw = body.split(":", 1)[1].strip()
                    val = raw
                    for _ in range(5):
                        val = val.replace("${env.HOME}", HOME).replace("${repo.name}", project)
                        val = re.sub(r"\$\{vars\.(\w+)\}", lambda m: vars_.get(m.group(1), m.group(0)), val)
                    final.append((project, cur, val.rstrip("/")))
    return final

def main():
    t0 = time.time()
    tr = trunk()
    decls = targets()
    central_str = str(CENTRAL)
    findings = []

    # A1 — declared target exists
    a1 = [(p, r, t) for p, r, t in decls if not os.path.lexists(t)]

    # A2 — declared central target is on trunk
    tracked = set(git("ls-tree", "-r", "--name-only", tr).split("\n"))
    a2 = []
    for p, r, t in decls:
        if not t.startswith(central_str + "/"):
            continue                      # external target: not this repo's to hold
        rel = t[len(central_str) + 1:]
        if os.path.isdir(t):
            if not any(x.startswith(rel + "/") or x == rel for x in tracked):
                a2.append((p, r, rel))
        elif rel not in tracked:
            a2.append((p, r, rel))

    # A3 — tracked but also ignored
    a3 = [x for x in git("ls-files", "-i", "-c", "--exclude-standard").split("\n") if x]

    for p, r, t in a1:
        findings.append(f"declared target missing: {p}:{r} -> {t}")
    for p, r, rel in a2:
        findings.append(f"declared target not on {tr} (lane-only, leaves disk on switch): {p}:{r} -> {rel}")
    for x in a3:
        findings.append(f"tracked but ignored: {x}")

    print(f"central verify — {len(decls)} declared links, {len(set(p for p,_,_ in decls))} projects")
    print(f"  A1 target missing      : {len(a1)}")
    print(f"  A2 target not on trunk : {len(a2)}")
    print(f"  A3 tracked-and-ignored : {len(a3)}")
    for f in findings[:40]:
        print("  !!", f)
    if len(findings) > 40:
        print(f"  … {len(findings)-40} more")
    print(f"elapsed {time.time()-t0:.2f}s")
    return 1 if findings else 0

sys.exit(main())
