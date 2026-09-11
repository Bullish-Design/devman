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

The Stage 3 registry/state split, Stage 4 direct workflow links, and live fleet
adoption remain separate work. The six Part C questions are recorded below.

## Part C — charter questions

1. **Claude settings write behaviour:** not settled. The fleet still has real
   `.claude/settings.local.json` files, but no controlled Claude permission
   approval was run in this audit. Keep these files local until that product
   write test is performed.
2. **`cliProvider = "store"`: settled.** `nix build
   .#repoman-toolchain-core` in vendomat produced a closure. The vendomat
   `tests/fixtures/store-consumer` repository entered a store-mode shell and
   `repoman doctor` completed successfully. It reported only the fixture's
   expected missing skill-entrypoint warnings. The closure measured 24K; the
   vendomat checkout's `.devenv` is 122M. Store mode removes the manager
   toolchain from the consumer venv, but a consumer that imports a local
   `path:` vendomat tree still pays the path-input copy cost.
3. **Agentman:** settled as new and now consumed. `groups/agent/` exists in
   devman, and `agentman run review --backend fake` completed cleanly with one
   validated turn and zero findings.
4. **CopyRoom git compatibility:** do not shrink this file as a whole. The
   call graph has callers in both `src/copyroom/workshop/registry.py` and the
   project/template/release/manage code. Workshop uses source and tag lookup;
   project workflows use worktree, status, commit, and diff operations.
5. **Lock-reader noise:** signal, not false positive. `check_local_sources`
   reports an actual stale `pytuin` pin for `atuout`, and `check_path_inputs`
   reports the measured 122M vendomat `.devenv` copy cost. The checks should
   remain warnings until the source or input is corrected.
6. **Promote conflicts:** measured at 12 of about 46 fleet migrations. The
   refusals were caused by the per-view state gap when an ancestor promotion
   made a nested canonical path available. Reconcile now records newly
   available canonical paths for all declarations after each successful step.
   The regression is covered in `tests/unit/test_link.py`.

## Verification record

The pre-fix baseline is saved in
`artifacts/20260911T130000Z-baseline/base-unit.log`. The final verification
logs are in `artifacts/20260911T130000Z-final/`:

- `base:check` passed.
- `base:unit` passed with 519 tests.
- `devman doctor` returned the same seven pre-existing findings: two link-drift
  entries, one local-source pin, one path input, one daemon-shell notice, and
  the watcher report.
- `base:test` was attempted in the nested workspace and hit the known Nix
  filter. An equivalent `nix flake check` from a temporary copy outside the
  outer Git root passed all 20 checks, including the Dagu service VM. The raw
  task failure and the successful rerun are preserved in the dated local
  artifacts.
- The follow-up promote-state fix passed `base:check`, `base:unit` with 520
  tests, and `devman doctor` with the same seven pre-existing findings.
