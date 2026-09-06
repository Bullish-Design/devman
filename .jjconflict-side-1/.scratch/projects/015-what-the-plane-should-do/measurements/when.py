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

# check/test runs by day, excluding devman
byday = collections.Counter()
per_proj_days = collections.defaultdict(list)
for d in rows:
    p, w = split2(d["name"])
    if w not in ("check","test"): continue
    day = (d.get("startedAt") or "")[:10]
    byday[(w,day)] += 1
    per_proj_days[p].append((day, w, "devman" if p=="devman" else ""))

print("=== check/test runs per day (whole plane) ===")
for (w,day), c in sorted(byday.items(), key=lambda x:(x[0][1],x[0][0])):
    print(f"{day}  {w:6} {c:4}")

print()
print("=== repos with >2 check+test runs ===")
for p, lst in sorted(per_proj_days.items(), key=lambda x:-len(x[1])):
    if len(lst) > 2:
        days = collections.Counter(d for d,_,_ in lst)
        print(f"{p:24} {len(lst):4}  days={dict(days)}")

print()
print("=== repos whose ONLY check/test runs are on a single day ===")
one = [p for p,lst in per_proj_days.items() if len({d for d,_,_ in lst})==1]
print(len(one), "repos:", sorted(one))
