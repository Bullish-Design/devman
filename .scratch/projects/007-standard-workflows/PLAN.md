# Plan — the investigations, spikes and refactor for stage 7

> **What this document is.** `PROPOSAL.md` states a design. `OPEN_QUESTIONS.md`
> states what it could not settle. This states **the order of work that closes
> the gap**, so that stage 7 is built on measurements rather than on the
> proposal's confidence.
>
> **Read `PROPOSAL.md` first.** This plan is unreadable without it.

---

## 0. What this plan found before it was written

Three facts came out of reading the code, and each one changes the shape of the
work. They are stated first because they move risk from where a reader would
expect it.

### 0.1 The refactor is almost entirely content, not code

**No group name and no workflow name is hardcoded anywhere in `src/devman/`.**
Verified by grep over all nine Python files: the only hits for `"validate"` are
`doctor`'s own label for its check, not a workflow name. `run`, `show`, `watch`,
`registry`, `workflow` and `cli` resolve every name from the registry.

The only Nix that names a group is two lines:

```nix
# modules/devenv.nix:374-375
default = [ "base" ];
example = [ "base" "python" ];
```

**Consequence.** Deleting the `python` group, renaming `python-format`, renaming
`validate` to `test` and renaming `base:lint` to `base:check` touch **`groups/`,
two lines of `modules/devenv.nix`, and six repositories' `devenv.nix`.** Nothing
else. The code changes in this plan are all *new capability* gated on an
investigation, never migration.

### 0.2 An unknown group is an evaluation failure, not a runtime one

`modules/devenv.nix:62`:

```nix
throw "devman: group '${group}' does not exist. There is no …"
```

**A repository that re-pins to the stage-7 rev while still listing `python` or
`python-format` cannot enter its shell at all.** Not a failed workflow — a failed
`devenv shell`. That is a harder failure than `PROPOSAL.md` §6 describes, and it
is the one thing in this plan that could produce the flag day the kickoff
forbids.

The same file already holds the escape (line 63-68): **a group may ship no
workflows at all**, and the module returns `{ }` rather than throwing. So a
deleted group can leave a **tombstone** — an empty directory — and every stale
pin keeps evaluating.

**S-3 exists to prove that, and it gates the whole migration.**

### 0.3 `nix flake check` already gates group content

`flake.nix:60` runs `dagu validate` over every `groups/*/workflows/*.yaml`. Every
group file this plan writes is checked by a command that already exists. No new
test harness is needed for R-1.

---

## 1. How the work is structured

Three kinds of work, with different rules.

| Kind | ID | Rule |
|---|---|---|
| **Investigation** | `I-n` | Measures the world. Changes no file that survives. Produces a number or a written answer |
| **Spike** | `S-n` | Builds a throwaway to de-risk one mechanism. Lives in `/tmp` or a throwaway `DAGU_HOME`. Nothing it produces ships |
| **Refactor** | `R-n` | The change that ships. Every one is gated on a named investigation or spike |

**Four gates.** No work in a gate begins before the previous gate closes. Within
a gate, items are independent and may run in any order or at the same time.

```
GATE 0  the hinge survives        I-3  I-5
   │
GATE 1  the migration is safe     I-6  S-3
   │
GATE 2  the content loads         S-2  S-5  S-6  S-4
   │
GATE 3  it scales                 S-1  I-2a
   │
   ├─ R-1 … R-4   the change
   └─ R-5 … R-7   the waves, carrying I-8 I-9 I-11 I-2b I-1 I-4
                  then the tail: I-7 I-10 I-12 I-13
```

**The stop rule.** If a Gate 0 investigation fails, stop and rewrite
`PROPOSAL.md` §1.1 before anything else. Gate 0 tests the hinge, and the hinge is
the proposal.

---

## 2. Gate 0 — the hinge survives

Two investigations. Together they cost less than a day. Nothing else starts until
both answer.

### I-3 — Does a one-step workflow's log name the devenv task that failed?

**This is the single most important measurement in the plan.** `PROPOSAL.md` §1.1
trades Dagu's per-step status for devenv's task graph. If the trade loses the
name of the failing task, the developer's failure report gets worse and the
proposal's central recommendation has to be re-argued.

**Why it is open.** `-v` exists because `devenv tasks run` otherwise captures a
task's stdout and prints nothing (`STAGE_2_LOG.md`, S4). Whether devenv *names
the failing task* in a dependency chain has never been measured, only assumed.

**Run it in `devman`.** Add three throwaway tasks to `devenv.nix`, make the
middle one fail, and read the log the plane wrote:

```nix
tasks."t7:a".exec = "true";
tasks."t7:b".exec = "exit 3";
tasks."t7:c".exec = "true";
tasks."t7:all".after = [ "t7:a" "t7:b" "t7:c" ];
```

```bash
devenv shell -- true                       # re-project
devenv tasks run -v t7:all; echo "exit=$?"  # the direct path
devman run check                            # through the plane, with check pointing at t7:all
ls .devman/.runs/logs/devman-check/*/        # read both streams
```

**Record.** The exit code. Whether the string `t7:b` appears in either stream.
Whether `t7:c` ran. Whether the run is `failed` in `metadata.jsonl`.

**Passes if** the log names `t7:b` and the run reports `failed`.

**Fails if** the log says only that something failed. Then:
- the one-step rule keeps its other four benefits and this becomes a devenv issue
  to file;
- **it does not become a reason to write the order twice in a workflow** —
  criterion 14 forbids that;
- `PROPOSAL.md` §1.1's "one real loss" section is rewritten from a prediction
  into a measurement, and the rollout gains one line telling developers where to
  look.

**Blocks:** everything.

---

### I-5 — What does an undefined task actually do?

**Why it is open.** `PROPOSAL.md` §2 rejects the null implementation (option C)
on the claim that a missing `base:check` "fails loudly". §6 rests the whole
no-flag-day argument on the same claim: a repository that re-pins before renaming
its tasks gets a loud failure when a human types `devman run check`. **Neither
has been measured.** If devenv exits 0 on an unknown task, or if Dagu records the
run as succeeded, both arguments collapse and the migration is unsafe.

**Run it.**

```bash
cd <any registered repo>
devenv tasks run -v base:does-not-exist; echo "exit=$?"
# then through the plane
devman run check          # with a check.yaml naming a task the repo has not defined
tail -1 .devman/.runs/metadata.jsonl
```

**Record.** devenv's exit code and message. Dagu's step status. The
`metadata.jsonl` status string.

**Passes if** devenv exits non-zero, names the task, and `metadata.jsonl` records
`failed`.

**Fails if** any of the three is silent. Then the migration needs a bridging
step: every repository defines `base:check` as an alias onto its old `base:lint`
**before** the group files land, so no window exists where a name is missing.
That is one extra line per repository and one extra wave, and it is cheap
insurance — but it must be decided here, not discovered in wave 1.

**Blocks:** R-1, R-5.

---

## 3. Gate 1 — the migration is safe

### I-6 — Confirm the unknown-group throw, and see what a developer sees

**Why it is open.** §0.2 above reads the throw in the source. It has never been
triggered by a real repository, and the message a developer sees at the end of a
Nix evaluation trace is not the message in the source.

**Run it.** In a throwaway clone of a registered repository:

```bash
sed -i 's/groups = \[ "base" \]/groups = [ "base" "not-a-group" ]/' devenv.nix
devenv shell -- true 2>&1 | tail -30
```

**Record.** Whether the shell enters. The last 30 lines. Whether the message
names the group, and whether `devman: group '…' does not exist` survives to the
top of the trace.

**Passes if** the shell refuses and the message is legible.

**Fails if** the message is buried in a Nix trace nobody can read. Then R-3 adds
nothing to the module but the tombstone in S-3 becomes mandatory rather than
preferred.

**Blocks:** S-3, R-3.

---

### S-3 — The tombstone group

**The question.** Can a deleted group leave an empty directory that keeps every
stale pin evaluating, shipping nothing?

**Why it matters.** This is the difference between a migration and a flag day.
With a tombstone, a repository that bumps `rev=` without editing `groups` gets a
working shell and no workflows from the dead group. Without one, it gets a
repository it cannot enter until it edits a text file.

**Build it.** In a throwaway branch, not on the real `groups/`:

```bash
mkdir -p /tmp/s7-groups/python          # a directory, and nothing inside it
# point a throwaway repo's devman.groupsRoot at it, or copy into a scratch checkout
```

Then evaluate a repository with `groups = [ "base" "python" ]` against it.

**Record.** Does evaluation succeed? Does the repository project exactly `base`'s
workflows and nothing else? Does the registry entry list `python` as a group with
no files? Does `devman doctor` report anything?

**Then test three variants**, because the module's `triggers.toml` resolution is
whole-file and last-group-wins:

| Variant | Question |
|---|---|
| empty directory | does it evaluate and ship nothing? |
| directory with a `README.md` only | same, and does `README.md` stay inert as §7.2 promises? |
| directory with a stale `triggers.toml` and no `workflows/` | **does the watcher get a glob pointing at a workflow that does not exist?** |

The third variant is the trap. `python-format`'s tombstone must **not** keep its
`triggers.toml`, or every `.py` save in a stale repository fires a workflow the
repository no longer has.

**Passes if** an empty directory evaluates, ships nothing, and produces no
trigger.

**Decides:** whether R-1 ships tombstones for `python` and `python-format`, and
for how long. **Recommendation to test:** ship them, and delete them one full
rollout after wave 4 — a tombstone costs one empty directory and buys the
no-flag-day promise the kickoff §6 demands.

**Blocks:** R-1.

---

## 4. Gate 2 — the content loads and runs

Four spikes. Each writes real files, in a branch, and proves them before R-1
commits to them.

### S-2 — The five workflow files, validated

**Build** the five files `PROPOSAL.md` §4 specifies:
`base/check.yaml`, `base/test.yaml`, `base/maintain.yaml`, `format/format.yaml`,
`release/release.yaml`.

**Prove them with the check that already exists:**

```bash
nix flake check .#checks.x86_64-linux.groups-validate
```

**Two things to get right, and both are in the current files already.**

1. `maintain.yaml` keeps `params: [DEVMAN_PROJECT_DIR: "", KEEP_DAYS: "7"]`.
   Dagu rejects a parameter a DAG did not declare, and `devman run` always passes
   the directory variable (`STAGE_4_LOG.md`, S3). Removing the `doctor` step does
   not remove the parameter block.
2. `check.yaml` and `test.yaml` declare **no** `type: chain`. One step needs no
   order, and the key existed to stop two devenv invocations contending
   (`groups/base/README.md`). Leaving it in would be cargo.

**Record.** The five files' line counts, against today's nine. The proposal
claims the group files get shorter; say by how much.

**Blocks:** R-1.

---

### S-5 — `plane-report`, run once by hand

**Build** the new workflow in `devman/.devman/workflows/plane-report.yaml`:
one step, `devman doctor`, output appended to a report, schedule `20 0 * * *`.

**Three questions it has to answer**, and only one is about the file:

1. **Does a workflow whose step fails still write its report?** `doctor` exits
   non-zero when it has findings, and `maintain` used that as its signal. Copy
   `review`'s `continue_on` shape or write the report before the exit, and say
   which.
2. **Does it need `DEVMAN_PROJECT_DIR`?** It targets `devman`'s own project and
   triggers no other DAG, so it holds the name like `maintain` does, and §11's
   rule does not reach it. Confirm against `doctor`'s cross-repo check.
3. **What does it cost?** Time it. This is the number `I-2a` extrapolates from.

**Prove it** with one manual run and one scheduled run, evidence in the shape
stage 6 used: `journalctl --user -u dagu | grep "Dispatching planned run"`, the
`metadata.jsonl` line, and the report.

**Blocks:** R-2.

---

### S-6 — The `release` gate against the renamed `test`

**Why a spike and not just an edit.** `release`'s gate derives the DAG name it
looks for from `${context.dag.name}` by stripping the last hyphenated component
(`groups/release/README.md`). Renaming `validate` to `test` changes the string it
greps for, and the first version of that derivation was wrong in a way that
reported a **different workflow's** success as this one's
(`STAGE_4_LOG.md`, S5).

**Run three cases in `devman`:**

| Case | Expected |
|---|---|
| no `<project>-test` line in `metadata.jsonl` | refuses, `NONE RECORDED`, run reports `failed` |
| a `partially_succeeded` line | refuses — the gate matches the full string `"status":"succeeded"` |
| a `succeeded` line, clean tree | opens |

**And one adversarial case the rename creates:** a project whose own name ends in
`-test`. `${me%-*}` on `foo-test-test`. Confirm the derivation still names the
right DAG, or state the limit as the file already states its hyphen limit.

**Blocks:** R-1.

---

### S-4 — Prove the format glob/hash hazard before it exists

**Why now, and not when somebody adds a glob.** `PROPOSAL.md` §4 states a
widening rule and admits nothing enforces it. The failure it predicts is silent
in the worst way: a run that reports `Succeeded` with a skipped step, which is
byte-identical to a correct loop-break. **A hazard nobody has seen is a hazard
nobody will remember.** Seeing it once, on purpose, is what makes the rule stick.

**Build** a throwaway group: `triggers.toml` with `"**/*.nix" = "format"`, and
`format.yaml` whose precondition hashes only `**/*.py`.

**Run.** Save a `.nix` file. Read `metadata.jsonl` and the step status.

**Expected.** One run, `Succeeded`, step skipped, the `.nix` file unformatted, and
**nothing anywhere saying so**.

**Then answer OPEN_QUESTIONS §4 with it:** is a `doctor` grep worth writing?
`doctor` already greps inside a projection three times — the handlers check, the
cross-repo check and the queue-name check — so a fourth is no new capability. The
argument against is that comparing a TOML glob list against a `find` expression is
a heuristic, and §15.7 says the plane grows no heuristics.

**Decides:** R-4a. **Recommendation to test:** write the check only if S-4 shows
the failure is genuinely invisible. If `doctor`'s existing drift or watcher
report already surfaces it, add nothing.

**Blocks:** R-4a only. It does not block R-1, because the shipped glob does not
widen.

---

## 5. Gate 3 — it scales

### S-1 — 58 DAGs on the `light` queue, synthetically

**Why synthetic.** `OPEN_QUESTIONS` §1 asks for a real observation at 58
projects, which cannot happen until wave 4. Waiting until wave 4 to learn that
the queue does not cope means learning it with 58 real repositories already
adopted. **Measure it first, in a throwaway.**

**Build.** A throwaway `DAGU_HOME` on a spare port, carrying a byte copy of the
installed `base.yaml` (the shape stage 6's S2 used). Generate 58 DAGs, each
naming `light`, each doing what `maintain` does: a `find` over a directory, a
report write, and nothing else. Give them all one `schedule:` a minute ahead.

**Record.** Maximum queue depth from `GET /queues/light/items`. Wall clock from
the first dispatch to the last completion. Any status that is not `succeeded`.
Whether the daemon's own CPU is the limit rather than the queue.

**Passes if** all 58 complete within a few minutes and none fails.

**Fails if** runs fail rather than wait — then the queue is not what criterion 12
claims, and the schedule shape in `PROPOSAL.md` §5 is wrong before it ships.

**Also measure the control:** the same 58 with `devman doctor` in each, which is
what today's `maintain` does. That number is the proposal's own justification for
splitting `maintain`, and it is currently arithmetic rather than measurement.

**Blocks:** R-1's decision to keep `5 0 * * *`.

---

### I-2a — The `dagu validate` cost curve

**Why it is open.** `PROPOSAL.md` §5 extrapolates `devman doctor` from **2.9 s at
6 projects and 36 workflows** to roughly 14 s at 58 projects, and labels the
extrapolation. The extrapolation assumes the cost is linear in files and that
nothing else in `doctor` grows.

**Measure cheaply, now, without registering anything:**

```bash
# one file
time dagu --dagu-home ~/.local/share/devman validate \
     ~/.local/share/devman/projects/devman/workflows/check.yaml
# the whole set, as doctor does it
time devman doctor
```

Then separate the two halves: `check_load`'s subprocess fan-out against
everything else `doctor` does. `doctor` has twelve checks and only one forks per
file.

**Record.** Per-file `dagu validate` cost. The fixed cost of the other eleven
checks. The predicted number at 174 files, with its error bar.

**Decides:** whether R-4b (a `--project` scope for `doctor`) is needed before
wave 4 or not at all.

**I-2b is the same measurement at each rollout batch** — 20, 30, 40, 50, 58
projects — and it costs nothing extra because wave 4 already records it.

---

## 6. The refactor

Each step names the gate that must have closed.

### R-1 — Group content · gated on S-2, S-3, S-6, I-5

The change that everything else follows.

| Action | Files |
|---|---|
| rewrite | `groups/base/workflows/check.yaml` — one step, `base:check` |
| add | `groups/base/workflows/test.yaml` — one step, `base:test` |
| rewrite | `groups/base/workflows/maintain.yaml` — drop the `doctor` step, keep `params:` |
| delete | `groups/base/workflows/validate.yaml`, `full-test.yaml`, `review.yaml` |
| rename | `groups/python-format/` → `groups/format/`, task `python-format:fmt` → `format:fmt` |
| delete | `groups/python/workflows/` — leave the directory as a tombstone |
| tombstone | `groups/python-format/` — empty, **no `triggers.toml`** (S-3's third variant) |
| rewrite | `groups/base/README.md`, `groups/format/README.md`, `groups/release/README.md` |

**The READMEs are not documentation debt, they are the group's contract.**
`groups/base/README.md` currently carries a whole section recommending a systemd
timer, which stage 6 retired. It is wrong today and would be wronger after this
change.

**Proof:** `nix flake check` passes; `devman show check` prints the source byte
for byte; `dagu validate` over all five.

---

### R-2 — `plane-report` · gated on S-5

Add `devman/.devman/workflows/plane-report.yaml`. Delete nothing else — this is
where `maintain`'s second step went.

**Proof:** one scheduled dispatch with `trigger: scheduler`, one report, one
`metadata.jsonl` line.

---

### R-3 — The module · gated on I-6, S-3

Two lines, and one decision.

```nix
default = [ "base" ];          # unchanged
example = [ "base" "format" ]; # was [ "base" "python" ]
```

**The decision:** whether `modules/devenv.nix:62`'s throw stays a throw. If S-3
proves the tombstone works, the throw stays — it is correct for a genuinely
misspelled group, and the tombstone handles the deletion case. If S-3 fails, the
throw becomes a warning and the module skips an unknown group, which is a real
loosening and needs its own argument in the charter.

**Do not change the throw without S-3's answer.** A module that silently ignores
a misspelled group is §15.4's misspelled-queue hazard in a second place.

---

### R-4 — `doctor`, three changes, each separately gated

| | Change | Gate | Ship if |
|---|---|---|---|
| **R-4a** | a check that a `format` glob and its hash agree | S-4 | S-4 shows the failure is invisible today |
| **R-4b** | a `--project` scope, so `plane-report` can page | I-2a, I-2b | the curve passes 30 s before 58 projects |
| **R-4c** | check 6 tells "machine was asleep" from "project stopped running" | I-10 | check 6 fires on every project after one missed night |

**None of the three is required for R-1 through R-3.** All three are capability,
not migration. Ship the migration first.

---

### R-5 — Wave 1 · the six registered repositories · gated on R-1, R-2, I-5

Thirteen lines across six repositories, exactly as `PROPOSAL.md` §6 tables them.

**Order within the wave matters.** `devman` first, because it owns the group
files and because its own `stack-validate` names `observantic-check` and
`siteman-check` as children — those DAG names do not change, so the cross-repo
workflow survives untouched. Confirm that rather than assume it.

**Carry three investigations through this wave:**

- **I-11** — time the first scheduled `maintain` after each re-pin. This is where
  stage 6's unexplained three-minute silence either reappears or does not.
- **I-9** — `devman` is checked out twice today. After the wave, read both
  checkouts' `.runs/` and `doctor`'s check 6.
- **I-2b** — `devman doctor` timing at 6 projects, post-change, as the curve's
  first point.

**Proof:** `doctor` clean at 6 projects; `devman run check` and `devman run test`
succeed in all six; six `maintain` reports and **one** plane report the next
morning; `observantic`'s `release` gate opens on the renamed line (S-6's third
case, for real).

---

### R-6 — The charter · gated on R-5

Five sections, with the new text already drafted in `PROPOSAL.md` §9: §7.1, §8's
boxed note, §14's criterion 14 commentary, §16's ecosystem bullet, and §13's
rollout.

**The charter changes in its own commit, after the measurement that forces it.**
That is stage 6's D9 and it is the rule for this stage too. Anything I-3 or S-1
contradicts is rewritten here rather than defended.

---

### R-7 — Waves 2, 3 and 4 · gated on R-5, R-6

| Wave | Repositories | Carries |
|---|---|---|
| 2 | `webdantic`, `poddantic`, `parsedantic`, `nix-desktop`, `loci.nvim` | proves the contract outside Python |
| 3 | `fsdantic` | **I-8** — the first live firing of §15.2's whitelist |
| 4 | the remaining ~46, in batches of ten | **I-4** before it starts; **I-2b** and **I-1** at each batch |

**I-4 runs before wave 4, not during it.** It sweeps all 58 repositories with the
command each would put in `base:test`, and records pass, fail or "no suite". If
most fail, wave 4 is adoption **and** repair, which is a different size of job
and the plan says so before starting rather than after.

**The batch crossing about 40 projects is the real test of criterion 12**, and
S-1 is what makes it safe to reach.

---

## 7. The tail — investigations that do not gate anything

Run after wave 4. Each is in `OPEN_QUESTIONS.md` with its measurement.

| ID | Question | Source |
|---|---|---|
| I-7 | do 7 of 58 git-hook users mean the recipe does not work? | OQ 8 |
| I-10 | should the plane notice a schedule it missed? | OQ 6 |
| I-12 | is a nightly cross-repository security audit worth building? | OQ 11 |
| I-13 | does `paloma-story-generation` get a `devenv.nix`, or is the denominator 57? | OQ 12 |

**I-10 feeds R-4c.** The other three feed a stage 8 or nothing.

---

## 8. What would falsify the proposal

The honest version of a plan says which results kill which recommendation.

| If this | Then this dies | And this replaces it |
|---|---|---|
| **I-3** shows the log does not name the failing task | `PROPOSAL.md` §1.1's "the loss is cosmetic" | the one-step rule survives on its other four benefits; the rollout gains a "where to look" line; a devenv issue is filed |
| **I-5** shows an undefined task is not loud | §2's rejection of the null implementation, and §6's no-flag-day argument | every repository aliases the new task name onto the old one **before** the group files land — one extra line, one extra wave |
| **S-3** shows a tombstone does not evaluate | §6's "this is not a flag day" | the migration becomes ordered and mandatory: every repository edits `groups` in the same commit as the `rev=` bump, and the plan says so loudly |
| **S-1** shows 58 dispatches fail rather than queue | §5's "the queue is what makes them fine" | `light`'s limit rises, machine-side, which is §4-legal and one number |
| **I-2a** shows `doctor` is superlinear | §5's one-nightly-plane-report | R-4b becomes mandatory before wave 4, not optional |
| **I-4** shows most repositories fail their own tests | wave 4's sizing | adoption and repair are separated into two passes, and `base:test` is defined as what the repository runs today, failing or not |
| **S-6** shows the gate derivation breaks on the rename | §6's rename of `validate` to `test` | the gate reads an explicit parameter instead of deriving from `${context.dag.name}`, or the rename is dropped |

**Two recommendations no investigation in this plan can falsify**, and that is
worth saying:

- **Deleting `full-test`** rests on a measurement already taken: `devenv test`
  exits 0 having tested nothing in 30 of 58 repositories. Nothing above changes
  that number.
- **Deleting the `python` group** rests on an argument, not a measurement — that
  a task graph belongs in devenv. If a reader disagrees, the place to argue is
  `PROPOSAL.md` §1.1, and no experiment settles it.

---

## 9. What is deliberately not in this plan

Four things a reader might expect.

**No new spike of Dagu itself.** Investigations A through E are closed and their
findings hold. This stage changes content, not mechanism. The one mechanism
question — whether the scheduler picks up a changed DAG — was measured at stage 6
and only its transition case is open (I-11).

**No performance work on `devenv shell` entry.** Criterion 7 is a delta against
`devman.enable = false`, and nothing in this plan touches the entry path. The
projection's 355 ms runs on a re-pin, which wave 1 and wave 4 will do a lot of —
so it is worth watching, not worth optimising in advance.

**No rewrite of `watch.py`, `run.py`, `show.py` or `registry.py`.** §0.1 is why:
none of them names a group or a workflow.

**No `devman list` or `devman status`.** §10 closed that and this stage reopens
nothing.

---

## 10. The order, as one list

For somebody who wants to start on Monday.

```
1.  I-3   one-step log names the failing task           ½ day   BLOCKS ALL
2.  I-5   an undefined task fails loudly                 2 h    BLOCKS ALL
    ── gate 0 ──
3.  I-6   unknown group: what a developer sees           2 h
4.  S-3   the tombstone group, three variants            ½ day
    ── gate 1 ──
5.  S-2   five workflow files, nix flake check           ½ day
6.  S-6   release gate against the renamed test          ½ day
7.  S-5   plane-report, one manual and one scheduled     ½ day
8.  S-4   the format glob/hash hazard, seen once         ½ day
    ── gate 2 ──
9.  S-1   58 synthetic DAGs on the light queue           1 day
10. I-2a  the dagu validate cost curve                   2 h
    ── gate 3 ──
11. R-1   group content                                  1 day
12. R-2   plane-report ships                             2 h
13. R-3   the module, two lines and one decision         2 h
14. R-5   wave 1, six repositories  (+I-11 I-9 I-2b)     1 day
15. R-6   the charter, five sections                     ½ day
16. R-4   doctor, whichever of a/b/c their gates opened  1–2 days
17. I-4   the base:test sweep across 58                  1 day
18. R-7   waves 2, 3, 4          (+I-8 I-2b I-1)         1–2 weeks
19. tail  I-7 I-10 I-12 I-13                             as they matter
```

**Roughly a week to the first shipped change, and the first two items decide
whether the design survives contact.**

**Write a `STAGE_7_LOG.md` as you go**, in the shape stage 1 through 6 used: the
answer, the versions, the exact command, the evidence, and the charter impact.
Commit each finding as it is confirmed. An investigation that loses a day's
evidence to a bad shell command has to run twice.
