# Link module recovery report

Date: 2026-09-14

## Target

Restore the source files that the Devman devenv module imports. Prove that the
Paseo Claude Code wrapper can enter this repository again. Do not change the
link-plane design or reconcile the known off-canonical Gitman state.

## Failure

The first baseline command was:

```text
devenv shell -- true
```

Nix evaluation stopped with exit 1 because `modules/devenv.nix` imports
`modules/link.nix`, but that file did not exist in the working tree. The Paseo
Claude Code override always runs its command through `devenv shell` when it
finds `devenv.nix`. Claude Code did not start because shell evaluation failed
first.

The baseline evidence is in
`artifacts/20260914T040026Z-link-module-repair/`.

## Cause

The deletion happened on 2026-09-13 at 18:34:13 EDT. A prior Codex session ran:

```text
git restore --source='stash@{0}' --worktree -- .
```

The stash predated the Project 038 files. Git therefore removed files that the
later `038-fixup-and-fanout` work had added. Eight seconds later, that session
restored only `src/devman/watch.py` and `tests/unit/test_watch.py`. It did not
restore the link-plane source set.

The command is recorded in the Codex transcript at
`~/.codex/sessions/2026/09/13/rollout-2026-09-13T17-58-55-01a09cc7-cf74-7990-87cb-d88897112e51.jsonl`.
The Paseo agent record is
`~/.paseo/agents/home-andrew-Documents-Projects-devman/12203a9a-c25f-4b6b-948d-b83a0cfa3b3e.json`.

## Design history

The deletion was not an approved cleanup.

Stage 17 made `src/devman/link.py` a temporary re-export because
`src/devman/watch.py` still imported it. The §11 cleanup can delete that Python
re-export after the watcher changes land.

Stage 18 added `modules/link.nix` as the permanent machine-owned devenv
interface. It declares `devman.link`, resolves project identity, and runs the
machine-installed `devman-link reconcile` command at shell entry. The Stage 18
follow-up also exposed the same module at
`/run/current-system/sw/share/devman/link-module.nix`.

The published Stage 18 source is at
<https://github.com/Bullish-Design/devman/blob/edd0b62834d9c9d8ac61d44f56219b63afb60bdf/modules/link.nix>.
The local reasoning is in the Stage 17 and Stage 18 sections of
`IMPLEMENTATION_LOG.md`.

Gitman cannot show those Stage 17 and Stage 18 commits in its current canonical
history. Its canonical `main` history ends at Project 038 Stage 13. The checkout
also has the known divergent `021-changelog` lane and the leftover raw Git ref
`038-fixup-and-fanout`. This repair does not run `gitman reconcile`; the project
plan defers that work.

## Repair

The repair restored 25 files from the verified Stage 18 follow-up Nix source
snapshot:

- `.devman/project.toml`
- `modules/link.nix`
- `nix/link-adapter.nix`
- `packaging/devman-link/pyproject.toml`
- three `src/devman/` contract and identity modules
- three `src/devman_contract/` modules
- eleven `src/devman_link/` modules
- four unit test modules

The repair preserved the existing changes in `src/devman/watch.py` and
`tests/unit/test_watch.py`.

The restored `modules/link.nix` matches the live installed module byte for
byte. Both copies have SHA-256
`40e9398a3e463e2c14853d992d91da0a905fba373eabc83834ec655b3524924e`.

## Proof

The following commands passed after the repair:

```text
devenv shell -- true                                      exit 0
devenv tasks run -v base:unit                             exit 0, 606 passed
devenv tasks run -v base:check                            exit 0
devenv tasks run -v base:test                             exit 0, all checks passed
paseo-agent-shell claude --version                        exit 0, Claude Code 2.1.207
```

The wrapper proof used the exact configured override path from the failure:

```text
/nix/store/8lrv7ndkb1nq84ly3bmyyr70zkxx2fvd-paseo-agent-shell/bin/paseo-agent-shell
```

`devman doctor` reached the plane and reported the same four known findings:
the `flora-037-part-e` link drift, dirty and unpinned Vendomat, dirty and
unpinned RepoMan, and the unpinned `git+file:` advice. It exited 1. This repair
does not claim to resolve those planned follow-up items.

The post-repair evidence is in these directories:

- `artifacts/20260914T040212Z-link-module-shell/`
- `artifacts/20260914T040351Z-base-unit/`
- `artifacts/20260914T040518Z-base-check/`
- `artifacts/20260914T040539Z-base-test/`
- `artifacts/20260914T040807Z-doctor/`
- `artifacts/20260914T040826Z-paseo-wrapper/`

## Result

The repository shell and the Paseo Claude Code wrapper work again. The repair
restores the intended Stage 18 boundary. It does not add a fallback, a feature
flag, or a second implementation.
