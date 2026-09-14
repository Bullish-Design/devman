# Wave 3 item 3 — record corrections

Date: 2026-09-14

## Corrections

- R1: `src/devman/watch.py:612` calls `run.trigger`. Experiment E2 proved
  that the watcher refuses while `reload.pending` exists. The module comment
  and Stage 10 log now describe the watcher as gated. The VM test remains
  uncovered for reload, as R10 records.
- R3: the ten Stage 37 consumer commits are published to consumer branches,
  not `main`. The Stage 37 log now records the measured result: all ten
  `git merge-base --is-ancestor <commit> origin/main` checks returned `NO`,
  and `origin/main:.devman/project.toml` was absent.
- R7: commit `976d14e` replaced the compatibility-registry read with an
  explicit `--projects-root` manifest sweep. The old session prompt now marks
  item H closed.
- R8: Dagu 2.15.0 expands `${DAG_NAME%.*}` in DAG-level environment values.
  The isolated `projA.check` and `loci.nvim.check` scheduled-run experiment
  produced two correct project directories. The 025 charter now records this
  as the design and keeps renderer removal behind the VM proof.
- R10: `nix/tests/` has no reload subtest. The reload-script comment now says
  the current marker coverage comes from unit tests and that the VM subtest
  must be added before relying on it.

## Scope

Changed files:

- `nix/nixos-module.nix`
- `.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md`
- `.scratch/projects/038-devman-plane-redesign/NEXT_SESSION_PROMPT.md`
- `.scratch/projects/025-the-link-plane/CONCEPT.md`

Verification: `devenv tasks run -v base:check` passed. `git diff --check`
passed. No runtime implementation or registry state changed.
