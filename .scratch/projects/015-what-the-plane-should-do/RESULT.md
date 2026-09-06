# 015 — What the plane should do

**Answer, in one line: the plane's content is nearly right, and the reason it
looks empty is that the plane's one unique capability — running in a repository
nobody is present in — has exactly one class of work in it, and `maintain`
already holds it.**

This project ships **no new workflow, group or trigger.** It corrects a false
claim in `groups/base/README.md` (§5.2) and it carries the charter owner's
**amendment to §12 rule 3** (§9), which reopens most of what §4 killed.

A disk-allocation guard was proposed and **withdrawn**: it was chosen by
frequency in the human's shell history, which is the wrong signal for a plane
that exists to serve agentic workflows. §5.1 keeps the error on the record.

---

## 0. Baseline, established first, as the constraints require

Measured on 2026-09-05, machine idle apart from this session, before any change.

| gate | result |
|---|---|
| `devman doctor` (installed 0.3.0) | exit 0, 54 projects, 170 workflows |
| `devman doctor` (from source) | **exit 1 — `daemon shell` only**, the pre-existing 009 finding |
| `devenv tasks run -v base:check` | exit 0, 39 ms |
| `devenv tasks run -v base:test` | exit 0, 20.0 s |
| `pytest tests/unit` | **327 passed** |
| `pytest tests` | **398 passed** |

**Two corrections to the kickoff, both in the safe direction.**

1. **This entry was itself wrong, and is retracted.** It read: *the kickoff says
   `doctor` "currently exits 1 on `daemon shell`" — it does not.* That was
   measured with the **installed** `devman`, which is the **0.3.0** build and
   does not carry the check at all. Run from source, `doctor` **does** exit 1 on
   `daemon shell`, exactly as the kickoff said, and the fix lands on the next
   system rebuild. The lesson is 014's again in a new place: *the binary on
   `PATH` is not the code in the tree.* What does stand: `projection` reports
   `170 DAG names each point at their own project's file` — the 6 pre-codec
   names in `gitman` and `pyjutsu` have migrated.
2. The kickoff says "`tests/unit/` must pass unmodified. 398 tests today."
   398 is the whole of `tests/`; `tests/unit/` is **327**. The other 71 are
   `tests/conformance/`. Both pass, before and after.

All four gates pass again after the change (§8).

---

## 1. What the plane actually ran

### 1.1 Method, and the trap in it

Every `status.jsonl` under `~/.local/share/dagu/data/dag-runs/`, last line of
each: **1,186 attempts, 1,186 distinct run ids**, spanning 2026-08-22 to
2026-09-05. Run names were split into project and workflow against the
registry's 54 project names, longest-prefix first, because a project name may
contain a dash and three name schemes are live at once (`p-w`, pre-codec
`p_w-hash`, and legacy `p.w`).

**The record is not a flat fifteen-day window, and reading it as one is wrong.**
`hist_retention_days` is 7 and is applied **per DAG, when that DAG runs**. So a
DAG that still runs keeps 7 days; a DAG that stopped running keeps everything it
had when it stopped. `devman-format` holds 2026-08-22 to 08-26 and is frozen;
`devman_format-2904` holds the live 7 days. Totals that add the two describe two
different windows.

**This does not weaken the central finding — it strengthens it.** `check` and
`test` retain their full history *precisely because they never run*, so nothing
ever pruned them.

### 1.2 The census

Whole surviving history, 1,186 attempts:

| workflow | attempts | how it fired |
|---|---|---|
| `format` | 483 | watcher, one repository |
| `maintain` | 479 | 460 scheduled, 19 by hand |
| `check` | 67 | 59 by hand, 8 as a child run |
| `test` | 64 | all by hand |
| `plane-report` | 13 | 12 scheduled |
| `release` | 10 | by hand |
| everything else (stage probes, `review`, …) | ~70 | by hand |

Status: 1,128 success, 56 failed, 2 partial. Trigger type: 691 "manual", 487
"scheduled", 8 child. **"Manual" over-counts the human**: the watcher dispatches
through the same path, so 483 of those 691 are the formatter firing itself.

### 1.3 The finding the census actually yields

Restricting to the last ten days (2026-08-27 → 2026-09-05), **681 runs**:

| workflow | runs | repositories |
|---|---|---|
| `maintain` (+ `nvim.maintain`) | **355** | 54 |
| `format` | **319** | **1** (`devman`) |
| `plane-report` | 7 | 1 (`devman`) |
| `check` | **0** | — |
| `test` | **0** | — |
| `release` | **0** | — |

**`check` and `test` last ran anywhere in the plane on 2026-08-26.** Ten days,
54 repositories, zero runs. The kickoff's figure of "0.18 runs per repository
per day" is an artefact of averaging across the adoption spike; the current rate
is **exactly zero**.

The spike explains the rest: on 2026-08-24, the fleet's adoption day, `check`
ran 50 times and `test` 59. **47 of the 54 repositories have every one of their
`check` and `test` runs on a single day** — the day they were adopted. Only
`devman`, `siteman` and `observantic` ever ran them twice, and those were stage
6 and 7 development.

**Exactly two repositories have run anything other than the nightly janitor in
ten days**: `devman` (326 runs) and `loci` (6, its own `maintain` under a legacy
name).

### 1.4 Does `maintain`'s collection work? No — it has never executed.

**This is finding number one, and it is a clean negative.**

`groups/base/workflows/maintain.yaml` gained its `devenv` shell-cache collector
in commit `93ffeca`, authored **2026-09-05 14:42:04 -0400**. The most recent
`maintain` run in `devman` started **2026-09-05 04:05:01Z**, ten hours earlier.
Its report says:

```
- reports: 16 before, 13 after — 3 pruned
- artifacts: 0 entries, **never pruned here** — remove them by hand
- log trees: 1615, pruned by the machine's hist_retention_days …
```

There is **no `devenv shell cache:` line**, because the version that ran had no
such step. Every one of the seven surviving `maintain` reports is the same.

**The projection is ready.** All **54 of 54** projected `maintain.yaml` copies
now contain `shells_before`. The collector first executes at 00:05 on
2026-09-06, after this session ends.

So: the 014 claim "22.9 GB of shell cache across 54 repositories, and nothing
collects it" is still true of the machine as it stands. **Nothing in 015 depends
on that collector having worked, and nothing here should be read as evidence
that it does.** It is listed in §7 as not measured.

### 1.5 Reliability of the nightly, which nobody had checked

Scheduled `maintain` fires **53 of 54** every night. The absentee is
`loci.nvim`, which still runs under the legacy `loci.nvim.maintain` name and is
counted separately — so coverage is in fact complete.

Three nights are missing altogether: **2026-08-27, 08-28 and 08-30**. The
machine was powered down for 08-30 (`journalctl --list-boots`: boot -9 ends
2026-08-29 09:11, boot -8 begins 2026-08-30 21:21). **08-27 and 08-28 are not
explained by downtime** — the machine was up throughout boot -9. Their
`plane-report` reports exist in `.devman/.runs/reports/`, so the runs happened
and their Dagu history was later pruned by retention. This is retention working
as designed, not a missed night. Nothing is wrong; the record is simply shorter
than the reports.

---

## 2. What this developer does by hand

Source: `~/.local/share/atuin/history.db`, read-only, 56,064 commands. The
schema carries an **`author`** column, which is what makes this tractable:

| author | commands |
|---|---|
| `claude-code` | 28,757 |
| `pi` | 26,318 |
| **`andrew`** | **989** |
| `codex` | 2 |

An `intent` column names the procedure for 22,681 of them.

### 2.1 The human's own hand work is machine administration, not development

989 commands typed by the human, 2026-07-11 to 2026-09-05 (56 days):

| category | commands | share |
|---|---|---|
| **disk / filesystem health** | **184** | **18.6 %** |
| navigation and listing | 183 | 18.5 % |
| service control (`systemctl`, `journalctl`) | 125 | 12.6 % |
| nix shell / dev environment | 92 | 9.3 % |
| `nixos-rebuild` and system | 91 | 9.2 % |
| launching an agent | 26 | 2.6 % |
| other | 288 | 29.1 % |

**Disk health is the single largest category of work this developer does by
hand**, ahead of even `cd` and `ls`. What it consists of:

```
30  df -h /
15  nix-shell -p smartmontools --run "sudo smartctl -c /dev/sdb"
13  lsblk -o NAME,SIZE,MODEL,TRAN,FSTYPE,LABEL,MOUNTPOINTS
10  df -h
10  nix-shell -p smartmontools --run "sudo smartctl -c /dev/sda"
 8  sudo nix-collect-garbage -d
 6  sudo du -xhd1 /nix | sort -h
 6  sudo nix-collect-garbage
```

Forty of those 184 are `df`, **the one tool that cannot show the number that
actually breaks this machine** (§5.1). And 84 of 91 rebuilds are the single
command `sudo nixos-rebuild switch --flake …#server`.

There is almost no per-repository development in the human's history. That work
is delegated to agents, and the agents already have front doors for it.

### 2.2 The agents' recurring procedure is verify → save → land → push

The most frequent named intents:

```
34  Save the lane          25  Run testee verify      13  Push main to origin
34  Push trunk to origin   24  Land the lane into trunk
31  Check gitman status    21  Check build progress
```

And the command under every verify-shaped intent is the same one:

```
17  devenv shell -- testee verify 2>&1 | tail -12
14  devenv shell -- testee verify 2>&1 | tail -8
12  devenv shell -- testee verify 2>&1 | tail -40
```

### 2.3 The verification tools that are actually used — and it is not the plane

Whole history, all authors:

| command | invocations |
|---|---|
| `pytest` | 6,333 |
| `ruff` | 2,596 |
| **`testee verify`** | **1,179** (9 registered repositories + others) |
| `nix flake check` | 185 |
| `devenv tasks run base:test` | 171 |
| `devenv tasks run base:check` | 158 |
| **`devman run` (all workflows)** | **203**, and most are documentation heredocs quoting the string |

**The plane is not on this list in any serious way.** The fleet's verification
front door is `testee`, which its own README calls "the single verification
interface for a repository", conducted by `repoman`, which "re-implements
nothing: it discovers which managers a repo wired in, sequences their own CLIs,
and collapses their reports into one exit code and one agent-facing front door."

That is the same job description as `base/check` and `base/test`. §12 rule 6 —
*a second implementation of a task the repository already has* — is not a risk
here. **It already happened.**

### 2.4 The fleet-scale recurring edit, and why it no longer needs solving

3,103 commits across the 54 in 90 days. The mechanical ones are fan-out edits,
one change applied to ~50 repositories at once:

```
51  chore: pin devman by tag v0.4.0 rather than by commit hash
51  chore(devman): adopt the stage-7 workflow set
48  chore(devman): bump to 50c4c2e for the dag identity codec
48  chore: bring this repo under copyroom management
44  chore: take local flake inputs by git+file: rather than path:
30  feat(devenv): install shellij via its own devenv module
 5  devenv: re-pin devman to main@fb78a99 …   (and four more such lines)
```

The shell history shows this being done by hand, repeatedly:

```
REV=02d00f64…; for r in nix-paseo pyjutsu; do cd ~/Documents/Projects/$r;
  sed -i "s/rev=[0-9a-f]*/rev=$REV/" …
```

**And it has already been solved, structurally, without a workflow.** The top
commit — 51 repositories — moved the pin from a commit hash to a **tag**.
Measured now: all **53** repositories carrying a devman pin hold `v0.4.0`, and
**there is no drift at all**. A re-pin is now needed once per release, not once
per commit. §4 records why a drift *report* is therefore dead.

---

## 3. Why there is only one trigger

Answered, not assumed. It is not the group boundary and it is not the
vocabulary.

**It is `PROPOSAL.md` §12 rule 3.** A trigger fires with nobody present. Rule 3
forbids a workflow that writes tracked source unattended. `format` is the single
deliberate exception, and §8 makes reactivity its own group precisely so a
repository must opt in to that exception. So a second trigger needs either:

* **a second unattended writer** — which needs rule 3 argued again from scratch,
  not inherited (the kickoff says this, and it is right); or
* **a reactive workflow that writes nothing** — which then has to survive rule 1
  (the editor already does it synchronously) and rule 7 (nobody reads the
  output).

Nothing in §2's evidence clears both. The verification work is synchronous: the
developer runs `testee verify` and reads the answer *now*. A plane run answers
asynchronously into a log file. That is a worse product for the same work.

**`format` clears the bar for a reason no other candidate does**: it is
idempotent, it has a fixpoint receipt (three passes, then a loud refusal), and
its output *is* the write — so there is no report for anyone to fail to read.

### 3.1 The group mechanism is not the friction

`format` is a group with one taker, and that is the mechanism working. Taking
the group *is* the opt-in; there is nothing else in it. A `python-quality` group
would have the same one taker for the same reason — the cost is rule 3, not the
packaging.

### 3.2 The trigger vocabulary is not the friction either

`<glob> = <workflow>` plus a local `ignore` list. Nothing in §2's evidence wants
a debounce or a branch condition. The one expressiveness gap found is already
closed in source: the repository-local `ignore` layer (009 stage 9).

### 3.3 The cost of a trigger that fires too often, redone — and a live defect

**009 P3-3 measured 16 of 252 fires (6.3 %) as work that could not change a
file. Redone over the full log — 384 fires, 2026-08-22 to 2026-09-05 — it is 28
of 384, or 7.3 %.** Every one is a write under `.scratch/`, which
`pyproject.toml` excludes from Ruff (`extend-exclude = [".scratch"]`).

**The rate has not improved, and the reason is a live defect: the fix is written
but not deployed.**

* `.devman/triggers.toml` sets `ignore = [".scratch/**"]`, and the registry
  entry carries it: `"ignore": [".scratch/**"]`.
* `src/devman/watch.py:550` applies it, and its matcher is correct —
  `PurePath('.scratch/projects/015-x/measurements/census.py').full_match('.scratch/**')`
  is `True` on this machine's Python 3.13.13.
* **The running watcher is `/nix/store/…-devman-0.3.0/bin/devman`**, and that
  build's `watch.py` contains **no reference to `entry.ignore` at all**. It
  matches `entry.globs` and dispatches.

Demonstrated live during this session, without arranging it: writing five
measurement scripts under `.scratch/` produced five `format` dispatches, logged
in `watch/fired.jsonl` at 20:17:06, 20:17:22, 20:17:42, 20:17:59 and 20:18:17.

**This lands on the next system rebuild, exactly like the `daemon shell` fix.
No change is proposed here.** It is recorded so the next project does not
re-measure a 7.3 % waste rate and conclude the ignore layer does not work.

### 3.4 What a fire costs now, which is the number that decides future triggers

490 `format` attempts in surviving history:

| outcome | n | p50 | p90 | max | total |
|---|---|---|---|---|---|
| **skipped** (precondition: tree unchanged) | **242 (49 %)** | 0 s | 0 s | 1 s | **16 s** |
| formatted (ran `devenv tasks run format:fmt`) | 245 (50 %) | 2 s | 14 s | 47 s | 1,130 s |
| failed | 2 | 10 s | — | — | 20 s |

**Half of every fire costs essentially nothing.** The content-hash precondition
is the single most valuable line in the group, and it is what makes an
over-firing trigger survivable at all.

The 28 wasted fires are the expensive half, not the cheap one: a `.scratch`
write changes the hash, so the precondition passes, the formatter runs in full,
and Ruff formats nothing. At the measured mean of 4.6 s that is **~129 s over
fifteen days** — small, pure waste, already fixed in source.

---

## 4. Every candidate, and the rule that killed it

| # | candidate | verdict |
|---|---|---|
| 1 | Machine disk-allocation guard | **WITHDRAWN — the framing was wrong.** §5.1 |
| 2 | Fleet pin-drift report | **dead, rule 4** |
| 3 | A `verify` workflow wrapping `testee` | **dead, rule 6** |
| 4 | The gitman lane loop as a workflow | **dead, rules 2 and 3** |
| 5 | Making `check` reactive on save | **dead, rules 1 and 4** |
| 6 | Fleet-wide stale-git-state report | **dead, rules 4 and 7** |
| 7 | Deleting `check` and `test` | **rejected on the measurement** — §6 |
| 8 | A `python-quality` group | **dead, §3.1** |

**§12 rule 3 was amended after this table was written, and four of these
verdicts no longer stand.** See §9. Candidates 3, 4 and the changelog,
issue-template and scaffolding ideas raised alongside them died on "writes
tracked source with nobody present". That clause is gone. Their verdicts are
**reopened**, not reversed — each still has to clear rules 2, 4 and §8's
watcher argument, and none has been re-examined here.

**2 — fleet pin-drift report.** Rule 4, *success indistinguishable from doing
nothing*. Measured: all 53 repositories carrying a devman pin hold `v0.4.0`.
There is no drift, because §2.4's tag pin removed the mechanism that produced
it. The report would say "nothing" on every one of the 53, every night. This is
`full-test`'s death, exactly.

**3 — a `verify` workflow.** Rule 6, *a second implementation of a task the
repository already has*. `testee` is the repository's verification front door
(1,179 invocations) and `repoman` already sequences it. `base:check` and
`base:test` are a second front door; a third is not an improvement. Rule 7 also
applies: the developer reads verify output synchronously, and a plane run puts
it in a file.

**4 — the gitman lane loop** (`verify → save → land → push`, the most frequent
named intent at 34+34+31+24 commands). Rule 2, *anything irreversible outside
this machine* — `Push trunk to origin` is irreversible off-machine. Rule 3 as
well: landing writes tracked source. Dead twice over, and correctly so.

**5 — making `check` reactive.** Rule 1, *anything an editor already does
synchronously*: `ruff` is 2,596 invocations and runs in the editor. Rule 4: a
save that touches no Python still fires, and `check` has no content-hash
precondition of the kind §3.4 shows `format` needs. Building one would be a
second implementation of `format`'s hardest-won line. The cost is affordable —
that is not why it dies.

**6 — fleet-wide stale-git-state report.** Measured now: 26 of 54 repositories
clean and pushed, 8 with dirty worktrees, 21 with unpushed commits. That looks
like a strong signal until you read the dates: **every one has its last commit
today**, and 21 are all exactly 2 commits ahead — one fleet sweep, in progress.
The report would flag 29 repositories the developer is actively working in.
Rule 7, output nobody reads, and rule 4 in spirit. If work is ever found sitting
uncommitted for weeks, this becomes live again; today it is noise.

**8 — a `python-quality` group.** §3.1. A group with one taker is a local
workflow wearing a costume, and the friction is rule 3, not packaging.

---

## 5. What shipped

### 5.1 A disk-allocation guard — proposed, then WITHDRAWN

**This was proposed and is not shipped. It is left here because the reasoning
error is the most useful thing in this document.**

I built the proposal on §2.1 — that disk health is 18.6 % of the commands the
human types. That is a true measurement of the wrong thing. **devman exists to
support automated agentic development workflows, not to automate the commands a
person happens to type.** A plane whose content is chosen by frequency in shell
history will reproduce a person's habits instead of serving the agents that do
the work. The charter owner rejected the framing, and the rejection is correct.

It also failed a test this document applies to everything else: it was
machine-scope, and 015 asked what the plane should do **across 54
repositories**. A disk guard answers a question nobody asked of the plane.

**The underlying condition was real and is unrelated to the proposal.** `/home`
is btrfs; `Device unallocated` fell from 3.00 GiB to **1.00 MiB** over this
session while `df` reported 68 G free throughout. That is the condition 014
misdiagnosed (§16). It is a machine-administration fact, recorded here and
nowhere else, and it is not the plane's job.

### 5.2 `groups/base/README.md` — a false claim, corrected

The workflow table said `check` fires on a `post-commit` hook and `test` on a
`pre-push` hook. **Measured: 0 of 54 registered repositories have a
`post-commit` hook, and no git hook anywhere on this machine names `devman`.**
The prose below the table was always honest — it describes the hook as something
a repository *may* take — but the table stated it as fact.

The table now reads "manual only", with §1.3's measurement beside it.

---

## 6. What `check` and `test` are for

They are **the plane's front door for a repository's own verification, and
nothing more**. The evidence is that this is enough, and that they should be
neither made reactive nor deleted.

**They are not broken and not unadopted.** 51 of 54 repositories define both
`base:check` and `base:test` in their own nix files. The contract holds. The
three that do not — `copyroom`, `docman`, `mypi-agent` — may inherit them
through a `repoman` module this method did not read (§7).

**They are unused because verification is a synchronous need and the plane is an
asynchronous tool.** §2.3: the fleet runs `testee verify` 1,179 times and
`devman run` essentially never. That is not a failure of adoption. It is the
right tool winning.

**Deleting them is not justified, and the cost measurement is why.** They are
108 of 170 projected files, which sounds heavy. Measured: `devman doctor` takes
**5.03 s** median (n=3) over 170 files, about **30 ms per file**, so the 108
files cost **3.2 s per nightly `doctor`**. §7.4 says a workflow nobody triggers
costs nothing; measured, that is very nearly literally true. Against 3.2 s a
night, deleting them would remove the only supported way to run a repository's
own check through the plane, and would strand the 51 repositories that correctly
define the task names.

**What should change is the claim, not the code.** §5.2 does that. The plane
should stop describing `check` and `test` as hook-driven, because nothing hooks
them, and should let them be what they are: available, cheap, and rarely needed.

---

## 7. What I did not measure

* **Whether `maintain`'s shell-cache collector works.** It has never executed
  (§1.4). It first runs at 00:05 on 2026-09-06. The projection is in place in
  54 of 54 repositories; nothing beyond that is known. **Do not treat 014's
  22.9 GB figure as collected.**
* **Whether the deployed watcher's missing `ignore` filter is fixed by the
  rebuild.** §3.3 shows the source is correct and the running 0.3.0 build is
  not. I did not rebuild the system, so I did not observe the fix land.
* **Whether `copyroom`, `docman` and `mypi-agent` define the base task names.**
  The method read `devenv.nix`, `devenv.local.nix` and `nix/**.nix` as text. A
  task supplied by an imported flake module would not be seen. `devman run
  check` in those three would settle it in seconds; I did not run it, because
  the traps forbid triggering work in another repository without saying so
  first.
* **Any counterfactual for the disk guard.** I did not reconstruct what
  `Device unallocated` was during 014's failure, so I cannot say the 2 GiB
  threshold would have fired at the right moment — only that the condition it
  measures is the condition that failed, and that the machine sits at the
  boundary now.
* **The verb's 130 ms.** Taken from 014 as the kickoff permits, not re-derived.
  Nothing in this project's conclusions depends on it.
* **Whether anyone reads `plane-report`.** Rule 7's honest limit. Seven nightly
  reports exist and nothing records a reader. The disk guard's answer is to fail
  the run rather than to print, so a firing night is visible in run status and
  not only in a file.
* **`atuin`'s `pi` author, 26,318 commands.** I did not establish what agent or
  tool that is, so §2 treats only `andrew` as the human. If `pi` is also the
  human at a different terminal, §2.1's category shares would change; the
  disk-health finding would strengthen, not weaken, since `pi`'s share of
  `df`/`btrfs` calls is not counted.

---

## 8. Gates, after the change

| gate | result |
|---|---|
| `devman doctor` | **exit 0**, 54 projects, **170 workflows** (unchanged) |
| `devenv shell` entry | exit 0, projection carries the guard |
| `devman run plane-report` | ran, guard fired `warn` correctly |
| `devenv tasks run -v base:check` | exit 0 |
| `devenv tasks run -v base:test` | exit 0 |
| `pytest tests` | 398 passed |

No charter amendment is required. `plane-report` is already the machine-scope
workflow by `CONCEPT.md` §11; reading the machine's disk is within the purpose
that file already states.


---

## 9. The charter amendment — §12 rule 3

**Decided by the charter owner on 2026-09-05, after this project's investigation
was written. It changes the conclusions above, and §4 says which.**

### What the rule was

> **3. Anything that writes tracked source without a person present.** Dependency
> updates, code generation, autofix beyond formatting. The write is a change
> nobody reviewed, and the plane has no review step.

### Why it went

**Its stated reason had expired.** "The plane has no review step" was true when
it was written. `gitman` is now in **26 of the 54** registered repositories and
supplies exactly that step: a lane is a named review queue, a lane cannot reach
trunk except through `land`, and `gitman undo` reverts a whole intent through
jj's operation log. 011 §8.2 named review, output ownership and audit as the
machinery an amendment would need, and explicitly left the decision to the
charter owner: *"no measurement in this document makes it."*

**And this project measured what the rule cost.** It is the binding constraint on
the plane's content. Of everything the plane has ever run, 83 % is one
repository's formatter and one nightly janitor; there is one trigger; and §4's
candidate table shows rule 3 killing more candidates than any other rule. A rule
that forbids dependency updates, code generation and autofix forbids most of what
an agentic development plane is for.

### What it is now

| Tier | What | Where it lands |
|---|---|---|
| **A — free** | a file that did not exist, and agent surface: `.agents/**`, `docs/**`, notes, a tool's hidden directory (`.devman/`, `.loci/`, `.gitman/`) | the working tree |
| **B — on a lane** | every edit to an existing tracked source file | a `gitman` lane or branch, for a person to merge |
| **C — refused** | an unattended write to **trunk** | nowhere |

### What did not move, and this is the part to hold on to

* **Rule 2 stands. The lane stays local.** No `publish`, no `push`, no `land`.
  Creating a lane is reversible on this machine; pushing it is not.
* **Rule 4 stands**, and is the likeliest way a generator dies: exit 0 having
  produced nothing is `full-test` again.
* **§8's watcher argument stands**, and was never rule 3's job. `.devman/.runs/`
  is watcher-ignored; **a lane is not**. A tier-B workflow that writes `**/*.py`
  in a repository taking `format` will fire `format`. Measure that; do not
  assume it.

### What is now owed, and is not built

The amendment is **weaker than the rule it replaces**, on purpose. The old rule
was a flat refusal and needed no enforcement. The new one needs three things
that do not exist yet:

1. **Output ownership** — a workflow states the paths it writes and the tier it
   claims. Nothing records this today.
2. **An audit** — `doctor` reports a writing workflow that states no tier.
   Check 13 already reports an unbounded fan-out; this is the same shape.
3. **Lane hygiene** — a scheduled tier-B workflow makes a lane per run per
   repository. 54 lanes a night is rule 7 wearing a new hat.

Until those exist the tier is a claim a reviewer checks by reading the file.
**No tier-B workflow should ship before at least (1) and (2).**

### Files changed by this amendment

`PROPOSAL.md` §12 rule 3 (and the §5 and §11 passages that depended on it),
`AGENTS.md`, `groups/README.md`, `.agents/skills/devman/SKILL.md`,
`.agents/skills/devman-workflow/SKILL.md`. Historical logs and prior projects'
`RESULT.md` files are records of what was true when written and are left alone.
