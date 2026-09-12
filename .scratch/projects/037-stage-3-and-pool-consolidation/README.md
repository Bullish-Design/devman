# Stage 3 and pool consolidation — Part E and Part A

Date: 2026-09-11
Status update: 2026-09-11

## Part E — `git+file:` inputs

### What was measured

The gate was `devenv shell -- true`. The timings below are wall-clock seconds
from `TIMEFMT='elapsed_seconds=%E'; time devenv shell -- true`.

| Repository | Before | After | Result |
|---|---:|---:|---|
| clinch | 4.56, configPath error | 0.43 | pass |
| fsdantic | 2.51, missing AgentFS CLI | 1.80, same blocker | held |
| inferference | 4.73, unfree CUDA | 0.29 | pass |
| flora | 1.44, config.cachix.enable | 17.43 from the original checkout | pass |
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
- `flora:037-part-e-flora` — published, landed, and pushed after the normal gate passed;
- `fsdantic:037-part-e-fsdantic` — saved and held because its existing AgentFS source has no `cli/Cargo.toml`.

The plain-Git repositories were bootstrapped with gitman first. Their existing
dirty work was reconciled into separate adopted lanes. It was not mixed into
the Part E lanes.

The published lanes were tested in their isolated workspaces. Their original
checkout stayed on its pre-existing adopted lane, so the post-land timing is
the workspace timing in the table above, except for Flora. Flora was re-entered
from its original checkout after the lane landed.

Flora's old devman input was `50c4c2e`, which did not define `devman.link`. The
lane updated only the input declaration and the three requested local inputs to
the link-compatible revision
`73dcc41bbeccae88d3910850551ae3ddc005fedc`. The isolated compatibility gate
took 17.13 seconds. The exact normal gate after landing took 17.43 seconds and
passed. Flora's unrelated `devenv.lock` refresh remains held in
`adopted-11ceb219`; it was not included in the lane.

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
`cli/Cargo.toml`. The lane `037-part-e-fsdantic` is saved and held at
`61bc87d7cd2ec3fc8f3cbfbe4bf0ffbca8473fee`. Its fresh baseline artifact
`/tmp/devman-037-fsdantic-agentfs.OUt6j5/baseline.txt` records a 1.75-second
wall-clock failure before realization. The resolved source is
`/home/andrew/Documents/Projects/fsdantic/.context/agentfs-main`, and it has no
`cli/Cargo.toml`; a separate `/home/andrew/Documents/Projects/agentfs`
checkout does. The repository owner must choose the approved AgentFS source or
repair the machine-local `vendor/agentfs` link. The lane must stay held until
that decision exists.

Flora is no longer open. Its Part E lane landed as
`56c3f4c9af0dc18d8dc8fd6e450575afbe9bc0c6` and was pushed to `origin/main`.
The original checkout passed a fresh `devenv shell -- true` recheck on
2026-09-12 in 424 ms. Its existing devman pin
`73dcc41bbeccae88d3910850551ae3ddc005fedc` is already link-compatible, so no
new Flora configuration change was needed. The held lock refresh remains in
the unrelated lane `adopted-11ceb219`; a pre-existing promoted-file backup is
held separately in `adopted-53eb515c`. Neither lane was landed.

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

Four of the six remaining projects were promoted through separate central
declarations and normal shell entry. Each source remains a symlink to its own
canonical file, and the SHA256 values match:

| Repository | Gate | SHA256 | Result |
|---|---:|---|---|
| nix-secrets | 0.43 s | `5fe5e9ccbe7e0d0adcc94ab05bca3a3c721756f88ad128cafaa321e05a48dde2` | landed |
| flora | 14.84 s | `a371b52ca003601520c6cd935956b3db28f4b331217d389aff305ebc633fc38b` | landed |
| image-gen-pipeline | 7.04 s | `4d79ca941d76055102cc1b8d851868278c5850e17512ec3991c3eadc11fabb00` | landed; config restored disabled |
| fleetman (archive) | 11.05 s | `80b4b562f7773ee2a10f3b50a89aaf2d6cba86faafc803dc13efd597e7901e68` | landed |

The central declarations and canonical files are landed in the central
checkout's `main` at `c78b3052e61a357108a539ab8c114e694991ee0a`. That checkout
has no remote, so there was no push. The lanes were:

- `037-claude-nix-secrets` plus its canonical-file follow-up
  `037-claude-nix-secrets-settings-file`;
- `037-claude-flora`;
- `037-claude-image-gen-pipeline`;
- `037-claude-fleetman`.

Image-Gen required a temporary `devman.enable = true` shell entry because its
normal overlay keeps it disabled. That entry registered its real repository and
materialized its central agent surface. The overlay is restored to
`lib.mkForce false`. The generated agent files and the pre-existing Flora local
ignore stay in the held central lane `037-central-settings-gate-2` at
`879eccf870a0af63a3b177be1e4c3cd0e5470772`; they were not landed. The same
temporary entry exposed Image-Gen's existing real-directory
`.claude/skills` drift. The reconciler refused to overwrite it because both
sides require review.

### Still open

Two requested projects could not be promoted safely:

- `nix-meta` has a regular settings file, but no `devenv.nix` or `devenv.yaml`.
  `devenv shell -- true` refused in 0.05 seconds with `File devenv.nix does not
  exist`. There is no normal shell entry through which the reconciler can run.
- `devman` has no `.claude/settings.local.json` source file. The settings file
  under the parent `Projects/.claude` belongs to the parent directory, not to
  this repository. No blank file or shared substitute was created.

These are source and shell blockers, not permission-survival failures. The
lodestar test already settled that question, so the Claude permission test was
not repeated.

## Verification record

The devman repository checks completed after the edits:

- `devenv tasks run -v base:check` — pass;
- `devenv tasks run -v base:unit` — 520 passed;
- `devenv tasks run -v base:test` — pass, including the NixOS VM check.

Before the deployment attempt, the plain local command `devman doctor` used
the unmerged Part B default state root and reported 1 project and 10
workflows. With the deployed layout selected explicitly,
`devenv shell -- devman --state ~/.local/share/devman doctor` reports 50
projects and 158 workflows. Flora drift and the Pytuin local-source pin are
resolved. The local-source check now passes with six libraries feeding 59
inputs, none dirty and no pin behind its source.

The final doctor has three findings, all link drift: Image-Gen's
`.claude/skills`, and Repoman's `.agents` and `.claude/skills`. The Repoman
findings pre-date this work. The Image-Gen finding is held for review as
described above. The daemon shell and watcher lines are informational. There
is no lodestar residue. No registry directory move and no §6.2a change was
made.

PR #161 is merged at
`73dcc41bbeccae88d3910850551ae3ddc005fedc`. The Part B release is now
available as [devman 0.5.2](https://github.com/Bullish-Design/devman/releases/tag/v0.5.2)
at tag commit `ec6710aaa59cd1f73ccc78858623d401a20221e0`. The exact release
build passed:

```text
devenv shell -- nix build --no-link \
  'git+file:///home/andrew/Documents/Projects/devman?ref=v0.5.2#devman'
```

The machine pin used the isolated lane `037-deploy-devman-0.5.2`. That lane
landed and was pushed in `nix-meta` as
`8422571f145a80782c22f9d97422d8d45c937fb1`. Its full machine-flake check
passed before activation.

The system was still
`v3lhkgv4r1lirf196sxm59nq5rpqyz86-nixos-system-server-26.11.20260705.d407951`
with devman 0.5.1 before the switch. The normal switch command reached the
system build but failed before activation because this session cannot elevate:
`sudo -n true` reports that a password is required, and updating
`/nix/var/nix/profiles/system` returned `Permission denied`. The dry activation
also required system authorization. No system generation changed.

The requested `devman-resync`, representative re-entry, plain doctor check,
and Dagu post-deployment comparison remain pending until that switch is run
with local administrator authentication. The deployed-layout doctor remains
stable at 50 projects and 158 workflows with the same three known link-drift
findings. The current pre-deployment state-root doctor sees 3 projects and 16
workflows, including the temporary held `flora-037-part-e` workspace entry;
that is not deployment evidence. Do not use `doctor --prune` on the held
workspace.

PR #162 is merged at `888ff1d09f7ebbe28e1bdeec1867dbdb4653d98d`. PR #163 is
merged at `67a0a0325343ee564f72f15358ccc11f8ac8b189`.
