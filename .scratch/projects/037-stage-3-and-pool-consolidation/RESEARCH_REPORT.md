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
- Flora's normal shell fails before the input change at
  `config.cachix.enable`; its workspace gate passes when duplicate devman
  registration is disabled. The normal post-land gate remains open.
- PyGentic had the same missing git-hooks input and then a crates.io 403. The
  standard pre-commit input plus the explicit Cachix substitute warmed its
  store; the exact gate completed in 0.38 seconds.
- Inferference had a pre-existing unfree CUDA evaluation failure. Adding its
  existing required `allow_unfree: true` declaration to the Part E lane made
  the exact gate pass in 0.29 seconds after conversion.

These are recorded blockers, not reasons to alter unrelated project code.
