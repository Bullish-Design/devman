# Investigate: what to do with the `atuout` reconciler branch

Decide the end state for the `reconciler-process-test` branch, its worktree, and
the `atuout-reconciler-test` plane registration. Wave 4 of stage 7 left this
one loose end: an adoption that could not land on `main` because its `devenv.nix`
must differ from the main checkout's. The work is done; the question is what
happens to the machinery.

Work in `/home/andrew/Documents/Projects/atuout-reconciler-test` (the worktree)
and `/home/andrew/Documents/Projects/atuout` (the main checkout). Both are
clean checkouts of the same repository, `github.com/Bullish-Design/atuout`.

## Read these first, in this order

1. `.scratch/projects/007-standard-workflows/STAGE_7_LOG.md`, the entry
   **"R-7 wave 4, batch 1"** — the adoption of `atuout` and
   `atuout-reconciler-test`, the note that pushing created
   `origin/reconciler-process-test`, and the record that the worktree's
   in-progress work was not committed.
2. The branch and worktree state, exactly as listed under "Where things stand"
   below. Re-verify the hashes with `git rev-parse` — do not trust this
   document's numbers over the repository's.
3. `.scratch/projects/007-standard-workflows/WAVE_4_PROMPT.md` — for the
   adoption shape and the environment's traps, which still apply.

## Where things stand — verified 2026-08-24, do not re-derive

**Branch topology.**

| | |
|---|---|
| branch `reconciler-process-test` | head `b9b12a2` — `chore(devman): adopt the stage-7 workflow set` |
| its parent | `ab4dbb1` — `fix: reconciler shuts down promptly on SIGTERM when tail stream is idle` |
| `main` | head `3ae56d0` — 5 commits ahead of `ab4dbb1` (`d198059` shellij, `edb5572` agent-ingest, `f12ffcd` + `219f941` docs, `3ae56d0` the atuout adoption) |
| merge-base | `ab4dbb1` — **the SIGTERM fix is on `main`** (verified `merge-base --is-ancestor`) |

The branch's **only committed delta** from the merge-base is the adoption
commit `b9b12a2`. That commit touches `devenv.yaml` and `devenv.nix` only.

**The adoption is checkout-specific, on purpose.** The branch's `devenv.nix`
declares `project = "atuout-reconciler-test"`; `main`'s declares
`project = "atuout"`. Two checkouts, two registrations. **Merging the branch
into `main` would overwrite `main`'s devenv with the worktree's and break the
main checkout's own registration.** A merge is wrong by construction; the
investigation must not propose one.

**Uncommitted work in the worktree (the user's, untouched by wave 4):**

| File | What it is |
|---|---|
| `M pyproject.toml` | adds a `slow` marker to `[tool.pytest.ini_options]` |
| `?? tests/test_reconciler_process.py` | **427 lines** — real detached-process integration tests for the reconciler: spawns `atuout reconcile --daemonize`, observes boot / flock / pidfile / `TailHistory` stream / live `ENDED` event / SQLite backfill fully out-of-process, plus the single-instance guard, clean SIGTERM shutdown, and crash-restart. Marked `slow`, skipped when `atuin` is not on PATH, per-test skip when the daemon predates PR #3510 |

**Main already has the pieces the test needs:**

- `main` declares the `slow` marker already (wording differs slightly from the
  worktree's addition — check for a duplicate/conflicting declaration under
  `--strict-markers` before committing the pyproject change).
- `main`'s devenv carries `atuin-src` + `rust-overlay` — the atuin daemon with
  PR #3510's Semantic service builds there.
- `main` has `tests/test_integration_daemon.py` (in-process reconciler tests);
  the new file is the out-of-process complement, testing the same fix
  (`ab4dbb1`) from outside.

**Registry.** The plane has project `atuout-reconciler-test` registered at the
worktree path (schema 3, groups `base`, workflows `check` + `test`). It is a
real, scheduled project: `base` gives it `maintain` at 00:05 and `plane-report`
coverage. Registration has no manual deregister command (CONCEPT.md §5.2); the
entry's lifecycle after the checkout disappears must be **measured, not
assumed** — see the measurements below.

**The worktree is a plain git worktree of `atuout`, not a paseo workspace**
(verified — paseo workspaces live under `~/.paseo/worktrees/`; this one lives
at `~/Documents/Projects/atuout-reconciler-test`). Nothing to archive in paseo.

## The question

Pick one end state and justify it with measurements:

**A. Salvage the test work to `main`, then retire the harness.**
The test file covers a fix that is on `main`; main has the build
prerequisites. If the suite passes on main's checkout, commit the test (and the
marker change, if main needs it) to `main`, then delete the branch and the
worktree, and observe the registry entry die.

**B. Keep the harness as-is.**
The branch, worktree, and registration persist. Legitimate, but permanent: the
branch diverges from `main` forever, and the `atuout-reconciler-test` project
keeps its 00:05 `maintain` runs for a checkout whose only purpose was a
temporary test.

**C. Delete everything without salvaging.**
Only if the test work is judged worthless. It almost certainly is not — measure
first.

## What to measure, per option

**Before choosing (the deciding measurement):** does the suite pass on `main`'s
checkout?

1. Check out `main` in the main checkout (it may already be there — `atuout`
   is currently on `main`).
2. `devenv shell -- true` — warms the shell; the first atuin build is ~9
   minutes cold (wave 4 measured 546 s on `tyo3`'s Rust build; expect the
   same class of cost here). **A timeout measures the cache, not the
   repository — re-run before recording a failure.**
3. `uv run pytest tests/test_reconciler_process.py -m slow -q` and record the
   result. Then run the same file without `-m slow` (the skips, not the suite).
4. Compare against the same run in the worktree, where it was authored.

**For option A:**

- Does `main`'s pytest need the worktree's `pyproject.toml` marker addition, or
  is `main`'s existing `slow` marker sufficient? Check for a duplicate
  declaration — `--strict-markers` rejects unknown markers and may reject
  redeclaration.
- After committing the test to `main` and pushing, delete the branch and the
  worktree:
  - `git worktree remove` the checkout (handle the uncommitted files explicitly
    first — they are the user's; commit them to the branch or to `main`, do not
    delete silently).
  - `git push origin --delete reconciler-process-test`.
- **Then measure the registry lifecycle:** what does `devman doctor` report for
  `atuout-reconciler-test` once its path is gone? Does the entry remove itself
  on the next shell entry of `atuout`, or does it linger as a stale entry
  (`doctor`'s "stale entries: every registered path is a directory" check)? Is
  the 00:05 `maintain` still scheduled for it? Record what actually happens —
  this is the part nobody has measured.

**For option B:** nothing to measure beyond confirming nothing else depends on
the branch (grep the plane and `.scratch` for `reconciler-process-test` and
`atuout-reconciler-test`).

**For option C:** same measurements as A minus the salvage; justify discarding
a passing suite.

## Rules

- **Measure, do not assume.** Every answer is a command, its output, and a
  verdict.
- **Trace the error before reporting the cause.** Wave 2 reported a
  five-for-five correlation as a mechanism and was wrong. Read the traceback.
- **Do not propose a merge of `reconciler-process-test` into `main`.** The
  devenv files are intentionally different; a merge clobbers the main
  checkout's registration.
- **The uncommitted work is the user's.** Its fate is a decision the prompt
  must surface, not a side effect of cleanup. Say what you left.
- **Leave the machine as you found it, and say what you left.**
- **Record the decision in `STAGE_7_LOG.md`** in the shape the log already
  uses: the answer, the versions, the exact command, the evidence, the charter
  impact, Rule 7 (what this entry did to the machine). Push it on
  `dagu-devenv-automation-eli5` (PR #131 is open for the wave-4 log; this entry
  can ride it or follow it — say which).
- **Pushing to atuout `main` works directly** — wave 4's adoption commits
  landed that way (no PR needed on atuout).

## Not in scope

- Changing `project = "atuout"` or the main checkout's adoption.
- Touching any other repository.
- New features on atuout.
- `nixos-rebuild switch` — still not run; R-4d/R-4f remain uninstalled. Say it
  is needed; do not run it.

## Traps this environment already sprang

- **The atuin cold build is long.** Wave 4 measured Rust builds at ~9 minutes
  cold; re-run before recording a failure.
- **The test needs atuin with PR #3510 on PATH.** The devenv builds it; the
  test skips when it is absent. A "passed" run that skipped everything is not a
  pass — check the skip counts.
- **`main` may already declare the `slow` marker.** A second declaration can
  break `--strict-markers` collection; check before committing the pyproject
  change.
- **The registry has no manual deregister.** The stale-entry lifecycle is
  unmeasured; `doctor`'s stale check may flag it, the next projection may not
  clear it. Record what happens rather than assuming cleanup.
- **`git worktree remove` refuses a dirty tree.** The uncommitted files must be
  resolved (committed or stashed) before removal; resolve them on purpose, not
  by accident.
- **`ls` and `cat` are aliased to eza and bat in this shell.** Use
  `find -printf` and `sed`/`head` for plain output.
- **A cold `devenv shell` can take minutes.** The first entry after any devenv
  change re-evaluates; batch commands into one `devenv shell -- …` invocation.
