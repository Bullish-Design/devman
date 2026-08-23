# Proposal — the standard workflow set

> **Design session. No implementation code was written.** Every number below is
> either measured on this machine on 2026-08-23, quoted from a stage log, or
> labelled as arithmetic over a measurement.

**The inventory moved since the kickoff was written.** Re-counted today under
`~/Documents/Projects`: **68** git repositories, **58** carrying `devenv.nix`,
**53** carrying `pyproject.toml`. The kickoff says 67 / 57 / 52. One repository
(`agentfs`) arrived. The gap the session exists to close is unchanged: **6
registered, 58 eligible.**

---

## 1. The recommendation, in ten lines

1. **One workflow, one step, one devenv task.** The repository's devenv task
   graph owns every order. Nothing in a group file re-states it.
2. **The ladder has two rungs**: `check` (fast, no build) and `test` (the
   suite). `validate` and `full-test` go.
3. **The universal contract stays and shrinks to two names**: `base:check` and
   `base:test`. Every one of the six registered repositories already honours a
   contract of this shape, including the two the kickoff predicted would break.
4. **Delete the `python` group.** A language's decomposition is a devenv task
   graph, not a Dagu file.
5. **Three groups**: `base` (`check`, `test`, `maintain`), `format` (`format`),
   `release` (`release`).
6. **A workflow deserves its own group when taking it costs the repository
   something it cannot decline any other way** — a task name it must define, or
   a write to its own files it did not ask for.
7. **`maintain` stops running `devman doctor`.** One nightly plane report, owned
   by `devman`, runs it once for the machine instead of 58 times.
8. **Nothing else gets scheduled.** Dependency updates and publishing never
   become workflows.
9. **Nine workflows become five.** Deleted: `validate`, `full-test`, `review`,
   `python/check`, `python/validate`.
10. **Rollout**: `devman`, then the five already registered, then `webdantic`,
    `poddantic`, `parsedantic`, `nix-desktop`, `loci.nvim`, then the rest in
    batches of ten.

### 1.1 The hinge — one workflow, one step, one task

Every other recommendation follows from this one, so it is stated first.

> **A default workflow runs exactly one `devenv tasks run`. The workflow names
> the rung; the repository's devenv graph decides what that rung pulls in.**

```yaml
# groups/base/workflows/check.yaml — the whole file
queue: light
steps:
  - name: check
    run: devenv tasks run -v base:check
```

A repository that wants `test` to lint first writes one line in `devenv.nix`:

```nix
tasks."base:test".after = [ "base:check" ];
```

**Four consequences, and they are the proposal.**

**It makes criterion 14 true by construction.** Criterion 14 says no default
workflow may re-state a dependency devenv already declares. Every multi-step
file in the current nine is a hand-written topological order over devenv tasks.
Today the criterion holds only because almost no repository declares a
dependency — and `pyjutsu` already declares one
(`tasks."pyjutsu:test".after = [ "pyjutsu:build" ]`). The criterion is one
`devenv.nix` edit away from being false in a repository nobody would edit for
that reason. The one-step rule removes the possibility.

**It deletes the `python` group's content.** `python/check` exists to run a
linter and a type checker in order. That order is a task graph, and devenv holds
task graphs. Written as a graph it is `tasks."base:check".after = [ "python:lint"
"python:typecheck" ]`, in the repository, where the developer can also run it by
hand. Written as a workflow it is a second copy of the same fact in a file the
plane promises never to parse. See §3.

**It removes a devenv invocation per step.** Spike A: `devenv tasks run` costs
0.16 s warm, 5.46 s cold, **1.44 s after a content change** (`CONCEPT.md`
§12.2). `python/validate` makes three invocations, `base/full-test` four. On the
path that matters — a tree that just changed — three invocations cost 4.3 s of
devenv against 1.44 s for one. That is arithmetic over a recorded measurement,
not a new measurement.

**It removes the reason `type: chain` exists in every file.** `groups/base/README.md`
gives the reason: two `devenv tasks run` invocations in one checkout contend for
one devenv state directory. One invocation per workflow removes the contention
rather than serialising around it.

**What it costs, stated plainly.** Dagu's per-step status is lost. Today a failed
`python/validate` shows `typecheck: failed` in the UI with its own log file;
tomorrow it shows `test: failed` and the reason is inside devenv's output. The
`-v` flag already exists because devenv's own output is what a reader reads
(`STAGE_2_LOG.md`, S4), so the information does not disappear — its location
changes from a step name to a log line. **This is the one real loss in the
proposal**, and OPEN_QUESTIONS §10 names the measurement that decides whether it
is acceptable.

---

## 2. The universal contract

**Answer: option A — a universal contract, and it is two names.**

| Task | What it means | Queue budget |
|---|---|---|
| `base:check` | the fast check that needs no build and runs no test | ≤ 5 s warm |
| `base:test` | the test suite | ≤ 5 min |

**`base:lint` is renamed to `base:check`.** Under the one-step rule the workflow
name and the task suffix are the same word, so a reader holds one name instead of
two. Today workflow `check` calls task `lint`, which is a split a reader has to
learn.

### Why option A, tested against the three cases the kickoff names

The kickoff asks the contract to survive a Nix flake repository, a Neovim
configuration, and `siteman`. **All three are already answered on disk.**

| Case | Repository | What it defines today |
|---|---|---|
| Nix flake | `nix-paseo` | `base:lint = nix flake check --no-build`, `base:test = nix flake check` |
| no language files | `siteman` | `base:lint = fmt-check && lint`, `base:test = ci` — shell functions from its own devenv |
| Neovim | none registered yet | `loci.nvim` carries `lua/` and a flake; `nixvim` and `nix-nvim` are Nix |

`siteman` is the kickoff's own hardest case and it honours the contract with two
ordinary lines. `nix-paseo`'s two commands differ only by `--no-build`, which is
the thinnest honest split in the inventory and still a real one: one builds
nothing and one builds everything, which is exactly the two rungs.

Three of the six honour the contract by **aliasing**, at one line each and no
duplicated command body (`STAGE_2_LOG.md`, S5):

```nix
tasks."base:check".after = [ "python:lint" "python:typecheck" ];
tasks."base:test".after  = [ "python:test" ];
```

### What a repository that cannot honour a name does

**It does not define the name, and `devman run check` fails loudly** with
devenv's own "no such task" error. That is the whole answer.

**Option C — the null implementation — is rejected.** `base:check = true` makes
`check` a workflow that reports success having checked nothing. That is the
failure the whole charter is built to avoid: a successful run that did the wrong
thing (`CONCEPT.md` §15.7). §12 of this proposal makes it a rule.

**Option B — no universal contract — is rejected** because it costs more than it
saves. Under it, `base` would ship only `maintain`, and every executing workflow
would come from a language group. The 58 devenv repositories break down as
**50 Python** (one of which, `pyjutsu`, is also Rust), **6 Nix**, **1 Lua**
(`loci.nvim`) and **1 with no language files** (`siteman`). Option B therefore
trades two task names for at least three groups, and §16's own promotion rule
forbids two of them: `lua` and `rust` serve one repository each. It also leaves
`siteman` with no executing workflow at all.

**Adoption cost of the contract: two lines.** That is the whole of what `base`
asks of a repository.

---

## 3. The group table

**The rule for when a workflow deserves its own group:**

> **A group exists when taking it costs the repository something it cannot
> decline any other way: a task name it must define, or a write to its own files
> it did not ask for.**

This replaces the candidate rule the kickoff offers ("a group per trigger
class"). Trigger class is close but not the property that matters. `maintain`
fires itself on a schedule and is still safe to ship inside `base`, because
everything it writes is under `.devman/.runs/`, which the plane created, git
ignores and the watcher ignores. `format` fires itself **and rewrites the
developer's source**, which is a cost only a group can decline. The distinction
is what the workflow touches, not what fires it.

**A language is not a reason for a group.** A language differs in what a task
*is*, and `devenv.nix` already holds that.

| Group | Purpose | Workflows | Required tasks | Who takes it |
|---|---|---|---|---|
| `base` | the universal contract and the plane's own housekeeping | `check`, `test`, `maintain` | `base:check`, `base:test` | **all 58 devenv repositories** |
| `format` | saving a file reformats it | `format` | `format:fmt` | opt-in. `devman` today; then any repository that wants it |
| `release` | build an artifact behind a policy gate | `release` | `release:build` | `devman`, `observantic` |

Three groups, down from four. `groups = [ "base" ]` is the default and covers
every repository in the inventory.

### What the population takes, by name

| Population | Count | Groups | Cost |
|---|---|---|---|
| Python libraries and applications — `fsdantic`, `poddantic`, `webdantic`, `parsedantic`, `observantic`, `pydantree`, `templateer_v2`, `docman`, `eventic`, `flora`, `flora-core`, `flora-qc`, and 38 more | 50 | `[ "base" ]` | 2 task lines |
| Nix module and configuration flakes — `nix-paseo`, `nix-desktop`, `nix-secrets`, `nixbuild`, `nix-nvim`, `nixvim` | 6 | `[ "base" ]` | 2 task lines, both `nix flake check` shaped |
| Neovim plugin — `loci.nvim` | 1 | `[ "base" ]` | 2 task lines, `luacheck` and a headless `nvim` run, or the flake's own check |
| No language files — `siteman` | 1 | `[ "base" ]` | 2 task lines, already written |
| **Total in scope** | **58** | | |
| Rust + Python — `pyjutsu` | *within the 50* | `[ "base" ]` | 2 alias lines onto `pyjutsu:*`, already written |
| The plane — `devman` | *within the 50* | `[ "base" "format" "release" ]` | 4 task lines |
| Node — `paloma-story-generation` | out of scope | no `devenv.nix` | — |

**The Nix-only repositories take `base`, and nothing else.** The kickoff asks
this question directly and says there are eleven. Re-counted today, the eleven
split three ways: **6 carry `devenv.nix`** and are in scope
(`nix-paseo`, `nix-desktop`, `nix-secrets`, `nixbuild`, `nix-nvim`, `nixvim`);
**4 carry only `flake.nix`** and are out of scope until they gain a `devenv.nix`
(`nix-meta`, `nixos-core`, `nix-terminal`, `silverbullet-server`); and `siteman`
is the eleventh, which is not a Nix repository but a repository with no language
files at all.

The answer for the six is that the Nix case was never the hard one —
`nix flake check` splits cleanly into `--no-build` and full, which is the
two-rung ladder without any invention. `nix-paseo` has run it for two stages.

**A Neovim configuration takes `base`.** `nixvim` and `nix-nvim` are Nix flakes
and take the Nix answer. `loci.nvim` carries Lua and a flake, so either answer
works and the repository picks.

### Answering the two failure modes

**Too few groups.** A repository takes `base` and inherits nothing it must
decline: `check` and `test` call names it defined on purpose, and `maintain`
calls nothing. There is no `release` to be rid of, because `release` is its own
group.

**Too many groups.** The common adoption is one word: `groups = [ "base" ]`. The
worst adoption in the inventory is `devman`'s three. Nothing in this proposal
approaches the seven-group example the kickoff warns about, because the one-step
rule deleted the only class of group that multiplies — the language group.

---

## 4. The workflow table

| Workflow | Group | Queue | Trigger | Writes files | Rung |
|---|---|---|---|---|---|
| `check` | `base` | `light` (4) | manual; post-commit hook, the repository's own | no | **1** |
| `test` | `base` | `normal` (2) | manual; pre-push hook, the repository's own | no | **2** |
| `maintain` | `base` | `light` (4) | schedule `5 0 * * *` | only under `.devman/.runs/` | — |
| `format` | `format` | `light` (4) | watcher, `**/*.py` | **yes — source files** | — |
| `release` | `release` | `heavy` (1) | manual | a report and artifacts | — |

Queue limits are the machine's: `light 4, normal 2, heavy 1, gpu 1,
exclusive 1` (`nix/nixos-module.nix`).

### The ladder, rung by rung

| | `check` | `test` |
|---|---|---|
| Trigger | manual, post-commit | manual, pre-push |
| Queue | `light`, limit 4 | `normal`, limit 2 |
| Budget | ≤ 5 s warm | ≤ 5 min |
| What it tells you | this tree does not lint, or does not typecheck | the suite passes |
| What the rung below did not tell you | — | that the code runs, not only that it reads correctly |

**A budget is guidance, not a check.** §15.7 is explicit that nothing in the
plane notices a `check` that grows to four minutes, and this proposal grows no
heuristic to notice it.

**There is no third rung, and the measurement is why.** See §6.

### The trigger matrix

| Workflow | save | commit | push | schedule | manual |
|---|---|---|---|---|---|
| `check` | — | ✓ | — | — | ✓ |
| `test` | — | — | ✓ | — | ✓ |
| `maintain` | — | — | — | ✓ | ✓ |
| `format` | ✓ | — | — | — | ✓ |
| `release` | — | — | — | — | ✓ |

Every workflow has at least one trigger. Nothing is dead weight.

**The hook column is a recipe, not something a group ships, and that is
deliberate.** §8 puts hooks with the repository, and the plane supplies no
option for one. Today **7 of 58** repositories configure `git-hooks` at all
(`nixbuild`, `clinch`, `devman`, `observantic`, `loci-core`, `pydantree`,
`webdantic`). §10 records the rejected alternative that would change this and
the condition that would reopen it.

**`check` is deliberately not fired by a save.** Every repository here has a
Neovim configuration with a language server that already reports the same
findings, synchronously, next to the cursor, in tens of milliseconds. The
plane's round trip after a content change is 1.44 s and lands in a log file. A
workflow that duplicates an editor is slower and invisible. §12 makes this a
rule.

### Criterion 13 — the loop, and the rule for widening a glob

`format` keeps the shape `python-format/format.yaml` already has: a step-level
`preconditions:` comparing a content hash of every `.py` file against the hash
stored after the last run. Copied, not replaced, because it is measured
(`STAGE_3_LOG.md`, S6) and because a hash is the only mechanism where **your own
edit still fires**.

**The glob stays `**/*.py`.** No Nix or Lua repository has asked for
format-on-save: **no repository under `~/Documents/Projects` takes
`python-format` at all** — the only taker is `devman` itself. §16's promotion
rule applies to a glob as much as to a file, so a glob arrives when a repository
wants it.

> **The widening rule, stated in advance.** Adding a glob to `triggers.toml`
> requires widening the hash in the same edit. A glob whose files the hash does
> not cover fires a run whose precondition is never true, so the new language's
> saves produce a run that skips and never formats. That failure is silent: the
> run reports `Succeeded` with a skipped step, which is exactly the status a
> correct loop-break produces. Nothing checks it (OPEN_QUESTIONS §4).

### Criterion 14 — the task graph exists once

Satisfied by construction. A one-step workflow declares no order, so it cannot
re-state one. This is the strongest reason for §1.1 and it holds permanently
rather than by everyone's continued care.

---

## 5. The scheduled set

| Workflow | Where it lives | Schedule | Reads or writes |
|---|---|---|---|
| `maintain` | `groups/base/workflows/` | `5 0 * * *` | writes only under `.devman/.runs/reports/` |
| `plane-report` | `devman/.devman/workflows/` | `20 0 * * *` | writes only under `devman`'s own `.runs/reports/` |

Two scheduled workflows. `maintain` runs in every registered repository.
`plane-report` runs **once for the machine**.

### `maintain` loses its second step, and gains a stated reason to exist

Today `maintain` prunes this project's reports and then runs `devman doctor`.
The second half does not scale, and the arithmetic is the argument:

- `devman doctor` runs **one `dagu validate` subprocess per projected file**
  (`src/devman/doctor.py`, `check_load`). Measured today: **2.9 s** at 6
  projects and 36 workflows.
- At 58 projects × 3 workflows that is 174 files, so roughly **14 s** per run.
  That figure is extrapolation, not measurement.
- 58 repositories × 14 s = about **13 CPU-minutes every night**, producing **58
  identical plane-wide reports**.

**58 identical failures is not a signal. One is.** So `devman doctor` moves to
`plane-report`, which runs once, and `maintain` keeps only the work no other
owner has: pruning `.devman/.runs/reports/` older than `KEEP_DAYS`, and counting
artifacts without ever deleting one.

> **`maintain`'s real job is to be a run, and this is not written down
> anywhere.** `hist_retention_days` prunes Dagu's history and the per-project log
> tree, but retention is **per DAG and runs when that DAG runs** (§9.2). A
> project whose workflows never run keeps its log tree forever. `maintain` is the
> nightly DAG that makes retention fire in a repository nobody touched this
> month. That is why it stays in `base` rather than becoming an opt-in group, and
> why a machine-side pruner cannot replace it (§10, rejected alternative 6).

### The schedule shape at 58 repositories

**58 simultaneous dispatches at `5 0 * * *` are fine, and the queue is what makes
them fine.** `maintain` names `light`, limit 4, so 58 enqueued runs proceed four
at a time. After `devman doctor` is removed, each run is a `find` over one
repository's report directory — milliseconds of work. Total wall clock is
seconds.

**Nothing carries a stagger, and nothing should.**

- **Not the expression.** A group file is shared, so an offset written there
  gives all 58 repositories the *same* offset. A per-repository offset requires
  shadowing 58 files, which is `STAGE_5_LOG.md` S9's timer problem in a new
  place: a project fact held outside the project, that nobody remembers to
  update.
- **The queue, if anything.** The concurrency limit is machine-side, it is one
  number, and §4 already lets the machine state how much may run at once. It is
  the only legal carrier.

**The second-order effect, stated.** For those seconds the `light` queue is
saturated, so a `format` fired by a developer at 00:05 waits. That is acceptable
and self-limiting.

### The candidates, sorted

| Candidate | Reads or writes | Verdict |
|---|---|---|
| repository-health digest across all projects | reads only | **accepted** — this is `plane-report` |
| stale-branch report | reads only | **folded into `plane-report`** — per project it is noise; across 58 it is a list |
| security audit (`pip-audit`, `nix flake check`) | reads only | **deferred**, not refused. See OPEN_QUESTIONS §3 |
| documentation build | writes | **refused** — nobody asked for it, and its output is either ignored or tracked |
| `nix flake update`, `uv lock` | **writes tracked source** | **refused**, and the reactivity answer is below |

**The reactivity answer for dependency updates.** The write lands at 03:00 with
nobody present. What fires next is: **nothing, and that is the problem.** The
watcher's glob is `**/*.py`, so `devenv.lock` and `uv.lock` fire no workflow at
all. The tree is simply dirty the next morning. Three things follow, and each is
worse than the last: `release`'s clean-tree gate refuses every release until
somebody looks; the developer's next `git status` shows a change nobody wrote;
and if the update broke the build, the plane produced it and cannot say why. A
dependency update is a change a person reviews. **It never becomes a workflow**
(§12).

---

## 6. What is deleted or renamed

### Deleted

| Workflow | Why | Migration |
|---|---|---|
| `base/full-test` | **measured vacuous** — see below | a repository whose `enterTest` differs from `base:test` folds it into `base:test`, or keeps its own `.devman/workflows/full-test.yaml` |
| `base/validate` | renamed to `base/test` | none for a repository; `release`'s gate string changes, see below |
| `base/review` | no trigger fires it, and a person reads `git status` faster | `devman show review` before the change lands, saved to `.devman/workflows/review.yaml` |
| `python/check` | content is a devenv task graph (§1.1) | `tasks."base:check".after = [ "python:lint" "python:typecheck" ]` |
| `python/validate` | same | `tasks."base:test".after = [ "python:test" ]` |
| the `python` group | nothing left in it | `groups = [ "base" ]` |

**`full-test` is deleted on a measurement, not a preference.** Its only content
beyond `validate` is a third step, `devenv test`. Measured today:

- **30 of the 58 devenv repositories define no `enterTest` at all.** In those,
  `devenv test` **exits 0 having tested nothing**: `copyroom` 5.6 s, `nix-paseo`
  15.2 s.
- **`nix-paseo` is a registered project taking `base`.** Its `full-test` runs
  `nix flake check --no-build`, then `nix flake check`, then 15.2 seconds of
  nothing, and reports success.
- **`siteman` already shadowed the file for the opposite reason**: its
  `enterTest` *is* `base:test`, so the third step re-ran finished work for 14 s
  and printed nothing (`siteman/.devman/workflows/full-test.yaml`).

A step that exits 0 without testing anything, in more than half the population,
is §12's rule made concrete. The rung carries no information a reader can rely
on, so it is not a rung.

**`review` is deleted, and the loss is real.** It is the only workflow that
leaves a durable record of what the tree looked like when the checks last ran.
Against that: no trigger fires it, and every line of its report is one git
command away from a person who is already in the repository. `metadata.jsonl`
and the log tree keep the run record. A repository that wants the document takes
it as its own file, which §7.3 already allows and which costs the plane nothing.

### Renamed

| From | To | Who is affected |
|---|---|---|
| workflow `base/validate` | `base/test` | `release`'s gate reads `<project>-validate`; it becomes `<project>-test` |
| task `base:lint` | `base:check` | 6 repositories, one line each |
| group `python-format` | `format` | `devman` only |
| task `python-format:fmt` | `format:fmt` | `devman` only |

**Why rename `python-format` to `format`.** Under §3's rule the group exists
because of the trigger and the write, not the language. Naming it after the
language says the language is the reason, which is what this proposal argues
against. The glob stays `**/*.py`; widening it later is a `triggers.toml` edit
under §4's widening rule, not another group rename.

### The shadow question the kickoff asks

The kickoff notes that `observantic` and `pydantree` already shadow `check`, and
that a rename breaks a shadow. **That shadow is between two groups, not between
a repository and a group**: `python/check` shadows `base/check` by §7.3's group
order. Deleting `python` does not break a shadow — it removes the shadowing
file, and `base/check` wins by being the only candidate. Both repositories must
then define `base:check`, which they do today as an alias onto `python:lint`.
The migration is to extend that alias by one entry so it also covers
`python:typecheck`, which they currently reach only through the shadowing
workflow.

**One repository-level shadow exists and it is deleted with its target**:
`siteman/.devman/workflows/full-test.yaml` shadows a file that will not exist.
`siteman` deletes it in the same sitting.

### The migration, per repository

| Repository | Edits | What changes |
|---|---|---|
| `devman` | 3 | `groups = [ "base" "format" "release" ]`; `base:lint` → `base:check`; `python-format:fmt` → `format:fmt` |
| `siteman` | 2 | `base:lint` → `base:check`; delete `.devman/workflows/full-test.yaml` |
| `nix-paseo` | 1 | `base:lint` → `base:check` |
| `pyjutsu` | 1 | `base:lint` → `base:check` (still an alias onto `pyjutsu:lint`) |
| `pydantree` | 3 | `groups = [ "base" ]`; `base:check.after = [ "python:lint" "python:typecheck" ]`; `base:test.after = [ "python:test" ]` |
| `observantic` | 3 | `groups = [ "base" "release" ]`; the same two alias lines |

**Thirteen lines across six repositories.**

### Why this is not a flag day

**Only one workflow is scheduled, and it calls no repository task.** In the
window between the group files landing and a repository re-pinning, that
repository's `check` and `test` call a task name it has not defined yet. Both are
manual-only. So **no automatic run breaks**: `maintain` keeps working, because
it calls nothing, and a human who types `devman run check` too early gets
devenv's own "no such task", which is loud and correct.

`release`'s gate is the one place a stale string is silent-adjacent. After the
rename it looks for `<project>-test` in `metadata.jsonl`, finds no line, and
refuses with `NONE RECORDED`. That is the gate working, and the message text
changes with the file.

---

## 7. Against the seventeen criteria

Nine of the seventeen are touched. The other eight — 1, 7, 8, 9, 10, 11, 15, 17
— concern the flake, registration and the projection, and this proposal changes
nothing on any of those paths.

| # | Criterion | Result |
|---|---|---|
| 2 | a repo adopts in three lines | **holds, unchanged.** `enable`, `project`, `groups = [ "base" ]`, plus two task lines — the same cost as today |
| 3 | a repo may take no groups at all | **holds, unchanged.** `groups = []` plus `.devman/workflows/` is untouched |
| 4 | **a repo may rename or replace every default** | **holds.** Nothing devman owns objects. Deleting the `python` group removes a shadowing file, and `base/check` then wins by being the only candidate — a resolution outcome, not a refusal. A repository that wants the old names shadows both files |
| 5 | shadowing is exact | **holds, and there is less to shadow.** `devman show test` still round-trips to `.devman/workflows/test.yaml`. `siteman`'s one repository-level shadow is deleted with its target |
| 6 | a workflow is portable Dagu | **holds, strengthened.** `check.yaml` becomes four lines and names no language. The same file serves a Python library, a Nix flake and a Neovim plugin without an edit |
| 12 | queues are real | **untested at this scale, and the rollout must test it.** 58 `maintain` runs enqueued in one minute against `light`'s limit of 4 is the first real load on a queue. Wave 4 measures it |
| 13 | the watchers do not chase each other | **holds.** `format` keeps the measured hash precondition byte for byte, and its glob does not widen. §4's widening rule is what keeps it holding when a glob is added |
| 14 | the task graph exists once | **holds by construction**, rather than by everyone's care. A one-step workflow declares no order. Today the criterion is one `devenv.nix` edit from being false |
| 16 | devman adopts itself | **holds.** `devman` takes all three groups, keeps `stack-validate`, `agent-review` and `bench-entry`, and gains `plane-report` |

**Criterion 4 is the sharp one and it deserves the longer answer.** The test is
whether a repository can drop `check`, define `smoke` and `ci`, and have nothing
in devman object. Under this proposal it can, by exactly the mechanism §7.3
already gives: write `.devman/workflows/smoke.yaml` and `ci.yaml`, and do not
take the group whose files it does not want. The proposal reserves no name,
teaches the plane no new word, and adds no Nix option. What it changes is what
the *defaults* are, which §7.2 calls content.

---

## 8. The rollout

Each wave ends with something that proves it worked. No wave begins before the
previous one's proof is in hand.

### Wave 0 — `devman` alone

Land the group files. Adopt them here. Retire nothing until the new set runs.

**Proves it worked:** `devman doctor` exits 0; `metadata.jsonl` carries one
`succeeded` line each for `devman-check`, `devman-test`, `devman-release`; a
`.py` save fires `format` exactly once and the next save-with-no-change fires a
run that skips (criterion 13); one scheduled `devman-maintain` and one scheduled
`devman-plane-report` land in the log, both `trigger: scheduler`.

### Wave 1 — the five already registered

`siteman`, `nix-paseo`, `pyjutsu`, `pydantree`, `observantic`. One `rev=` bump
and the edits in §6, each repository in one sitting.

**Proves it worked:** `devman doctor` clean at 6 projects; `devman run check` and
`devman run test` succeed in all six; the next night shows six
`maintain-*.md` reports and exactly **one** plane report. `observantic` runs
`devman run release` and the gate opens on the renamed `<project>-test` line.

### Wave 2 — the first five new repositories, by name

Chosen for coverage rather than convenience: three Python, one Nix, one Lua.

| Repository | Why it is in this wave |
|---|---|
| `webdantic` | plain Python, already configures `git-hooks`, so it proves the post-commit recipe |
| `poddantic` | plain Python, no `enterTest` — proves `full-test`'s deletion cost nothing |
| `parsedantic` | plain Python, the third of the `*dantic` family |
| `nix-desktop` | Nix-only, no Python — the second Nix repository, so the contract is proved outside `nix-paseo` |
| `loci.nvim` | Lua and a flake — **the Neovim case the kickoff demands** |

**Proves it worked:** the registry reaches 11 projects; `devman run check` and
`devman run test` succeed in each; `doctor` exits 0; the next night shows 11
`maintain` reports and one plane report. **`loci.nvim` and `nix-desktop` passing
is the proof that the universal contract is not a Python fiction.**

### Wave 3 — `fsdantic`, on purpose, because it must fail first

`fsdantic` is the only repository in the inventory with a colliding `.devman/`.
It holds `.devman/store/vendor/agentfs`, which is §15.2's "vendored store" shape.
The whitelist says registration must **refuse and report**.

**Proves it worked:** entering `fsdantic`'s shell with `devman.enable = true`
refuses, names the unexpected directory, and writes no registry entry. Then
`fsdantic` moves the directory to `.store/` — its own change, not the plane's —
and registers normally. **This is the first live exercise of §15.2, which has
never fired.**

### Wave 4 — the remaining repositories, in batches of ten

Roughly 46 left after wave 3. Ten at a time.

**Proves each batch worked:** the registry count rises by ten; `doctor` exits 0;
and one number is recorded each time — **how long `devman doctor` takes at 20,
30, 40, 50 and 58 projects.** If it passes 30 s, `plane-report` needs paging or
`doctor` needs a project scope, and OPEN_QUESTIONS §2 is the entry that becomes
urgent.

**The batch that crosses about 40 projects is the one that tests criterion 12**,
because that is where 00:05 first enqueues more `maintain` runs than the `light`
queue's limit of 4 can absorb in the time a single run takes. Record the queue
depth and the last run's completion time.

---

## 9. Charter impact

Five sections change. Each new text is supplied.

### §7.1 — the sentence naming the default workflows

**Current:** "The base group ships `check`, `validate`, and `full-test` because
most repos want a fast one, a gate, and an exhaustive one — so `devman run check`
usually resolves."

**New:** "The base group ships `check` and `test` because most repos want a fast
one and a gate — so `devman run check` usually resolves. There is no third rung:
an exhaustive tier was measured to carry no information in more than half the
population (stage 7)."

### §8 — the boxed note, generalised

**Current:** "**Reactivity is its own group.** §7.4's 'an inherited workflow you
never trigger costs nothing' does not carry over — a *triggered* workflow
rewrites the developer's files while they are editing them — so a group that
declares triggers ships the workflows they fire and nothing else."

**New:** "**A workflow that writes the repository's own files without being asked
is its own group.** §7.4's 'an inherited workflow you never trigger costs
nothing' does not carry over — such a workflow rewrites the developer's files
while they are editing them — so the group that ships it ships the workflows it
fires and nothing else. **What fires it is not the test; what it touches is.** A
self-firing workflow that writes only under `.devman/.runs/`, which the plane
created and the watcher ignores, may ride in a general group. `maintain` is the
worked example, and its schedule is why the distinction had to be stated."

### §14 — criterion 14 gains its mechanism

**Append to the commentary:** "**Since stage 7 this holds by construction.** A
default workflow runs exactly one `devenv tasks run`, so it declares no order and
cannot re-state one. Before that it held only because almost no repository
declared a task dependency — and `pyjutsu` already declared one, so the criterion
was one ordinary `devenv.nix` edit away from being false."

### §16 — "Python and Nix, and nothing else yet"

**Current conclusion:** a language group per ecosystem, gated on a second
repository wanting the same file.

**New:** "**There are no ecosystem groups.** A language differs in what a task
*is*, and `devenv.nix` already holds that. A language group's whole content, once
a workflow is one step calling one task, is a namespace prefix — which §7.3
cannot promote and no second repository can want. The `python` group was deleted
at stage 7 for this reason, and `rust`, `node` and `lua` were never created: each
would serve one repository (`pyjutsu`, `paloma-story-generation`, `loci.nvim`).
The surviving groups are named for what taking them costs — a task name, or a
write to your own files — and the highest-coverage marker is still `devenv.nix`
at 58 of 68, which is why `base` carries the leverage."

### §13 — the rollout gains a stage

**Append:** "**Stage 7 — the standard set.** Nine workflows in four groups become
five in three. The ladder is two rungs. The universal contract is `base:check`
and `base:test`. `devman doctor` moves out of `maintain` and into one plane
report. The plane goes from 6 registered repositories to 58, in four waves."

---

## 10. Rejected alternatives

**1. Keep the three-rung ladder, rename the rungs to `smoke` / `check` / `full`.**
Lost on the measurement. `full-test`'s only content beyond `validate` is
`devenv test`, which exits 0 having tested nothing in 30 of the 58 devenv
repositories (`copyroom` 5.6 s, `nix-paseo` 15.2 s), and which duplicated
`base:test` in the one repository that shadowed it. Renaming a rung that carries
no information keeps the information problem and adds churn.

**2. Keep `python` and add `nix`, `lua`, `rust`.** Lost because once a workflow is
one step calling one task, a language group's whole content is a namespace
prefix — the file is identical in every group. §16's own promotion rule ("a group
begins when a second repository wants the same file") cannot be satisfied by a
file that is the same file. And three of the four would serve one repository
each: `rust` → `pyjutsu`, `node` → `paloma-story-generation`, `lua` →
`loci.nvim`.

**3. Split `base` into `core` (calls nothing) and `base` (calls tasks).** The
argument for it is real: a repository that cannot define `base:check` still wants
`maintain`. Lost on the inventory. **No repository in the 68 is that
repository** — `siteman`, the kickoff's hardest case, has no language files and
already defines both names as shell functions. The split would buy a refusal
nobody uses and cost 57 repositories one extra word in `groups`.

**4. Make `maintain` opt-in as its own group, because a schedule is an opt-in the
way a watcher glob is.** Lost because refusing `maintain` is actively harmful.
Dagu's retention is per DAG and runs when that DAG runs (§9.2), so `maintain`'s
nightly run is what makes a quiet repository's log tree prune at all. A group
that a repository is worse off refusing is not an opt-in. This is what forced
§3's rule to be about what a workflow *touches* rather than what fires it.

**5. Make `maintain` machine-side — one nightly job walking the registry instead
of 58 DAGs.** Attractive: the registry is machine-side derived state, and
`doctor --prune` already writes from there, so it is legal by §4. Lost for the
same reason as 4, from the other side: a machine-side pruner is not a run, so
Dagu's per-DAG retention never fires for that project and the log tree — the
larger half — grows forever. `maintain` has to *be a run*.

**6. Extend `triggers.toml` with a `[hooks]` table, so a group can declare
`post-commit = "check"`.** It would raise hook adoption from 7 of 58 and remove
the recipe from a README. Lost because a hook needs devenv's `git-hooks` input,
which costs about 20 ms on every shell entry, forever, in every repository taking
the group (§3.2) — against criterion 7's budget of 10 ms for the whole module.
§8 puts hooks with the repository on purpose. Reopen if hook adoption is still
near 7 of 58 after wave 4.

**7. Schedule `test` nightly across all repositories, to catch bit-rot from
nixpkgs drift.** Genuinely valuable at 58 in a way it is not at 6. Lost because
58 nightly suites on a `normal` queue of limit 2 is hours of compute for a signal
nobody has agreed to read, and because the plane cannot tell "this repository
rotted" from "this repository is finished". OPEN_QUESTIONS §3 names the one
measurement that would settle it.

**8. Ship `format` with globs for `.nix` and `.lua` as well as `.py`.** Lost
because no repository has asked. Not one of the 58 takes `python-format`; the
only taker is `devman`. Designing a glob for a demand with no instance is the
opposite of §16's promotion rule.

---

## 11. Agent workflows (Q6)

**Answer: none of the three becomes a group, and two of them never can.**

| Workflow | Verdict | Reason |
|---|---|---|
| `stack-validate` | **never a group** | its steps name specific DAGs — `observantic-check`, `siteman-check`. A group file cannot name another project without holding a project fact, which §4 forbids and §11 already places in `devman` |
| `bench-entry` | **never a group** | it measures a *named other* project. §11 says a workflow belonging to no project belongs to `devman`. A per-repository benchmark campaign is also meaningless at 58 |
| `agent-review` | **not yet a group**, and the condition is stated below | one repository wants it |

### What would promote `agent-review`, exactly

§16's rule is that a group begins when a **second** repository wants the same
file. Two further conditions apply to this one, and both are about secrets.

1. **A second repository writes the same file.** Today `devman` is the only
   repository carrying `claude-code` and `codex-cli` in its packages.
2. **§9.4 resolves one real secret, measured.** §9.4 has never fired — stage 4's
   S7 declined it and three stages have passed. `devman`'s own `agent:review`
   needs no secret, because those tools authenticate from `$HOME`. A group would
   reach repositories where the agent needs `ANTHROPIC_API_KEY`, and that is
   §9.4's first use, machine-wide, with a real credential. **A group is the wrong
   place to prove an untested path.**

### The shape it would take, so a later stage does not redesign it

| | |
|---|---|
| Group | `agent` |
| Required task | `agent:review` — the group names the task and never the tool, so `claude`, `codex` or a script all fit |
| Queue | `exclusive`. Not `heavy`: `heavy` says "this costs a lot of machine", `exclusive` says "this must not overlap with other exclusive work". An agent run is long, non-deterministic, and reads a tree another run may be rewriting |
| Writes | one file under `.devman/.runs/reports/`, which the watcher and git both ignore. **An agent workflow that rewrote source would need `format`'s whole argument**, and would belong in a reactive group |
| Secrets | the workflow declares Dagu's own `secrets:` block; the module reads the value from the machine's secret manager and sets it on the user service. **The repository declares a dependency on a secret and never holds one** (§9.4) |
| Trigger | manual only. An agent that runs on a commit is an agent nobody asked a question |

---

## 12. What must never become a workflow (Q7)

Seven rules. This is what a future stage points at when it wants to say no.

**1. Anything an editor already does synchronously.** LSP diagnostics,
format-in-buffer, jump-to-definition. The plane's round trip after a content
change is 1.44 s and its answer lands in a log file; the editor's is tens of
milliseconds and its answer lands next to the cursor. Every repository here has a
Neovim configuration. This is why `check` is not fired by a save.

**2. Anything irreversible outside this machine.** Publishing a wheel, pushing a
tag, cutting a release, deploying. `release` builds and does not publish, on
purpose (`STAGE_4_LOG.md`, S7). A plane that can publish is a plane whose bug is
somebody else's problem, and it is the reason §9.4 is still unused.

**3. Anything that writes tracked source without a person present.** Dependency
updates, code generation, autofix beyond formatting. The write is a change nobody
reviewed, and the plane has no review step. `format` is the single exception and
it is bounded three ways: one glob, a content hash, and its own group.

**4. Anything whose success is indistinguishable from doing nothing.**
`full-test`'s third step is the worked example: exit 0, 15.2 s, nothing tested,
in 30 of 58 repositories. §15.7 says nothing in the plane will ever notice this
for you, which is exactly why it must not be shipped as a default.

**5. Anything needing a fact the repository did not state.** A workflow naming
another project, an absolute path, or a per-project schedule offset. §4 says the
machine never learns a project fact, and `STAGE_5_LOG.md` S9 is the measured
consequence of breaking that: five hand-written unit lines, one repository
silently never scheduled, and nothing reporting the gap.

**6. A second implementation of a task the repository already has.** §6: one
logical task, one implementation, every caller reaching it the same way. A
workflow running `pytest` directly rather than `base:test` is the thing that
drifts, and it drifts silently because both keep passing.

**7. Anything whose output nobody reads.** 58 nightly `devman doctor` reports is
the worked example, and this proposal deletes it. A report produced 58 times is a
report produced zero times.

---

## 13. What this proposal does not settle

See `OPEN_QUESTIONS.md`. Twelve entries, each with the measurement that would
settle it. The three that gate the rollout are: what `devman doctor` costs at 58
projects, whether the `light` queue absorbs 58 dispatches, and whether a
one-step workflow's log still names the devenv task that failed.
