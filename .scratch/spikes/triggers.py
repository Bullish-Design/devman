"""Spike D: whole-repo trigger-collision detection.

repoman/docs/SKILLS.md lists this as an open question, and must: no single
component sees every skill at once. Anything that compiles the whole set can.
"""
import pathlib, re, collections, json

def keywords(p):
    t = p.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    if not m:
        return None, []
    fm = m.group(1)
    name = (re.search(r"^name:\s*(.*)$", fm, re.M) or [None, p.parent.name])[1].strip()
    kw = re.search(r"^auto_trigger:\s*\n\s*keywords:\s*(\[.*?\])", fm, re.M | re.S)
    if not kw:
        return name, []
    try:
        return name, [k.lower().strip() for k in json.loads(kw.group(1))]
    except Exception:
        return name, re.findall(r'"([^"]+)"', kw.group(1))

REPOS = ["testee", "gitman", "docman", "copyroom", "my-ai", "shellij", "repoman", "fleetman"]
grand = 0
for repo in REPOS:
    root = pathlib.Path(f"/home/andrew/Documents/Projects/{repo}/.agents/skills")
    if not root.exists():
        continue
    idx = collections.defaultdict(set)
    skills = sorted(root.glob("*/SKILL.md"))
    n_kw = 0
    for s in skills:
        name, kws = keywords(s)
        n_kw += len(kws)
        for k in kws:
            idx[k].add(name)
    collisions = {k: v for k, v in idx.items() if len(v) > 1}
    grand += len(collisions)
    status = f"{len(collisions)} COLLISIONS" if collisions else "clean"
    print(f"{repo:<10} skills={len(skills):<3} keywords={n_kw:<4} {status}")
    for k, v in sorted(collisions.items()):
        print(f"    ! {k!r}  ->  {sorted(v)}")
print(f"\nTOTAL colliding keywords across repos: {grand}")
