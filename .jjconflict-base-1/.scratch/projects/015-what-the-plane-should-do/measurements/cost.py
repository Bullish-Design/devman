#!/usr/bin/env python3
"""What does a format fire cost, and how many do real work?

Method: every devman format attempt in Dagu's surviving history.
Duration = finishedAt - startedAt. A run whose only node is skipped by the
precondition did no formatting.
"""
import json, os, glob, collections, datetime, statistics, re
DATA = os.path.expanduser("~/.local/share/dagu/data/dag-runs")

def parse(t):
    return datetime.datetime.fromisoformat(t)

rows = []
for d in ("devman-format", "devman_format-2904"):
    for p in glob.glob(os.path.join(DATA, d, "**", "status.jsonl"), recursive=True):
        last = [l for l in open(p).read().splitlines() if l.strip()]
        if not last: continue
        rows.append(json.loads(last[-1]))

print(f"format attempts in surviving history: {len(rows)}")
durs, skipped, worked, failed = [], 0, 0, 0
node_status = collections.Counter()
for r in rows:
    try:
        dt = (parse(r["finishedAt"]) - parse(r["startedAt"])).total_seconds()
    except Exception:
        continue
    durs.append(dt)
    for n in r.get("nodes", []):
        node_status[n.get("status")] += 1
    st = [n.get("status") for n in r.get("nodes", [])]
    if r.get("status") != 4:
        failed += 1
    elif st and all(s == 5 for s in st):   # 7 == skipped in dagu
        skipped += 1
    else:
        worked += 1

print("node status spread (dagu enum):", node_status.most_common())
print(f"skipped(precondition met, no work): {skipped}")
print(f"did work:                           {worked}")
print(f"failed:                             {failed}")
print()
durs.sort()
def pct(p): return durs[int(len(durs)*p)] if durs else 0
print(f"duration n={len(durs)}  min={durs[0]:.2f}s  p50={pct(.5):.2f}s  p90={pct(.9):.2f}s  max={durs[-1]:.2f}s  mean={statistics.mean(durs):.2f}s")
print(f"total wall-clock spent in format:   {sum(durs):.0f}s")

# --- split durations by outcome ---
print()
print("=== duration split by outcome ===")
buckets = collections.defaultdict(list)
for r in rows:
    try:
        dt = (parse(r["finishedAt"]) - parse(r["startedAt"])).total_seconds()
    except Exception:
        continue
    st = [n.get("status") for n in r.get("nodes", [])]
    if r.get("status") != 4: k = "failed"
    elif st and all(s == 5 for s in st): k = "skipped (precondition: tree unchanged)"
    else: k = "formatted (ran devenv tasks run format:fmt)"
    buckets[k].append(dt)
for k, v in sorted(buckets.items()):
    v.sort()
    print(f"{k:44} n={len(v):4} p50={v[len(v)//2]:5.1f}s p90={v[int(len(v)*.9)]:5.1f}s max={v[-1]:5.1f}s total={sum(v):6.0f}s")
