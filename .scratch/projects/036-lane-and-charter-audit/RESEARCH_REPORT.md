# Link-plane closure research report

Date: 2026-09-11

## Question

Where should the per-project `.local.gitignore` live, and does link
reconciliation handle the bootstrap declarations that share a canonical path?

## Evidence

- The charter's boundary rule says content that remains true for another clone
  is tracked, while machine-specific views are central and symlinked. See
  [`025-the-link-plane/CONCEPT.md`](../025-the-link-plane/CONCEPT.md), §P0 and
  §3.1.
- `src/devman/link.py` makes the central file the canonical side and the
  repository `.git/info/exclude` the view side. The config repository currently
  has no ignore rule for `projects/*/.local.gitignore`.
- The bootstrap declarations use `projects/<project>/agents` for `.agents` and
  `projects/<project>/agents/skills` for `.claude/skills`. Before this fix, the
  first missing canonical path was created from the view name `.agents` as a
  file, so the second declaration could not create `agents/skills`.
- The pre-fix unit baseline passed 518 tests. The final unit run passed 519,
  including the shared-ancestor regression in
  [`tests/unit/test_link.py`](../../../tests/unit/test_link.py).

## Decision

Track `.local.gitignore` in each per-project directory of the central devman
config repository. It is authored policy, so gitman lanes carry changes to it.
The repository-side `.git/info/exclude` remains a symlinked projection and is
not tracked in the project repository.

Resolve all link declarations before creation. Mark any canonical path that is
an ancestor of another canonical path as a directory. This makes first
reconcile deterministic for shared canonical trees.

## Verification

`base:check` passed. `base:unit` passed with 519 tests. `devman doctor` showed
seven findings already present before this closure and no new finding. The
nested-workspace `base:test` task hit the known outer Git-root filter. An
equivalent `nix flake check` from a temporary copy outside that root passed all
20 checks, including the Dagu service VM. Both results are in the dated local
artifact logs.

The Part C follow-up state-gap fix passed `base:check` and `base:unit` with 520
tests. It keeps the existing refusal when both sides really changed, while
allowing a nested view whose canonical path appeared during the same declared
reconcile.

The other Part C checks produced these results:

- vendomat's `repoman-toolchain-core` built successfully;
- the store-mode consumer's `repoman doctor` completed successfully;
- the agentman fake capsule completed with zero findings;
- CopyRoom's compatibility helper has callers in both workshop and project
  flows, so a whole-file removal is not justified;
- the lock readers report real stale pins and path-copy costs;
- Claude permission-save behaviour remains untested and its local settings
  files stay local for now.
