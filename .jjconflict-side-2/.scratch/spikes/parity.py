"""Prove the click-free walker matches the click route, fact for fact."""
import json, subprocess, sys
TC = "/home/andrew/.local/share/repoman/venv/bin/python"
SH = "/home/andrew/Documents/Projects/shellij/.devenv/state/venv/bin/python"
CASES = [(TC, "copyroom.cli"), (TC, "gitman.cli"), (TC, "docman.cli"),
         (TC, "repoman.cli"), (SH, "testee.cli")]
def run(py, script, mod):
    p = subprocess.run([py, script, mod, "app"], capture_output=True, text=True)
    return json.loads(p.stdout)
bad = 0
for py, mod in CASES:
    a = run(py, "walker.py", mod)
    b = run(py, "walker_click.py", mod)
    if not (a["ok"] and b["ok"]):
        print(f"{mod:<14} SKIP (ok={a['ok']}/{b['ok']})"); continue
    ka, kb = set(a["commands"]), set(b["commands"])
    diffs = []
    if ka != kb:
        diffs.append(f"names {sorted(ka ^ kb)}")
    for k in sorted(ka & kb):
        na, nb = a["commands"][k], b["commands"][k]
        if na["kind"] != nb["kind"]:
            diffs.append(f"{k}: kind {na['kind']}!={nb['kind']}")
        elif na["kind"] == "leaf":
            if na["positional"] != nb["positional"]:
                diffs.append(f"{k}: pos {na['positional']}!={nb['positional']}")
            if set(na["options"]) != set(nb["options"]):
                diffs.append(f"{k}: opts {sorted(set(na['options'])^set(nb['options']))}")
        elif na["children"] != nb["children"]:
            diffs.append(f"{k}: children {na['children']}!={nb['children']}")
    bad += len(diffs)
    print(f"{mod:<14} {len(ka):>3} nodes  {'MATCH' if not diffs else 'DIFF'}")
    for d in diffs[:6]:
        print(f"     - {d}")
print(f"\ntotal discrepancies: {bad}")
