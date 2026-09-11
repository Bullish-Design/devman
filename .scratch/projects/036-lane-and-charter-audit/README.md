# Lane and charter audit closure

Date: 2026-09-11

This report closes the lane cleanup and the link-plane decisions from the audit
prompt in this directory.

## Part A — in-flight lanes

- `031-audit-doc-corrections` was verified and landed as `ecff7ae`.
- `032-link-plane-hardening` was the live implementation lane. Its central
  exclusion work is retained and this closure adds the shared-canonical-path
  regression fix.
- `034-stage-3-readiness-audit` supplied the regression and the Stage 3
  readiness findings. Its useful source fix is folded into this closure. Its
  remaining Stage 3 work stays deferred.
- `review-009-code-review` was abandoned after its files were byte-identical
  to trunk.
- `preexisting-draft` was abandoned because it contained only an unfinished
  kickoff prompt unrelated to this audit.

The closure lane is the source of truth for the retained 032 implementation,
the 034 regression fix, the charter decision, and this report.

## Part B — orphaned lanes

All 15 orphaned lanes were checked. Each tip is already an ancestor of `main`
and has no unique patch relative to it, including the agent-factory spike tip.
They were abandoned explicitly. `gitman status` no longer reports ORPHANED
lanes.

## Part C — decisions

### `.local.gitignore` ownership

Track `.local.gitignore` in the per-repository directory of the central devman
config repository. It contains authored exclusion policy and can contain
promoted local rules. It is not runtime state and must not be covered by the
central config repository's ignore rules. The repository's
`.git/info/exclude` remains a symlinked projection of that tracked file.

This applies the boundary rule in
[`025-the-link-plane/CONCEPT.md`](../025-the-link-plane/CONCEPT.md): the file
is true for the config repository and must be recoverable there; the absolute
repository-side link is machine-specific and remains ignored.

### Shared canonical paths

The bootstrap declarations for `.agents` and `.claude/skills` share the
canonical `agents` directory. Reconcile now resolves the complete declaration
set first and creates an ancestor canonical path as a directory. The regression
is in [`tests/unit/test_link.py`](../../../tests/unit/test_link.py).

### Deferred questions

The remaining Stage 3 registry/state split, Stage 4 direct workflow links, live
fleet adoption, and the other open questions remain separate work. This closure
does not silently flip those designs or change unrelated repositories.

## Verification record

The pre-fix baseline is saved in
`artifacts/20260911T130000Z-baseline/base-unit.log`. The final verification
logs are in `artifacts/20260911T130000Z-final/`:

- `base:check` passed.
- `base:unit` passed with 519 tests.
- `devman doctor` returned the same seven pre-existing findings: two link-drift
  entries, one local-source pin, one path input, one daemon-shell notice, and
  the watcher report.
- `base:test` was attempted and hit the known nested-workspace Nix filter:
  Nix sees `closure/flake.nix` as untracked below the outer Git root. The
  parent 032 workspace is the supported explicit-flake-check location; the
  closure lane must be landed into that workspace before the hermetic check can
  see it.
