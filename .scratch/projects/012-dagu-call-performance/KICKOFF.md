# 012 — the performance of the plane's Dagu calls

Kickoff. Written 2026-09-04, from measurements taken against the live plane on
this machine during project 011.

Open a clean session at `~/Documents/Projects/devman` and work from here.

---

## The question

devman is the system-wide Dagu control plane. 011 decided that and closed the
alternative (`.scratch/projects/011-plane-vs-watcher/DECISION.md`). **This
project takes the decision as settled and asks the next question: how fast can
the plane's path from a trigger to a running step be made?**

The output is not an opinion about Dagu. It is a decomposition of every term in
the path, a measurement of each, a ranked list of what is worth removing, and a
change to the ones that pay — with the refusals intact.

## What is already measured — do not redo this

All from 011, on this machine, 2026-09-04. Verify anything you intend to lean
on; do not spend the session re-taking it.

| | p50 | max | source |
|---|---:|---:|---|
| edit -> dispatch logged | **502 ms** | 685 ms | `PIPELINE_RESULT.md` §15.2 |
| edit -> effect on disk | **2,568 ms** | **18,476 ms** | same |
| watchexec debounce (default; live argv does not override it) | 50 ms | — | `RESULT.md` §4.2 |
| `devman watch --dispatch` — Python CLI cold start | 119 ms | 108–135 | §4.2 |
| `devman run …` — a **second** full Python start, registry re-read, YAML re-parsed | 147 ms | 122–163 | §4.2 |
| `dagu enqueue` — Go binary cold start | **57 ms** | 43–75 | §4.2 |
| accounted | ~373 ms | of the 502 | §4.2 |

**The single most important fact from 011: Dagu is about 11% of the dispatch.**
The "502 ms Dagu dispatch floor" does not exist. `dispatch()` calls
`subprocess.run([self_binary(), …, "run", …])` (`src/devman/watch.py`), so
**devman's own Python CLI starts twice per filesystem event**, and both starts
read the registry while the second re-parses and re-validates the workflow the
first already resolved.

## The two numbers nobody has explained, and they are the whole project

### 1. The ~130 ms unaccounted in the dispatch

373 ms of 502 ms is accounted. The rest is filesystem event delivery,
`match()`'s work over the registry, and the `fired.jsonl` append. **Nobody has
split those three.** §4.2's method used `devman --help` and `dagu --help` as
cold-start floors, which by construction cannot see the dispatch's own work.

### 2. The gap between 502 ms of dispatch and 2,568 ms of effect — and the 18.5 s tail

**This is the largest unexplained term in the entire plane, by a factor of
four, and it has never been decomposed.** Between `dagu enqueue` returning and
the step running there is: the queue write, the scheduler noticing, the queue
admitting against its limit, the run directory being made, `log_dir` being
resolved, the shell starting, and only then `devenv tasks run`.

Three of ten runs completed under 800 ms and one took 18.5 s. **A queue that is
empty behaves nothing like a queue that is not**, and the plane gives no way to
tell which one you are in from the outside.

**A concrete lead, from the pinned Dagu 2.15.0's own config schema — untested:**

```
scheduler.lock_retry_interval    default '5s'    "Interval between lock retry attempts"
scheduler.lock_stale_threshold   default '30s'   "Duration after which a lock is considered stale"
scheduler.zombie_detection_interval, stale_threshold, failure_threshold
proc.heartbeat_interval          default '5s'
```

An 18.5 s tail is suspiciously close to a small number of 5 s retries.
**Test this first.** `~/.local/share/dagu/config.yaml` sets none of them, so
every one is at its default. If the tail is lock contention, it is a
configuration change, not an architecture change — and it is the single
cheapest win available anywhere in the plane.

## The traps. Read these before you measure anything.

**A single sample is worthless here.** The plane's edit-to-effect varied 490 ms
to 18 s across ten runs. Every number needs n >= 20, its p50 AND its max, and a
note on what else was running. 011's own §9 lists "one sample per point" as its
first methodological gap; do not repeat it.

**Latency is not one number, and the two halves have different owners.**
*Dispatch* is devman's overhead before anything starts. *Effect* includes
`devenv tasks run format:fmt`, which is real work and is not the plane's to
optimise. **Say which half every number belongs to, every time.** A change that
improves dispatch by 200 ms and leaves effect at 2.5 s has improved the thing
nobody was waiting on.

**The cheap win is not the interesting win.** ~266 ms of double process start is
known, ranked and un-prototyped. Take it early so it stops distracting from the
2 s that nobody has explained.

**Do not optimise by removing a refusal.** `src/devman/run.py`'s refusals are
the plane's safety boundary, and every one has a measurement behind it — a
directory named literally `${DEVMAN_PROJECT_DIR}` committed twice, a run
executing another project's workflow in this project's directory and reporting
success, `DEVMAN_PROJECT_DIR=/elsewhere` retargeting a run. **`CLAUDE.md` law 5
is the governing rule: a successful run that did the wrong thing is the failure
this design exists to prevent. Never make a check pass by making it check
nothing.** If a refusal is genuinely expensive, move it — do not drop it.

## The investigation

### Part A — decompose the whole path, end to end

One timeline, from the write() that changes a file to the first byte of the
step's output. Every segment named, measured, and attributed to watchexec,
devman, Dagu, or the work itself. At least:

`write -> inotify delivery -> watchexec debounce -> dispatch process start ->
registry load -> match() -> run process start -> registry load again ->
workflow read + YAML parse + validate -> refusal checks -> dagu enqueue process
start -> queue write -> scheduler pickup -> queue admission -> run dir + log_dir
-> shell start -> devenv tasks run`

**The scheduler-pickup and queue-admission segments are the ones that matter.**
Instrument them from Dagu's own data (`~/.local/share/dagu/data/queue`,
`data/dag-runs`, `data/scheduler`) and from `metadata.jsonl`'s `started_at`
against the `fired.jsonl` timestamp, which is already a matched pair the plane
writes on every event.

### Part B — the four candidate changes, costed and measured

1. **In-process dispatch.** `dispatch()` resolves and enqueues by calling
   `run.py`'s code rather than exec'ing `devman run`. Est. ~266 ms. **Every
   refusal must still fire** — `run.py`'s tests are the specification, and the
   change is only correct if they all still pass unmodified.
2. **What is `devman --help`'s 119 ms?** Measure with `python -X importtime`.
   If it is `yaml`, or the entry-point wrapper, or `requests`, some of it may be
   deferrable behind a lazy import. State how much is irreducible interpreter
   start — the spike measured a bare `python -c pass` at 32–35 ms on this
   machine, which is the floor.
3. **Do not start a Dagu process at all.** `dagu enqueue` is 57 ms of binary
   start to write to a queue. Dagu runs an HTTP server on `127.0.0.1:8080` and
   a coordinator on `50055`. Is there an API that enqueues? If so, weigh it
   honestly: an HTTP call is faster than a process, and it is also a second way
   to enqueue that `doctor` would have to know about. **`run.py`'s docstring
   says the file must never grow a `--now`; a faster enqueue is not a `--now`,
   but check that the distinction survives contact.**
4. **Turn off what is not used.** `config.yaml` enables the coordinator
   (`coordinator.enabled` defaults true) and 011 recorded it as configured and
   unused; `dagu start-all` costs 25 CPU ticks per 60 s idle and 103 MB.
   Measure what the coordinator, and anything else unused, actually costs. Do
   not disable anything before measuring it, and say so before changing
   `~/.local/share/dagu`.

### Part C — what gets slower as the plane grows

The registry holds 54 projects and 171 DAGs; `data/` is 17 MB with 208 recorded
runs. Every dispatch loads the whole registry, and `dagu` walks `dags_dir`.

- How does dispatch scale with registered projects — 54, 200, 1,000?
- How does enqueue scale with queue depth and with history size?
- `hist_retention_days` is 7. What does a year of history do to `data/`, and to
  the UI, and to enqueue?
- `dag_discovery.recursive: true` and `symlinks: true` over 171 DAGs — measured?

### Part D — the bound worth stating

**How fast could this path be, in principle?** Add up the terms that cannot be
removed: inotify delivery, a debounce that exists for a reason, the queue write,
and the work itself. Then say what the plane's overhead floor actually is, and
how far the current 502 ms sits above it. **A target with an argument behind it
is worth more than a percentage improvement.**

And state the other side plainly: **is dispatch latency worth optimising at
all?** §12 rule 1 forbids the plane from competing with what the editor does
synchronously, and the only reactive workload on this machine is one repository
firing `format` on `**/*.py`. If the honest answer is "the 2 s tail matters and
the 500 ms does not", that is a finding, and it should change what Part B ships.

## Constraints

- **The plane is live and managing 54 real repositories.** Do not stop it,
  reconfigure it, or edit anything under `~/.local/share/dagu` or
  `~/.local/share/devman` without saying so first. Triggering work in the
  `devman` repository itself is fine — that is how 011's numbers were taken,
  and `.scratch/**` is in this repository's own trigger ignore list.
- **`devman doctor` must exit 0 before and after any change** to `modules/`,
  `groups/`, `nix/` or `src/devman/`, along with `base:check` and `base:test`.
- **011's decision is settled.** Dagu stays. Nothing from the reconciler spike
  is on the table — see `011-plane-vs-watcher/DECISION.md` for the named list.
  A finding that Dagu is slow is a reason to make the calls faster, not a
  reason to re-open 011.
- Every number gets its method beside it: how many samples, what machine state,
  what was running at the same time.

## Deliverable

`.scratch/projects/012-dagu-call-performance/RESULT.md`, holding:

1. **The full path decomposition**, every segment measured and attributed.
2. **An explanation of the 2,568 ms effect and the 18,476 ms tail**, or an
   honest statement of why it resisted explanation.
3. **The four candidate changes**, each with its measured saving, its risk, and
   whether it was shipped.
4. **The scaling answers** for registered projects, queue depth and history size.
5. **The overhead floor**, with the argument for it.
6. **A ranked list of what to do next**, and what is not worth doing.
7. **What you did not measure**, listed plainly.

Ship the changes that pay in the same branch, with `doctor`, `base:check` and
`base:test` green, and every refusal in `run.py` still firing. A measurement
with no change is an acceptable outcome; a change with no measurement is not.
