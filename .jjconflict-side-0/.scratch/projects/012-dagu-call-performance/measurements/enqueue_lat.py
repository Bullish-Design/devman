#!/usr/bin/env python3
"""012 Part A — `dagu enqueue` returning, to the step's first byte.

THE TWO TIMESTAMPS ARE THE PLANE'S OWN, AND BOTH CARRY MILLISECONDS.

`status.jsonl` reports `startedAt` to the second, which is useless against a
figure near one second. The file names beside it do not: Dagu names a dag-run
log `dag-run_<date>.<time>.<ms>.<id>.log` and a step's stdout
`<step>.<date>.<time>.<ms>.<id>.out`. The first is written at enqueue and
equals `createdAt`; the second is written when the step starts. Their
difference is the segment nobody had split — the queue write, the scheduler
noticing, admission, the run directory, and the shell — with no instrumentation
added to anything.

Usage:  enqueue_lat.py N [GAP_SECONDS]
  N            how many runs to enqueue
  GAP_SECONDS  seconds between enqueues. 0 makes a burst, which is what
               distinguishes a poll from an interrupt: under a poll every run
               of a burst starts on the SAME tick.
"""
from __future__ import annotations
import datetime as dt, json, os, pathlib, re, subprocess, sys, time

DEVMAN = os.environ.get("DEVMAN", "/tmp/012/devman-src/bin/devman")
REG = pathlib.Path.home() / ".local/share/devman"
DAGU_HOME = pathlib.Path.home() / ".local/share/dagu"
DATA = DAGU_HOME / "data/dag-runs"
WORKFLOW, PROJECT = "format", "devman"
TS = re.compile(r"\.(\d{8})\.(\d{6})\.(\d{3})\.")
RUNID = re.compile(r"run-id=(\S+)")


def stamp(name: str):
    m = TS.search(name)
    if not m:
        return None
    d, t, ms = m.groups()
    return dt.datetime.strptime(d + t, "%Y%m%d%H%M%S") + dt.timedelta(milliseconds=int(ms))


def enqueue_http():
    """The other enqueue: Dagu's own HTTP API, `POST /api/v1/dags/<dag>/enqueue`.

    It is here to answer 012's candidate 3 — "do not start a Dagu process at
    all" — and it answers it against the segment that matters rather than the
    one that is easy to measure. Note what this call does NOT do: it names a
    DAG and enqueues it, with no project resolution, no parameter derivation
    and none of `run.py`'s refusals. The plane could not adopt it as written.
    """
    import urllib.request
    t0 = time.time()
    req = urllib.request.Request(
        f"http://127.0.0.1:8080/api/v1/dags/devman.{WORKFLOW}/enqueue",
        data=b'{"params":"DEVMAN_PROJECT_DIR=/home/andrew/Documents/Projects/devman"}',
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read().decode()
    t1 = time.time()
    m = re.search(r'"(?:dagRunId|requestId)"\s*:\s*"([^"]+)"', body)
    if not m:
        sys.exit(f"http enqueue gave no run id: {body[:300]}")
    return m.group(1), t0, t1


def enqueue():
    t0 = time.time()
    p = subprocess.run(
        [DEVMAN, "--registry", str(REG), "--dagu-home", str(DAGU_HOME),
         "run", WORKFLOW, "-p", PROJECT],
        capture_output=True, text=True)
    t1 = time.time()
    m = RUNID.search(p.stderr + p.stdout)
    if p.returncode or not m:
        sys.exit(f"enqueue failed rc={p.returncode}\n{p.stderr}")
    return m.group(1), t0, t1


def find(run_id: str, timeout=120):
    """The status record for one run id, once its step has a stdout file."""
    end = time.time() + timeout
    while time.time() < end:
        for f in DATA.rglob(f"*{run_id}*/**/status.jsonl"):
            for line in f.read_text().splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                node = (r.get("nodes") or [{}])[0]
                if r.get("dagRunId") == run_id and node.get("stdout"):
                    return r
        time.sleep(0.15)
    return None


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    gap = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
    print(f"# devman={DEVMAN}\n# n={n} gap={gap}s load={open('/proc/loadavg').read().split(' 0')[0]}")
    fired = []
    for i in range(n):
        fired.append(enqueue_http() if os.environ.get("ENQUEUE") == "http" else enqueue())
        if gap:
            time.sleep(gap)
    rows = []
    for run_id, t0, t1 in fired:
        r = find(run_id)
        if r is None:
            print(f"  {run_id}  NO RECORD")
            continue
        enq = dt.datetime.fromtimestamp(r["createdAt"] / 1000)
        out = stamp(pathlib.Path(r["nodes"][0]["stdout"]).name)
        rows.append(dict(run=run_id,
                         proc_ms=(t1 - t0) * 1000,
                         enq=enq,
                         out=out,
                         lat_ms=(out - enq).total_seconds() * 1000,
                         status=r["nodes"][0].get("status")))
    print(f"\n{'run':26s} {'devman run (ms)':>15} {'enqueued at':>16} {'step out at':>16} {'queue->step (ms)':>17} st")
    for r in rows:
        print(f"{r['run']:26s} {r['proc_ms']:15.1f} {r['enq']:%H:%M:%S.%f} {r['out']:%H:%M:%S.%f} "
              f"{r['lat_ms']:17.1f} {r['status']}")
    lat = sorted(x["lat_ms"] for x in rows)
    proc = sorted(x["proc_ms"] for x in rows)
    def P(xs, q): return xs[min(len(xs) - 1, int(q * len(xs)))]
    for label, xs in ((("POST /enqueue -> returned" if os.environ.get("ENQUEUE")=="http" else "devman run -> returned"), proc), ("enqueue -> step's first byte", lat)):
        print(f"\n{label}  n={len(xs)}")
        for q in (0, .5, .9, 1.0):
            print(f"   p{int(q*100):>3}: {P(xs, q):9.1f} ms")
    json.dump(rows, open(sys.argv[3] if len(sys.argv) > 3 else "/tmp/012/enq.json", "w"),
              default=str, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
