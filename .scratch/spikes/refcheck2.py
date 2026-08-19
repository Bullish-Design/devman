"""Spike C v2: stale-reference check with parameter-aware facts.

Measures BOTH error rates:
  - false positives on real skills (v1 scored 6/6 false)
  - true positives on an injected synthetic skill with known-bad references
"""
import json, re, subprocess, sys, pathlib, tempfile

TC = str(pathlib.Path.home() / ".local/share/repoman/venv/bin/python")
SH = "/home/andrew/Documents/Projects/shellij/.devenv/state/venv/bin/python"

# Prefixes a skill may put in front of the tool name. Found by spike:
# testee's skill writes every command as `devenv shell testee verify`.
PREFIX = r"(?:\$\s*)?(?:devenv\s+shell\s+(?:--\s+)?|devenv\s+run\s+|uv\s+run\s+|uvx\s+)?"

def facts(python, module):
    p = subprocess.run([python, "walker3.py", module, "app"],
                       capture_output=True, text=True)
    return json.loads(p.stdout)

def refs(text, tool):
    """Yield (command_path, flag, raw) candidates from prose."""
    spans = re.findall(r"`([^`\n]+)`", text)
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.S):
        spans.extend(block.splitlines())
    out = []
    pat = re.compile(rf"^{PREFIX}{re.escape(tool)}\s+([a-z][a-z0-9-]*)"
                     rf"(?:\s+([a-z][a-z0-9-]*))?(.*)$")
    for s in spans:
        m = pat.match(s.strip())
        if m:
            out.append((m.group(1), m.group(2), m.group(3) or "", s.strip()))
    return out

def check(tool, cmds, text):
    """Return (n_refs, findings). A finding is (severity, message)."""
    found, n = [], 0
    for one, two, tail, raw in refs(text, tool):
        n += 1
        node = cmds.get(one)
        if node is None:
            found.append(("stale-command", f"`{tool} {one}` is not a command"))
            continue
        # Only treat word2 as a subcommand when word1 is a GROUP.
        # For a leaf, word2 is a positional VALUE (e.g. `copyroom layer add`).
        if two and node["kind"] == "group" and two not in node["children"]:
            found.append(("stale-subcommand",
                          f"`{tool} {one} {two}` — `{one}` has no `{two}`"))
        # Strict tier: unknown long options on a leaf.
        if node["kind"] == "leaf":
            for opt in re.findall(r"(--[a-z][a-z0-9-]*)", tail):
                if opt not in node["options"]:
                    found.append(("unknown-option",
                                  f"`{tool} {one} {opt}` — no such option"))
    return n, found

CASES = [
    ("copyroom", TC, "copyroom.cli",
     "/home/andrew/Documents/Projects/copyroom/src/copyroom/agent/assets/skills"),
    ("gitman", TC, "gitman.cli", "/home/andrew/Documents/Projects/gitman/.agents/skills"),
    ("docman", TC, "docman.cli", "/home/andrew/Documents/Projects/docman/.agents/skills"),
    ("testee", SH, "testee.cli", "/home/andrew/Documents/Projects/testee/.agents/skills"),
]

FACTS = {}
tot_refs = 0
by_sev = {}
print("=== PART 1: real skills (every finding here is a candidate FALSE POSITIVE) ===")
for tool, py, mod, sd in CASES:
    f = facts(py, mod)
    if not f["ok"]:
        print(f"{tool}: introspection FAILED {f['error']}"); continue
    FACTS[tool] = f["commands"]
    root = pathlib.Path(sd)
    files = sorted(root.glob(f"{tool}*/SKILL.md")) if root.exists() else []
    for fp in files:
        n, findings = check(tool, f["commands"], fp.read_text())
        tot_refs += n
        for sev, msg in findings:
            by_sev.setdefault(sev, []).append(f"{fp.parent.name}: {msg}")
        print(f"  {tool:<9} {fp.parent.name:<26} refs={n:<3} findings={len(findings)}")
for sev, msgs in sorted(by_sev.items()):
    print(f"\n  [{sev}] x{len(msgs)}")
    for m in msgs[:8]:
        print(f"    - {m}")
print(f"\n  TOTAL: {tot_refs} references, {sum(len(v) for v in by_sev.values())} findings")

print("\n=== PART 2: injected synthetic skill (findings here are TRUE POSITIVES) ===")
SYN = """
# Synthetic
- `copyroom frobnicate` renamed away
- `copyroom update --nonexistent-flag`
- `gitman remote nope`
- `devenv shell testee verify --mode quick`
- `copyroom layer add my-template`
- `gitman version bump minor`
- `devenv shell testee rerun-failures --last`
"""
expect = {"copyroom": 2, "gitman": 1, "testee": 0}
for tool in ["copyroom", "gitman", "testee"]:
    n, findings = check(tool, FACTS[tool], SYN)
    got = len(findings)
    ok = "PASS" if got == expect[tool] else "MISMATCH"
    print(f"  {tool:<9} refs={n} findings={got} expected={expect[tool]}  {ok}")
    for sev, msg in findings:
        print(f"    - [{sev}] {msg}")
