# Kickoff — lane 4: project Git excludes from `links.yaml`

You are working in `/home/andrew/Documents/Projects/devman`.
Implement lane 4, `m14-l9w-excludes-on-links-yaml`, from `PLAN-lanes.md`.
Complete the implementation, verification, evidence report, gitman land, and push.
Do not stop after planning.

This prompt was written on 2026-10-06. Treat every count, path, and commit below
as dated evidence. Measure the current state before you rely on it.

## Outcome and boundary

Make devman's `.git/info/exclude` projection read `links.yaml` directly. The
projection must select links whose resolved targets lie outside the repository.
It must preserve the existing exclude file byte for byte on every live project.
It must keep `.devman/.runs/` in the entry list without a declaration.

Keep this lane to `src/devman/linking.py`, a new `src/devman/excludes.py`, focused
tests, and the lane's verification report. Keep `src/devman_link/` and the
current Linkman reconciliation flow intact. Lane 5 replaces that engine. Lane 6
ports its callers. Do not switch engines, remove the adapter, change the shell
hook, edit Nix packaging, deploy a machine generation, or rewrite central
project declarations in this lane.

The 60 project files under `~/.config/devman/projects/` are operator-owned
machine configuration. Read them for evidence. Do not edit them by hand.

## Read before editing

1. Read `AGENTS.md`, `AGENTS_GUIDE.md`, and the `writing`, `gitman`, and `devman`
   skills. Follow the repository's gitman and verification rules.
2. Read `PLAN-lanes.md` §0, lane 3, lane 4, and F3. Read `DECISIONS.md` D23,
   D25, and D10. The revised plan and these decisions govern this lane.
3. Read `VERIFY-diff-all-projects.md` §5 and `OPEN-QUESTIONS.md` O0 and O3a.
   **O0's 2026-10-06 resolution supersedes the report's old `.loci` finding.**
   Linkman's `.loci` design files are tracked in its repository. The old
   `.loci` line in its central `.local.gitignore` was commented by the operator.
   Do not add a `.loci` link or restore that exclusion.
4. Read `src/devman/linking.py`, `src/devman_link/excludes.py`,
   `src/devman_link/paths.py`, `src/devman_link/state.py`, and
   `src/devman_link/reconcile.py`'s `link_path`. Read the relevant cases in
   `tests/unit/test_linking.py` and `tests/unit/test_link_adapter.py`.
5. Read the sibling Linkman checkout's `src/linkman/config.py`,
   `models/config.py`, `resolve.py`, `topology.py`, and `repository.py`. Use these
   as the declaration and target-resolution contract. Do not import Linkman
   into the new exclude module. If a non-obvious legacy line must change, read
   the stage log cited by its comment first.

Older M14 material describes a Python-library cutover. `PLAN-lanes.md` §0 and
`DECISIONS.md` D23-D26 supersede that route. Do not follow the old library or
15-lane instructions.

## Baseline to confirm

On 2026-10-06, devman trunk was `d910b98`, in sync with origin, with no active
lane. Lanes 1 and 2 had landed at `651af40`. `base:test`, `base:check`,
`base:unit`, and host `devman doctor` passed. Linkman had its own green verify
hook. The lane 3 report measured 60 overlay projects, 59 live checkouts, and
283 external links across those checkouts. `foreman` had no checkout.

The lane 3 report proves exclude **entry-set** behavior. It does not preserve a
byte snapshot of every `.git/info/exclude`. Capture that byte baseline now,
before the first source edit. Recount projects and checkouts. Record any change
since lane 3. Do not repeat its old "58 of 59" verdict as a current fact.

Use `devenv shell` for work. Run all version-control commands through gitman;
never run raw `git` or `jj`. Check `gitman status` after shell entry. Resolve
unexpected worktree changes before starting `m14-l9w-excludes-on-links-yaml`.
If shell entry changes a lockfile, follow the gitman skill's lockfile rule.

## Implementation contract

1. Read both declaration layers when present: `<repo>/links.yaml` and
   `<overlay>/projects/<project>/links.yaml`. Preserve Linkman's disjoint
   namespace rule for link names and variable names. A duplicate must refuse.
   Parse with PyYAML, which is already a devman dependency. Accept Linkman's
   version 1 `vars` and `links: {view: {target: string}}` shape. Refuse
   malformed or unsupported input with the file and link name in the error.
2. Resolve `${vars.*}`, `${env.*}`, and `${repo.*}` with Linkman's current
   behavior. The fleet currently uses `${repo.name}`, but Linkman also supports
   `root` and `parent`. Preserve missing-name errors, variable-cycle refusal,
   its depth limit, invalid tokens, and NUL refusal. Resolve relative targets
   against the repository root. Use Linkman's `Path.resolve(strict=False)`
   scope rule, including symlinked parent directories.
3. Start entries with `.devman/.runs/`. Add each declared view whose resolved
   target is external to the repository root. Keep declaration order and remove
   duplicates without sorting. Internal targets add no exclude line. This
   is `exclusion_entries`'s old `central`/`external` rule expressed against
   `links.yaml`; Linkman calls the result `TargetScope`.
4. Remove `_as_resolved_links`, `Declaration`, and `ResolvedLink` from
   `src/devman/linking.py`. Call the new projection with the repository root,
   overlay root, and project identity. The new `src/devman/excludes.py` must
   compute the entries without importing the Linkman library or calling its
   command. The existing `linking.py` may still use Linkman for the other
   reconcile steps in this transitional lane.
5. Preserve `git_exclude_path`, `append_entries`, `local_gitignore_path`,
   `State`/`content_hash`, and `link_path` behavior. Reuse their existing
   implementations where possible. Keep the central `.local.gitignore`, the
   linked-worktree common Git directory, the append-only author lines, the
   promotion refusals, and the `{canonical, hash}` state record. Do not make
   the projection regenerate or reorder existing lines.

Keep the current six-step order in `reconcile_with_linkman`. Lane 5 handles
`linkman apply --json` and its `applied[]` gate. Update stale comments or
docstrings in the touched files so they describe lane 4 accurately.

## Proof before the live run

Add focused tests for behavior that could fail while a check stays green:

- external and internal targets, including a symlinked parent that changes
  scope; unconditional `.devman/.runs/` and stable entry order;
- environment, repository, and nested variable interpolation; unset names,
  invalid tokens, cycles, and a duplicate name across declaration layers;
- exact preservation of comments, blank lines, authored exclusions, and
  existing line endings when no entry is missing;
- the existing promotion refusal and linked-worktree path, with behavior
  unchanged from the old projection.

Use real temporary files and public behavior where practical. Do not accept a
skipped `test_linking.py` as proof of the Linkman-backed flow. Its module calls
`pytest.importorskip("linkman")` in the hermetic suite. Run it in an environment
with the `cutover` extra, and report how many cases actually ran. Keep the
hermetic suite green as well.

Use Linkman's read-only `config --json` as an independent oracle for resolved
target scope. Check every current project declaration. For `foreman`, if it
still lacks a checkout, use a disposable repository fixture with its overlay
declaration. Do not claim a live Git exclude file exists for that project.

## The byte gate

Before editing, capture each live checkout's actual Git exclude path through
`git_exclude_path`. Save its `Path.read_bytes()` result or SHA-256 digest, its
file kind, and any raw symlink target. Also record the matching central
`.local.gitignore` bytes and the state record needed to explain a change.
Store raw snapshots and command logs outside the tracked repository. Put the
per-project hashes, counts, exceptions, and command results in
`VERIFY-lane-4-excludes.md` beside this prompt.

First compute entries without writing. Confirm that every current external
entry already exists in its central file, and that the live exclude link and
state permit a no-op. If this preflight finds a mismatch, investigate it before
running the projector against live files. Fix a code error in this lane; do
not silently change central operator data to make the gate pass.

Then run the new exclude projection against each live checkout and compare the
captured bytes, file kind, and raw symlink target. Compare the central file and
state bytes too. Run it a second time to prove idempotence. Report an exact
numerator and denominator. The expected shape from lane 3 is **59/59 live
exclude files unchanged**, with one absent checkout, but use current counts.
If any byte changes, the gate fails. Diagnose the change before landing. Do not
claim "60/60 byte-identical" while `foreman` lacks a checkout.

The report must distinguish this byte gate from lane 3's entry-set comparison.
Record the date, devman and Linkman revisions, commands, exit codes, project
counts, and any limitation. If current evidence contradicts a premise in
`PLAN-lanes.md`, amend that plan with the measurement in the same commit.

## Verify and land

Run these commands inside devman's devenv shell. Keep each command's exit code;
do not pipe a failing check into `tail` and report the pipe's exit code.

```bash
devenv tasks run -v base:check
devenv tasks run -v base:unit
devenv tasks run -v base:test
devman doctor
```

`devman doctor` must exit 0 before a `src/devman/` change is committed. Run the
targeted integration and the fleet byte gate as well. If a check fails,
investigate and rerun it after the fix. Preserve the failure evidence.

Review `gitman status` and every relevant worktree change. Use the gitman lane
loop: `start` → edit and verify → `describe` → `land` → `push`. Run `describe`
and `land` in one shell without re-entering devenv. Include the tests, report,
and any relevant active worktree changes in the lane. Add no attribution line
to the commit. Do not begin lane 5.

Finish with a short report: what changed, the current fleet count, the exact
byte-gate result, targeted and full check results, any limitation, and the
landed and pushed revision.
