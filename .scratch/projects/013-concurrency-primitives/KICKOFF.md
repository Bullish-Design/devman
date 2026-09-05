# 013 — what the plane should actually say about concurrency

Kickoff. Open a clean session at `~/Documents/Projects/devman` and work from
here. **Read this whole file before running anything.**

---

## The question

Today a workflow declares one string — `queue: light` — and that string is
made to carry **three unrelated ideas at once**:

1. **Mutual exclusion.** "Do not run this while it is already running." Every
   workflow that writes a fixed path needs it: `format` writes
   `.devman/.runs/.format.hash`, `release` writes an `--out-link` at a fixed
   path, `agent-review` appends to one report file.
2. **Class of service.** "A save's formatter must not queue behind a
   half-hour build." This is what keeps the reactive path responsive and is
   the thing `PROPOSAL.md` §12 rule 1 cares about.
3. **Machine capacity.** "Do not run eight `nix flake check`s on eight cores."

**One string cannot express three orthogonal things, and the evidence that it
does not is already in the tree.** `nix/nixos-module.nix`, at the
`baseFile` definition, says this out loud:

```
# A DAG naming no queue lands in a queue named after itself, at concurrency
# 1 (S-9 — not "no limit at all", which is what A1 recorded and §15.4 now
# corrects). The default is still needed, for the reason underneath that
# number: a per-DAG queue bounds a DAG against ITSELF and bounds the machine
# against nothing, so 53 projects would run 53 lanes wide with no stated
# limit anywhere.
```

**Dagu hands out identity locks for free, and devman gives them up** — because
the same mechanism cannot also bound the machine. Idea 1 was traded away to buy
idea 3. Nobody wrote down what that cost.

**This project is not "make it faster". It is: what are the right primitives,
what is the cleanest way to express them, and how much of that can this
orchestrator carry?** A measurement with no change is acceptable. A change
without a design argument behind it is not.

---

## What this project must NOT inherit

Project 012 produced claims about this area **in conversation, not in
measurement**, and several were wrong. They are listed here so you re-derive
them rather than repeat them.

| claim made in 012 | status |
|---|---|
| "Identity locks are not expressible in Dagu." | **WRONG.** The module comment above says the opposite. Re-derive from scratch. |
| "The queue is the plane's only lever on concurrency." | **Unverified as stated.** True of the *global queue config*; 012 never read Dagu's **DAG** schema, only its **config** schema. |
| "`max_active_runs` is deprecated and ignored." | **Verified** for the global queue config's own field. **Not** verified for the DAG-level field of the same name. Two different things; 012 conflated them. |
| "`format` runs can race on `.format.hash` because `light` allows 4." | **Inferred, never demonstrated.** Four concurrent `devman.format` runs were observed. The race was not. Demonstrate it or disprove it. |
| "`normal: 2` should be raised to ~6." | **A guess with no measurement.** The five limits have no sizing evidence anywhere in the repository. |
| "Dagu's drain is a 3.000 s ticker with no config key." | **Verified**, n=50 plus 494 historical runs. `012/RESULT.md` §2. Safe to build on. |
| "The daemon is the parent of every run." | **Verified** — `pid 3015302, ppid 1204`. Safe to build on. |
| "Runs are tracked for liveness by heartbeat files under `data/proc/<queue>/`." | **Verified** as file locations and config keys. The *semantics* were not tested. |

**Treat everything in the first six rows as a lead, not a finding.**

---

## What is re-openable, and what is not

**The charter is amendable and you should be willing to amend it.**
`CLAUDE.md` law 2 requires that a change contradicting the charter changes the
charter *in the same commit, with the measurement that forced it*. That is a
procedure for changing it, not a prohibition.

In particular:

* **Law 3's "five queue names are a closed list" is in scope.** The law says
  adding a sixth "is a charter change, not an implementation detail" — which
  is an instruction about how to do it, not a refusal. If the right design has
  three primitives instead of one, say so and amend §7.1.
* **`groups/README.md`'s "a `queue:` name" as the portable unit is in scope.**
* **S-9's either/or is in scope, and is the specific thing to attack.**

**What is not in scope:**

* **Reopening 011.** Dagu stays. A finding that Dagu expresses something badly
  is a reason to design around it or ask upstream, not to relitigate the
  orchestrator. `011-plane-vs-watcher/DECISION.md` names the closed list.
* **Law 4, in any form.** *A successful run that did the wrong thing is the
  failure this design exists to prevent.* A concurrency model that admits a run
  it should have deferred is exactly that failure. **Never make a check pass by
  making it check nothing**, and never trade a refusal for latency.
* **devman executing work.** `CLAUDE.md`: devman itself executes nothing. A
  design where devman holds a lock *across* the work makes devman a supervisor
  and is a different project.

---

## The investigation

### Part A — what can Dagu 2.15.0 actually express?

**012 read the config schema and stopped. Do not stop there.**

1. **Extract the full DAG schema** from the pinned binary, not just
   `definitions.QueueDef`. 012's method:
   `.scratch/projects/012-dagu-call-performance/RESULT.md` §8 and the snippets
   in its measurements. The binary at
   `/nix/store/…-dagu-2.15.0/bin/dagu` embeds a complete JSON schema.
2. **Read the source at the `v2.15.0` tag.** `dagu-org/dagu` is GPL-3.0 and
   public. 012 never read a line of it and said so in its §7. The packages that
   matter are visible in the binary's own paths:
   `internal/queue/`, `internal/service/scheduler/`, `internal/schedulerstate/`.
3. **Enumerate every mechanism that could produce "not concurrently with
   itself"**, and for each answer four questions:
   * Does it **defer** or **drop**? (A drop loses work. See the trap below.)
   * Is it **machine-global**, or per-process/per-DAG-file?
   * Does it **survive a `SIGKILL`** of the run, and of the daemon?
   * Can it **compose** with a separate machine-wide bound?

   Candidates to start from — the list is not exhaustive and finding one that
   is not on it is a good outcome: the implicit per-DAG queue (S-9); an
   explicitly named queue; DAG-level `maxActiveRuns`; step `preconditions`;
   `skipIfSuccessful`; `type: build` materialisation reuse; whatever
   `internal/queue/enqueue_retry` and `dispatchAdmissionSlot` turn out to be —
   both appear as symbols in the binary and neither is documented.
4. **Can one run be constrained by two things at once?** This is the crux of
   S-9's either/or. If a run can be admitted against *both* a per-identity
   limit and a shared capacity limit, the trade in that comment evaporates and
   most of this project is a projection change.

### Part B — what does this plane actually need to exclude?

**Do not assume. The conflict set has never been written down.**

1. **Enumerate every workflow on the machine**, not just this repository's.
   `~/.local/share/devman/projects/*/workflows/*.yaml` is 170 projected files
   across 54 projects, and it is readable. Also `groups/*/workflows/`.
2. **For each, find what it writes to a fixed path** — a hash file, an
   out-link, a report, a lock, a cache. Classify each conflict:
   * **self-conflict** — the same workflow against itself in the same project;
   * **sibling conflict** — the same workflow in *different* projects (does
     `format` in two repositories actually conflict? Probably not — check);
   * **cross-workflow conflict** — two *different* workflows over one file.
     `.devman/.runs/` is shared by every workflow in a project. Does anything
     collide there?
   * **resource conflict** — no shared file, but they cannot both have the
     machine.
3. **Demonstrate at least one real collision.** The `format` hash race is the
   obvious candidate and it is unproven. Two concurrent `format` runs in one
   repository, instrumented; either the hash ends up wrong or it does not.
   **A design justified by a hypothetical race is a design with no measurement
   behind it.**

### Part C — the design, before the implementation

**Write down the primitives first, independent of what Dagu offers.** The
working hypothesis this kickoff starts from — attack it, do not adopt it:

> Three orthogonal declarations, not one string:
> an **exclusion key** (default: the workflow's own identity), a **class of
> service**, and a **machine capacity** that is a property of the machine
> rather than of any workflow.

For whatever set you arrive at, answer:

* **What does a group author have to type**, and what do they get wrong if they
  type nothing? A default that is silently wrong is worse than a required field.
* **Where does each live?** §7.2's rule is that group content is portable text
  and machine facts are machine state. An exclusion key is content. A core
  count is not. Which of the three is which?
* **What does `doctor` check?** Every primitive that can be declared can be
  declared wrongly. §10's checks are the plane's honesty and a new primitive
  with no check is a new way to fail silently.
* **What does the projection have to render**, and does it still satisfy
  criterion 10 (no absolute path, no project fact, in a workflow file)?

### Part D — spike the winner, then measure it

**Build the smallest thing that demonstrates the design and run it.** Not a
proposal document with a table of options — a working projection with the real
Dagu and the real registry, on a throwaway `DAGU_HOME`.

Prove three things:

1. **The collision from Part B is prevented.** The same experiment that
   demonstrated it now fails to.
2. **The machine bound still holds.** Whatever replaces `light: 4` still stops
   eight `nix flake check`s. **This is the half S-9 was protecting, and losing
   it silently is the failure mode.**
3. **Latency did not regress.** 012 left the dispatch at ≈289 ms and the drain
   tick at a mean 1.5 s. Re-measure both; a design that adds a second enqueue
   or a second poll has to say so.

### Part E — the numbers nobody has

Two measurements this plane has never taken, both needed before any limit is
written down again:

* **What does this machine sustain?** 1, 2, 4, 6 concurrent `base:test`
  (`nix flake check`, 91.9 s alone). 8 cores, 125 GB. **The obvious rule
  "capacity = cores" is wrong** — `nix flake check` hands its work to
  `nix-daemon`, which already claims the machine, so `nproc` runs each wanting
  `nproc` cores asks for `nproc²`. Find the real shape.
* **What are the five current limits worth?** `exclusive 1, gpu 1, heavy 1,
  light 4, normal 2` appear as values in `nix/nixos-module.nix` and nowhere as
  an argument. Either justify them or replace them.

---

## The traps

**A drop is not a defer, and the difference is silent.** "If it is already
running, skip" loses the second trigger. For `format` that means the second of
two quick saves is never formatted — the exact failure
`groups/format/workflows/format.yaml`'s own comment describes ("a suppression
window would have swallowed that edit, and would still have passed a naive 'one
save, one run' test"). Dagu's `preconditions` **skip**; they do not defer.
Check the semantics of any mechanism before building on it.

**A dead run must not hold a lock forever.** Anything keyed on "is it running"
needs an answer to "the holder was `SIGKILL`ed". Dagu's answer is heartbeats
plus `stale_threshold`; any new mechanism needs its own, and a design without
one wedges a workflow permanently and silently. Three of today's five queues
are limit 1, so this is not hypothetical.

**Do not tune your way out of a design problem.** Raising `normal` to 6 makes
the 42 s tail shorter and fixes nothing about what the string means. If the
answer is "the limits were just wrong", say that with the Part E numbers — but
do not let it substitute for Part C.

**One sample is worthless.** 012's method holds: n ≥ 20, p50 **and** max, and a
note on what else was running. This machine has an unrelated `find` over sysfs
pinning one core; check whether it is still there and record the load with every
figure.

**The plane is live and manages 54 real repositories.** Do not stop it,
reconfigure it, or write under `~/.local/share/dagu` or `~/.local/share/devman`
without saying so first. Every Dagu experiment goes on a throwaway `DAGU_HOME`
under `/tmp` on ports 18080/50155 —
`012/measurements/coordinator_cost.sh` is a working example, including how to
kill only your own instance. Triggering work in the `devman` repository is fine.

---

## Constraints

* **`devman doctor` must exit 0 before and after**, along with
  `devenv tasks run base:check` and `base:test`. **It exits 1 today**, for a
  machine-state reason 012 recorded: the running daemon predates
  `nix/nixos-module.nix`'s own `UnsetEnvironment = "SHELL"`, and the profile's
  `devman` has no `project` subcommand. **The machine needs a rebuild and a
  service restart before this project can verify anything.** Ask for it first.
* **Every refusal in `src/devman/run.py` keeps firing.** `tests/unit/test_run.py`
  is the specification and must pass unmodified, as it did through 012.
* Every number gets its method beside it: sample count, machine state, what
  else was running.

## Deliverable

`.scratch/projects/013-concurrency-primitives/RESULT.md`, holding:

1. **What Dagu can express**, enumerated, each mechanism with its defer/drop,
   scope, crash-survival and composability answers.
2. **The conflict set** — every workflow on this machine that needs exclusion,
   classified, with at least one collision demonstrated.
3. **The design**, stated as primitives with the argument for each, and what a
   group author types.
4. **The spike**, with the three proofs from Part D.
5. **The numbers** from Part E.
6. **What S-9's either/or actually costs**, now that somebody has priced it.
7. **What you did not measure**, plainly.

Ship the change if it wins on the argument and the measurement. Amend the
charter in the same commit if it contradicts one — with the measurement that
forced it. **A clean concept that costs a refusal is not clean.**
