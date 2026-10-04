# Lane assessment — two unlanded lanes in `devman`

Date: 2026-10-03
Scope: `041-doctor-project-source`, the retired-enrollment lane, in this repository
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
  retired-enrollment        draft   1 change, +0 −6                                     · 2 behind trunk
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

## Lane 2 — retired enrollment marker

The six-line enrollment marker deletion was a real change, not a no-op. At the
assessment snapshot, the lane was two commits behind trunk and had no conflict.
Its base repository already linked its agent surface centrally, and both the
repository and machine guidance pointed to the separate writing skill. The
marker therefore had no remaining consumer.

The deleted file recorded a Copier enrollment for a personal instruction
layer, pinned to v0.2.0. The repository's own template enrollment was separate.
Removing the marker stopped future layer updates from selecting this repository;
it did not remove the repository's own template relationship or the writing
rules.

The central pool no longer held this skill, and the shared writing guidance had
already moved into skills/writing/SKILL.md. The earlier report found that the
fleet had crossed to central agent surfaces before the source template was
archived. That ordering removed the risk of leaving repositories without their
agent files.

The original recommendation was to leave the lane parked for coordination. The
2026-10-03 retirement request superseded that recommendation and authorized
landing this deletion with the rest of the retirement work. The lane's deletion
was independent of the central project's archive work.

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
