#!/usr/bin/env python3
"""Part B: what does this developer run by hand, and where?

Method: atuin history.db, read-only. 56,064 commands.
Bucket by first two tokens; attribute to a registered project by cwd prefix.
"""
import sqlite3, os, collections, datetime, re, sys

DB = os.path.expanduser("~/.local/share/atuin/history.db")
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

REGDIR = os.path.expanduser("~/.local/share/devman/projects")
import json
PATHS = {}
for p in os.listdir(REGDIR):
    m = os.path.join(REGDIR, p, "metadata.json")
    if os.path.exists(m):
        PATHS[json.load(open(m))["path"]] = p

def proj_of(cwd):
    best = None
    for path, name in PATHS.items():
        if cwd == path or cwd.startswith(path + "/"):
            if best is None or len(path) > len(best[0]):
                best = (path, name)
    return best[1] if best else None

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 90
cut = int((datetime.datetime.now() - datetime.timedelta(days=DAYS)).timestamp() * 1e9)

rows = list(c.execute(
    "select timestamp, duration, exit, command, cwd from history "
    "where timestamp > ? and deleted_at is null", (cut,)))
print(f"commands in last {DAYS} days: {len(rows)}")

def head(cmd):
    t = cmd.strip().split()
    if not t: return ""
    if t[0] in ("sudo","time","nohup"): t = t[1:]
    if not t: return ""
    # keep two tokens when the first is a multiplexer
    if len(t) > 1 and t[0] in ("git","nix","devenv","devman","gh","uv","cargo","npm","just","systemctl","docker","dagu","nixos-rebuild","home-manager","gitman","docman","repoman","copyroom","siteman","foreman","atuin","claude"):
        return t[0] + " " + t[1]
    return t[0]

verbs = collections.Counter()
verb_proj = collections.defaultdict(collections.Counter)
proj_tot = collections.Counter()
for ts, dur, ex, cmd, cwd in rows:
    h = head(cmd)
    if not h: continue
    verbs[h] += 1
    p = proj_of(cwd)
    if p:
        verb_proj[h][p] += 1
        proj_tot[p] += 1

print()
print("=== top 45 command heads (whole machine) ===")
for h, n in verbs.most_common(45):
    nrep = len(verb_proj[h])
    inreg = sum(verb_proj[h].values())
    print(f"{n:6}  {h:28} in-registered-repos={inreg:5}  distinct-repos={nrep}")

print()
print("=== commands run inside registered repos, by repo ===")
for p, n in proj_tot.most_common(20):
    print(f"{n:6}  {p}")
