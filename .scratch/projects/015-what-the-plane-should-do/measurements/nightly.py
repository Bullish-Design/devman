#!/usr/bin/env python3
import json, os, collections, re
HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "runs.json")))
PROJ = sorted(os.listdir(os.path.expanduser("~/.local/share/devman/projects")), key=len, reverse=True)
def split2(n):
    if "." in n:
        p,_,w = n.partition("."); return p,w
    m = re.match(r"^(.*)_(.*)-[0-9a-f]{4}$", n)
    if m: return m.group(1), m.group(2)
    for cand in PROJ:
        for slug in {cand, cand.replace(".","-"), cand.replace("_","-")}:
            if n == slug: return cand, ""
            if n.startswith(slug+"-"): return cand, n[len(slug)+1:]
    return "?"+n, "?"

REG = set(os.listdir(os.path.expanduser("~/.local/share/devman/projects")))
night = collections.defaultdict(set)
for d in rows:
    p, w = split2(d["name"])
    if w not in ("maintain",) or d.get("triggerType") != 1: continue
    day = (d.get("startedAt") or "")[:10]
    night[day].add(p)

print("=== scheduled maintain: which repos fired each night ===")
for day in sorted(night):
    got = night[day]
    missing = REG - got
    extra = got - REG
    print(f"{day}  fired={len(got):3}  missing={len(missing):2} {sorted(missing) if len(missing)<8 else '(many)'}  extra={sorted(extra)}")
