#!/usr/bin/env python3
"""Part B: what the HUMAN types, and what named intents recur.

Method: atuin history.db, read-only. `author` separates the human ('andrew')
from agents ('claude-code', 'pi', 'codex'). `intent` names procedures a skill ran.
"""
import sqlite3, os, collections, datetime, json
DB = os.path.expanduser("~/.local/share/atuin/history.db")
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
REGDIR = os.path.expanduser("~/.local/share/devman/projects")
PATHS = {}
for p in os.listdir(REGDIR):
    m = os.path.join(REGDIR, p, "metadata.json")
    if os.path.exists(m):
        PATHS[json.load(open(m))["path"]] = p
def proj_of(cwd):
    best = None
    for path, name in PATHS.items():
        if cwd == path or cwd.startswith(path + "/"):
            if best is None or len(path) > len(best):
                best = path; bn = name
    return bn if best else None

print("=" * 70)
print("A. WHAT THE HUMAN TYPES  (author='andrew')")
print("=" * 70)
rows = list(c.execute("select timestamp, command, cwd, exit from history "
                      "where author='andrew' and deleted_at is null order by timestamp"))
print(f"human commands on record: {len(rows)}")
first = datetime.datetime.fromtimestamp(rows[0][0]/1e9)
last  = datetime.datetime.fromtimestamp(rows[-1][0]/1e9)
print(f"span: {first:%Y-%m-%d} -> {last:%Y-%m-%d}  ({(last-first).days} days)")
print()
def head(cmd, n=2):
    t = cmd.strip().split()
    if not t: return ""
    if t[0] in ("sudo","time","nohup"): t = t[1:]
    if not t: return ""
    return " ".join(t[:n]) if len(t) > 1 else t[0]
hc = collections.Counter(head(cmd) for _, cmd, _, _ in rows)
print("--- top 40 things the human typed ---")
for h, n in hc.most_common(40):
    print(f"{n:5}  {h}")
print()
print("--- full commands the human repeated 4+ times ---")
fc = collections.Counter(cmd.strip() for _, cmd, _, _ in rows)
for cmd, n in fc.most_common(40):
    if n >= 4:
        print(f"{n:5}  {cmd[:110]}")
print()
print("--- which repos the human worked in ---")
pc = collections.Counter(proj_of(cwd) for _, _, cwd, _ in rows)
for p, n in pc.most_common(15):
    print(f"{n:5}  {p}")

print()
print("=" * 70)
print("B. NAMED INTENTS  (a procedure something already runs repeatedly)")
print("=" * 70)
rows2 = list(c.execute("select intent, command, cwd, author, count(*) from history "
                       "where intent is not null and deleted_at is null "
                       "group by intent order by count(*) desc"))
print(f"{'intent':38} {'n':>4}  author       example command")
for intent, cmd, cwd, author, n in rows2:
    print(f"{intent[:37]:38} {n:4}  {author:12} {cmd.strip()[:60]}")
