# 041 — Personal-layer retirement record

**Checked:** 2026-10-03

This record tracks cleanup across active machine files and project repositories.
The source archive remains intact. The user excluded `~/Notes/1_Projects/`.
The scan also excludes Git history, caches, conversation logs, worktrees, and archives.
No history was rewritten.

## Work completed

The live central overlay was removed from the target and from local `main`.
The central repository has no remote. Its default workspace remains parked on an older
ancestor. An earlier switch attempt had no lasting effect; Gitman reported it was already
undone. I did not rebase it. Central `base:check` passed.

The active top-level enrollments and deployed skill copies were removed or landed.
Project instructions, templates, code, tests, and research records were edited by hand.
The edits preserve useful context and behavior. Generated preview patches were refreshed.
Local build-garage checkouts and historical simulator output remain excluded caches.

Repository commit IDs, checks, pushes, and Gitman relations are recorded in
`~/.local/state/retire-personal-layer/current-gitman-status.json`.
The exact remaining paths and text counts are recorded in
`~/.local/state/retire-personal-layer/REMAINING.md`.

## Checks

`devman` `base:check` passed in the cleanup lane. A second run also passed.
The central repository `base:check` passed. `devman doctor` reported local-source
findings for Repoman and Pytuin during concurrent repository updates; the final
health check remains to be repeated after those updates settle.

Repository suites passed where the lane reports record them. Some suites could not
run because local dependencies or test tools were absent. The status file records
those exact results.

## Work still blocked

Four isolated instruction lanes could not land while their repositories have
unbookmarked changes in the default workspace: `parsedantic`, `poddantic`,
`terminal-state`, and `webdantic`. The changes do not touch `AGENTS.md`.
I preserved each default workspace, lock lane, and test artifact.

The `siteman` default workspace contains an unbookmarked deployment change with
fourteen paths. I preserved all fourteen paths and updated only `AGENTS.md` from
current main. Gitman still flags that file as a local edit. I did not describe,
split, or rebase the deployment change.

`structured-agents-v2` is open on an adoption lane with a local shell input. I
updated only `AGENTS.md` from current main and preserved the lane. I did not sync
or land it because that would include local lock work.

Repoman's two historical doctor records now carry dated context in main and in
the live lock lane. Its local lock lane remains separate. A fleet-lock hook blocks
the main push because the lock resolves local `file:` inputs.

`clinch` remains blocked by its lock and missing test dependency. The `nixvim`
pre-existing lane remains conflicted. `llama-infernal` keeps local-only `main`;
no upstream branch was created. Four instruction files still have text matches:
`parsedantic/AGENTS.md`, `poddantic/AGENTS.md`, `terminal-state/AGENTS.md`, and
`webdantic/AGENTS.md`. Their cleanup lanes cannot land while each repository has
unbookmarked default-workspace changes. Those changes do not touch `AGENTS.md`.

This record does not claim complete retirement while the final scan reports any
in-scope path or text match.
