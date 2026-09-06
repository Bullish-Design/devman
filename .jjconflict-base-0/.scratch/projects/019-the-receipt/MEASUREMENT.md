# 019 — Question 1, measured

**Read-only. No workflow was run.** Window: the 7-day retention window,
2026-08-30 → 2026-09-06. 687 attempts, which matched `dagu history` exactly, so
this is the population and not a sample.

## The headline number is real and it is misleading

**About 500 of 687 runs (73 %) succeeded while changing nothing.** Do not carry
that number forward without its decomposition, because most of it is the design
working.

| workflow | runs | did work | changed nothing | how "nothing" was decided |
|---|---|---|---|---|
| `format` (devman only) | 356 | **23** | 331 (93 %), + 2 failed | step skipped, or ruff reported `0 files reformatted` |
| `maintain` (54 repos) | 324 | 160 | **164** (51 %) | its own report says `0 reports pruned` and `0 shell scripts collected` |
| `plane-report` | 7 | — | effectively all | consecutive reports byte-identical but for run id, timestamp, uptime |
| `check` | **0** | — | — | never ran in the window |
| `test` | **0** | — | — | never ran in the window |

**331 of `format`'s "did nothing" runs are not rule 4.** 208 were the
precondition skipping, which is the hash doing its job. That is a correct
loop-break, and a check that flagged it would be flagging the feature.

## The finding that changes the design

`format`'s 356 runs decompose exactly:

- **208 skipped** — precondition matched. Dagu reports `succeeded`.
- **125 ran the formatter, which reformatted nothing** (`N files left
  unchanged`). **These wrote `.devman/.runs/.format.hash` anyway.**
- **23 actually reformatted a file.**

**THE RECEIPT IS A TREE HASH, SO IT CANNOT TELL CASE 2 FROM CASE 3.** It is
written on 148 runs, and only 23 of those did work. The precondition fires
whenever any `.py` file's content or set changes — including a file another tool
already formatted correctly.

**A generalised receipt copied from this prototype inherits that blindness.**
§5's question 2 asked what shape a receipt takes; this answers it. **A receipt
must record a delta, not a state hash.** `format`'s hash is right for
`format`'s own job — it is a precondition, read by the next run — and wrong for
the job 019 wants, which is read by `doctor`.

The 125-vs-23 split was only knowable because ruff prints a summary line to
stdout. **That is a property of the tool in that step, not of the plane.** No
plane-level record distinguishes them.

## `check` and `test` ran zero times

The two workflows the `full-test` disaster came from did not run at all in the
window. **A detector shipping today would point at `format` and `maintain` — the
two least suspicious workflows in the plane — and stay blind to the class that
motivated the project.** State this in the result. It is the strongest argument
for scoping 019 to writers and saying so.

## A live rule-4 finding, and it answers an open 014 question

**`maintain`'s devenv shell-cache collector deleted 0 files in all 324 runs, in
all 54 repositories.** The 014 measurement that justified it — 277,950 files,
22.9 GB — has not recurred in this window.

`maintain`'s 160 "productive" runs are also **entirely self-referential**: every
one pruned only reports `maintain` itself had written on an earlier night,
deltas of 1–7 files. It cleans up after itself and does nothing else.

**A rule-4 check would be right to flag `maintain`, and this is the project's
first real subject.**

## Question 4's premise is confirmed

**One project of 54 has a `writes.toml`** — `groups/format/writes.toml`. A check
that reported on every workflow declaring nothing would report 53 findings on
day one, which is no report.

## What `maintain` got accidentally right

`maintain` prints `N before, N after` for both the reports and the shell cache.
**That is a receipt with counts, written unconditionally.** It is a log by
intent, and its body carries the delta anyway. It is the closest thing in the
plane to the shape 019 wants, and it was not designed to be. **Read it before
designing the receipt format.**
