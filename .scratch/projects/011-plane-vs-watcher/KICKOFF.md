# 011 — system-level Dagu plane against a per-repository watcher

Kickoff. Written 2026-09-04, from measurements taken against the live plane on
this machine and against the reconciler spike.

Open a clean session at `~/Documents/Projects/devman` and work from here.

---

## The question

devman today is **one Dagu control plane per machine**, with a registry, a
projection, workflow resolution, run directories, queues and a Nix module layer
that repositories join through a flake. `CLAUDE.md` states the contract: *Dagu
orchestrates, devenv executes, devman is the contract between them.*

`~/Documents/Projects/devman-spike` is the alternative: **one small watchfiles
process per repository**, a flat `rules.toml`, collectors, templates and a
manifest. 1,028 lines of core. No registry, no projection, no run directories,
no orchestrator.

**Decide which shape devman should be, and on what evidence.** The output is not
a preference. It is a capability inventory, a set of measurements, a set of
named trade-offs, and a recommendation that says what would change your mind.

## The two systems, and where to read them

**The plane.** `~/Documents/Projects/devman`.

| | lines |
|---|---:|
| `src/devman/doctor.py` | 1,133 |
| `src/devman/project.py` | 686 |
| `src/devman/registry.py` | 622 |
| `src/devman/watch.py` | 574 |
| `src/devman/run.py` | 359 |
| `src/devman/workflow.py` | 294 |
| `src/devman/cli.py`, `show.py`, entry points | 255 |
| **Python total** | **3,923** |
| `modules/`, `nix/`, `groups/` Nix | **2,126** |

Read: `CLAUDE.md`, `AGENTS_GUIDE.md`, `.scratch/projects/006-automation-plane/CONCEPT.md`
(the charter), `.scratch/projects/007-standard-workflows/PROPOSAL.md` (the
amendment, especially §12), `groups/README.md`, `.devman/workflows/README.md`.

**The spike.** `~/Documents/Projects/devman-spike`.

| | lines |
|---|---:|
| reconciler core (`src/dspike/*.py`) | **1,028** |
| planning collectors and models | 748 |
| tests | 2,022 |
| scripts, gates and demos | 1,688 |

Read: `SPIKE_RESULT.md` (the gate table and Q1–Q3),
`PIPELINE_RESULT.md` (especially §12–§15), `REVIEW_FIXTURE_PIPELINE.md`,
`SYSTEM_LEVEL_OPTIONS.md`, `GENERATION_SERVICE_NOTE.md`, and
`~/Documents/Projects/devman/.scratch/projects/010-reactive-spike/PROTOTYPE_SPIKE_GUIDE.md`.

## What is already measured — do not redo this

All of it is on this machine, 2026-09-04. Verify anything you intend to lean on;
do not spend the session re-taking it.

| | plane | spike |
|---|---|---|
| processes | **3**: `dagu start-all`, `devman watch`, one `watchexec` per watched project | **1** |
| resident memory | 103 + 29 + 10 = **142 MB** | one Python process |
| idle CPU, 60 s | 25 + 14 + 2 = **41 ticks** | **2 ticks** |
| edit → dispatch logged | **p50 502 ms**, max 685 ms | — |
| edit → effect on disk | **p50 2,568 ms**, max **18,476 ms** | **p50 255 ms**, max 276 ms |
| cold invocation | — | 212 ms (was 1,942 before Templateer 0.3.0) |
| warm reconcile | — | 2.4 ms no-op, 5.9 ms one rule |
| socket client → running daemon | — | **5.9 ms** |

Gate bounds the spike set itself: A4 ≤ 400 ms p50 and ≤ 2,000 ms max; A10 ≤ 20
ticks per 60 s; A8 cold/warm ratio ≥ 20; A9 ≤ 1,200 lines.

**The single most useful measured detail:** `watchexec` alone costs **2 ticks** —
exactly what the spike's entire daemon costs. The file-watching layer was never
the expense in either design.

## The methodological trap. Read this before you measure anything.

**The gates were designed by the spike, for the spike.** A4, A8, A9, A10 encode
the spike's values: low idle CPU, low latency, small line count. Judging Dagu by
them is judging a defendant by the prosecution's rules. §15 of
`PIPELINE_RESULT.md` says the plane fails A4 and A10 — that is true and it is
also unfair on its own, because those gates never asked what Dagu is for.

**So do the opposite exercise first.** Before measuring anything, write down the
gates *Dagu* would set if it were designing the comparison: run history,
recoverability after a crash, cross-project fan-out with bounds, queue fairness,
observability, one place to look when something failed at 3am, a UI. Then hold
the spike to those. **A comparison that only runs one side's gates is not a
comparison.**

Two more biases to name and manage:

- **The spike is a spike.** It implements one workload — a save fires one
  deterministic idempotent step — and refuses chains by design. The plane
  implements a general one. Comparing them on the narrow workload flatters the
  spike; comparing them on the general one flatters the plane. **Say which
  workload each number belongs to, every time.**
- **The plane is real and in use; the spike is not.** 54 registered projects and
  171 projected DAGs against a four-fixture demo. Survivorship runs the other
  way here: the plane's costs are visible because it has been running for
  months, and the spike's are invisible because nobody has depended on it.

## The question nobody has asked, and it may decide this

**Does the plane amortize anything across projects?**

The registry holds **54 projects** and **171 projected DAGs**. Exactly **one**
`watchexec` is running. So the plane's cost today is a fixed 39 ticks plus 2
ticks for the one project that is watched.

The arithmetic that matters, and it is not obvious which way it goes:

- **plane** = 39 fixed + (2 ticks × N watched projects)
- **per-repo watcher** = 2 ticks × N

If that model is right, **the plane never amortizes the watching — only the
orchestration — and it is strictly more expensive in CPU at every N.** Memory
runs the other way: `watchexec` is 10 MB, a Python reconciler daemon is roughly
40–60 MB, so at N = 54 the plane would use far less memory.

**Establish the real curve.** Watch 1, 5, 10 and 25 projects under each design
and measure idle CPU, resident memory, file descriptors, and inotify watch
consumption (`/proc/sys/fs/inotify/max_user_watches` is 524,288 here — find out
how much each design uses per project). This is the most decision-relevant
measurement available and nobody has taken it.

## The investigation

### Part A — capability inventory, from source, not from documentation

Produce a table of every capability each system has. Derive it by reading the
code, then confirm by running. For each row: which system has it, where it is
implemented, whether it is used today, and what it would cost the other system
to gain it.

Cover at least: trigger mapping and glob semantics; workflow resolution and
inheritance from groups; the projection into Dagu; run history and artifacts;
queues, concurrency limits and fan-out bounds; scheduling; retries and backoff;
preconditions and skip logic; secrets; the doctor; the CLI surface; the Nix
module layer and how a repository joins; multi-machine assumptions; the UI.

Then the same for the spike: rule loading and refusals; the manifest and
staleness; input hashing and the purity audit hook; the lazy registry and its
fingerprint gate; the socket and the compiled client; obsolete-output pruning;
the watcher's two selection clauses.

**Name what each cannot do at all.** That list is usually shorter and more
decisive than the feature list.

### Part B — the distribution and adoption story

This is the axis the spike has never addressed and it may be the strongest
argument for the plane.

A repository joins devman by taking a Nix flake. Groups (`base`, `format`,
`python`, `release`) arrive with it; 54 repositories share them; changing a
group changes every taker at once. The spike has **no distribution story at
all** — every repository would need its own copy of `dspike`, its own rules, and
its own upgrade.

Answer concretely: how would a per-repo watcher be distributed, versioned and
upgraded across 54 repositories? What replaces a group? What happens when the
reconciler needs a breaking change? **If the answer is "a Nix flake", say
plainly how much of devman that re-creates.**

### Part C — operational properties, under failure

Measure, do not reason:

- What does each do when the work fails? Where does a person look?
- What survives a crash, a `SIGKILL`, a reboot, a full disk?
- What happens when two runs of the same work overlap? (The spike has a known
  unreproduced manifest race, `PIPELINE_RESULT.md` §7 item 1; the plane has
  Dagu's queue.)
- What happens when a repository is moved, renamed or deleted?
- How does each behave when it falls behind — 20,000 files change at once? The
  spike has gate A14 for this. Run the equivalent against the plane.
- Can either tell you it is healthy, and is that claim ever false? `devman
  doctor` is 1,133 lines; find out whether each of its checks has a case where
  it fails.

### Part D — the workload boundary

`PROPOSAL.md` §12 lists eight things that must never become a workflow. Read it
carefully, then answer: **how much of what the plane can do is already forbidden
by devman's own laws?** Scheduling, expensive periodic work and unattended
writes to tracked source are Dagu's strengths and §12's refusals.

If most of Dagu's capability surface is out of bounds by charter, the comparison
narrows sharply — and that is a finding, not an assumption. Test it: enumerate
Dagu's capabilities against §12 and count.

### Part E — what each shape makes possible that the other forecloses

Not features. Directions.

- With a plane: cross-project workflows, a machine-wide view, one place to add
  a capability for 54 repositories, a scheduler if the laws ever permit one.
- With a per-repo watcher: a repository that works standalone with no machine
  state; a reconciler that can be a library rather than a service; the
  generative path measured in `PIPELINE_RESULT.md` §14, where a model writes an
  input and a person accepts it.
- **Is a hybrid real, or is it the worst of both?** `SYSTEM_LEVEL_OPTIONS.md`
  §3.1 proposes "the daemon for state, a client for triggering". Consider
  whether the plane could keep the registry and the group distribution while
  dropping Dagu, or whether Dagu could remain for scheduled and cross-project
  work while saves go direct. Cost each honestly.

## Constraints

- **The plane is live and managing 54 real repositories.** `dagu start-all` is
  pid 1204. Do not stop it, reconfigure it, or edit anything under
  `~/.local/share/dagu` or `~/.local/share/devman` without saying so first.
  Measuring by triggering work in the `devman` repository itself is fine — that
  is how §15's numbers were taken.
- Register a scratch project into the plane if you need to measure fan-out.
  Prefer that to touching a real one.
- **Do not modify `devman-spike`** except to add measurement scripts, and say so
  if you do.
- Every number gets its method beside it: how many samples, what machine state,
  what was running at the same time. The plane's latency varied 490 ms to 18 s
  across ten runs; a single sample is worthless here.

## Deliverable

`.scratch/projects/011-plane-vs-watcher/RESULT.md`, holding:

1. **The capability inventory**, both directions, with what each cannot do.
2. **The scaling curve** for CPU, memory, descriptors and inotify watches at
   N = 1, 5, 10, 25 — the answer to "does the plane amortize anything".
3. **Both gate sets run against both systems**, with the spike's gates and the
   gates Dagu would have set, and a note wherever a gate is unfair to the system
   it is being applied to.
4. **The distribution answer** — how a per-repo watcher reaches 54 repositories,
   and how much of devman that re-creates.
5. **The §12 count** — how much of Dagu's surface devman's own laws forbid.
6. **A recommendation**, in one paragraph, with **the three measurements that
   would reverse it.**
7. **What you did not measure**, listed plainly. This document is worth more
   with an honest gap list than with a confident conclusion.

Do not decide before Part A is done. The strongest finding available may be that
the two systems are not alternatives at all — that one is a distribution and
policy layer and the other is an execution strategy — and that the real question
is which parts of the plane survive if Dagu does not.
