# Kickoff prompt — devenv lockfile churn on shell entry

**Evidence gathered:** 2026-10-03, read-only, by a prior session. Line numbers,
counts, and commit hashes may have drifted. Re-verify before you act on any of
them — the commands to re-verify are given inline.

**Your job:** find the root cause of this bug and recommend one fix, with
evidence. You do not need to ship the fix in this session unless the
investigation is quick and the evidence is solid — a correct diagnosis with a
clear recommendation is an acceptable deliverable on its own. **Do not guess
the root cause. Measure it.**

The original investigation kept this file untracked in devman's `.scratch/projects/`.
The user later authorized this follow-up to record it with the report.

---

## 1. The bug, as measured

**Entering a `devenv` shell rewrites tracked lockfiles** — `devenv.lock`, and
in most of these repositories `uv.lock` too. It happens on *every* shell
entry, not only when running a verify task. One agent who saw it described it
as "devenv auto-upgrades the lock on shell entry when its pinned version is
stale." That description is a hypothesis carried from a prior session — it is
not yet proven. Test it; do not repeat it as fact.

Because every `gitman` invocation in these repositories goes through `devenv
shell`, the consequences are:

- Plain `gitman status` dirties the lockfile.
- `gitman start` would then adopt that drift into a lane.
- **Worst case, and it happened:** in `boomtube`, an agent restored the
  lockfile, ran `gitman describe`, and then **`gitman land` itself re-entered
  the shell and re-triggered the rewrite between describe and land.** Commit
  `e8c8f131f97b1270fe67eb66ad48d0abaee2de59` carries `AGENTS.md` (11
  insertions, 6 deletions) and `devenv.lock` (8 insertions, 76 deletions — 84
  lines touched) under a message that describes only the `AGENTS.md` change.
  Re-verify:
  ```
  git -C ~/Documents/Projects/boomtube show --stat e8c8f131
  git -C ~/Documents/Projects/boomtube show e8c8f131 -- devenv.lock
  ```
  The `devenv.lock` diff drops a `home-manager` node and a `shellij` node that
  are not referenced in `boomtube`'s `devenv.yaml` inputs — consistent with
  devenv pruning flake inputs it considers no longer reachable from the
  committed `devenv.yaml`. Confirm this reading yourself; do not take it on
  faith.

**Repositories observed with this pattern** (read-only, by reading
`devenv.yaml`/`devenv.lock`, never by entering their shells): `fornix`,
`image-gen-pipeline`, `interplay`, `observantic`, `boomtube`, `cairn`,
`embeddy`, `flora`, `flora-core`, `forgelab`, `pydantree`, plus `linkman`,
`devman`, and `gitman` themselves. Re-establish the real extent yourself —
read files, do not enter shells to probe. A scan command that touches no
shell:
```
for repo in <names>; do
  python3 -c "import json; d=json.load(open('<repo>/devenv.lock')); n=d['nodes'].get('devenv',{}).get('locked',{}); print(n.get('rev'), n.get('lastModified'))"
done
```

### A concrete, measured data point on the likely mechanism

The installed `devenv` binary on this machine reports:
```
$ devenv version
devenv 2.2.2+b8030c5 (x86_64-linux)
```
The `+b8030c5` suffix looks like a short git commit hash of the `devenv`
source tree used to build this CLI.

Every one of the fourteen repositories checked carries a **different** `rev`
in its `devenv.lock`'s own `"devenv"` node (the `src/modules` input devenv
uses to evaluate `devenv.nix`), and **none** of those revs' short forms match
`b8030c5`. Examples, read directly from each repo's `devenv.lock`:

| repo | `devenv.lock`'s `devenv` node `rev` (short) | `lastModified` |
|---|---|---|
| fornix | `f022d7d` | 1780874819 |
| linkman | `fe20b5c` | 1790701375 |
| boomtube | `26c5ae8` | 1768846984 |
| pydantree | `0ad2d68` | 1749934215 |
| devman | `d1fb321` | 1783538213 |
| gitman | `d1fb321` | 1783538213 |

None of these match `b8030c5`, and no two repos necessarily agree with each
other either. **This is suggestive, not proven.** It is consistent with a
story where devenv, on shell entry, reconciles the locked `devenv` module
input against something tied to the installed CLI build and rewrites the
lock when they disagree — but this session has not confirmed that devenv
actually behaves this way, only that the mismatch exists. Read devenv's own
source or documentation (check the nix store and devenv's GitHub repo) to
confirm or refute this mechanism before you rely on it. Re-run the table
above yourself; it may have changed since 2026-10-03, especially if anyone
entered any of these shells since.

### Second consequence: this interacts with gitman's land gate

`gitman` can gate `land` on a hook via `[land.pre_hook]`. The *current*
mechanism — confirm the line numbers, they move — snapshots the jj working
copy before and after the hook runs and diffs the two snapshots
(`gitman/src/gitman/hooks.py`: `snapshot_commit`, `tracked_changed_paths`,
`describe_changes`). As of 2026-10-03 this snapshot is **gitignore-aware**:
a hook that writes only gitignored paths does not block the land. This is a
fix that landed in gitman's own repository under project
`64-config-gate-audit`, option (b) — see
`gitman/.scratch/projects/64-config-gate-audit/GATE-AUDIT.md`, the "Update
(2026-10-02) — option (b) landed" section near the end. **If you are reading
an older description of this mechanism that names a function called
`filesystem_snapshot` and a constant `_IGNORED_DIRS = {.git, .jj, .gitman,
.worktrees}`, that description is stale** — it describes the pre-fix
mechanism, replaced by the jj-snapshot approach above. Read
`gitman/src/gitman/hooks.py` yourself; it is short (164 lines as of
2026-10-03).

**Why the gitignore fix does not save you here.** `devenv.lock` and `uv.lock`
are **tracked** files, not gitignored. The land-hook snapshot still sees a
hook-triggered rewrite of a tracked file as a real change, and still blocks
on it, exactly as the pre-fix mechanism did. "Make gitman ignore it" is not a
legitimate fix for this specific bug — the right fix stops the rewrite, or
makes it a no-op, not the gate that catches it.

For more background on why this gate exists and what else it catches, read
(numbers may have drifted):
- `devman/.scratch/projects/041-central-autoland/DECISIONS.md`, decision
  **D18** — the measured finding that gitman blocks a land on any
  hook-written file, including why `allowed_paths` does not rescue it.
- `devman/.scratch/projects/041-central-autoland/CONCEPT.md`, **§14.5** — the
  same finding, with gitman's own `.pytest_cache` as the worked example.
- `gitman/.scratch/projects/64-config-gate-audit/GATE-AUDIT.md` — the full
  gate audit, including the option (b) fix referenced above.

---

## 2. What you need to establish

Do not guess. Measure each of these, and report what you found, including
"could not determine."

1. **Which devenv writes the lock, and why?** Is the installed `devenv`
   newer than what each repository's `devenv.yaml`/`devenv.lock` pins, so
   devenv normalizes the lock on entry? The table in §1 is a starting point,
   not a conclusion. Read devenv's own documentation and source (check the
   nix store — `nix-store -q --references $(readlink -f $(which devenv))`
   finds runtime deps but not necessarily source; look for a devenv flake
   input to one of these repos, or fetch devenv's GitHub source directly) for
   a description of when and why it rewrites `devenv.lock` on shell entry.
2. **Is the rewrite deterministic, or does it oscillate?** This decides
   everything else. If you enter a shell in one repository, is the resulting
   lock content stable on a second entry (idempotent), or does it keep
   changing? You are permitted to test this (see §5 for how, carefully, and
   how to clean up), but only in a repository where doing so is low
   consequence, and only after you have exhausted what you can learn by
   reading.
3. **Can the rewrite be suppressed?** Look for a devenv CLI flag or
   environment variable that makes shell entry read-only with respect to the
   lock (something like a `--no-lock-update`, a strict/offline/frozen mode,
   or a documented env var). Say plainly if you find no such control, rather
   than leaving the question open.
4. **Is this fleet-wide drift from one stale shared pin, or N independent
   drifts?** Look at whether the `devenv` node's `rev` clusters (several
   repos sharing one old pin) or is scattered (every repo independently
   stale). This affects whether fix (c) below is one change or thirty-five.
5. **Does `uv.lock` share the same cause, or a different one?** Do not
   assume. `uv.lock` is written by `uv`, not by `devenv` directly, though
   something inside the devenv shell's activation may invoke `uv sync` or
   similar on entry. Trace what actually touches `uv.lock` on shell entry
   before concluding it is the same bug.

---

## 3. Candidate fixes — compare them, pick one, show your evidence

**(a) Commit the normalized lock once per repository.** If the rewrite is a
one-time normalization (deterministic and idempotent — see §2.2), committing
the post-rewrite lock ends the churn permanently. Costs roughly one lane per
affected repository (~14 measured so far, possibly more), each a
lockfile-only commit with an honest message ("devenv.lock: accept the
devenv-driven normalization," not "fix bug"). **You must verify idempotency
before recommending this** — a second shell entry after committing must
produce no further change. If you cannot verify this without entering a
shell, say so and propose how the next session should verify it, rather than
recommending (a) on faith.

**(b) Suppress the rewrite** via a devenv flag or environment variable (see
§2.3), applied wherever shells are entered. Smaller change if such a control
exists. If none exists, say so and move on — do not invent one.

**(c) Align the pinned devenv version fleet-wide** so no repository's lock
disagrees with the installed CLI. Addresses a plausible cause rather than
only the symptom, but may be a larger migration depending on what §2.4 finds.

**(d) Change gitman's snapshot to ignore gitignored paths.** This already
shipped (§1, option (b) in the gate audit) for a different, prior bug
(`.pytest_cache`). **State explicitly that it does not help this bug** —
`devenv.lock` and `uv.lock` are tracked, not gitignored, so this fix is
already in place and already insufficient. Do not leave this unexamined; it
is the first idea anyone reaches for, and it is a dead end here.

**(e) Do nothing; discipline only** — restore the lock before every
`describe`. This is what agents did on 2026-10-03, and it **measurably
failed** in `boomtube`: `gitman land` re-enters the shell and re-triggers the
rewrite *after* the last manual check, between `describe` and the actual
fold. State plainly that discipline has already been tried and has a
documented failure (the boomtube commit in §1) — it is not a live option,
only a fallback if nothing else works.

Pick one (or a combination) and say why, with the measurements that support
it. If the evidence is ambiguous, say that too, and name what additional
measurement would resolve it.

---

## 4. Scope boundaries

**In scope:** the lockfile rewrite itself, and its interaction with
gitman's land-hook gate.

**Out of scope — do not sweep these in, even if you trip over them:**
- Fixing the repositories whose *pre-existing* lane state blocks other work
  for unrelated reasons (as of 2026-10-03: `pyjutsu` had 22 open lanes,
  `inferference` 4, `structured-agents-v2` 4, `forgelab` a lane in conflict,
  `loci-core` off its canonical bookmark, and others with foreign
  uncommitted work). Those block a different task. Re-check `gitman status`
  per repository before you touch it, and if it is not clean for reasons
  unrelated to this bug, leave it alone and note it in your report.
- **The `boomtube` commit `e8c8f131` itself.** You may *report* on it (as
  this document does) but must not rewrite history — no amend, no rebase, no
  force-push. Whether to correct that record is the operator's call, not
  yours.

---

## 5. Traps — each of these cost real time on 2026-10-03

1. **`git status` lies in a jj-colocated repository.** The git index is
   jj's export artifact, not ground truth. Trust `gitman status` instead of
   plain `git status` for anything that matters to a land/start decision.
   (Plain read-only `git show`, `git log`, `git diff` for *historical*
   inspection, as used throughout this document, are fine — the trap is
   using `git status` to decide whether a *working copy* is clean.)
2. **`HEAD` is a detached pointer**, potentially older than jj's trunk.
   `git log` / `git ls-tree HEAD` can answer a different question than
   `gitman status` does. Use the trunk hash `gitman status` reports, not
   `git`'s idea of `HEAD`.
3. **A clean `gitman status` is not sufficient** to greenlight `gitman
   start`. `start` has refused with "uncommitted work not based on trunk"
   even when `status` reported 0 lanes, in sync, no warning. **`gitman
   start`'s own refusal is the real gate** — treat a clean `status` as
   necessary, not sufficient.
4. **Verify a skip marker (or a suppression flag) by running the negative
   case**, not by reading the code that implements it. Reading code that
   looks like it skips something is not the same as confirming it skips it.
5. **Bulk `rm -rf` loops are permission-denied** as irreversible mass
   destruction. A single, discrete `rm -rf <one specific path>` is normally
   allowed. Plan cleanup as individual commands, not a loop.
6. **`gitman undo` is blocked** in this environment. There is no easy unwind
   after a bad land. Check carefully before landing; do not plan on undoing
   after.
7. **Concurrent sessions commit to these repositories.** Trunk can move
   between when you read a hash and when you act on it. Re-check `gitman
   status` at the moment you act, not from a hash recorded earlier in this
   document or in your own notes from five minutes ago.

---

## 6. House rules

- **Run everything inside the repository's devenv shell** — except the
  specific read-only reconnaissance this bug requires you to do *without*
  entering one. Never invoke bare `uv`, `python`, `pytest`, `ruff`. Plain
  read-only `git` (`status` only for historical inspection per trap 1,
  `show`, `log`, `diff`) is disclosed, accepted practice in this lineage —
  `devman/.scratch/projects/035-config-repo-cleanup/` §10 recorded the same
  choice with its justification. Never run a *mutating* bare `git` or `jj`
  command — route mutations through `gitman`.
- **Route all version control through `gitman`. One lane per repository.
  Never push without asking the operator first.**
- **This bug is triggered by entering a devenv shell.** Each shell entry in
  an affected repository is itself a measurement with a side effect. Before
  you enter one, know what you are testing, expect the lockfile to move, and
  have a restoration plan ready (see below). Prefer reading
  `devenv.yaml`/`devenv.lock` over entering a shell wherever reading
  suffices.
- **If you must enter a shell to confirm something:** note which repository.
  Immediately after, run `git status --short` in that repository. If
  `devenv.lock` or `uv.lock` shows modified, restore it with a **plain file
  write** of the committed content — `git show main:devenv.lock >
  devenv.lock` (or the correct trunk ref from `gitman status`) — never
  `git checkout`, never `git reset`, never a gitman verb for the restore.
  Report every repository you entered a shell in, and confirm the restore
  worked (`git status --short` clean again).
- devman's own verify is `devenv tasks run -v base:check` and
  `devenv tasks run -v base:unit` — the `-v` is load-bearing, do not drop it.
  **devman does not use Testee.** Do not run `nix flake check` in devman —
  it is red for a reason outside this bug's scope (the Linkman cutover owns
  that).
- Each repository's own verify step differs. If a repository has no verify
  task defined, **do not invent one, and do not land blind.**
- Write in Simplified Technical English: short sentences, active voice, one
  word per meaning, no filler.

---

## 7. Verification standard

Before you recommend a fix, you must be able to answer, with a command and
its actual output, not a guess:

- What exact change did shell entry make to the lock (a diff, not a
  description)?
- Did a second shell entry after that change produce a further change, or
  nothing?
- If you suppressed the rewrite (fix (b)), did a shell entry after
  suppression leave the lock untouched — confirmed by diff, not by absence
  of an error?
- For every repository you touched to answer the above, is its working copy
  now exactly as it was before you started (confirmed by `git status
  --short`, read per trap 1's caveat, plus a content diff against trunk)?

---

## 8. Report back

1. **Root cause**, stated as what you measured, not what you inferred. If
   you could not pin it down, say exactly what you tried and what blocked
   you.
2. **Which fix you recommend** ((a) through (e), or a combination), with the
   evidence from §2 and §7 that supports it over the alternatives.
3. **Every repository you entered a devenv shell in during this
   investigation**, and confirmation that each one's working copy matches
   trunk afterward.
4. **Anything in this prompt you found to be wrong.** Line numbers, commit
   hashes, counts, and function names in this document were measured on
   2026-10-03 and may have drifted — if the code or the machine disagrees
   with this document, **the code and the machine win.** Say what was wrong
   and what the current truth is.
5. If you implemented a fix: what you changed, which repositories it
   touched, and the verify output for each one.
