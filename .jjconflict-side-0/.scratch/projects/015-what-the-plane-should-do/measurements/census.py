#!/usr/bin/env python3
"""Run census over Dagu's dag-run status files.

Method: read the LAST line of every status.jsonl under DATA/dag-runs.
Each such file is one attempt; the last line is its final state.
"""
import json, os, sys, collections, datetime

DATA = os.path.expanduser("~/.local/share/dagu/data/dag-runs")

STATUS = {0: "none", 1: "running", 2: "failed", 3: "cancelled", 4: "success",
          5: "queued", 6: "partial"}
TRIGGER = {0: "unknown", 1: "scheduled", 2: "manual", 3: "api", 4: "trigger/child"}

rows = []
for root, dirs, files in os.walk(DATA):
    if "status.jsonl" not in files:
        continue
    p = os.path.join(root, "status.jsonl")
    last = None
    with open(p) as fh:
        for line in fh:
            line = line.strip()
            if line:
                last = line
    if not last:
        continue
    try:
        d = json.loads(last)
    except Exception as e:
        print(f"UNPARSED {p}: {e}", file=sys.stderr)
        continue
    rows.append(d)

print(f"attempts read: {len(rows)}")

# distinct dagRunIds (an attempt is a retry of a run)
runs = {}
for d in rows:
    runs.setdefault(d.get("dagRunId"), []).append(d)
print(f"distinct dag-run ids: {len(runs)}")

def name_split(n):
    # projected names are <project>.<workflow> pre-codec or <project>-<workflow>
    return n

print()
print("=== raw enum spread ===")
print("status:", collections.Counter(STATUS.get(d.get("status"), d.get("status")) for d in rows).most_common())
print("triggerType:", collections.Counter(TRIGGER.get(d.get("triggerType"), d.get("triggerType")) for d in rows).most_common())
print("procGroup:", collections.Counter(d.get("procGroup") for d in rows).most_common())

print()
print("=== time span ===")
ts = sorted(d.get("startedAt","") for d in rows if d.get("startedAt"))
print("first:", ts[0])
print("last :", ts[-1])

json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs.json"), "w"))
