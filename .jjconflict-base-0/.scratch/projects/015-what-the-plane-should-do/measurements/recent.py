#!/usr/bin/env python3
import json, os, collections, re, datetime
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

day_wf = collections.defaultdict(collections.Counter)
for d in rows:
    p, w = split2(d["name"])
    day = (d.get("startedAt") or "")[:10]
    day_wf[day][w] += 1

print("=== runs per day, per workflow ===")
for day in sorted(day_wf):
    c = day_wf[day]
    tot = sum(c.values())
    top = ", ".join(f"{w}={n}" for w,n in c.most_common(6))
    print(f"{day}  total={tot:4}   {top}")

# Last 10 days
CUT = "2026-08-27"
print()
print(f"=== since {CUT} ===")
recent = collections.Counter()
recent_proj = collections.Counter()
for d in rows:
    day = (d.get("startedAt") or "")[:10]
    if day < CUT: continue
    p, w = split2(d["name"])
    recent[w] += 1
    recent_proj[p] += 1
print("by workflow:", recent.most_common())
print()
print("distinct projects with any run:", len(recent_proj))
print("projects with a NON-maintain run:")
nm = collections.Counter()
for d in rows:
    day = (d.get("startedAt") or "")[:10]
    if day < CUT: continue
    p, w = split2(d["name"])
    if w != "maintain": nm[p] += 1
print(" ", dict(nm))
