# 019 — Every workflow writes a receipt, and an absent receipt is the finding

Kickoff. Open a clean session at `~/Documents/Projects/devman` and work from
here. **Read this whole file before running anything.**

---

## The question

**§12 rule 4 — "anything whose success is indistinguishable from doing nothing"
— has no enforcement, and it is the only rule on the list that does not.**

Rules 1, 2, 3, 5, 6, 8 and 9 are all decidable by reading files, and `doctor`
decides them: `literal dir`, `cross-repo`, `fan-out`, `writes`, `trigger
target`. Rule 4 is decided by a reviewer reading a workflow and imagining its
failure. `full-test` proves how well that works — it exited 0 in 15.2 s having
tested nothing, in **30 of 58 repositories**, and stayed that way for a month.

This project asks whether the plane can see rule 4 for itself.

---

## The idea that started it, and why it is wrong as stated

> *Force every Dagu workflow to write a log, so there is positive output
> regardless.*

**Dagu already does this, unconditionally, and it is exactly the problem.**
Every run writes `stdout` and `stderr` to `.local/share/dagu` and records a
status. `full-test` produced a full log for every one of its empty runs. The log
said the step completed, because the step did complete.

**A log records that a workflow ran. Rule 4 is about whether it did anything.**
More logs is rule 4 with more bytes, and a log nobody reads is rule 8.

---

## The idea that survives: a receipt, and the absence of one

**`format` already does this and has since 013.** It writes
`.devman/.runs/.format.hash` — a receipt — and its whole design is about when
it must **refuse** to write one:

```
format: the tree never settled across 3 passes. Refusing to write
.devman/.runs/.format.hash, because a receipt now would claim work
this run did not do and the next save would be skipped.
```

That refusal is the mechanism this project generalises. A receipt is not a log:

| | a log | a receipt |
|---|---|---|
| written when | always | **only when the run did the thing** |
| says | that the run happened | **what changed** |
| its absence means | the daemon is broken | **rule 4, and it is now visible** |

**The finding is the missing receipt.** A workflow that ran 40 times this week
and wrote no receipt did nothing 40 times, and nobody had to read the workflow
to know it.

---

## What already exists, and it is more than half of this

**Do not rebuild these. Read them first.**

| piece | where | what it gives |
|---|---|---|
| the receipt prototype | `groups/format/workflows/format.yaml` | the fixpoint, the honest refusal, and the three bounds |
| the receipt path | `.devman/.runs/` | §7.1's third global name, git-ignored by registration, **watcher-ignored** so writing one is not an event |
| output ownership | `.devman/writes.toml` (016) | a workflow states the paths it writes and the tier it claims |
| the static audit | `doctor` check `writes` | that a declaration is well formed |

`check_writes`' own docstring names the gap this project closes:

> **What it CANNOT decide** … It cannot tell that a workflow which declares
> nothing writes nothing, and it cannot tell that a declaration is true.
> `doctor` reads YAML and a TOML table; it does not run the step.

**A declaration plus a receipt makes the declaration checkable.** The workflow
says it writes `src/**` at tier `lane`; the receipt says what it wrote; `doctor`
compares two sets. That is set membership, not a heuristic, so §15.7 does not
reach it — the same argument `check_writes` already makes for itself.

---

## The line this project must not cross

**Law 5: devman never parses a workflow to understand it.** The plane resolves a
name to a file and runs it. It has no opinion about what the work is.

A receipt respects that, and this is the whole reason the design works: the
**workflow** declares what it writes and the **workflow** writes the receipt.
`doctor` compares a declared set against a written set and understands neither.
A check that had to know what `pytest` means would be over the line.

**Any design that requires the plane to interpret a step is out of scope, and
saying so is a legitimate result.**

---

## What is in scope, and what is honestly not

**In scope — writers.** A workflow that declares paths in `writes.toml` can be
held to them. An empty lane, a `free` write that touched nothing, a declared
path never written: all decidable. **The 52-empty-branches disaster 016 avoided
by measurement would have been loud under this check** — the workflow said it
writes, and it did not.

**Not in scope — verifiers, and this is not a gap to close later.** `full-test`
writes nothing. Its entire output is an exit code. For a checker, "succeeded"
and "did nothing" are the same observation, and no receipt outside the workflow
separates them. **That half belongs to the workflow, not the plane** — `pytest`
already exits 5 when it collects nothing, and the step swallowed it. A verifier
that cannot fail on vacuum is broken at its own source, and the fix is in the
step.

**State this split in the result.** A reader who thinks 019 made rule 4
decidable in general will trust a clean `doctor` run further than it deserves.

---

## The questions to answer, in order

1. **Does the finding already exist?** Count runs in the retention window that
   produced no change, per workflow. If the number is zero, the plane has no
   rule-4 writers today and this check would ship green forever — which is
   rule 4 pointed at itself. **Measure before building.**
2. **What is the receipt's shape?** `format` writes a bare hash for its own
   precondition. A general receipt has a different job — it is read by `doctor`,
   not by the next run. One file per run under `.devman/.runs/`, or one file per
   workflow, overwritten? What does it cost to write, and to read across 54
   repositories? **The local-sources check is the bar: 104 ms, reading sources
   rather than consumers.**
3. **Who writes it?** A line each workflow adds, or something the projection
   wraps around a step? A wrapper is one place instead of 170 — and it is also
   the plane growing an opinion about a step. Decide, and say which rule made
   the decision.
4. **What does a workflow with no `writes.toml` entry do?** Most declare
   nothing today — 1 project of 54. A check that reports 53 findings on day one
   reports nothing.

---

## Verify before you save

```bash
devenv tasks run -v base:check
devenv tasks run -v base:test
devman doctor
```

**`devman` on PATH is `/run/current-system/sw/bin/devman`, a system build.** It
lags this working tree until a rebuild — 018's `local sources` check is in the
source and not in that binary. Run `doctor` from source when checking your own
change.

**Tests must not shell out to real `git`.** 018 lost a `base:test` this way: the
tests passed in the devenv shell and failed in the Nix sandbox, which has no
git. Stub the boundary.

---

## Related

`.scratch/projects/015-what-the-plane-should-do/RESULT.md` lists three things the
tier amendment owed. This is **item 2, the audit** — and it is the one still
open. Item 1 (output ownership) shipped as 016. Item 3 (lane hygiene) is blocked
in gitman, at `.scratch/projects/39-lane-lifecycle-facts/` in that repository.
