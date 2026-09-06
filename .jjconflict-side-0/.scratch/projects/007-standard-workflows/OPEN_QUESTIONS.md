# Open questions — the standard workflow set

What the design session could not settle, and the measurement that would settle
each one. Twelve entries. The first three gate the rollout in `PROPOSAL.md` §8;
the rest can be answered while it proceeds.

Each entry states the question, why it is open, and the exact command or
observation that closes it.

---

## The three that gate the rollout

### 1. Does the `light` queue absorb 58 simultaneous `maintain` dispatches?

**Open because** the plane has never had more than 6 projects. `maintain` names
`light`, whose limit is 4 (`nix/nixos-module.nix`). At `5 0 * * *` all 58
repositories enqueue in the same minute. Criterion 12 says queues are real, and
it was proved with **two** workflows, by hand, on the `exclusive` queue.

**Settled by** watching one night at about 40 projects and again at 58, and
recording three numbers: the maximum queue depth from
`GET /queues/light/items`, the wall-clock gap between the first dispatch and the
last completion, and whether any run reports a status other than `succeeded`.

**What each answer means.** Under about two minutes: nothing to do, and criterion
12 has its first real measurement. Over about ten minutes: raise `light`'s limit,
which is one machine-side number and the only legal carrier of a stagger
(`PROPOSAL.md` §5). If runs fail rather than wait, the queue is not doing what
criterion 12 claims and the proposal's schedule shape is wrong.

---

### 2. What does `devman doctor` cost at 58 projects?

**Open because** the only figure is **2.9 s at 6 projects and 36 workflows**,
measured today. `doctor` runs one `dagu validate` subprocess per projected file
(`src/devman/doctor.py`, `check_load`), so the cost is linear in workflows.
`PROPOSAL.md` §5 extrapolates to about 14 s at 58 projects × 3 workflows, and
labels that as extrapolation.

**Settled by** timing `devman doctor` at each rollout batch — 6, 20, 30, 40, 50,
58 projects — and plotting the five numbers. This costs nothing extra: wave 4
already records it.

**What each answer means.** Under 30 s: `plane-report` runs it nightly, once, and
the proposal stands. Over 30 s: either `doctor` gains a project scope, or
`plane-report` pages the plane across several nights. **Do not solve it by
putting `doctor` back into `maintain`** — that is the 58-identical-reports
problem the split exists to remove.

---

### 3. How many of the 58 repositories pass their own `base:test` today?

**Open because** nobody knows, and it decides two things: whether wave 4 is a
week of adoption or a month of repairs, and whether a scheduled `test` would be a
signal or a wall of red (`PROPOSAL.md` §10, rejected alternative 7).

**Settled by** one sweep, before wave 4: in each of the 58, run the command the
repository would put in `base:test` and record pass, fail, or "no suite". This is
a read-only sweep and needs no adoption.

**What each answer means.** If most pass, a nightly `test` becomes worth
reconsidering and rejected alternative 7 reopens with evidence. If most fail,
adoption must not imply repair — `base:test` is defined as what the repository
runs today, failing or not, and fixing it is separate work.

---

## The rest

### 4. Should `doctor` check that a `format` glob and its hash agree?

**Open because** `PROPOSAL.md` §4 states the widening rule — adding a glob to
`triggers.toml` requires widening the hash in `format.yaml` — and **nothing
enforces it**. The failure is silent in the worst way: the new language's saves
fire a run whose precondition is never true, so the run reports `Succeeded` with
a skipped step, which is exactly what a correct loop-break produces. A reader
cannot tell "nothing to do" from "never does anything".

**Settled by** deciding whether `doctor` may read inside a workflow body. It
already does, three times: the `handlers` check, the `cross-repo` check
(`action: dag.run` and `DEVMAN_SELF_DIR`) and the `queue names` check all grep
the projection. A fourth grep is no new capability. The argument against is that
comparing a glob list to a `find` expression is a heuristic, and §15.7 says the
plane does not grow heuristics.

**Cheaper answer to consider first:** ship the glob list once, in
`triggers.toml`, and have the workflow read it — which needs the workflow to know
its own group's store path, and it does not. Record why that is closed before
proposing the grep.

---

### 5. Does a one-step workflow's log still name the devenv task that failed?

**Open because** this is the one real loss in the one-step rule
(`PROPOSAL.md` §1.1). Today a failed `python/validate` shows `typecheck: failed`
as a Dagu step with its own log file. Tomorrow it shows `test: failed` and the
reason is inside devenv's output. `-v` exists because devenv's own output is what
a reader reads (`STAGE_2_LOG.md`, S4), so the information should still be there —
but "should" is not a measurement.

**Settled by** one experiment in `devman`: define `tasks."base:test".after =
[ "a" "b" "c" ]`, make `b` fail, run `devman run test`, and read
`.devman/.runs/logs/devman-test/…`. The question is whether the log names `b`.

**What each answer means.** If it names `b`, the loss is cosmetic and the
one-step rule is free. If it does not, the rule keeps its other four benefits and
this becomes a devenv issue to file — **not** a reason to write the order twice
in a workflow, which criterion 14 forbids.

---

### 6. Should the plane notice a schedule it missed?

**Inherited from stage 6**, which recorded it rather than answering it. Dagu
fires on a cron expression; a machine asleep at 00:05 missed 00:05. At 6
repositories that is one lost `maintain`. At 58 it is 58, and the visible symptom
is 58 report directories that stopped ageing — which is `doctor`'s check 6 firing
everywhere at once, for a reason that is not the reason check 6 exists.

**Settled by** suspending the machine over 00:05 once, and reading what `doctor`
says the next morning. If check 6 fires on all 58, the check needs to know the
difference between "this project stopped running" and "the machine was asleep".

**Note** that Dagu has no catch-up setting this plane uses, and adding a systemd
timer to compensate puts project names back outside repositories — the thing
stage 6 deleted.

---

### 7. What caused the three-minute silence in `STAGE_6_LOG.md` S3?

**Inherited and still unexplained.** A DAG the daemon already knew, without a
schedule, that then *gained* one, took three scheduled minutes to fire and a
restart cured it. Adoption, removal and a changed expression were each measured
and need no restart, so the steady state is fine.

**It matters more at 58 than at 6**, because the transition it describes — an
existing DAG gaining a schedule — is exactly what `PROPOSAL.md` §6's rename does
to every repository that re-pins.

**Settled by** watching one wave-1 repository re-pin and timing the first
`maintain` dispatch afterwards. If it is late by minutes, the rollout instruction
gains one line: restart the daemon once after each wave. Stage 6 called this a
Dagu source question, and it can stay one — the plane only needs to know whether
to restart.

---

### 8. Do 7 of 58 repositories using git hooks mean the recipe does not work?

**Open because** `check` and `test` have no trigger the plane ships. The hook is
the repository's own by §8's design, and today `nixbuild`, `clinch`, `devman`,
`observantic`, `loci-core`, `pydantree` and `webdantic` are the only ones with
any hook at all. If that number is still near 7 after wave 4, the two rungs are
manual-only in practice and the ladder is doing less than the table claims.

**Settled by** counting `git-hooks` users again at the end of wave 4, and asking
one question of the repositories that did not take it: was it the 20 ms input
cost, the generated `.pre-commit-config.yaml`, or that nobody read the README.

**What each answer means.** If the cost is the reason, `PROPOSAL.md` §10's
rejected alternative 6 reopens with evidence. If it is the README, the fix is
documentation, not design.

---

### 9. Does §15.2's whitelist actually refuse `fsdantic`?

**Open because** §15.2 has **never fired**. The survey that produced the
whitelist found four `.devman/` shapes and predicted the rule would almost never
run. Today exactly one repository in 68 carries a colliding `.devman/`:
`fsdantic`, holding `.devman/store/vendor/agentfs` — the "vendored store" shape.

**Settled by** wave 3, which exists for this. Enter `fsdantic`'s shell with
`devman.enable = true` and read what registration says.

**The failure to watch for** is silent adoption: a registry entry appears,
`fsdantic` gains a `.devman/workflows/` beside its `store/`, and nothing reports
that a directory the plane does not recognise is now inside a directory the plane
manages. §15.2 also notes the collision runs the other way — the older `devman
0.2.0`'s `init --force` calls `shutil.rmtree` on `.devman/`.

---

### 10. What happens to `maintain` in a repository checked out twice?

**Open because** run output belongs to a **working tree**, and the registry holds
one path per **project** (§9.2). `maintain` runs in `working_dir`, which is the
registered checkout, so a second worktree's `.runs/` is pruned by nobody and its
log tree never ages out.

**This is not hypothetical.** `devman` is checked out twice right now — the
primary at `~/Documents/Projects/devman` and this branch at
`~/.paseo/worktrees/1n48r26y/special-dragon`.

**Settled by** looking, after wave 1: does either `devman` checkout hold a
`.runs/` that stopped ageing, and does `doctor`'s check 6 see it? The answer may
be that this is correct behaviour stated badly rather than a defect — a second
worktree is a place you work, not a project the plane serves.

---

### 11. Is a nightly cross-repository security audit worth building?

**Deferred rather than refused** in `PROPOSAL.md` §5. It reads only, so §8's
reactivity argument does not reach it, and it is the one candidate in the
kickoff's list that survives the sort. What blocks it is shape: 58 per-project
audits produce 58 reports nobody reads, which is §12's rule 7. It wants to be one
cross-repository workflow in `devman` — and §11's mechanism is `action: dag.run`
over child DAGs, which means each of the 58 needs an `audit` workflow to be
called.

**Settled by** answering one narrower question first: what does `pip-audit` or
`nix flake check` report across the 58 today, run by hand, once? If the total is
a handful of findings, one hand-run sweep per quarter is the right tool and no
workflow is needed. If it is dozens and moving, the shape question becomes worth
solving.

---

### 12. Do `pyjutsu` and `paloma-story-generation` stay served by `base` alone?

**Open because** each is the only repository in its ecosystem — Rust+Python and
Node — and §16's promotion rule means neither gets a group. `pyjutsu` already
proves the answer for Rust: it aliases `base:check` and `base:test` onto
`pyjutsu:*`, which run its own build and test chain, and it has worked since
stage 5. `paloma-story-generation` is untested and carries **no `devenv.nix`**,
so it is outside the plane entirely today.

**Settled by** deciding whether `paloma-story-generation` should carry a
`devenv.nix` at all. If yes, it takes `base` with `base:check = npm run lint` and
`base:test = npm test`, and the contract is proved in a fourth ecosystem. If no,
the inventory's honest denominator is **57**, not 58, and every count in
`PROPOSAL.md` shifts by one.

---

## What is deliberately not open

Three things a reader might expect to find here.

**Whether the universal contract survives a non-Python repository.** It is not
open. `siteman` has no language files and defines both names; `nix-paseo` is a
Nix flake and defines both names. Both have run through the plane for two stages.

**Whether whole-file shadowing is coarse enough.** Closed at stage 3 by decision
(§16), and this proposal reduces the pressure on it rather than adding to it:
five default workflows instead of nine, and one repository-level shadow deleted.

**Whether the schedule belongs in the workflow file.** Settled at stage 6, on the
installed daemon, with `trigger: scheduler` in the evidence. This proposal adds a
second scheduled workflow and changes nothing about the mechanism.
