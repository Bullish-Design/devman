# GitMan lane creation fails in an off-canonical checkout

Date: 2026-09-12

Status: open

Severity: high for the repository workflow

## Summary

GitMan could not create a documentation lane in the Devman repository.

The checkout contained pre-existing source and test changes. The requested
documentation needed its own lane so those changes would not enter the commit.
GitMan refused to create the lane because older lanes had non-linear or
divergent history.

gitman reconcile reported success, but the next gitman status reported the
same off-canonical errors. The recovery command did not change the state that
blocked lane creation.

The problem prevents a new, unrelated change from using GitMan in this
checkout. It also makes the safe handling of pre-existing work unclear.

## Repository state before the attempt

The checkout was on branch 037-follow-up-results.

The worktree already contained these changes:

~~~
 M src/devman/link.py
 M src/devman/watch.py
 M tests/unit/test_link.py
 M tests/unit/test_watch.py
~~~

Those files did not belong to this project. They were not changed, staged, or
committed as part of this work.

The new documentation was under:

~~~
.scratch/projects/038-devman-plane-redesign/
~~~

## Reproduction

Run these commands from the Devman repository.

### 1. Check the repository

~~~
devenv shell -- gitman status
~~~

The first result was:

~~~
Gitman status — OFF-CANONICAL
Reason: not inside a jj workspace
Recover: gitman init --colocate
~~~

### 2. Try the suggested bootstrap command

~~~
devenv shell -- gitman init --colocate --trunk main
~~~

Result:

~~~
already initialized (trunk 'main' is frozen).
~~~

### 3. Check the repository again

~~~
devenv shell -- gitman status
~~~

Result:

~~~
Gitman status — OFF-CANONICAL
Reason: lane(s) 037-deployment-handoff-results, 037-follow-up-results contain
a merge commit (non-linear) — run gitman reconcile. lane(s) 021-changelog
have a divergent change-id (one change → multiple commits) — run
gitman reconcile.
Recover: gitman reconcile — adopt it into a lane, or abandon it.
Exit: 1
~~~

The complete status output named these repository-wide findings:

- 037-deployment-handoff-results contains a merge commit.
- 037-follow-up-results contains a merge commit.
- 021-changelog has a divergent change ID.

### 4. Run the suggested recovery command

The non-destructive form was used. No --abandon command was run.

~~~
devenv shell -- gitman reconcile
~~~

Result:

~~~
Gitman reconcile — CLEAN
already canonical — no strays, refs in sync.
note: gitman.toml: [version] is ignored — gitman reads and writes the version
through uv (uv version). Delete the table; it becomes an error in 0.7.0.
~~~

### 5. Check the repository after reconciliation

~~~
devenv shell -- gitman status
~~~

Result: the same OFF-CANONICAL errors for the same three lanes.

### 6. Try to create the new lane

~~~
devenv shell -- gitman start 038-devman-plane-redesign
~~~

Result: GitMan refused because the repository was still off-canonical. It
reported the same merge-commit and divergent-change-ID findings and again
recommended gitman reconcile.

### 7. Check the available split and save operations

gitman split --help showed that split operates on a current lane. The checkout
did not have a usable current lane for this new project. This did not provide
a path to isolate the selected directory before lane creation.

gitman save --help was inspected, but no save operation was run. No command was
run that could abandon, reset, or rewrite another task's work.

## Observed failures

### 1. reconcile and status disagree

reconcile says that the repository is clean and that its references are in
sync. status says that the repository is off-canonical and blocks new work.

These commands either use different definitions of canonical state, or
reconcile does not repair the condition that status checks. In either case,
the user cannot trust the success result from reconcile as proof that the
repository is ready for a new lane.

### 2. Historical lane problems block unrelated work

The problems are in older lanes, but they block creation of a new lane for an
unrelated documentation change. One invalid historical lane therefore becomes
a repository-wide blocker.

This may be intentional for operations that require a fully canonical history.
It is still a usability problem because the error does not offer a safe way to
start independent work from a known-good base.

### 3. The safe recovery path is not actionable

The status output offers reconcile, adoption, or abandonment. Reconcile did not
change the result. Adoption and abandonment require decisions about existing
lanes and could affect work that is unrelated to the current task.

The user therefore cannot choose a safe recovery action from the reported
options without first understanding GitMan's internal lane state.

### 4. Dirty worktree isolation is unclear

GitMan's lane start operation can adopt a dirty worktree. That is unsafe for a
new task when the worktree contains unrelated edits.

The desired operation was narrower: create a lane for one new directory and
leave the existing source and test edits alone. The available commands did not
make that operation possible while the repository was off-canonical.

## Impact

- The concept document could not get an isolated GitMan lane.
- Existing source and test changes could not remain separate through GitMan.
- The new project could not use the normal lane workflow.
- The safe immediate option was to leave the documentation uncommitted.
- The user had to authorize a raw Git fallback.

This incident does not prove that the old lanes are invalid or that their
history should be abandoned. It proves that GitMan cannot create new work in
this checkout while it reports the repository as off-canonical.

## Expected behavior

GitMan should provide at least one of these safe paths:

1. reconcile repairs the reported condition, and the next status agrees.
2. status identifies the bad lanes but permits a clean new lane from a
   known-good base.
3. start creates a lane from a clean base without adopting the current dirty
   worktree.
4. split can isolate a selected path before a new lane exists.
5. A documented, non-destructive, path-scoped operation can create a lane for
   selected files while leaving all other dirty paths untouched.

No path should discard or silently move unrelated work.

## Proposed fixes

### A. Use one canonical-state validator

Make status, start, split, save, and reconcile use the same validator and the
same findings.

If a merge commit or divergent change ID is invalid, reconcile should either
repair it or return the same blocker that status reports. It must not report
CLEAN while the next status check still blocks all new work.

### B. Separate repository health from lane creation

Report historical lane problems as lane-specific health findings. Allow a clean
new lane when the requested base is valid and the new operation does not touch
the affected lanes.

If GitMan intentionally requires a fully canonical repository before any new
lane, the command should explain why and provide a read-only way to inspect and
repair each named lane.

### C. Add a clean-base lane operation

Provide an explicit operation such as:

~~~
gitman start 038-devman-plane-redesign --from main --workspace
~~~

The command should create an isolated workspace from main. It must not adopt,
stage, move, or rewrite dirty files in the current worktree. The output should
state the base, workspace path, and files that were changed.

### D. Add path-scoped adoption before lane creation

Provide an explicit operation such as:

~~~
gitman start 038-devman-plane-redesign --paths \
  .scratch/projects/038-devman-plane-redesign
~~~

Only the selected path should enter the new lane. All other dirty paths must
remain in their original state. The command should refuse ambiguous overlaps
and show the exact selected path set before changing anything.

### E. Add regression tests for the state machine

At minimum, test these cases:

1. A lane with a merge commit blocks status and produces the same finding in
   reconcile.
2. A lane with a divergent change ID produces the same result.
3. reconcile repairs every supported invalid history shape.
4. A second reconcile is idempotent.
5. A historical bad lane does not stop a clean new lane when isolation is
   explicitly requested.
6. A path-scoped operation isolates only the selected dirty path.
7. Unrelated dirty paths are not staged or moved.
8. A clean-base workspace starts from the requested base revision.
9. Every operation reports whether it changed, adopted, moved, or discarded
   anything.

### F. Resolve the gitman.toml warning

The recovery output says that [version] is ignored and will become an error in
GitMan 0.7.0 because the version is read and written through uv version.

Remove or migrate that configuration in a separate focused change. It did not
cause the lane-creation failure, but it is a known future failure and should
not remain mixed with the canonical-state issue.

## Acceptance criteria

- status and reconcile agree about canonical state.
- A historical finding names the affected lane and the repair scope.
- A clean new lane can start without repairing or abandoning unrelated lanes.
- A dirty worktree can isolate a selected path without touching other paths.
- Command output states the base and every changed, adopted, moved, or discarded
  path.
- Regression tests cover the state transitions and isolation guarantees.
- No --abandon operation is required for an unrelated task.
- The gitman.toml warning is resolved or tracked as a separate issue.

## Workaround used for this project

The user explicitly authorized raw Git after GitMan failed to create the lane.

The workaround stages only:

~~~
.scratch/projects/038-devman-plane-redesign/
~~~

It does not stage:

~~~
src/devman/link.py
src/devman/watch.py
tests/unit/test_link.py
tests/unit/test_watch.py
~~~

The raw Git commit is a temporary workaround. It does not resolve the GitMan
defect.
