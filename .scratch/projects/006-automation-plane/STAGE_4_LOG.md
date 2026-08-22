# STAGE 4 — what was measured while giving the plane something to do

`STAGE_1_LOG.md` holds what stage 1 found while building the two modules,
`STAGE_2_LOG.md` what stage 2 found while turning the plane on, and
`STAGE_3_LOG.md` what stage 3 found while making it react. This holds stage 4,
in the same shape: the answer, the versions, the exact command, the evidence,
and the charter impact.

**Stage 4 is the first stage whose deliverables are files rather than
machinery**, so one more column matters in every entry below: *what a person
reads afterwards*.

**Environment for every entry below**, unless it says otherwise:

| Fact | Value |
|---|---|
| Host | NixOS 26.11.20260705, hostname `server`, Nix 2.34.7 |
| Dagu | 2.15.0, installed, running as `systemd --user` unit `dagu` |
| devenv | 2.1.2 |
| devman | 0.3.0, `/run/current-system/sw/bin/devman` — `run`, `show`, `doctor`, `watch` |
| watchexec | 2.5.1, running as `systemd --user` unit `devman-watch` |
| Registry | `~/.local/share/devman/` — 6 projects, 19 workflows, 19 DAGs |
| Date | 2026-08-22 |
| devman rev | branch `dagu-devenv-automation-eli5` |

---

## S1 — What "done" means for stage 4, written before anything was built

**Why this entry exists.** Stages 1, 2 and 3 each closed on a table of
measurements somebody else wrote down first: §14's seventeen criteria.
**§14 contains no stage-4-only criterion**, so stage 4 is the first stage whose
success has no measured definition. `STAGE_4_PROMPT.md` §6 requires this entry
to be written first and to be what the stage is judged against. It was written
before the first deliverable file existed, and it has not been edited since —
later entries record where it was met and where it was not.

**The state it was written against**, checked rather than copied forward:

```
$ devman doctor
devman doctor — 6 projects, 19 workflows
ok  plane / queues / validate / queue names / literal dir / shadowing /
    stale entries / run output / cross-repo / watcher            (ten checks)
Nothing to report.                                               exit 0
```

### The nine conditions

**D1 — Six deliverables, and each one has run.** §13 names six:
`review workflows`, `release`, `maintenance`, `benchmark campaigns`,
`agent workflows`, `policy gating`. Each is a file in one of §7.3's three
homes. **A workflow that was written and never run is not delivered**: each one
runs at least once on the installed service, in a real repository, and the entry
quotes its `metadata.jsonl` line and its log.

**D2 — Measured by coverage, not by count.** Six files that all run in devman's
own checkout prove less than two a second repository takes unedited. So:

- at least one deliverable reaches **three or more** registered repositories
  with no edit to any of them beyond the group name and the task names that
  group asks for;
- at least one deliverable is run in a **second** repository, unedited, and the
  entry quotes both runs;
- every deliverable states **which of the three homes** it landed in — a group
  every repository takes, a group taken by name, or one repository's own
  `.devman/workflows/` — and which measurement or rule put it there (§16's
  promotion rule: a group begins when a second repository wants the same file).

**D3 — Every criterion that holds must still hold, measured rather than
asserted.** A criterion-by-criterion table against §14, in the shape of stage
2's S17 and stage 3's S12. Four are re-run by command rather than reasoned
about, because content pressures them hardest:

| # | Why stage 4 pressures it |
|---|---|
| 1 | new files evaluate under both interfaces; `nix flake check` must still pass |
| 10 | a release wants a version, a campaign wants a target, an agent wants a path — each is a route to an absolute path in a workflow |
| 14 | a campaign and a gate both want an order, and devenv already states one |
| 17 | a release and an agent run both want to know *which project* — the registry is the only answer, and reading it must stay the only way in |

Criterion 13 is re-run as well, because stage 4 adds workflows that **write into
a tree the watcher watches** while the watcher is running.

**D4 — Grow the plane only under a measurement, and record the measurement
first.** §7.1's list of global names stays at **four**, §10's command list at
**four** (`run`, `show`, `doctor`, `watch`), and §7.4's repo interface at
**three keys** — unless an entry below records the run that could not be written
without the growth, *before* the commit that grows it. The same rule covers a
new queue name, a new machine-module option and a new registry field.

**D5 — Six decisions answered with evidence, none deferred.**
`STAGE_4_PROMPT.md` §7 names them: how scheduled work is triggered; whether
stage 4 needs a secret and whether the machine module grows to supply one;
whether agent workflows fit the contract, and how an argument reaches a run;
whether policy gating needs a fifth global name; which queue a benchmark
campaign names; and where each deliverable lives. Each gets a stated answer,
with the command that decided it. "Left for stage 5" is not an answer.

**D6 — Every deliverable leaves something a person can read without re-running
it.** §10 of the prompt is explicit that a wrong answer from stage 4 is a
*successful run that did the wrong thing*, and that the plane will not grow a
check for it. So visibility is the deliverable's own job: every stage-4 run
leaves, in the triggering project's own tree, its `metadata.jsonl` line **and**
either a report under `.devman/.runs/reports/` or a log that holds the finding
rather than only the verdict. **A run whose only evidence is its exit code is
not delivered.**

**D7 — A gate that fails is a gate; a gate that skips is not.** Any deliverable
that decides whether something may proceed records a **failed** run when it
refuses. This is stated in advance because the plane already contains the
opposite pattern for a good reason — `python-format`'s step-level precondition
records `Succeeded` with a skipped step, so that a self-stopping loop does not
fill the history with things that look like failures (S6). A release that
silently skips is D6's failure mode arriving through the mechanism chosen to
avoid it.

**D8 — Nothing gives the registry a second entry path.** The rule that outranks
everything else, unchanged since stage 1. No `devman register`, no hand-written
entry, no `dagu profile` keyed by project, no fallback scan, no "just this once"
initialisation step. A deliverable that appears to need one stops and says so
here before it is written. Reading devman's own registry is not scanning;
walking the disk to find repositories is (§15.1).

**D9 — The charter changes only in its own commit, and the log entry comes
first.** Rule 4. Stages 1–3 did this six times; stage 2 once let a charter
change share a commit with the code that motivated it and had to record the
slip.

**D10 — The machine is left as it was found, and every touched repository is
named.** No throwaway project left in the registry, no directory named literally
`${DEVMAN_PROJECT_DIR}` or `${DEVMAN_SELF_DIR}` anywhere, `devman doctor` back
to `Nothing to report`, and every change to somebody else's repository committed
there and listed here (rule 7). No `nixos-rebuild switch` — a machine change is
proposed, evaluated, and handed over (rule 8 of the prompt's §8).

### What this deliberately does not promise

- **Not that stage 4 makes the first use of §9.4.** The prompt observes that
  secrets are specified and never used, and asks for a decision. D5 requires the
  decision and the measurement behind it; it does not require the answer to be
  yes. A secret declared because the section exists would be theatre, and §9.4's
  own argument is about what a workflow *needs*.
- **Not a seventeenth-and-a-half criterion.** §14 is the charter's, and D3 says
  its seventeen must still hold. This entry adds no permanent criterion; it
  defines when *this stage* is finished.
- **Not that every deliverable is portable.** §16's promotion rule says a group
  begins when a second repository wants the same file. A deliverable only
  devman wants belongs in devman's own `.devman/workflows/`, and D2 asks it to
  say so rather than to pretend otherwise.

**Charter impact:** **none.** This entry is stage 4's own definition of done,
not an amendment to §14.
