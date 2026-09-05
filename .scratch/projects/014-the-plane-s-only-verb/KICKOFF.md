# 014 — `devenv tasks run` is the plane's only verb. What does it cost, and what does it share?

Kickoff. Open a clean session at `~/Documents/Projects/devman` and work from
here. **Read this whole file before running anything.**

---

## The question

Every default workflow runs exactly one `devenv tasks run`. That is the
contract between Dagu and devenv: **Dagu orchestrates, devenv executes**, and
order lives in the repository's task graph rather than in a Dagu file.

**114 of the 170 projected workflow files on this machine execute it** (`check`
54, `test` 54, `release` 2, and one each of `format`, `agent-review`,
`bench-entry`, `gitman-commit-message`). The other 56 are `maintain` ×54,
`plane-report` and `stack-validate`, which run plain shell.

Nobody has ever measured the verb.

Project 013 tripped over two facts about it while doing something else, and
neither has been investigated:

1. **It is almost entirely startup.** `ruff format .` is 31 ms. `devenv tasks
   run format:fmt` is ~1600 ms. `devenv tasks run` **running nothing at all**
   is ~1550 ms. **The work is 2% of the price.**
2. **It has shared mutable state, and the plane runs it concurrently.**
   `.devenv/state/tasks.db` is a SQLite database (WAL mode) holding per-task
   file state. `check`, `test`, `format` and `release` in one repository all
   write it. **Nothing in the plane knows this file exists.**

**This project is: what does the plane's only verb actually cost, what does it
actually share, and is there a safe warm path?** A measurement with no change
is acceptable. A change without a design argument behind it is not.

---

## What this project must NOT inherit

013 produced these while investigating concurrency primitives. Several are
single-figure observations, not findings. **Re-derive them.**

| claim from 013 | status |
|---|---|
| "`devenv tasks run` doing nothing costs ~1550 ms." | **n=3, one repository, cold.** Directionally certain, precisely unverified. Re-measure with n>=20 across several repositories. |
| "No devenv flag avoids it — `--offline`, `--no-reload`, eval cache." | **n=2-3 each.** Re-derive. And read devenv's source: it is Rust and public, unlike Dagu. |
| "Inside a Dagu run it is far cheaper — 18.4 ms, `Evaluating shell in 4.61ms (cached)`." | **Read from ONE step log.** This is the most important number in the project and it rests on a single observation. **Establish what makes a run warm, and what would make it cold.** |
| "`. .devenv/load-exports && ruff format .` is 16 ms." | **n=3, and it bypasses law 4.** The figure is a bound on what a warm path could win, not a proposal. |
| "The format fixpoint costs +1.03 s (2.289 s -> 3.319 s)." | **One run each.** It is now the live cost of every save in this repository. Re-measure properly. |
| "`.devenv/state/tasks.db` is shared mutable state." | **Observed as a file. Its semantics were never tested.** Nothing was run concurrently against it. |
| "114 of 170 projected files run the verb." | **Verified** by grep over the live registry. Safe to build on. |
| "devenv is 2.1.2." | **Verified.** Safe to build on. |

**Treat every row except the last two as a lead.**

---

## What is re-openable, and what is not

**In scope:**

* **How the verb is invoked.** One `devenv tasks run` per step is the shape
  today. Nothing says the plane may not make that invocation cheaper, and
  nothing says the shape itself is fixed.
* **`base.yaml`'s shell.** The machine's Dagu base config already chooses
  `default_shell`. What a step's shell has already done before the step's first
  byte is machine state, and machine state is amendable.
* **Whether `format`'s second pass should exist in its current form**, if the
  cost turns out to be structural rather than incidental.

**Not in scope:**

* **Law 4, in any form.** A warm path that runs a step against a stale
  environment is a successful run that did the wrong thing. **A cache with no
  freshness check is not a candidate**, however fast it is.
* **Putting a project fact in shared group content.** Law 5. A workflow naming
  `ruff` hard-codes one repository's tooling into a file every adopting
  repository inherits. That is the objection to it — not the shape of the step.
  **Align with what Dagu can express**; where Dagu and devenv both offer a way,
  measure both and say which is better and why.
* **Reopening 013's concurrency design.** Its RESULT stands and its
  recommendation stands: it does not ship without a real-projection spike.
  **This project is not that spike.** If findings here change the conflict set,
  say so and stop.

---

## The investigation

### Part A — what is devenv actually doing for 1.5 seconds?

**013 measured the number and never asked the question.**

1. **Read the source.** devenv is Rust, public, and unlike Dagu it is **in the
   Nix store** — start from `devenv 2.1.2`'s own store path and
   `devenv.yaml`/`flake.lock`. 013 read no source at all.
2. **Profile one invocation.** Where does the wall clock go: process start, Nix
   evaluation, the eval-cache SQLite open, building or realising the profile,
   the task runner, the TUI? `--no-tui` exists.
3. **Is the cost fixed or does it scale?** With the size of `devenv.nix`, the
   number of tasks, the number of packages, the repository? Measure across
   several of the 54 real repositories, which vary widely.
4. **What makes a run warm?** The single most valuable question here. A step
   log showed `Evaluating shell in 4.61ms (cached)`, and a cold shell shows
   ~1550 ms. **Find the cache, find its key, and find what invalidates it.**
   A nightly `check` on a repository nobody has entered for a month is the case
   that matters, and it is the case nobody has measured.

### Part B — what does the verb share, and does the plane collide on it?

**This is 013's §8.3, the largest unexamined conflict in the plane.**

1. **Enumerate the shared state.** Known so far, none of it tested:
   `.devenv/state/tasks.db` (SQLite + WAL), `.devenv/nix-eval-cache.db`
   (SQLite + WAL), `.devenv/state/venv`, `.devenv/run` (a symlink into `/tmp`,
   recreated per shell), `.devenv/profile`, `.devenv/load-exports`.
2. **`exec_if_modified` is devenv's own receipt, and 013 just fixed the same
   bug shape in `format`.** A step log shows devenv doing
   `Removing stale watched_file entry ... Updating file state for task`.
   **Ask 013's question of devenv: is the receipt written before or after the
   work, and what happens to a file edited during the task?** If it is the
   same defect one level down, `format`'s fixpoint does not save it.
3. **Run them concurrently and find out.** `check` and `test` in one repository
   at once — today `light` and `normal` are different queues, so **the plane
   already permits this and always has.** Does `tasks.db` block, corrupt,
   return `database is locked`, or silently skip a task?
4. **Classify what you find** the way 013 §3.3 did: self, sibling,
   cross-workflow, resource. **A sibling collision would be new** — 013 found
   none, because it only looked at workflow bodies, and `.devenv/` is not in
   any workflow body.

### Part C — is there a safe warm path?

**Only if it survives all three of these. State plainly which one kills it.**

* **It keeps ordering in the repository.** A step that names tools instead of
  a task moves one repository's decisions into shared group content (law 5).
* **It has a freshness check.** What invalidates it, how the check is made, and
  what it costs — because a check that costs 1.5 s has won nothing.
* **`doctor` can see it.** §10's checks are the plane's honesty. A warm path
  that can be silently stale with nothing to detect it is not a candidate.

Candidates to start from; finding one not on this list is a good outcome:
devenv's own caching made to persist correctly; `base.yaml`'s `default_shell`
doing the warm-up once per run; a `devenv tasks run` invoked so that its caches
hit; whatever Part A finds is actually slow, fixed at the source.

**"Do nothing" is a legitimate answer**, and if the honest finding is that the
1.5 s is irreducible without breaking law 4 or law 5, **say that and stop.**

### Part D — what does this cost the plane, in total?

The number nobody has. 114 files execute the verb; `check` and `test` are 108
of them and every one is nightly or reactive. **Estimate the machine's daily
spend on devenv startup, and state the method.** Then say what fraction of it
Part C could recover, and what that is worth against the risk it carries.

---

## The traps

**A warm cache with no freshness check is Law 4 with better latency.** The
whole of 013 §3.4 was one silent skip. Do not trade a refusal for milliseconds.

**The plane refuses files it cannot read, and it will refuse yours.** 013's
first attempt at a workflow edit produced `not loadable as YAML: unacceptable
character #x0080 — fix the source; the plane publishes no file it cannot read`,
and the projection kept the old file. **Check what actually got projected**
under `~/.local/share/devman/projects/<project>/workflows/` before believing a
change is live. Editing `groups/` is not publishing; re-entering the devenv
shell is what projects.

**One sample is worthless.** 013's own §10 numbers are n=3 and are listed above
as leads for exactly that reason. n>=20, p50 **and** max, and the load average
with every figure.

**The machine is not quiet.** A `find` over sysfs has held one core since at
least project 012, now past 20 hours. Check whether it is still there and
record the load with every number.

**The plane is live and manages 54 real repositories.** Triggering work in the
`devman` repository is fine. **Running `devenv tasks run` inside somebody
else's repository writes their `.devenv/state/`** — if Part B needs a second
repository, clone one to `/tmp` rather than using the live one, and say which.
Every Dagu experiment goes on a throwaway `DAGU_HOME` under `/tmp` on ports
18080/50155. **Use the `DAGU_HOME` environment variable, not `--dagu-home`:**
013 established the flag is not propagated to forked children, so a throwaway
instance configured with the flag is not isolated at all.

---

## Constraints

* **`devman doctor` must exit 0 before and after**, with
  `devenv tasks run base:check` and `base:test`. All three exit 0 today.
* **`tests/unit/test_run.py` is the specification and must pass unmodified.**
  390 unit tests pass today.
* Every number gets its method beside it: sample count, machine state, what
  else was running.

## Deliverable

`.scratch/projects/014-the-plane-s-only-verb/RESULT.md`, holding:

1. **Where the 1.5 s goes**, from profiling and from source — not from a black-box timer.
2. **What makes a run warm**, what invalidates it, and what a cold nightly run costs.
3. **The shared state**, enumerated, with at least one concurrency experiment against `tasks.db`.
4. **Whether `exec_if_modified` has the defect 013 found in `format`.**
5. **The warm-path verdict**, against all three of Part C's tests, including "no safe path exists" if that is the answer.
6. **The plane's total daily spend on the verb**, with its method.
7. **What you did not measure**, plainly.

Ship the change if it wins on the argument and the measurement. Amend the
charter in the same commit if it contradicts one — with the measurement that
forced it. **A faster plane that can silently skip work is not faster.**
