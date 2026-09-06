# 020 — A schedule bypasses its queue, and LLM calls are the first workload that cannot live with it

Kickoff. Open a clean session at `~/Documents/Projects/devman` and work from
here. **Read this whole file before running anything.**

---

## 1. The problem, stated as a measurement

**Dagu's own scheduler does not enqueue. It starts.**

A queue in Dagu is an admission gate on the **enqueue** path. `max_concurrency`
is enforced by the queue reader, and nothing consults a queue when a run begins
by another route. Three routes exist and one is gated:

| how a run starts | path | gated |
|---|---|---|
| `devman run` (watcher, hook, by hand) | `dagu enqueue` | **yes** |
| `dagu start` | direct | no |
| `schedule:` — Dagu's scheduler | direct | **no** |

Measured in project 007, S-1, over the same 58 DAGs all naming `light`
(`max_concurrency: 4`):

```
58 × dagu enqueue   never exceeded 4 concurrent, drained in 311 s
58 × schedule:      all 58 started at once, queue depth 0
```

Two `exclusive` DAGs (`max_concurrency: 1`) were also seen starting in the same
second on the installed plane.

**The queue name in a scheduled workflow parses, validates, and binds nothing.**

## 2. Why this has been survivable, and why that ends

The rule that replaced the property is in `AGENTS.md`:

> **what the plane schedules must be cheap by construction**

It has held because the plane schedules two things, and both obey it:

```
groups/base/workflows/maintain.yaml:139     schedule: "5 0 * * *"
.devman/workflows/plane-report.yaml:68      schedule: "20 0 * * *"
```

`maintain` prunes its own report directory and calls no repository task.
`plane-report` reads the plane. 54 simultaneous dispatches of either are fine —
**and the queue is not what makes them fine**, which is a comment `maintain.yaml`
got wrong until 009 P2-5 corrected it.

**An LLM call is not cheap by construction, and no rewrite makes it so.**

## 3. Why an LLM call breaks the rule rather than bending it

**AND THIS IS THE ARGUMENT THAT REVERSES A PRIOR CONCLUSION. IT IS THE REASON
THIS PROJECT EXISTS AND NOT A RESTATEMENT OF 007.**

The standing objection to a queued-schedule path was that **a queue smooths work
and does not make it affordable**: 54 expensive runs through a gate are still 54
expensive runs, finishing at 04:00 instead of 00:30. For CPU work that is
correct — the machine does the same total work either way, and the queue buys
only a quieter peak.

**It is wrong for a metered resource, and an LLM call is metered.** The
constraint is not this machine's CPU. It is a **quota held outside this
machine** — requests per minute, tokens per minute, and money — and it is
**shared by all 54 repositories at once**.

For a rate limit, spreading *is* the fix:

- 54 concurrent calls against a per-minute limit **fail**, and the failure is
  not a slower run. It is `429`, a partial fan-out, and 54 runs recorded green
  or red for a reason unrelated to the work.
- The same 54 calls at 4 at a time **succeed**, and cost the same money.

**A queue converts a breached limit into a longer wall clock.** That is exactly
the trade the standing objection said a queue could not make, and it is the one
this workload needs. The objection was right about CPU and does not reach here.

## 4. Four more things an LLM workflow touches, and none is the queue

**State these in the result. A project that solves only the queue has solved the
smallest of the five.**

**4.1 The five queue names are a closed list, and this needs a sixth.** Law 3:
`exclusive`, `gpu`, `heavy`, `light`, `normal` — adding one is a charter change,
not an implementation detail. LLM work wants its own queue, because its
concurrency is set by an **external quota** and not by this machine's cores.
Sharing `heavy` couples it to local builds and tunes neither. **Decide whether
the sixth name is `llm`, and amend `CONCEPT.md` §7.1 in the same commit that
adds it, with the measurement that forced it.**

**4.2 §9.4 fires for the first time in this plane's life.** A workflow that
calls an API needs a key, and §9.4 — the secrets path — has never run. It is
designed and unexercised. It gives two properties that matter here:

- **Dagu masks a resolved secret in logs.** Without it, any step can echo a key
  into a log under `.devman/.runs/`, and from there into a screenshot.
- **A missing secret fails the run before any step runs**, naming the secret and
  the provider.

Per workflow, never in `base.yaml` — a `secrets:` block in `base.yaml` grants
every workflow on the machine every secret and deletes the sentence §9.4 exists
for. **Law 8 still holds: nothing in this repository holds a value.**

**4.3 Rule 4 is sharper for an LLM than for anything the plane runs today.** A
model that returns a fluent, empty, plausible answer produces exit 0 and a full
log. This is `full-test` with prose. **019 is a hard dependency, not a related
project** — an LLM workflow that writes must leave a receipt, and an LLM
workflow that verifies must be able to fail on vacuum.

**4.4 An LLM that edits tracked source is tier B, and lands on a lane.** §12
rule 3 as amended by 015. Not the working tree, not trunk. The lane hygiene this
implies is blocked in gitman, at `.scratch/projects/39-lane-lifecycle-facts/`.

**4.5 Cost has no ceiling in this design.** A queue bounds concurrency. Nothing
bounds spend. A retry loop against a paid API is the one failure in this
document that a person pays for in money. **Decide whether a bound belongs here
or in the workflow, and say which.**

---

## 5. The options

Six. Each entry states the mechanism, what it costs, which law it touches, and
**what must be measured before it is chosen.** No option here is recommended in
advance; §6 says what to measure first.

### Option A — an external timer calls `devman run`

A systemd timer or cron entry runs `devman run <project> <workflow>`.

**Mechanism.** `devman run` **always** enqueues and never starts
(`src/devman/run.py:13`). The third arrow is made to re-enter through the first
arrow's path. The gate is then the same gate the watcher already passes.

**What it gives.** Zero new mechanism. Every refusal `run.py` already makes —
the unresolved-path refusal, the ambiguous-DAG refusal, the wrong-directory
refusal — applies unchanged.

**What it costs.** **The schedule leaves the repository.** §7.4 says a schedule
is *content*, exactly as a queue name is, and content lives in a workflow file.
This puts it in a systemd unit, where `doctor` cannot see it, the projection
does not manage it, and taking a group no longer brings its schedule. It also
re-introduces a per-machine unit per project — law 5, the plane learning a
project fact.

**Measure.** Whether a generated timer can be projected from the workflow's own
`schedule:` field, which would keep the fact in the repository and put only the
mechanism outside it.

### Option B — a scheduled dispatcher DAG that enqueues the real runs

One workflow carries the `schedule:`. Its steps are `action: dag.enqueue`
against the real workflows.

**Mechanism.** The scheduler starts one cheap DAG, ungated — which is legal,
because a dispatcher obeys "cheap by construction". Its children go through the
gate.

**Measured already, and this is the evidence it works.** S-8 ran two DAGs naming
`exclusive` (`max_concurrency: 1`) 12 ms apart. Under `action: dag.run` they ran
**concurrently**. Under `action: dag.enqueue` they **serialised, and the
scheduler logged the admission.**

**Rule 9 does not block this, and the distinction must be written down.** Rule 9
says a fan-out can respect the queue **or** learn whether the child failed, never
both, because `dag.enqueue` returns immediately. That killed the fan-out verify,
whose entire purpose was collecting verdicts. **A dispatcher does not want the
verdict.** Each child records its own outcome and `doctor` reads run history. The
property rule 9 removes is one this shape never needed.

**What it costs.** The dispatcher must name its children, so **it holds a list**.
A list of 54 project names in a shared group file is law 5 exactly. **This is the
option's central problem and the thing to solve first**: the dispatcher must
derive its fan-out from the registry rather than state it, and `doctor`'s
`fan-out` check requires a stated bound.

**Measure.** The cost of 54 `dag.enqueue` calls from one run. §12 rule 9 wants a
bound; find the real number before writing one.

### Option C — make Dagu's scheduler enqueue

Change the behaviour at its source, by configuration if it exists, and upstream
if it does not.

**Mechanism.** If Dagu 2.15.0 has a scheduler setting that routes a scheduled
run through the queue, this is one config line in the machine module and every
option below becomes unnecessary.

**What it gives.** The queue name in a scheduled workflow would mean what every
reader already assumes it means. It repairs the misreading that survived from
the charter into `maintain.yaml`'s comment until 009 caught it.

**What it costs.** If the setting does not exist, this is an upstream feature
request and a dependency on someone else's release. **It is also a machine-wide
behaviour change**: `maintain`'s 58 nightly dispatches would begin to serialise,
turning a 5-second burst into a queued drain, and `plane-report` would follow it
through the same gate 15 minutes later.

**PARTLY MEASURED AT KICKOFF, AND THE RESULT IS "NOT FOUND", NOT "DOES NOT
EXIST".** On dagu 2.15.0:

- `dagu scheduler --help` exposes **no queue-routing flag**. Its only flag is
  `--dags`. Its description says the scheduler "initiates DAG-run executions
  when their scheduled time arrives" **and separately** "also consumes DAG-runs
  from the queue and executes them" — two paths in one sentence, which is the
  behaviour S-1 measured.
- `dagu config` prints resolved **paths only**. It does not enumerate settable
  keys, so it neither confirms nor denies a scheduler option.

**This is not sufficient to reject Option C, and it must not be recorded as
one.** The binary embeds a web UI, so a strings search over it returns the UI's
vocabulary and is not evidence about the scheduler. **Finish this properly:**
read the 2.15.0 documentation and changelog for a scheduler-to-queue setting,
and if none is documented, run the direct test — give two DAGs the `exclusive`
queue and a `schedule:` one minute out, and see whether they serialise. That
test is the same shape as S-1 and takes two minutes.

### Option D — the workflow throttles itself

The schedule stays. The workflow's first step waits on a machine-wide semaphore.

**Mechanism.** A lock file or a counter under a known path, taken before the
call and released after.

**What it gives.** No new scheduling path. It works for a run started by any of
the three routes, which is a property no other option here has.

**What it costs.** **It re-implements the queue in shell, in a shared group
file, and it is the one option the plane cannot audit.** Law 7 wants shell to
stay a thin wrapper. A lock leaked by a killed run blocks every repository until
a person finds it. 013's finding applies directly: mutual exclusion is not the
same property as correct ordering, and it was measured failing at exactly this.

**Measure.** Nothing. **This option is here to be rejected in writing**, so it
is not proposed again in six months. Reject it on 013's evidence, not on taste.

### Option E — do not schedule LLM work at all

Fire it from a trigger, a hook, or by hand.

**Mechanism.** The two gated arrows already exist and already work. A commit
hook or a watcher glob reaches `dagu enqueue` through `devman run`.

**What it gives.** The whole problem disappears. It is also the honest reading of
the existing rule: if what the plane schedules must be cheap, and an LLM call is
not cheap, then **an LLM call is not something the plane schedules.**

**What it costs.** Some work is genuinely periodic and has no event — a weekly
digest, a nightly sweep. Those cannot be expressed. **Establish whether the
intended workload actually has an event.** Much of what reads as "nightly" is
"after the last commit of the day", and that is a trigger.

**Measure.** List the intended LLM workflows and mark each *event-driven* or
*genuinely periodic*. **If the list is entirely event-driven, Option E is the
answer and this project ships a paragraph.**

### Option F — `maxActiveRuns` — rejected, recorded so it is not re-proposed

Dagu bounds concurrent runs **of one DAG**. The problem here is 54 **different**
DAGs, one per repository, each running once. `maxActiveRuns` binds none of that.
It is the right tool for a workflow re-firing on itself and the wrong one here.

---

## 6. The order of work

1. **Option C's measurement.** One command. If a scheduler setting routes
   through the queue, most of this document is moot.
2. **Option E's list.** Enumerate the intended LLM workflows and mark each
   event-driven or periodic. This is a conversation, not a measurement, and it
   may end the project.
3. **Only then** choose between A and B, and reject D in writing.
4. **The sixth queue name is a charter change** and lands with the measurement
   that forced it.

## 7. Out of scope, and each is somebody else's project

- **The receipt** — 019. A dependency, not a duplicate.
- **Lane hygiene** — gitman 39.
- **Which LLM workflows are worth having.** 015 left three uninvestigated
  candidates: changelogs, docs sync, loci scaffolding. **This project builds the
  road and picks no destination.**

## 8. One discovery to follow up

`dagu 2.15.0` ships a **`human-task`** command, and nothing in this plane uses
it or mentions it. 015's amendment invented the lane as the review step because
"the plane has no review step". **Find out what `human-task` does before the
next project assumes the lane is the only shape available.**

---

## Verify before you save

```bash
devenv tasks run -v base:check
devenv tasks run -v base:test
devman doctor
```

**`devman` on PATH is a system Nix build and lags this tree** until a rebuild.
Run `doctor` from source when checking your own change.

**Tests must not shell out to real `git`.** The Nix sandbox has no git; 018 lost
a `base:test` this way. Stub the boundary.
