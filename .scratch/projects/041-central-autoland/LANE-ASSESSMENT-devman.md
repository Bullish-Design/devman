# Lane assessment — two unlanded lanes in `devman`

Date: 2026-10-03
Scope: `041-doctor-project-source`, `parked-my-ai-enrollment`, in this repository
(`/home/andrew/Documents/Projects/devman`).
Mode: read-only assessment. Nothing was mutated. No mutating `gitman`/`jj`
command ran. All version-control inspection used `gitman status`, `gitman
workspace list`, and read-only `git` (`log`, `diff`, `show`, `ls-tree`,
`merge-base`). The in-tree binary was run twice, read-only, from the lane's own
workspace checkout. `devenv tasks run -v base:check` / `base:unit` ran in that
same workspace.

`gitman status` confirmed the brief's numbers before starting:

```
trunk: main @ ce4c87d5a834e8e28ba17b2f1f5f6e6b1b8853be  (in sync with origin)
  041-doctor-project-source draft   1 change, +137 −8   · ws 041-doctor-project-source · 2 behind trunk
  parked-my-ai-enrollment   draft   1 change, +0 −6                                     · 2 behind trunk
```

Both lanes branch from the same merge-base, `ef24f6e` (`m041: the central
guard — devman central-verify, a repaired link-drift check, and a ledger
check`). Trunk has since gained two commits past that point: `1d8584b` ("m041
phase 1+2: make a devman check prove it can fail") and `ce4c87d` ("m041 O9:
restore the duplicate-registration refusal, and detect a collision"). Both are
large changes to `src/devman/doctor.py` and `tests/unit/test_doctor.py`. A
naive `git diff main..<lane>` conflates these two trunk commits with each
lane's own change; all diff stats below use
`git diff $(git merge-base main <lane>)..<lane>` to isolate the lane's own
commit.

---

## Lane 1 — `041-doctor-project-source`

**Recommendation: SYNC THEN LAND.** Deciding fact: the change works exactly as
claimed (verified live, both headers pasted below) and is complete, but it sits
in a workspace 2 commits behind a trunk that rewrote large parts of the same
two files — a sync is needed before landing, and one conflict is likely (small,
mechanically trivial, not a reason to withhold the lane).

### What it changes

One commit, `3cc6508`, "fix: report doctor project metadata source." Diff stat
against its own merge-base (`ef24f6e`):

```
 .scratch/projects/042-doctor-project-source/RESULT.md | 85 ++++++++++++
 src/devman/doctor.py                                  | 22 ++++---
 tests/unit/test_doctor.py                             | 38 +++++
 3 files changed, 137 insertions(+), 8 deletions(-)
```

In `src/devman/doctor.py`, the five `print()` statements that used to sit
directly in `main()` (lines ~1749–1760 of the base revision) are extracted into
a new `_print_header(reg, dagu_home)` function, which adds one line:
`print(f"    projects   {reg.project_source or reg.state_projects_dir}")`
— the exact source `Registry.load()` used to populate the count, named next to
the `registry` and `state` lines that were already there. No other line in
`doctor.py` changes; `check_mode` is untouched. In `tests/unit/test_doctor.py`,
three pre-existing git-dependent tests gain a `@needs_git` skip marker, and one
new parametrized test (`test_header_names_the_project_metadata_source`) asserts
the printed `projects` line names the actual source in both compatibility and
plane mode, using `tmp_path` fixtures rather than the live machine.

### Completeness

The lane's own `RESULT.md`
(`.scratch/projects/042-doctor-project-source/RESULT.md`, readable from the
workspace checkout at
`/home/andrew/Documents/Projects/devman/.worktrees/041-doctor-project-source/`)
claims: both live headers fixed, `check_mode` deliberately left alone and
reasoned about, no other command found to misreport its project source, and a
verification table of `base:unit`/`base:check`/`PATH`-stripped runs.

The code matches the claim — this was checked by running it, not by trusting
the document:

| Claim | Verified | Evidence |
|---|---|---|
| Default header names the real source | Yes | live run below |
| `--registry <active>` header names the real source | Yes | live run below |
| `base:unit` 654 passed, 1 skipped | Yes | ran in workspace, identical count |
| `base:check` all checks pass | Yes | ran in workspace |
| `PATH`-stripped run: zero errors | Yes | `64 passed, 3 skipped in 0.74s`, matches RESULT.md |
| No new `check_*` call added to `main()` | Yes | `main()`'s body inspected; the only change is the header, which is not a check |

### Does it work? — live headers, both modes

Run from the workspace checkout,
`/home/andrew/Documents/Projects/devman/.worktrees/041-doctor-project-source`,
using its own built binary, `.devenv/state/venv/bin/devman`:

```
$ .devenv/state/venv/bin/devman doctor
devman doctor — 4 projects, 19 workflows
    registry   /home/andrew/.local/share/devman
    state      /home/andrew/.local/state/devman
    projects   /home/andrew/.local/state/devman/projects
    dagu home  /home/andrew/.local/share/dagu
```

```
$ .devenv/state/venv/bin/devman --registry ~/.local/state/vendomat/devman/active doctor
devman doctor — 48 projects, 152 workflows
    registry   /home/andrew/.local/state/vendomat/devman/active
    state      /home/andrew/.local/state/devman
    projects   /home/andrew/.local/state/vendomat/devman/active/projects
    dagu home  /home/andrew/.local/share/dagu
```

Both match RESULT.md's "headers after" exactly. The `projects` line correctly
names `/home/andrew/.local/state/devman/projects` (the state root, where the
four compatibility-mode projects actually live) in the first case, and
`.../active/projects` (the plane projection) in the second — the defect is
fixed.

### Tests, and the negative case

`tests/unit/test_doctor.py::test_header_names_the_project_metadata_source` is
the firing test: it builds two `tmp_path` registries (one compatibility, one
plane), stubs every `check_*` except `check_mode`, and asserts the exact
`projects` line and the exact project set loaded. Reverting the `doctor.py`
change would make this test fail, because `_print_header` would no longer
print the `projects` line at all — there would be nothing for the assertion
`f"    projects   {source}" in lines` to match. This was not independently
re-run against a manually reverted copy, since `base:unit`'s own count (654 vs
RESULT.md's claimed before/after of 652/654) already establishes the test is
new and additive; "unverified beyond that" would require reverting the
workspace, which this assessment does not do (read-only).

`PATH`-stripped run, from the workspace, in a throwaway empty directory:

```
PATH=/tmp/emptydir .devenv/state/venv/bin/python -m pytest tests/unit/test_doctor.py -q -p no:cacheprovider
64 passed, 3 skipped in 0.74s
```

Zero errors, matching RESULT.md's claim and trap 3's negative-case
requirement.

### Firing-test guard

`tests/unit/test_doctor.py` carries `_checks_in_main()` / `FIRING_TESTS` /
`INFORMATIONAL`, per the brief. Grepping `main()`'s body in the lane's
`doctor.py` shows no new `check_*` call was added — the only change inside
`main()` is replacing five inline `print()` calls with one call to
`_print_header()`, which is not a check and is not parsed by
`_checks_in_main()`. The guard does not apply to this lane, and `base:unit`
passing in the workspace (which exercises the guard) confirms it was not
tripped.

### Conflict risk against current trunk

**Confidence: medium-high that one small, mechanically trivial conflict
appears in `tests/unit/test_doctor.py`; `src/devman/doctor.py` should sync
clean.** Established by diffing the lane against trunk for the *same* files,
both taken from the shared merge-base `ef24f6e`, and looking for overlapping
hunks — no `gitman sync` was run.

**`src/devman/doctor.py` — no overlap, high confidence clean.** The lane's only
edit is at the base file's lines ~1736–1762 (adds `_print_header`, replaces the
inline prints inside `main()`, immediately before the `rep = Report()` /
`check_mode(rep, reg)` lines). Trunk's `main()` hunk is at base line ~1778 —
inserting `check_duplicate_identity(rep)` between `check_trigger_targets` and
`check_link_drift`, well past the header block. Trunk's other `doctor.py`
hunks (the new `EMPTY` status/legend near the top, the 15 per-check `EMPTY`
input guards, the `check_mode` docstring relabelling) are all in functions the
lane does not touch. No hunk ranges intersect.

**`tests/unit/test_doctor.py` — one real overlap, in the import/marker block.**
Trunk's first hunk spans base lines 6–30 (docstring additions, new imports
`ast, inspect, os, sys, time`, and — independently — the same
`needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs a
git binary")` marker the lane also adds, plus a sibling `needs_dagu` marker).
The lane's hunk at the same location (base lines 12–26) adds `import shutil`
and the *identical* `needs_git` line, but at a different position relative to
trunk's larger, reordered import block. Both sides want the same end state for
`needs_git`, but the surrounding lines differ enough that a 3-way merge is
likely to need a manual pick rather than auto-resolving — this is a textual
conflict over an already-agreed-upon change, trivial to resolve by keeping
trunk's definition and dropping the lane's redundant one.

**The three `@needs_git` decorator additions — low risk, probably clean.** The
lane decorates `test_link_drift_reports_a_view_on_trunk_as_ok`,
`test_link_drift_fires_on_a_dangling_view`, and
`test_link_drift_fires_on_a_lane_only_view` with `@needs_git`. Trunk's hunks at
the same three base locations (lines 88, 109, 130) add the *exact same*
decorator to the *exact same* three functions, as part of its own project 041
phase-2 work — this is an identical edit made independently on both sides,
which most 3-way merges collapse without a conflict. Trunk additionally edits
the body of the first function (adds an "empty surface" tuple row) and adds
three brand-new functions after the third — none of that overlaps the single
decorator line the lane also touches.

**The lane's new test — no overlap.** The lane inserts
`test_header_names_the_project_metadata_source` after
`test_mode_reports_plane_when_a_generation_file_is_active` (base line ~505–511).
Trunk's neighbouring hunks sit at base lines 486–492 (a new
`test_schema_reports_empty_...` test, inserted *before*
`test_mode_reports_compatibility_with_no_generation_file`) and resume only at
base line 707. The lane's insertion point falls inside that untouched gap.

### Duplication against trunk's `check_mode` relabelling

No duplication. Trunk independently relabelled `check_mode` as informational
(docstring-only change, "PROJECT 041 PART 4 — RELABELLED, NOT GIVEN A FAULT
BRANCH," at base line ~876). The lane's `RESULT.md` explicitly agrees with and
defers to this: *"`check_mode` stays informational: the mode is a label, not a
finding. The load path and mode choice did not change."* The lane's code does
not touch `check_mode` at all — zero overlap, and the stated reasoning in both
places is in agreement, not competing.

### Cost if this recommendation is wrong

If synced and landed as "LAND NOW" without a sync, the lane would apply over
only 2-commit-old trunk content and `gitman land`'s own pre-hook test run would
likely fail outright on the `tests/unit/test_doctor.py` conflict region, or
silently drop trunk's `needs_dagu`/docstring additions if force-applied — low
real risk given `land` would refuse first, but worth the extra sync step
rather than skipping it. If this recommendation is wrong in the other
direction (i.e., the sync is messier than assessed here), the cost of finding
out is one `gitman sync` plus manual resolution of a few lines in one file —
small, bounded, and `--dry-run` safe to attempt first.

---

## Lane 2 — `parked-my-ai-enrollment`

**Recommendation: LEAVE FOR ITS OWNER**, with a note that it is already safe
to land whenever that owner is ready. Deciding fact: devman's own `.agents` is
already the link-plane symlink (`.agents -> /home/andrew/.config/devman/projects/devman/agents`),
and `AGENTS.md:111` already cites `.agents/skills/writing/SKILL.md`, not
`my-ai` — devman has already crossed the retirement sequence's prerequisite,
so this deletion has no ordering hazard left to wait on; it was parked for
coordination, not blocked on anything technical.

### Confirmed: exactly one deletion

```
$ git diff $(git merge-base main parked-my-ai-enrollment)..parked-my-ai-enrollment
diff --git a/.copier-answers.my-ai.yml b/.copier-answers.my-ai.yml
deleted file mode 100644
index 4efb5da..0000000
--- a/.copier-answers.my-ai.yml
+++ /dev/null
@@ -1,6 +0,0 @@
-# Changes here will be overwritten by Copier; NEVER EDIT MANUALLY
-# This is the my-ai *personal layer* link. The repo's own template is recorded
-# separately in .copier-answers.yml — the two converge independently.
-#   copyroom update --layer my-ai
-_commit: v0.2.0
-_src_path: gh:Bullish-Design/my-ai
```

One file, 6 lines, nothing else. `git diff --stat` confirms `+0 -6` as `gitman
status` reports.

### Is the deletion already on trunk? No — not a no-op

```
$ git ls-tree -r --name-only main | grep -i copier
.copier-answers.my-ai.yml
```

Trunk still has the file. The lane's merge-base is the only common ancestor;
`git diff` between that merge-base and trunk for this path is empty — trunk has
not touched it since the lane branched. This is **not** the 15-orphaned-lane
case from project 036 Part B (a tip already an ancestor of trunk with no
unique patch): this lane carries a real, as-yet-unlanded change. **Do not
abandon it for being redundant — it is not.**

### Is the my-ai retirement actually in progress?

Yes, actively. Evidence, independent of this lane:

- **gitman's own trunk already landed the identical pattern.** `gitman log` in
  `/home/andrew/Documents/Projects/gitman` shows a landed commit, "chore:
  remove my-ai Copier enrollment," in its ancestry.
- **devman has already crossed over locally.** `.agents` in this repository is
  a symlink to `/home/andrew/.config/devman/projects/devman/agents`, not a
  real directory — the state project 035 §9.1 names as the trigger that makes
  "whatever copyroom previously wrote inside it … superseded wholesale."
  `.claude/skills` is the matching symlink into the same pool.
- **The pool's skill set has no `my-ai` entry.**
  `/home/andrew/.config/devman/projects/devman/agents/skills/` lists
  `copyroom`, `copyroom-adopt`, `copyroom-template-edit`, `devman`,
  `devman-adopt`, `devman-workflow`, `gitman`, `writing` — no `my-ai`.
- **The citation move (§9.3 steps 1–2) already happened.** `devman/AGENTS.md:111`
  reads *"See `.agents/skills/writing/SKILL.md`"*, and the user's own global
  `~/.claude/CLAUDE.md` likewise cites `.agents/skills/writing/SKILL.md` for
  the full writing rules — both already point at the new `writing` skill, not
  `my-ai`. Project 035 §9.2 named this exact citation move as the one thing
  that must happen before `my-ai` could be safely retired, and it is done.

### What `.copier-answers.my-ai.yml` is for, and the consequence of deleting it

It is Copier's per-layer answers file, recording that this repository is
enrolled in the `my-ai` personal-layer template at `gh:Bullish-Design/my-ai`,
pinned to `v0.2.0` (the file's own header: *"This is the my-ai personal layer
link… `copyroom update --layer my-ai`"*). Deleting it un-enrolls devman from
that layer: a future `copyroom update --layer my-ai` would have no record to
act on for this repository and would skip it rather than recreate the file
(copier's update path keys off the presence of the answers file; nothing in
`copyroom`'s own docs or `devman/AGENTS.md` suggests it self-heals a deleted
answers file). Project 035 §9's table marks `copyroom update --layer my-ai` as
the thing this retirement explicitly intends to retire — so this is the
intended, not an accidental, consequence.

### Is it safe at this point in the §9.3 sequence?

Yes. §9.3 step 4's warning — *"archive the template repo only once the
`.agents` symlink is actuated fleet-wide… archiving it early would strand
[repositories not yet crossed over]"* — is about the shared template repo
`~/Documents/Projects/my-ai`, a fleet-wide, one-time, irreversible action. It
is not about any individual repository dropping its own answers file; step 3
explicitly describes that as the *per-repository*, safe, and expected unit of
work, gated only on that repository's own `.agents` having become the
symlink. devman meets that gate (confirmed above). This deletion is one
repository's step 3, not an early step 4 — the ordering mistake the brief
warned to check for does not apply here.

### Who should land it, and when

The lane's own describe message is explicit: *"Parked, not landed: the my-ai
retirement is its own workstream and its owner should land this with the rest
of it."* That is a coordination choice (batch devman's piece with the other
~61 repositories' pieces for a consistent fleet-wide record), not a technical
hold — nothing found here blocks landing it today. Recommendation: respect the
parking and leave it for the my-ai retirement's owner, but note to that owner
that devman has no outstanding prerequisite; it can be folded into their next
batch, or landed standalone, with equal safety. Sync risk is zero (trunk has
not touched this file since the lane branched).

### Cost if this recommendation is wrong

If it should instead have been landed now: negligible cost either way — the
change is a one-file, zero-conflict deletion with no dependents found. If it
should instead have been abandoned (it should not be — see "not a no-op"
above): abandoning a real, correct, unlanded change would silently leave
devman's enrollment file in a state the retirement project says should not
exist, to be rediscovered later as the same finding.

---

## Where this brief's measurements held up, and where they needed correction

- The lane-size numbers (`+137 −8`, `+0 −6`, "2 behind trunk" for both) matched
  `gitman status` exactly, unchanged from the brief.
- `.scratch/projects/042-doctor-project-source/` does **not** exist on trunk or
  in the default working copy — it exists only inside lane 1's own workspace
  checkout (`.worktrees/041-doctor-project-source/`), because the lane has not
  landed. The brief's instruction to read it "under
  `.scratch/projects/042-doctor-project-source/`" is correct, but a reader
  following it from the repository root (not the workspace) would find
  nothing; the brief's own hint to "read the files there [the workspace] if
  that is easier" turned out to be necessary, not optional.
- The brief's framing of lane 1's conflict risk ("trunk has since gained large
  changes… establish whether a sync would conflict") undersold one specific,
  checkable detail: trunk's `needs_git` marker is **textually identical** to
  the lane's own addition, because both are solving the same discovered gap
  (git-dependent tests without a skip marker) independently. That turns what
  could read as a large, scary conflict surface into one small, trivial-to-
  resolve conflict plus several auto-resolvable identical insertions.
