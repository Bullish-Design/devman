#!/usr/bin/env python3
import json, os, collections, datetime, re
HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "runs.json")))
STATUS = {2:"failed",3:"cancelled",4:"success",6:"partial"}
TRIGGER = {1:"scheduled",2:"manual",3:"api",4:"trigger/child"}

def split(n):
    # codec: project-workflow ; pre-codec: project_workflow-hash or project.workflow
    if "." in n:
        p, _, w = n.partition(".")
        return p, w, "pre-codec-dot"
    m = re.match(r"^(.*)_(.*)-[0-9a-f]{4}$", n)
    if m:
        return m.group(1), m.group(2), "pre-codec-us"
    return None, None, "dash"

# We cannot split "a-b" unambiguously (project names contain dashes).
# Use the registry's project list to disambiguate: longest matching prefix.
PROJ = sorted(os.listdir(os.path.expanduser("~/.local/share/devman/projects")), key=len, reverse=True)
def split2(n):
    p, w, kind = split(n)
    if p is not None:
        return p, w, kind
    for cand in PROJ:
        slug = cand.replace(".", "-").replace("_", "-")
        if n == slug or n.startswith(slug + "-"):
            return cand, n[len(slug)+1:], "dash"
    return "?" + n, "?", "unmatched"

per_wf = collections.Counter()
per_proj = collections.Counter()
per_wf_trig = collections.defaultdict(collections.Counter)
per_proj_wf = collections.defaultdict(collections.Counter)
fails = collections.Counter()
unmatched = collections.Counter()
for d in rows:
    p, w, kind = split2(d["name"])
    if kind == "unmatched":
        unmatched[d["name"]] += 1
    per_wf[w] += 1
    per_proj[p] += 1
    per_wf_trig[w][TRIGGER.get(d.get("triggerType"), "?")] += 1
    per_proj_wf[p][w] += 1
    if d.get("status") != 4:
        fails[(p, w, STATUS.get(d.get("status")))] += 1

print("=== per workflow (all 1186 attempts) ===")
for w, c in per_wf.most_common():
    print(f"{w:28} {c:5}   {dict(per_wf_trig[w])}")
print()
print("=== unmatched names ===", dict(unmatched))
print()
print("=== per project, sorted ===")
for p, c in per_proj.most_common():
    print(f"{p:28} {c:5}   {dict(per_proj_wf[p])}")
print()
print("=== non-success ===")
for k, c in fails.most_common():
    print(k, c)
