# 015 — The plane is built, it is fast, and almost nothing uses it. What should it do?

Kickoff. Open a clean session at `~/Documents/Projects/devman` and work from
here. **Read this whole file before running anything.**

---

## The question

Nine projects built this plane. 001–007 designed and shipped it, 009 hardened
`doctor`, 011 established what a watcher is for, 012 halved the dispatch, 013
found the concurrency primitives, and 014 made the verb twelve times faster.

**It works. Here is what it does.**

170 projected workflow files across 54 repositories. **One trigger in the entire
plane** — `**/*.py` → `format`, in `devman` and nowhere else. Of 1,186 recorded
runs over fifteen days:

| workflow | runs | how it fires |
|---|---|---|
| `format` | **496** | the one trigger, in one repository |
| `maintain` | **489** | nightly ×54, and it calls no repository task |
| `check` | 73 | by hand |
| `test` | 70 | by hand |
| everything else | 58 | by hand |

**83 % of everything the plane has ever run is one repository's formatter and a
nightly janitor.** `check` and `test` are projected 54 times each, carry no
schedule and no trigger, and fire about **0.18 times per repository per day**.

So: **the machinery is finished and the content is empty.** This project is not
about making the plane faster or safer. It is about deciding what it is *for*,
and shipping the smallest set of workflows and triggers that earns its keep.

**"The current set is right and nothing should be added" is a legitimate
answer**, and if the honest finding is that 54 repositories genuinely need three
workflows and one trigger, say so and stop. But say it with evidence about what
this developer actually does by hand, not from the armchair.

---

## What this project must NOT inherit

014 ended with several things that read like facts and are not. **Re-derive
anything you intend to build on.**

| claim | status |
|---|---|
| "The verb costs ~130 ms." | **Verified**, n=20, across three repositories, after the `git+file:` conversion. Safe to build on. |
| "52 of 54 repositories are on `git+file:`; `maintain` projects to 54 of 54." | **Verified** by direct read. Safe. |
| "Six repositories are incompatible with `git+file:`." | **RETRACTED — this was false.** All six were btrfs metadata exhaustion. `RESULT.md` §16. |
| "`exec_if_modified` has a silent-skip defect." | **Verified from source and reproduced.** Exposure is **zero** — nothing sets it. Re-check that before relying on it. |
| "`devenv gc` never collects the shell cache." | **Verified** by reading all 85 lines of `gc.rs`. Safe. |
| "The plane's daily spend on the verb is ~39 s." | Measured **before** the 12× speedup and from a 15-day window dominated by one repository. **Recompute it if you need it.** |
| "`maintain`'s collection works." | **Never observed running.** It was projected on 2026-09-05 and first fires at 00:05. **Check the run log before assuming.** |

**The last row is the first thing to check in this session.**

---

## What is re-openable, and what is not

**In scope:**

* **Which workflows exist.** `check`, `test`, `maintain` are the whole of `base`.
  Nothing says that is the right set — `full-test` was deleted at stage 7 on a
  measurement, and the same knife cuts both ways.
* **Triggers.** There is one. §8 makes reactivity its own group precisely so a
  repository opts in. Whether one trigger in one repository is the intended
  outcome or a symptom is exactly the question.
* **Whether `check` and `test` should be reactive or scheduled at all.** They
  are neither today, which means the plane's two headline workflows are a
  slightly slower way to type a command.
* **New groups.** `groups/README.md` describes the mechanism; only three groups
  exist (`base`, `format`, `release`) and two of them have one taker each.

**Not in scope:**

* **The nine rules in `PROPOSAL.md` §12.** Every one exists because an obvious
  idea failed a measurement. A candidate that trips one is dead; if you believe
  a rule is wrong, that is a charter amendment with its own evidence, not a
  workflow proposal.
* **The projection, the codec, the registry, the queues.** 001–013 settled
  these. Read them; do not reopen them.
* **Making anything faster.** 012 and 014 did that. The verb is 130 ms and
  dispatch is halved. **Latency is not this project's problem.**

---

## The investigation

### Part A — what does the plane actually do, and for whom?

1. **Recompute the run census.** `~/.local/share/dagu/data/dag-runs/**/status.jsonl`,
   last line of each. 014 §8 has the method, including the trap that a
   multi-line step lives in `step.script` and a `commands`-only scan misses it.
   Report per workflow, per repository, per trigger type.
2. **Did `maintain` actually collect anything?** It has never been observed
   running. Read its reports under `.devman/.runs/reports/` and the shell-cache
   counts it prints. **If it did not fire, or fired and collected nothing, that
   is finding number one and it changes the rest of this project.**
3. **What fraction of repositories have run anything at all?** 54 are
   registered. How many have a non-`maintain` run in the last month?

### Part B — what work is this developer doing by hand?

**This is the part nobody has done, and it is where the answer lives.**

The plane has one trigger because nobody has asked what else deserves one.
Sources, in rough order of value:

1. **Shell history.** `atuout` is running on this machine and has been for
   months. What commands recur, in which repositories, at what frequency?
2. **The `.agents/skills/` layer.** Several repositories carry skills describing
   procedures a human or agent follows by hand. A procedure written down and
   repeated is a workflow that has not been noticed.
3. **`git log` across the 54.** What kinds of commit recur? Version bumps,
   lockfile updates, generated-file refreshes?
4. **The other `man` tools** — `gitman`, `docman`, `repoman`, `copyroom`,
   `siteman`, `foreman`. Each automates something. **Which of them are invoked
   by hand today and would be better as a workflow, and which must not be?**

**Classify every candidate against §12's nine rules before proposing it.** Most
good-sounding ideas die on rule 1 (the editor already does it), rule 3 (writes
tracked source unattended) or rule 7 (nobody reads the output).

### Part C — why is there only one trigger?

1. **Is it the group boundary?** `format` is its own group with one taker. Would
   a repository take a `python-quality` group if it existed, or is the group
   mechanism itself the friction?
2. **Is it the trigger vocabulary?** `<glob> = <workflow>` is the whole
   language. What cannot be expressed that people want — a debounce, a branch
   condition, a "only when tests exist" guard?
3. **Measure the cost of a trigger that fires too often.** 009 P3-3 found 16 of
   252 `format` fires did work that could not change a file. With the verb now
   at 130 ms rather than 1.5 s, **that arithmetic has changed by an order of
   magnitude and should be redone.** A trigger that was too expensive in July
   may be cheap now.

### Part D — what should `check` and `test` be?

They are projected 54 times, fire 143 times in fifteen days, and carry neither a
schedule nor a trigger.

1. **Is a post-commit hook installed anywhere?** `groups/base/README.md` names
   `check` as hook-driven. Verify whether any repository has the hook.
2. **Should they be reactive?** A `check` on save costs 130 ms of plane plus the
   repository's own lint. Rule 8 forbids expensive *scheduled* work; reactive
   work has no such rule, only rule 1.
3. **If they should not be, say what they are for.** A workflow nobody triggers
   costs nothing (§7.4) — but it also earns nothing, and 108 of the 170 files
   are these two.

### Part E — the smallest set worth shipping

Propose **the fewest workflows, groups and triggers that would change how this
machine is actually used**, each with:

* which §12 rules it was checked against and how it survives them
* what it costs per fire, measured, not estimated
* who takes it — a group with one taker is a local workflow wearing a costume
* how `doctor` would notice if it broke

**Ship at most what you can defend.** 007 deleted `full-test` on one
measurement; deleting is as valid an outcome as adding.

---

## The traps

**A workflow nobody triggers is not free — it is 54 files of noise.** `check`
and `test` are 108 of 170 projected files and 12 % of runs. Adding a fourth
`base` workflow adds 54 more files to every `doctor` run, every projection, and
every reader's head.

**The nine rules are not a checklist to pass, they are a graveyard.** Read
`PROPOSAL.md` §12 properly. Rule 4 — "success indistinguishable from doing
nothing" — killed `full-test`, which exited 0 having tested nothing in 30 of 58
repositories. Your best idea is probably rule 4's next victim.

**`format` is the only reactive workflow and it rewrites tracked source.** Rule
3 says a workflow must not write tracked source with nobody present; `format` is
the deliberate exception, which is why reactivity is its own opt-in group. **Any
new writer needs that argument made again, not inherited.**

**The machine lies about disk.** `/home` is btrfs. `df` reported 75 GB free
while the device was fully allocated and Nix could not create a file. 014 spent
hours attributing that to a flake input scheme. **Before believing any failure
is yours, check `btrfs filesystem usage /home` and the `Device unallocated`
line.**

**A verification harness with no retry cannot tell a broken change from a busy
machine.** 014 §16 is the whole lesson. If you gate anything, retry it.

**`devenv tasks run` succeeding proves nothing about `devenv shell`.** They
build different derivations. Gate on the one a developer actually uses.

**The plane is live and manages 54 real repositories.** Triggering work in
`devman` is fine. Anything that writes to another repository is not, without
saying so first. Every Dagu experiment goes on a throwaway `DAGU_HOME` under
`/tmp` on ports 18080/50155, set by **environment variable, not `--dagu-home`**
(013: the flag is not propagated to forked children).

---

## Constraints

* **`devman doctor` must exit 0 before and after** — with the caveat that it
  currently exits 1 on `daemon shell`, a 009 finding whose fix is already in
  0.4.0's module and lands when the system is rebuilt. **Establish the baseline
  first and say what it is.**
* `devenv tasks run base:check` and `base:test` both exit 0.
* **`tests/unit/` must pass unmodified.** 398 tests today.
* Every number gets its method beside it: sample count, machine state, what else
  was running.

---

## Deliverable

`.scratch/projects/015-what-the-plane-should-do/RESULT.md`, holding:

1. **What the plane actually ran**, per workflow and per repository, and whether
   `maintain`'s collection works.
2. **What this developer does by hand that recurs**, with evidence.
3. **Every candidate considered, and which §12 rule killed the ones that died.**
4. **The proposal** — the smallest set of workflows, groups and triggers worth
   shipping, each with its cost measured and its `doctor` story.
5. **Why there is only one trigger**, answered rather than assumed.
6. **What `check` and `test` are for**, or the case for changing them.
7. **What you did not measure**, plainly.

Ship the change if it wins on the argument and the measurement. Amend the
charter in the same commit if it contradicts one — with the measurement that
forced it. **A plane with more workflows nobody runs is not a better plane.**
