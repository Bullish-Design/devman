Session root: ~/Documents/Projects/devman

# Phase 5 — close out the toolchain refactor

Phases 0-3 of `.scratch/projects/023-toolchain/` are done and verified. Phase 4
(the shared command closure) was built ahead of its own schedule and is most of
the way there. This phase finishes the parts that are still open, in an order
that never leaves a command unreachable.

Audited 2026-09-08. Every "measured" line below was run, not recalled.

## What is already true. Do not re-derive, do not re-do.

- **Phase 0**: the stray `.pth`, the `uv tool` gitman and the `nix profile`
  devenv are all gone. `nix profile list` holds `act` only.
- **Phase 1**: `uv` is in the developer packages; `programs.repoman.enable`
  defaults false; the 3.13 baseline is written into `nix-meta/profiles/
  developer.nix` and `repoman/AGENTS.md`; `repoman/flake.nix` is on
  `python313Packages`; the `rsync`/`rlist`/`rstatus` aliases live in
  `nix-meta/profiles/terminal.nix`. The prescribed `home.sessionPath` to the venv
  was superseded: `home.sessionVariablesExtra` appends the Nix closure instead.
- **Phase 2a**: `gitman log --revset <r> --json` exists (`gitman/src/gitman/
  cli.py:173`), oldest-first, exit 3 naming an unparseable revset, with tests in
  `gitman/tests/test_log_range.py`.
- **Phase 2b/2c**: templateer is tagged `v0.4.0` and pinned in `repoman.lock`
  `[managers.template]`. `deps:toolchain` reports 59 packages mutually
  compatible — the 2c stop condition did not fire.
- **Phase 2d**: `groups/changelog/workflows/changelog.yaml` has no
  `TEMPLATEER_PATH`, no `PYTHONPATH` and no `import pyjutsu`. It calls
  `gitman log` and `templateer` as console scripts, probes `command -v` for both
  the way a *step* runs, and refuses both a `failure_reason` and an empty
  artifact. `base:check`, `base:test` and `devman doctor` all exit 0.
- **Phase 3**: MEASURED — `nix build .#pyjutsu-wheel` and the published GitHub
  release asset are **byte-identical** (sha256 `ffb0aa2f…`). Empty RUNPATH; only
  `libgcc_s`, `libm`, `libc`, `ld-linux`. `UV_NO_BUILD_PACKAGE` is inverted
  (`vendor.noBuild` defaults false). The dev-version rule is in
  `vendomat/src/vendomat/wheels.py:76`. All six no-face repos are clean.
- **Phase 4, partly**: `copyroom`, `repoman`, `docman`, `gitman` and now
  `templateer` are Nix applications at 3.13, composed into
  `repoman-toolchain-core` and on the login PATH through Home Manager.
  vendomat is at `v0.3.6`; nix-meta pins it and evaluates to
  `g497xl6ac4lwhiln0b0h6bqsmxkyxg4i-repoman-toolchain-core`.

## Open work, in dependency order

### 1. Apply the rebuild, if the owner has not already

    cd ~/Documents/Projects/nix-meta
    sudo nixos-rebuild test --flake .#server
    zsh -lic 'command -v templateer gitman repoman copyroom docman'
    sudo nixos-rebuild switch --flake .#server

Rollback is `sudo nixos-rebuild --rollback`. **Ask before running `switch`.**

### 2. Refresh the shelf's recorded metadata

`repoman doctor` currently reports two FAILs, both stale metadata, not drift:

    version:managers.git-vendomat  0.3.2 installed, checkout declares 0.3.6
    version:repoman                0.7.2 installed, checkout declares 0.7.5

`repoman.lock` also still pins `[managers.git-vendomat]` at `@v0.3.2`; bump it to
`v0.3.6`. Then `devenv shell -- repoman-sync --machine` and re-run the doctor.

The `zensical not on PATH` FAIL in the `doc` section is a docman issue and is NOT
part of this project. Leave it.

### 3. Make store mode the default, then retire the shelf copy of templateer

**This is the one ordering that matters. Getting it wrong takes `templateer` off
every devenv's PATH and breaks the changelog workflow's own probe.**

Today `repoman.cliProvider` defaults to `"venv"` (`repoman/modules/devenv.nix:95`),
so inside a devenv the shelf venv wins and outside it the store closure wins.
`templateer` therefore has two owners again, decided by PATH order — the exact
defect this project exists to remove.

In this order, verifying between each:

  a. Flip `cliProvider`'s default to `"store"`. Keep `"venv"` first-class; the
     module already errors actionably when `REPOMAN_TOOLCHAIN_BIN` is unset
     (`modules/devenv.nix:201`). Keep `editable` working for a tool's own repo.
  b. Prove in a real devenv that `command -v templateer gitman` both resolve into
     `/nix/store`, not into `~/.local/share/repoman/venv`.
  c. Only then remove `[managers.template]` from `repoman.lock`, and re-sync.

Do NOT do (c) before (b) passes.

### 4. Package `testee`

CONCEPT 03 §6 stage 2 names it and it is the only roster tool still missing.
`vendomat/lib/mkPythonCli.nix` reads everything from `pyproject.toml` and throws
on an unmapped dependency, naming the tool and the dependency. Add each missing
name to `defaultDepMap` when nixpkgs carries it. When nixpkgs does NOT carry it,
or carries a version the consumer's own metadata rejects, use
`lib/mkPypiWheel.nix` inside an overlay on a separate interpreter — read
`pkgs/templateer-deps.nix` first, including its header. Both of its constraints
were measured, not chosen:

- A standalone pin produces a duplicate distribution the moment anything else in
  the closure still resolves the nixpkgs one, and buildPythonPackage refuses that
  closure. Override the SET.
- A global override rebuilds every other roster tool. Use a separate interpreter.

Each tool gets a package build test, a command-origin test and a consumer
integration test. `vendomat/tests/test_toolchain_nix.py` holds the pattern,
including the two roster tests that pin the exact command list — **they will fail
until you add the new name to both.**

### 5. The end-to-end changelog run

The one deliverable of 2d that was never exercised. PR #159 says so itself:
"End-to-end run against a real gitman-managed repository … not exercised here —
no repository has adopted it yet."

Required by `.scratch/projects/022-templateer-changelog/KICKOFF.md`: a disposable
adopter, real `gitman start` / `save` / `land`, the real post-hook enqueue, the
chained run reaching generation, and a person reading the lane diff. Plus BOTH
refusals — the empty batch, and a second unreviewed lane.

Traps already paid for, do not rediscover: `dir:` is now `working_dir:`; `env` is
a reserved step id; and `DEVMAN_PROJECT_DIR` must be **exported in the enqueuing
shell**, because `base.yaml`'s `log_dir` reads the variable and DAG `params:` do
not reach it.

**The local LLM endpoint was down at audit time** (`curl http://127.0.0.1:8000/v1/models`
returned nothing). Bring it up first, or this phase cannot complete. Check the
model id it actually lists — the workflow sends `openai:$GPU_LLM_MODEL`, and
`--model gemma` without the provider prefix returns `config_error`.

### 6. Merge PR #159

devman PR #159 (`021-changelog` → main) is OPEN and MERGEABLE. It should merge
after (5) passes, with the end-to-end checkbox ticked or its absence stated.

### 7. Phase 3b's manifests — decide, then act

`vendomat.toml` does not exist in `gitman`, `repoman`, `copyroom` or `docman`.
Phase 3b's GOAL was met another way: every `repoman.lock` source is now a git tag
or a release URL, no `path:` entry remains, and the `UV_FIND_LINKS` precondition
is gone. What is missing is only the pre-push hook that keeps those tags current
automatically; today a tag bump is manual.

This is a real choice, not an oversight. Decide with the owner:
 - add the manifests, and read the `--dry-run` output before the first push
   (expect a nonzero status; the `published GitHub-source commit(s)` line above
   it is the success signal), or
 - record in `023-toolchain/` that manual tag bumps are the accepted cost, and
   close 3b.

## Rules

- **Route every version-control action through gitman.** Never raw `git` or `jj`.
  `~/Documents/Projects/gitman/.agents/skills/gitman/SKILL.md` is the reference;
  vendomat and nix-meta carry no local copy of it. In devman, open a PR to main —
  `gitman push` on `branch:main` is refused there. vendomat and nix-meta land and
  push to main directly, which is what the last two commits did.
- devman keeps **no `uv.lock` and an empty venv**. Its workflows call console
  scripts, so it needs no Python dependencies. Do not add `templateer` to its
  `pyproject.toml`.
- Do not reverse: the loud failure on an unset `${DEVMAN_PROJECT_DIR}`; the
  empty-batch and unreviewed-lane refusals; `GPU_LLM_*` as DAG `params:`;
  `gitman/pyproject.toml`'s `[tool.uv.sources]` pyjutsu URL.
- **Preserve unrelated worktree changes in devman.** That tree has ~2,600 entries
  in `git status`, including `.jjconflict-base-0/` directories from an old
  colocation conflict. `gitman status` reports CANONICAL; jj is authoritative and
  the raw git index is stale. Do not "clean it up" as part of this work — and do
  not read the raw git index as evidence about that repo's state.

## Stop if

- Step 3(b) does not resolve `templateer` into `/nix/store` from inside a devenv.
  Do not proceed to 3(c); a shelf entry removed early leaves no templateer at all.
- A new roster tool's dependency needs a version nixpkgs lacks AND has no
  published wheel. `mkPypiWheel` installs a published artifact; it does not build
  one. Building is `mkMaturinWheel`'s job and a different decision.
- `repoman-sync` rejects a source spelling. Add a source form; never overload
  `wheel:`.
