Session root: ~/Documents/Projects/vendomat

# Phase 4 — the shared command closure (a separate project, not a step)

Do not begin until Phases 0-3 are done and stable.

Context: the machine's CLI family currently lives in a mutable virtualenv at
`~/.local/share/repoman/venv`, installed from four live working trees, with no
rollback and with PATH order deciding between duplicate names. This repository
already holds the correct design for replacing it, written 2026-07-16 and never
implemented.

Read first, in full:
`.scratch/projects/03-shared-repoman-toolchain/CONCEPT.md`

Then `~/Documents/Projects/devman/.scratch/projects/023-toolchain/TARGET.md`,
section "Where this lands, with Face D".

## The target

```
gitman · repoman · copyroom · docman · templateer
   built once as Nix Python applications, all at Python 3.13
   composed into one roster closure, on PATH in every devenv,
   the login shell, and every Dagu step

pyjutsu
   a build input of the gitman derivation, with exactly one consumer
   still published for outside adopters, no longer load-bearing

the other ~60 repos
   declare zero first-party Python dependencies
```

Under this, issue G3 cannot be expressed: a repo never runs `uv add gitman`,
because gitman is a command on its PATH, not a library it depends on.

## Phasing — follow CONCEPT.md §6 exactly

0. Inventory every manager's console script, dependencies and venv-path call
   sites. Add `repoman.cliProvider = "venv"` as an unchanged default, with
   regression tests for current behaviour.
1. Package `copyroom` and `repoman` at 3.13. Prove one fixture has no manager in
   its venv and that both resolve to `/nix/store`.
2. Add `testee`, then `docman`, one at a time. Each gets a package build test, a
   command-origin test and a consumer integration test.
3. `gitman`, built against the published pyjutsu wheel. Prove a `git` consumer
   pulls no Rust, no maturin and no cargo.
4. Make store mode the default. Keep `editable` first-class for tool authors.
5. Expose the closure through Home Manager, replacing the `home.sessionPath` line
   added in Phase 1.

## Decide before writing code

CONCEPT.md §8.2: is vendomat's flake lock authoritative in store mode, or does
`repoman.lock` gain a `toolchain:` source kind? Either needs an explicit mismatch
check, not implicit precedence. This is the owner's call.

§8.1 names package materialization as the principal cost and is right: every
`pyproject.toml` must be made to build under Nix, one tool at a time. Do not
assume a tool is supported because its package evaluates — exercise its doctor
and task flow.

## Constraint learned the hard way

Nothing in the closure may sit on the shell-entry critical path without a
degrade. A broken `vendor-status` once took down loci-core's devenv shell
entirely (gitman project 32, G3).

## Acceptance — CONCEPT.md §7

- Two consumers with identical locks resolve to the same store paths.
- Their `.devenv` venvs contain neither the manager distributions nor their
  console-script wrappers.
- Tasks and doctors use the shared paths even when a conflicting executable
  exists in the venv or inherited PATH.
- A tool's own repo can opt into editable mode and run uncommitted changes.
- A missing, stale or mismatched manager fails actionably. No silent fallback.
