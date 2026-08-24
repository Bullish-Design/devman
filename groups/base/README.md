# base — the group every repository takes

`devman.groups = [ "base" ]` is the default, because `devenv.nix` is the
highest-coverage marker in the surveyed repositories — 58 of 68 (D4). This group
holds the leverage, so it stays small.

Stage 7 narrowed it. It ships **three files**, calls **two task names**, and the
ladder has **two rungs**.

## The hinge — one workflow, one step, one devenv task

> **A default workflow runs exactly one `devenv tasks run`. The workflow names
> the rung; the repository's devenv task graph decides what that rung pulls in.**

```yaml
# groups/base/workflows/check.yaml — the whole file
queue: light
steps:
  - name: check
    run: devenv tasks run -v base:check
```

Four things follow, and they are why the group looks like this:

- **Criterion 14 holds by construction.** A one-step workflow declares no order,
  so it cannot re-state an order devenv already declares. Before stage 7 the
  criterion held only because almost no repository declared a task dependency —
  and `pyjutsu` already declared one.
- **A language group has nothing left in it.** `python/check` existed to run a
  linter and a type checker in order. That order is a task graph, and devenv
  holds task graphs. The `python` group was deleted (`PROPOSAL.md` §1.1).
- **One devenv invocation per run.** `devenv tasks run` costs 0.16 s warm and
  1.44 s after a content change. Three invocations cost 4.3 s of devenv against
  1.44 s for one.
- **`type: chain` is gone.** The key existed to stop two `devenv tasks run`
  invocations in one checkout contending for one devenv state directory. One
  invocation removes the contention instead of serialising around it.

**What it costs, stated plainly.** Dagu's per-step status is lost: a failed run
shows `test: failed`, and which devenv task failed is inside devenv's output.
Measured at stage 7 (I-3), the loss is smaller than that sounds — the failing
task name reaches **three** places: the step's `stderr` file, the DAG-level log,
and **Dagu's own recorded `error` field**, which is the string the web UI shows.

**Read `.err`, not `.out`.** On devenv 2.1.2 the task's own output goes to stdout
and devenv's task ledger goes to stderr, and Dagu files the two separately. The
failing task name appears **0 times** in `check.*.out`. devenv 2.2.0 puts both
streams on stderr.

**The second trade: fail-fast for fan-out.** Under a devenv `after` list the
siblings run **concurrently**, so a failing task does not stop the others. A
repository that wants the old ordering states it in `devenv.nix`.

## The task names this group calls

A group's workflows call task names, and **task names are group-local
convention** (`CONCEPT.md` §7.1). Taking a group is an agreement to define that
group's names:

| Task | What the repository puts in it | Budget |
|---|---|---|
| `base:check` | the fast check that needs no build and runs no test | ≤ 5 s warm |
| `base:test` | the test suite | ≤ 5 min |

Two names, and the list is closed.

```nix
tasks."base:check".exec = "ruff check .";
tasks."base:test".exec  = "pytest";
```

**A budget is guidance, not a check.** Nothing in the plane notices a `check`
that grows to four minutes, and nothing will (§15.7).

**A repository that cannot honour a name does not define it.** `devman run check`
then fails loudly with devenv's own `no such task` error. Do not write
`base:check = true`: a workflow that reports success having checked nothing is
the one failure the whole charter exists to avoid (§15.7).

**The `base:` prefix is not decoration — devenv requires it.** An un-namespaced
name is an evaluation error:

```
× Invalid task name: check. Task names must be in format 'namespace:name'
```

**Two groups cost two names, not two bodies.** A devenv task needs no `exec` at
all: one with only `after` runs its dependency and then does nothing itself, and
a failure in the dependency still fails the run.

```nix
tasks."base:check".after = [ "python:lint" "python:typecheck" ];
tasks."base:test".after  = [ "python:test" ];
```

Measured on devenv 2.1.2 (`STAGE_2_LOG.md`, S5). This is also how a repository
adds a rung to a rung: `tasks."base:test".after = [ "base:check" ];` makes `test`
lint first, in the file where the developer can also run it by hand.

## The workflows

| File | Queue | Trigger | Writes | Runs |
|---|---|---|---|---|
| `check.yaml` | `light` (4) | manual; post-commit hook | no | `base:check` |
| `test.yaml` | `normal` (2) | manual; pre-push hook | no | `base:test` |
| `maintain.yaml` | `light` (4) | `schedule: 5 0 * * *` | only under `.devman/.runs/` | no repository task |

**There is no third rung.** `full-test` was deleted at stage 7 on a measurement:
its only content beyond `test` was `devenv test`, which **exits 0 having tested
nothing in 30 of the 58 devenv repositories** (`copyroom` 5.6 s, `nix-paseo`
15.2 s). A step whose success is indistinguishable from doing nothing is not a
rung (`PROPOSAL.md` §6).

**`review` was deleted too, and the loss is real.** It was the only workflow that
left a durable record of what the tree looked like when the checks last ran.
Against that: no trigger fired it, and every line of its report is one git
command away from a person already in the repository. A repository that wants the
document keeps its own copy under `.devman/workflows/review.yaml`.

**`base:lint` was renamed to `base:check`** at stage 7. Under the one-step rule
the workflow name and the task suffix are the same word, so a reader holds one
name instead of two.

## Why every step says `devenv tasks run -v`

`-v` is load-bearing and must not be tidied away. Without it `devenv tasks run`
captures the task's stdout and prints none of it, on the success path and the
failure path alike, so a step running `ruff check .` writes a log holding `{}`
and nothing else. `-v` is the only flag that restores it — `--show-output`
documents itself as equivalent and, measured, is not.

**Which stream the output lands on depends on the devenv version**, so no group
file should depend on one:

| devenv | plain | `-v` |
|---|---|---|
| 2.1.2 | stdout lost | task stdout on **stdout**, ledger on stderr |
| 2.2.0 | stdout lost | task stdout on **stderr**, beside the ledger |

## What is deliberately absent from every file

`name`, `working_dir`, and `log_dir`.

- A top-level `name:` makes `dagu validate` fail — "entrypoint document must not
  define name". A DAG's identity is its file name (A5).
- `working_dir` and `log_dir` are per project, so **the projection writes them**
  into each project's own generated copy, together with `env: DEVMAN_PROJECT_DIR`
  (`STAGE_6_LOG.md`, S2). A group file states none of the three.

`queue` stays, because it is the one thing that genuinely varies from workflow to
workflow (§7.2).

## `maintain`, and why it has to be a run

`maintain` calls no repository task. It prunes `.devman/.runs/reports/` older
than `KEEP_DAYS` (default 7), **counts artifacts and never deletes one**, and
writes one report.

```bash
devman run maintain                 # keep 7 days
devman run maintain KEEP_DAYS=30    # keep 30
```

**Its real job is to be a run.** `hist_retention_days` prunes Dagu's history and
the per-project log tree, but retention is **per DAG and fires when that DAG
runs** (§9.2). A project whose workflows never run keeps its log tree forever.
`maintain`'s nightly run is what makes retention fire in a repository nobody
touched this month. That is why it stays in `base` rather than becoming an opt-in
group, and why a machine-side pruner cannot replace it (`PROPOSAL.md` §10,
rejected alternative 5).

**It prunes reports and never artifacts.** A report is regenerable text; an
artifact is the thing you were about to ship. Deleting one unattended is exactly
§15.7's failure.

**`KEEP_DAYS` cannot default to the machine's `hist_retention_days`.** That is
Dagu's own field in `base.yaml` — inherited into a run rather than readable from
one, and reading the file would put a machine-specific absolute path into a group
workflow. The two numbers are stated in two places and this group says so.

**It stopped running `devman doctor` at stage 7.** `doctor` forks one
`dagu validate` per projected file — measured at 87.6 ms per file across the
whole rollout, so about 15 s at 54 projects. Run from here that is roughly 13
CPU-minutes a night producing 54 **identical** plane-wide reports. 54 identical
failures is not a signal; one is. The check moved to `devman`'s own
`plane-report`, which runs once for the machine.

## Running one of these on a schedule

**Use Dagu's own `schedule:` key.** `maintain` carries `schedule: "5 0 * * *"`,
so every repository that takes `base` is maintained without anybody writing a
systemd unit — and a repository that adopts `base` next month is maintained from
that night.

**This works only because the projection is generated.** Under `schedule:` the
enqueueing process is the Dagu daemon, which has one environment for the whole
machine. Before stage 6 a projection that interpolated `${DEVMAN_PROJECT_DIR}`
produced a run in a directory of that literal name (`STAGE_4_LOG.md`, S2). Since
stage 6 each project's projected copy states its own `working_dir`, `log_dir` and
directory variable, so the daemon needs nothing from a trigger.

> **A scheduled run does not pass through its queue.** Measured at stage 7 (S-1):
> 58 DAGs sharing one `schedule:` all started at once with queue depth 0, and two
> DAGs on `exclusive` — limit 1 — both started in the same second. The same 58 put
> through `dagu enqueue` never exceeded 4 and drained in 311 s. **Nothing throttles
> the scheduled set**, so anything you schedule must be cheap by construction.
> 54 repositories firing one cheap DAG at 00:05 costs 2 seconds; 58 concurrent
> `devman doctor` runs measured 139 s each against 14.3 s alone.

**Nothing carries a stagger, and nothing can.** A group file is shared, so an
offset written here gives every repository the same offset, and a per-repository
offset is a project fact held outside the project — which is `STAGE_5_LOG.md`
S9's timer problem in a new place.

**To opt out, use §7.3.** Shadow the file with your own
`.devman/workflows/maintain.yaml` and leave the key out, or do not take `base`.
There is no per-workflow Nix option, by §7.4: a schedule is content exactly as a
queue name is.

### Scheduling something for one project only

A timer is still the answer when the schedule belongs to one repository rather
than to a group:

```ini
# ~/.config/systemd/user/devman-nightly.service
[Service]
Type=oneshot
ExecStart=/run/current-system/sw/bin/devman run test --project siteman
```

`--project` is what makes this work from a timer, which has no working directory
in any repository. `devman run` resolves the path from the registry, exports
`DEVMAN_PROJECT_DIR`, passes it as a parameter, and **refuses with a message**
when it cannot.

**A timer holds project names, so it drifts, and only one direction tells you:**
a renamed project makes the unit fail loudly; a newly adopted project is simply
never scheduled, silently. That asymmetry is why `maintain` uses `schedule:`
instead.

## Triggering one of these on a commit

The plane supplies `devman run`. The hook that calls it is the repository's own,
and it is devenv's `git-hooks` module rather than anything of devman's:

```nix
git-hooks.hooks.devman-check = {
  enable = true;
  name = "devman check";
  entry = "devman run check";
  stages = [ "post-commit" ];
  pass_filenames = false;
  always_run = true;
};
```

devenv 2.1.2 first needs the input:

```bash
devenv inputs add git-hooks github:cachix/git-hooks.nix --follows nixpkgs
```

Three things to know before taking it (measured in `STAGE_3_LOG.md`, S9):

- **It is not a gate.** `devman run` enqueues and returns, so the commit is not
  blocked and the workflow starts a second or two later. A repository that wants
  to stop a bad commit wants a `pre-commit` hook that runs the task directly.
- **The run reads the tree it finds**, which is the tree after the commit rather
  than the tree that was committed.
- **It costs a devenv input** — about 20 ms on every shell entry — and a
  generated `.pre-commit-config.yaml` in the working tree.

Hooks stay with the repository on purpose (§8). A `[hooks]` table in
`triggers.toml` was considered and rejected: it would charge every taker of the
group 20 ms of shell entry forever, against criterion 7's 10 ms budget for the
whole module (`PROPOSAL.md` §10, rejected alternative 6).
