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
