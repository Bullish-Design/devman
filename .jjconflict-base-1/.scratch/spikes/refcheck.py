"""Spike C: can we detect stale CLI references in skill prose without noise?"""
import json, re, subprocess, sys, pathlib

def facts(python, module, attr="app"):
    p = subprocess.run([python, "walker.py", module, attr], capture_output=True, text=True)
    return json.loads(p.stdout)

# Candidate extraction: `tool sub` or `tool sub subsub` inside backticks or fenced blocks.
def references(text, tool):
    hits = {}
    # inline code spans and fenced blocks both matter
    spans = re.findall(r"`([^`\n]+)`", text)
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.S):
        spans.extend(block.splitlines())
    for s in spans:
        s = s.strip().lstrip("$").strip()
        m = re.match(rf"^{re.escape(tool)}\s+([a-z][a-z0-9-]*)(?:\s+([a-z][a-z0-9-]*))?", s)
        if not m:
            continue
        one, two = m.group(1), m.group(2)
        hits.setdefault(one, set()).add(s)
        if two:
            hits.setdefault(f"{one} {two}", set()).add(s)
    return hits

TOOLCHAIN = str(pathlib.Path.home() / ".local/share/repoman/venv/bin/python")
CASES = [
    ("copyroom", TOOLCHAIN, "copyroom.cli",
     "/home/andrew/Documents/Projects/copyroom/src/copyroom/agent/assets/skills"),
    ("gitman", TOOLCHAIN, "gitman.cli",
     "/home/andrew/Documents/Projects/gitman/.agents/skills"),
    ("testee", "/home/andrew/Documents/Projects/shellij/.devenv/state/venv/bin/python",
     "testee.cli", "/home/andrew/Documents/Projects/testee/.agents/skills"),
]

total_refs = total_stale = 0
for tool, py, mod, skills_dir in CASES:
    f = facts(py, mod)
    if not f.get("ok"):
        print(f"## {tool}: INTROSPECTION FAILED — {f.get('error')}\n"); continue
    known = set(f["commands"])
    root = pathlib.Path(skills_dir)
    files = sorted(root.glob("*/SKILL.md")) if root.exists() else []
    print(f"## {tool} — {len(known)} real commands, {len(files)} skill files")
    if not files:
        print(f"   (no skills at {skills_dir})\n"); continue
    for fp in files:
        refs = references(fp.read_text(), tool)
        stale = {r: v for r, v in refs.items() if r not in known}
        # a two-word ref whose first word is real is only stale if the pair is unknown
        stale = {r: v for r, v in stale.items()
                 if " " not in r or r.split()[0] in known}
        total_refs += len(refs); total_stale += len(stale)
        flag = "STALE" if stale else "ok"
        print(f"   {fp.parent.name:<28} refs={len(refs):<3} {flag}")
        for r, examples in sorted(stale.items()):
            print(f"      ! `{tool} {r}` not in CLI   e.g. {sorted(examples)[0]!r}")
    print()
print(f"TOTAL: {total_refs} references extracted, {total_stale} flagged stale")
