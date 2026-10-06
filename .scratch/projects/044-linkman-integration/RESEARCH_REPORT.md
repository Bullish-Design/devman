# Gate investigation — 2026-10-06

## Target and environment

Make `devenv tasks run -v base:test` exit 0 before the Linkman cutover.
Keep lanes 4-8 and the 60 central project files unchanged.

The devman baseline is trunk `f4a245f`. Its gate fix reached origin at
`651af40`. The Linkman baseline was trunk `81c1668`. Both baselines were in
sync with origin when work began. The shell uses Nix
2.34.7. The hermetic Python check uses Python 3.13.15. The VM packages devman
with Python 3.14.7. All commands ran on 2026-10-06 inside each repository's
devenv shell. The raw command logs are under `/tmp/devman-044-gate-2026-10-06/`
on the measuring machine.

## Measured gate sequence

| Check | Before | First edit | Final, 2026-10-06 |
|---|---|---|---|
| `devenv tasks run -v base:test` | Exit 1 in 25.9 s. Three cutover modules failed collection: `No module named 'tools'`. | The targeted checks found the next failures. | **Exit 0 in 29 s.** `nix flake check` printed "all checks passed!" |
| `nix build '.#checks.x86_64-linux.python-tests' --no-link` | The full gate exposed the collection error. | Exit 1: 707 passed, 34 skipped, 5 failed in 10.27 s. | **Exit 0 in 15 s:** 720 passed, 26 skipped in 11.36 s. All three cutover modules passed. |
| `nix build '.#checks.x86_64-linux.dagu-service' --no-link` | Exit 1 in 83 s. Doctor raised `InfraError: git is not on PATH`. | Exit 1 in 91 s. Doctor found no `writing` skill in the VM pool. | **Exit 0 in 121 s.** VM doctor printed "Nothing to report." |
| `devenv tasks run -v base:check` | Not run before edits. | Exit 0 in 7 s. | **Exit 0 in 6 s.** Ruff reported "All checks passed!" |
| `devenv tasks run -v base:unit` | Not run before edits. | Exit 0 in 21 s. | **Exit 0 in 20 s:** 745 passed, 1 skipped in 12.51 s. |
| `devman doctor` on the host | Not run before edits. | Exit 0 in 1 s. | **Exit 0 in 2 s.** "Nothing to report." |

The host doctor reported 291 live overlay views and 59 live surfaces with
`writing`. The VM's missing pool was specific to its fixture. Its final test
script finished in 112.33 s, including a doctor subtest that passed in 2.22 s.

The baseline Python failure comes from the source fileset in
[`flake.nix`](../../../flake.nix). It omits `./tools`, but three test modules
import `tools.cutover`. Adding `./tools` fixed collection and exposed five test
failures. Four report `nix-instantiate is not on PATH`. The fifth expects JSON
from a command that failed for the same reason. The check's `nativeBuildInputs`
contains Python and Dagu, but not Nix. The call in
[`src/devman_link/config.py`](../../../src/devman_link/config.py) requires
`nix-instantiate`. The user approved adding `pkgs.nix` to the check's inputs.
That addition made the targeted build pass. Remove it if the test suite no
longer invokes `nix-instantiate`.

The VM failure comes from [`nix/devman-cli.nix`](../../../nix/devman-cli.nix).
The wrapper supplies Dagu and watchexec, but C3 calls `git ls-tree` through
[`src/devman/central.py`](../../../src/devman/central.py). Adding `git` to the
wrapper removed the crash. The VM then reached the universal-pool check in
[`src/devman/doctor.py`](../../../src/devman/doctor.py). Its fixture in
[`nix/tests/dagu-service.nix`](../../../nix/tests/dagu-service.nix) creates no
`~/.config/devman/skills/writing`. The doctor check requires that pool entry
even when it finds no live skill surfaces. The user approved a minimal
`writing/SKILL.md` in the VM fixture. The next VM build passed. Keep that
fixture while doctor requires the shared skill pool.

Neither newly exposed failure required weakening a check. The first needed a
declared test tool. The second needed the VM to model a healthy shared pool.
The full devman gate passed after both changes.

## Linkman prerequisite and hook

Linkman's `nix flake check` exited 0 in 5 s before the hook. Rebuilding its
overlay check took 3 s, and rebuilding its package check took 6 s. After adding
`[publish] verify = ["nix", "flake", "check"]` with a 300 s timeout, the check
exited 0 in 6 s. `repoman doctor` exited 0. The hook was landed and pushed as
`a48d65a` on 2026-10-06. The timeout allows for an uncached build; the measured
rebuilds were shorter. These checks cover this host's x86_64-linux outputs.

## Decision and limits

[D29](DECISIONS.md) keeps O4 to the wrapper fix. Doctor still refuses loudly
if another environment removes `git` from PATH. A separate lane can define and
test a structured unavailable status later.

The two source changes landed as separate commits and reached devman origin at
`651af40`. The `./tools` entry remains only while `tools/cutover/` exists.
The fixture skill is test data, not a machine skill installation.

The successful gate proves the host's x86_64-linux flake checks. Nix omitted
aarch64-darwin, aarch64-linux, and x86_64-darwin as incompatible with this
host. This session did not install a new machine generation or start the
Linkman cutover.
