# Stage 3 and pool consolidation — Part E and Part A

Date: 2026-09-11

## Part E — `git+file:` inputs

### What was measured

The gate was `devenv shell -- true`. The timings below are wall-clock seconds
from `TIMEFMT='elapsed_seconds=%E'; time devenv shell -- true`.

| Repository | Before | After | Result |
|---|---:|---:|---|
| clinch | 4.56, configPath error | 0.43 | pass |
| fsdantic | 2.51, missing AgentFS CLI | 1.80, same blocker | held |
| inferference | 4.73, unfree CUDA | 0.29 | pass |
| flora | 1.44, config.cachix.enable | 0.30 in workspace with devman registration disabled | held |
| PyGentic | 0.65, missing pre-commit input | 0.38 | pass |

The baseline failures were recorded before the edits. The exact gate ran after
each input conversion. PyGentic and clinch needed the official devenv Cachix
substitute once to bypass crates.io HTTP 403 responses. The exact gates passed
from the warmed store.

The eight conversions are:

- clinch: shellij;
- fsdantic: shellij;
- inferference: repoman modules and shellij;
- flora: repoman modules, vendomat, and shellij;
- PyGentic: shellij.

`git+file:` honors `.gitignore`, so it excludes each input's `.devenv` cache.
The existing measurement remains 1448 ms to 149 ms for the large vendomat
input. No new 014 measurement was run.

### What changed

The changes are in these gitman lanes:

- `clinch:037-part-e-clinch` — published and landed;
- `PyGentic:037-part-e-PyGentic` — published and landed;
- `inferference:015-gemma-eval-and-library-pinning/037-part-e-inferference` — landed into its existing parent lane;
- `flora:037-part-e-flora` — saved and held because the normal shell still fails at `config.cachix.enable`;
- `fsdantic:037-part-e-fsdantic` — saved and held because its existing AgentFS source has no `cli/Cargo.toml`.

The plain-Git repositories were bootstrapped with gitman first. Their existing
dirty work was reconciled into separate adopted lanes. It was not mixed into
the Part E lanes.

The published lanes were tested in their isolated workspaces. Their original
checkout stayed on its pre-existing adopted lane, so the post-land timing is
the workspace timing in the table above.

The clinch and PyGentic shells also received the fleet-standard
`pre-commit-hooks` input. Inferference received its required
`allow_unfree: true` declaration. These changes fixed shell evaluation errors
that existed before the eight input conversions.

### What was decided

`git+file:` is the correct local development form for these inputs. It keeps
the working tree available and excludes ignored `.devenv` state. A pinned
remote tag remains preferable where the consumer does not need local changes.

`cliProvider = "store"` is a separate axis. It does not remove a `path:` input
copy. The fleet still has about 39 GB of standing `.devenv` state. The
previous maintain sweep measured 42%; this session did not delete or rerun it.

### Still open

Fsdantic needs its `vendor/agentfs` source to point to a tree containing
`cli/Cargo.toml`. Flora needs its normal shell gate repaired for the existing
`config.cachix.enable` evaluation error. Land those lanes only after their
normal exact gates pass.

## Part A — Claude settings survival

### What was measured

The test used lodestar. Its original regular file had SHA256
`22b20133f080318b7530e7e33128df7e16dbc290d178b89bbda14888379ac7f0`.

The normal `devman.link` reconciler ran from a shell entry. It promoted the
file to the central store and made the repository path a symlink. Claude Code
was then trusted in the repository and ran the controlled Bash print test.
After that run, `test -L` remained true and the central and repository hashes
matched.

### What changed

The central declaration is in the config lane
`037-part-a-lodestar-only`. It adds
`.claude/settings.local.json` as a per-project central link. The test checkout
used the fleet v0.5.1 input so the current `devman.link` option existed.
Lodestar is backburner-only with no groups. After the test, its temporary
registry entry was removed and the overlay was restored to
`devman.enable = lib.mkForce false`.

`CONCEPT.md` §13 item 1 now records the result. The central copy remains
per-project. The six other settings files should use the same shape; they
should not share one file because their allowlists contain project-specific
paths and commands.

### Still open

The six remaining files need a separate measured sweep. Keep one canonical
file per project because each allowlist is project-specific.

## Verification record

The devman repository checks completed after the edits:

- `devenv tasks run -v base:check` — pass;
- `devenv tasks run -v base:unit` — 520 passed;
- `devenv tasks run -v base:test` — pass, including the NixOS VM check.

The plain local command `devman doctor` uses the unmerged Part B default
state root and reports 1 project and 10 workflows. This is expected while
Part B is not deployed. With the deployed layout selected explicitly,
`devman --state ~/.local/share/devman doctor` reports 48 projects and 152
workflows. It reports the pre-existing flora, pytuin, daemon, watcher, and
vendomat findings, plus two existing repoman link findings; it reports no
lodestar entry and no Part A finding. The Part E held lanes remain open until
their normal shell gates pass.
