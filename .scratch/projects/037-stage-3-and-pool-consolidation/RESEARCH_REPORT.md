# Research report — 2026-09-11

## Clinch shell gate

The Part E gate is `devenv shell -- true` in the `clinch` Part E workspace.
The input change converts `shellij` from `path:` to `git+file:`.

The first gate failed during Nix evaluation. The pinned `devenv` module read
`cfg.configPath` from its fallback `git-hooks` module, although no git-hooks
input existed. The local module source showed the failing interpolation at
`src/modules/integrations/git-hooks.nix:126`.

The durable fix follows the fleet recipe: declare
`github:cachix/pre-commit-hooks.nix` in `devenv.yaml`. The temporary local
`git-hooks.configPath` and disablement workaround was removed. The shell then
reached realization, but crates.io returned HTTP 403 for
`astral-tokio-tar-0.5.6.tar.gz`.

The successful proof used the official devenv Cachix substitute explicitly:

```text
devenv shell --nix-option extra-substituters https://devenv.cachix.org \
  --nix-option extra-trusted-public-keys \
  devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw= -- true
```

It completed in 8.79 seconds. The exact, unmodified gate then completed in
0.43 seconds from the warmed store. The lane also records `cachix.pull = [
"devenv" ]` in `devenv.nix` so the normal shell has the intended cache route.

Upstream issue [devenv #2433](https://github.com/cachix/devenv/issues/2433)
records the git-hooks shell regression. The current upstream integration is
documented in [git-hooks.nix](https://github.com/cachix/devenv/blob/main/src/modules/integrations/git-hooks.nix).

## Other shell blockers found

The exact baseline and post-conversion gates also exposed existing problems:

- fsdantic cannot evaluate its shell because
  `/home/andrew/Documents/Projects/vendor/agentfs` resolves to a reference tree
  without `cli/Cargo.toml`. The Part E lane only changes the shellij input.
- Flora's initial normal shell failed before the input change at
  `config.cachix.enable`. The lane updated its old devman input to the
  link-compatible revision `73dcc41bbeccae88d3910850551ae3ddc005fedc`. The
  exact normal gate from the original checkout passed after landing in 17.43
  seconds. An unrelated `devenv.lock` refresh remains held.
- PyGentic had the same missing git-hooks input and then a crates.io 403. The
  standard pre-commit input plus the explicit Cachix substitute warmed its
  store; the exact gate completed in 0.38 seconds.
- Inferference had a pre-existing unfree CUDA evaluation failure. Adding its
  existing required `allow_unfree: true` declaration to the Part E lane made
  the exact gate pass in 0.29 seconds after conversion.

These are recorded blockers, not reasons to alter unrelated project code.

## Follow-up — 2026-09-11

The fsdantic lane remains held. Its fresh baseline artifact records a
1.75-second wall-clock evaluation failure. The source resolved through
`/home/andrew/Documents/Projects/vendor/agentfs` is the frozen
`fsdantic/.context/agentfs-main` reference tree, which has no
`cli/Cargo.toml`. The separate `Projects/agentfs` checkout has that file, but
the lane does not select it because the repository owner has not approved that
source. The exact blocker remains unchanged after the `shellij` conversion.

The Pytuin local-source finding is closed in two landed Gitman changes. The
`atuout` lock entry moved from `d9b69592ed0e1560bf689d3e018ff57b56986240` to
`3acdf1e9e85cf9acd7ea714202974350a1552e58`. The normal original-checkout gate
passed in 0.50 seconds. Pytuin main is synchronized at
`0d09c06d7e270c7d26b32c14062efe149fa8480c`.

Four remaining Claude settings files are now separate central canonical files.
The source symlinks and central SHA256 values match for nix-secrets, Flora,
Image-Gen, and archived fleetman. Nix-meta has no normal devenv shell, and
devman has no source settings file, so neither received a declaration or a
blank replacement. The lodestar permission test was not repeated.

The deployed-layout doctor now reports 50 projects and 158 workflows. Flora
and Pytuin findings are gone. Three link-drift findings remain: Image-Gen's
`.claude/skills`, plus the pre-existing Repoman `.agents` and
`.claude/skills` drift. The temporary Image-Gen shell left a real registry
entry and generated central agent files; its overlay is backburner-disabled,
and the generated files remain held in the central lane
`037-central-settings-gate-2` for a later owner decision.

## Deployment handoff — 2026-09-12

PR #161 is merged at `73dcc41bbeccae88d3910850551ae3ddc005fedc`. The release
object for the existing `v0.5.2` tag was created at
https://github.com/Bullish-Design/devman/releases/tag/v0.5.2. The tag points to
`ec6710aaa59cd1f73ccc78858623d401a20221e0`. The exact package build passed:

```text
devenv shell -- nix build --no-link \
  'git+file:///home/andrew/Documents/Projects/devman?ref=v0.5.2#devman'
```

The machine pin was isolated in the `nix-meta` workspace lane
`037-deploy-devman-0.5.2`. The full machine-flake check passed. The lane then
landed and `nix-meta` `main` was pushed at
`8422571f145a80782c22f9d97422d8d45c937fb1`.

The normal switch command was:

```text
NO_SHELLIJ=1 devenv shell -- nixos-rebuild switch \
  --flake path:/home/andrew/Documents/Projects/nix-meta/.worktrees/037-deploy-devman-0.5.2#server \
  --no-write-lock-file --show-trace
```

It built the target but failed before activation while trying to update
`/nix/var/nix/profiles/system`: the unprivileged session received
`Permission denied`. `sudo -n true` confirmed that a password is required.
The old system generation and devman 0.5.1 binary remain active. The dry
activation also failed at its `systemd-run` authorization step. No
`devman-resync` was run because the release is not active yet.

The explicit pre-deployment doctor remained at 50 projects and 158 workflows.
It retained the known Image-Gen `.claude/skills` drift and the pre-existing
Repoman `.agents` and `.claude/skills` drift. The plain doctor saw the small
pre-deployment state root at 3 projects and 16 workflows. It also reported a
new `flora-037-part-e` workspace entry created by the held-lane shell
inspection. That entry was not pruned because its workspace still exists.

The original Flora checkout passed a fresh normal shell recheck in 424 ms. Its
existing `73dcc41` devman input is already compatible with `devman.link`, so no
new Flora fix was required. The unrelated lock-refresh lane
`adopted-11ceb219` and the pre-existing promoted-file backup lane
`adopted-53eb515c` remain held.

## Deployment handoff follow-up — 2026-09-12

The `nix-meta` `main` checkout was moved back to its clean main content before
the switch. Commit `8422571f145a80782c22f9d97422d8d45c937fb1` pins devman
0.5.2. After the switch, the system binary resolved to
`/nix/store/djih27x5rnik61zjyhr5zcfmsaq9amlc-devman-0.5.2/bin/devman`.
`dagu.service` and `devman-watch.service` were active after restarting at
09:53:20 EDT.

The released script was run with:

```text
NO_SHELLIJ=1 devenv shell -- devman-resync
```

The command exited 1. It read the old registry's 50 metadata entries and
re-entered their recorded repositories. The new state root ended with 4
projects and 19 workflows. The explicit old-layout doctor remained at 50
projects and 158 workflows.

The state split exposed a compatibility condition that the pre-deployment
plan did not measure. Forty-five registered projects still import devman
`v0.5.1`. `paloma-text-pipeline` and `talkee` import still older revisions.
Those modules generate shell hooks without the new `stateDir` argument, so a
normal shell entry cannot populate `~/.local/state/devman`. The four projects
that did populate it are `devman`, `flora`, `pydantree`, and the held
`flora-037-part-e` workspace.

The old Dagu projection remains safe and live. Its `dags/` directory contains
164 symlinks. Dagu resolves 161 valid names and warns on three broken `my-ai`
links. The held Flora workspace contributes three valid names above the normal
158-workflow projection. No old registry entry or DAG link was deleted.

The resync also recorded independent shell blockers. SecretSpec refused
access without a reason in `browsee`, `fornix`, `mypi-agent`, `templateer_v2`,
`tyo3`, and `zelligate`. RepoMan reported an unset store toolchain in
`image-gen-pipeline`, `llgym`, `nix-desktop`, `nix-paseo`, and `talkee`.
These blockers were not bypassed.

The deployment handoff therefore remains open. The safe next step is to
refresh the registered consumer devman inputs to v0.5.2 in isolated gitman
lanes, with the normal `devenv shell -- true` gate for each lane. The old
registry must remain until the new state-root counts match the old projection.
