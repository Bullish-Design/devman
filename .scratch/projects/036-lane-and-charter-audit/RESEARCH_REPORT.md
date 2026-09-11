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
closure-path `base:test` attempt is preserved in the artifacts and failed only
because Nix filters nested workspaces through the outer Git root; the hermetic
check will run after this change is landed into the parent 032 workspace.
