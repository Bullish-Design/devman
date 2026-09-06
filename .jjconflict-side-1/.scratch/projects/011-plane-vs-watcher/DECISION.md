# 011 — DECISION: devman is the system-wide Dagu plane. Closed.

Status: **DECIDED, 2026-09-04.** This decision closes projects 010 and 011.
Evidence: [`RESULT.md`](RESULT.md). Raw data: [`measurements/`](measurements/).

---

## The decision

**devman is, and remains, one system-wide Dagu control plane per machine.**
`CLAUDE.md`'s contract stands unchanged and unqualified:

> **Dagu orchestrates. devenv executes. devman is the contract between them.**

**No part of the reconciler spike is adopted. Not now, and not as a staged
plan, a hybrid, an experiment, or a library.** The spike is closed as a
completed investigation with a negative result. `~/Documents/Projects/devman-spike`
is a separate repository and has no relationship to devman going forward.

---

## What is explicitly NOT adopted

Named individually, so that nothing is re-imported later by a different name.

| Not adopted | Where it came from |
|---|---|
| A per-repository watcher process of any kind | the spike's `watcher.py` |
| `watchfiles`, or any second file-watching implementation | the spike's core |
| A `rules.toml`, or any glob-to-generator rule file | the spike's `rules.py` |
| A content manifest — input hashes, output hashes, `rendered_at` | the spike's `manifest.py` |
| Output ownership and obsolete-artifact pruning | the spike's `reconcile._obsolete` |
| The purity audit hook (`sys.addaudithook`) | the spike's `reconcile.py` |
| A Unix socket trigger path, or a compiled client | the spike's `server.py`, `client/dspike-gen.c` |
| A lazy template registry, Templateer, or any render step inside devman | the spike's `registry.py` |
| In-process execution of workflow work | the spike's whole premise |
| "Hybrid A" — keep the registry, drop Dagu | `RESULT.md` §7.3 |
| "Hybrid B" — Dagu for scheduling, saves go direct | `RESULT.md` §7.3 |
| "Hybrid C" — a socket on `devman watch` | `RESULT.md` §7.3 |
| Derived-artifact generation as a devman workload | `PIPELINE_RESULT.md`, the whole fixture pipeline |

**The last row is the one that matters most.** §12 rule 3 already names *code
generation* as what must never become a workflow. That rule is reaffirmed, not
amended. devman does not own generated artifacts. The question "should it?" is
**closed as no**, and re-opening it is a charter change requiring the
measurement that forced it (`CLAUDE.md` law 2).

---

## Why — the four grounds, each with its measurement

1. **The plane's costs are fixed; a per-repository design's are linear.**
   `RESULT.md` §2, measured at N = 1, 5, 10, 25. The plane's watching layer is
   one process, 0 CPU ticks per 60 s idle at every N, and 9.1 -> 11.6 MB
   across a 25x increase in watched trees. A per-repository watcher costs 1.64
   ticks and 18.8 MB *per repository* — and 41.5 MB for a real daemon. Memory
   crosses over at N between 3 and 8; CPU at N about 25. The registry holds 54
   projects.

2. **A per-repository design has no distribution story, and acquiring one
   re-creates devman's Nix and group layers.** `RESULT.md` §3. The spike
   declares `templateer = { path = "../templateer_v2" }` and has no flake. It
   works because a sibling directory happens to exist. Reaching 54
   repositories means re-building `modules/devenv.nix`, `nix/devman-cli.nix`
   and `groups/` — and would still lack the registry that lets `devman doctor`
   name `gitman` and `pyjutsu` as unmigrated.

3. **The three gates it fails fairly have no path to being fixed within its
   shape.** `RESULT.md` §6.2 — durable accept (D2), a concurrency bound (D4),
   and distribution (D6). §4.1 is the measurement behind D4: 2,000 filesystem
   events produced **4 runs, all succeeded, converged in 17 s**. The queue is
   load-bearing, and no per-repository design has one.

4. **Nothing the reconciler does is foreclosed to the plane by Dagu.**
   `RESULT.md` §1.2 and §1.3.1, checked row by row against the pinned Dagu
   2.15.0 schema. Duplicate-output refusal is a shape devman already
   implements for DAG names. Orphan tracking is a layer neither system built,
   and Dagu does not prevent it. The purity audit is impractical for devman's
   execution model rather than absent from Dagu's capability. The one genuinely
   structural gap — Dagu cannot hold warm state between triggers — buys only
   latency that §12 rule 1 forbids the plane from spending.

**And the argument that looked strongest against the plane does not survive
measurement.** `RESULT.md` §4.2: the "502 ms Dagu dispatch floor" is not
Dagu's. Dagu is 57 ms of it — about 11%. The rest is devman's own CLI starting
twice per filesystem event.

---

## What this decision does NOT do

Two honest limits, so this document is not read as more than it is.

**It does not claim the plane is cheap.** 3 processes, 142 MB and 41 CPU ticks
per 60 s idle is a real standing cost, and today it serves **one** reactive
repository (`RESULT.md` §0.2 — of 54 registered projects, exactly one declares
a trigger map). The plane is the right shape at the scale devman is built for;
it is oversized for the scale devman currently runs at. That is a reason to
grow the reactive set or to accept the cost — not a reason to change shape.

**It does not settle the reversal conditions.** `RESULT.md` §8.3 lists three
measurements that would reverse this decision. They stand. This document is a
decision, not a proof, and the reversal conditions are what make it honest.

---

## One finding to keep, and it is not the spike's

`RESULT.md` §4.2 found that `dispatch()` calls
`subprocess.run([self_binary(), …, "run", …])`, so devman's Python CLI starts
**twice per filesystem event**, and both starts read the registry while the
second re-parses and re-validates the workflow the first already resolved.
About 266 ms of the 502 ms dispatch is that second process start.

**This is a devman-internal finding about devman's own code. It is not a spike
concept and adopting it imports nothing from the spike.** It is recorded here
because it was found in this investigation and would otherwise be lost. It is
**optional and independent** of this decision: the plane is correct either way,
and §9 item 8 records that it was never prototyped. Whoever picks it up should
treat it as new work with its own measurement, not as a conclusion of 011.

---

## Leakage audit — 010 and 011 reached nothing else

Checked 2026-09-04, before this decision was written.

| Check | Result |
|---|---|
| `dspike`, `devman-spike`, `watchfiles` anywhere outside `.scratch/projects/010-*` and `011-*` | **none** |
| Links to the 010 or 011 directories from anywhere else | **none** |
| Concept-level terms (`rules.toml`, `manifest`, per-repository watcher, in-process, derived artifact) in `CLAUDE.md`, `AGENTS_GUIDE.md`, `README.md`, `USER.md`, the three skills, every `groups/*/README.md`, `.devman/workflows/README.md` | **none** |
| Commits touching anything outside `.scratch/` since 010 began | **none** — the most recent is `9898f70 feat: §7.3's last layer, for triggers — 009 stage 9` |

**010 and 011 produced only `.scratch/` documents. No source file, Nix module,
group, workflow, skill or governing document was ever touched by either.** The
charter (`006-automation-plane/CONCEPT.md`) and its amendment
(`007-standard-workflows/PROPOSAL.md`) are unmodified and remain the design.

`010-reactive-spike/` and this directory stay in place as the record, under
`CLAUDE.md` law 1 — the measurement behind a decision is not deleted. Both now
carry a header pointing here, so neither is picked up as live direction.

---

## Moving forward

devman is the system-wide Dagu plane. Work continues on the plane's own terms:
the registry, the projection, the groups, the Nix module layer, the queues,
`doctor`, and the workflows the groups ship. `PROPOSAL.md` §12's nine rules
govern what may become a workflow, and rule 3 is reaffirmed by this decision.

The next stage picks up from **009**, not from 010 or 011.
