#!/usr/bin/env python3
"""012 Part A — fit a periodic drain to the measured enqueue->start latencies.

If the scheduler drains its queue on a ticker of period T at phase p, then a run
enqueued at t starts at the first tick after t, so

    latency(t) = (p - t) mod T   + c

with c the fixed cost of starting the run once picked up. This scans T and p,
reports the best fit and its residuals, and prints the runs that do not fit —
which are the interesting ones, not noise to be hidden.

Usage: tick_fit.py enqueue-*.json [more.json ...]
"""
from __future__ import annotations
import datetime as dt, json, sys


def load(paths):
    out = []
    for p in paths:
        for r in json.load(open(p)):
            enq = dt.datetime.fromisoformat(r["enq"])
            out.append((enq.timestamp(), r["lat_ms"] / 1000.0, r["run"]))
    return sorted(out)


def fit(rows, T):
    best = None
    for step in range(0, 3000):
        p = step * T / 3000
        res = []
        for t, lat, _ in rows:
            pred = (p - t) % T
            res.append(abs(lat - pred))
        res.sort()
        med = res[len(res) // 2]
        if best is None or med < best[0]:
            best = (med, p, res)
    return best


def main() -> int:
    rows = load(sys.argv[1:])
    print(f"n={len(rows)}")
    print(f"{'T (s)':>7} {'phase (s)':>10} {'median |residual| (ms)':>23} {'runs within 50 ms':>18}")
    table = []
    T = 0.5
    while T <= 6.001:
        med, p, res = fit(rows, T)
        within = sum(1 for x in res if x <= 0.050)
        table.append((med, T, p, within))
        print(f"{T:7.2f} {p:10.3f} {med*1000:23.1f} {within:14d}/{len(rows)}")
        T += 0.25
    med, T, p, within = min(table)
    print(f"\nBEST FIT: period {T:.2f} s, phase +{p:.3f} s, median residual {med*1000:.1f} ms,"
          f" {within}/{len(rows)} runs within 50 ms")
    print("\nper run (predicted vs measured, ms):")
    for t, lat, run in rows:
        pred = (p - t) % T
        flag = "" if abs(lat - pred) <= 0.050 else ("   <-- missed a tick" if abs(lat - pred - T) <= 0.10 else "   <-- OFF GRID")
        print(f"  {run:26s} pred {pred*1000:7.0f}  measured {lat*1000:7.0f}"
              f"  residual {(lat-pred)*1000:+8.0f}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
