# Wave 3 item 15 — documentation sweep

Date: 2026-09-15 (UTC timestamp `20260915T124543Z`)
Branch: `wave-3-item-15-documentation-sweep`, from `main` at `58330a1`.

## Files changed

| File | What changed |
|---|---|
| `AGENTS.md` | property 6: the three roots, the deferred `registryDir` move, dated generation evidence |
| `AGENTS_GUIDE.md` | §3: `registry.py` and `watch.py` responsibilities, the full `doctor` check list, the `mode` swap, the new `check_load` measurement, the lagging machine CLI. §4: the registry-root table, the derived-registry rule, a new reload-gate subsection |
| `README.md` | the three roots, identity, render-to-link and `registryDir` not shipped, the scheduled-run trigger bypass |
| `USER.md` | `doctor` modes, active generation, reload gate and its limits, the three roots, the identity refusal row, the scheduled-run bypass |
| `.scratch/projects/025-the-link-plane/CONCEPT.md` | §6.2a amendment separating proven mechanism from shipped migration; Stage 3 item 2 gains the Stage 41 refusal; Stage 3 item 4 points at the amendment |
| `.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md` | Stage 37 correction gains the Stage 42 outcome; new Stage 46 |
| this artifact | new |

No implementation code, generated registry file, active-generation file,
overlay, Dagu state, or other repository changed.

## Corrected records

| Record | Correction now carried by the documentation |
|---|---|
| **R1** | The watcher is gated. `watch.py:612` calls `run.trigger`, whose first statement is the `reload.pending` refusal. Only Dagu's own scheduled enqueues bypass it. Recorded in `AGENTS_GUIDE.md` §3 and §4, `README.md` "Schedules", `USER.md` §2.7 and §6 |
| **R3** | The ten Stage 37 consumer commits were published to branches, not merged into `origin/main`. The Stage 37 correction note stands, and now points at Stage 42, which landed them on 2026-09-14 |
| **R7** | `976d14e` removed the compatibility-registry enumeration for `devman link status --all`. `README.md` and `USER.md` document only the `--projects-root` manifest sweep. No document claims the registry read |
| **R8** | The `${DAG_NAME%.*}` scheduled-run mechanism is designed and measured under Dagu 2.15.0. Render-to-link has **not** shipped. `025/CONCEPT.md` §6.2a now states the split and names the unproven safety property: a shared source resolving to a missing directory reports `Succeeded` |
| **R10** | The VM test had no reload subtest before Wave 3 item 7. `AGENTS_GUIDE.md` §4 states only the coverage the tests provide: three unit-level marker tests plus the timeout, stopped-Dagu and failed-restart subtests added in item 7 |

## Measurements used

| Measurement | Value | Command |
|---|---|---|
| `check_load` cost | **16.8 ms per projected file** — 2.549 s over 152 files, 2026-09-15. Supersedes the 87.6 ms rollout figure | `doctor.check_load` timed directly against the active generation |
| whole-plane `doctor` wall clock | 10.5 s at 152 files, against 6.0 s at the 16-file state-root view | `time devman doctor` |
| machine CLI lag | installed `devman` reported `3 projects, 16 workflows`; the same binary with `PYTHONPATH=<repo>/src` reported `48 projects, 152 workflows` | both runs from `/tmp` |
| active generation | generation 3, 48 project directories, 152 DAG files | `ls` under the active root; `generation.json` |
| `reloadMaxWaitSec` | 600 s, from an observed maximum of 279 s over 1306 runs | `nix/nixos-module.nix:495-506` |
| scheduled-run bound | 20 s max over 550 records; `maintain` 5 s over 551; 45 DAGs at 00:05 daily | Wave 3 investigation, `025/CONCEPT.md` Stage 3 item 5 |

## Commands used

```sh
git switch -c wave-3-item-15-documentation-sweep
cd /tmp && time env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman doctor
cd /tmp && time env -u PYTHONPATH -u NIX_PYTHONPATH \
  PYTHONPATH=/home/andrew/Documents/Projects/devman/src \
  /run/current-system/sw/bin/devman doctor
git diff --check
devenv tasks run -v base:check
devenv tasks run -v base:unit
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
devenv shell -- nix build .#packages.x86_64-linux.devman-link --no-link
```

## Results

| Gate | Result |
|---|---|
| `git diff --check` | clean, exit 0 |
| `base:check` | `All checks passed!` |
| `base:unit` | **590 passed** in 10.29 s |
| `base:test` | `all checks passed!` in 138 s |
| `nix build .#checks.x86_64-linux.dagu-service` | exit 0 |
| `nix build .#packages.x86_64-linux.devman-link` | exit 0 |
| canary `devman-link status --project vendomat` | exit 0, five `ok` states, central config path |
| canary `devman link status --project vendomat` | exit 0, five `ok` states, central config path |
| fleet sweep | `47 0` clean, `1 1 image-gen-pipeline` — the known promote drift. No new refusal |

## Live plane state

```
active generation  3
projects           48
DAG files          152
dagu_digest        sha256:d3bbe557424a1137700d5cad5b35f983489313227ea1f8c92161be7ee5cf1278
dagu               2.15.0, up 60 h
reload markers     absent
```

## Every doctor finding

`devman doctor` run from `/tmp`, 2026-09-15, exit 1. Two `!!` sections. The
count of 4 is a line count: `Report.findings` sums the lines of every `!!`
section, and each section here holds two lines.

1. `literal dir  /tmp/${DEVMAN_PROJECT_DIR}`, plus its explanation line — a
   leftover of the Wave 3 investigation's isolated `${DAG_NAME}` experiment.
   `stat` dates the directory to 2026-09-14 14:12, and it holds
   `logs/projA_cmdsub` and `logs/projB_cmdsub` run logs. `check_literal`
   searches `Path.cwd()`, so the finding appears only when `doctor` runs from
   `/tmp`. Item 15 did not create it and did not remove it.
2. `local sources  vendomat: uncommitted changes, consumed unpinned by 1
   project(s)`, plus the unpinned `git+file:` advice line.

The `flora-037-part-e:devenv.local.nix: create` finding is gone — Stage 43
archived that worktree and pruned its entry. The RepoMan dirty-and-unpinned
finding no longer appears in this run. **No new plane finding appeared.**

## Failed attempts, preserved

- The first `devman doctor` run reported `3 projects, 16 workflows` against
  generation 3. That looked like a regression in the active generation. It is
  not: the installed `/run/current-system/sw/bin/devman` predates Wave 3 item 5,
  so it enumerates the stable state root. Re-running the same binary with
  `PYTHONPATH` set to this repository's `src` reported `48 projects, 152
  workflows`. The documentation now states this lag instead of hiding it.
- The `AGENTS_GUIDE.md` §3 figure of 87.6 ms per file could not be reproduced.
  It is a 2026-07 rollout measurement against the compatibility registry. The
  new run measured 16.8 ms per file. The guide records the new number and says
  which measurement it replaces.
