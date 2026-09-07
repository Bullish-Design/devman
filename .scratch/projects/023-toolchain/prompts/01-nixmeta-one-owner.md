Session root: ~/Documents/Projects/nix-meta

# Phase 1 — one owner per tool name, and one Python baseline

Context: an investigation in
`~/Documents/Projects/devman/.scratch/projects/023-toolchain/` found three tools
installed twice, with PATH order deciding which one runs, and three different
Python versions in play. This phase makes each name resolve to one thing.

Read first, all absolute paths:
- `~/Documents/Projects/devman/.scratch/projects/023-toolchain/PROBLEMS.md` (P3, P9)
- `~/Documents/Projects/devman/.scratch/projects/023-toolchain/RUNBOOK.md` Phase 1

## Measured facts. Do not re-derive.

- A login shell has no `gitman`, no `uv`, no `jj`, no `templateer`.
- `repoman` resolves to Home Manager's **0.7.0 on Python 3.12** in a login shell,
  and the shared toolchain venv's **0.7.1 on 3.13.13** inside any devenv. Your
  `rlist` / `rstatus` / `rsync` aliases get 0.7.0.
- Every devenv runs 3.13.14. `pyjutsu` ships `cp313-abi3`, which loads on 3.13
  and forward and **cannot** load on 3.12 — measured:
  `ImportError: _pyjutsu.abi3.so: undefined symbol: Py_GetConstantBorrowed`.
- `repoman/src/` reads no config file, so the `xdg.configFile."repoman/repoman.toml"`
  that `nix-terminal/modules/repoman.nix` writes is unread. Re-verify before deleting.

## The job, in order

1. `profiles/developer.nix`: add `uv` to the `nix-meta.developer.packages` default.

2. Same file, in the `users.${username}` block, add — LAST, so it can never
   shadow a Nix-managed binary:
   ```nix
   home.sessionPath = [ "${homeDir}/.local/share/repoman/venv/bin" ];
   ```
   This is the same venv RepoMan's devenv module already prepends inside a
   devenv. It adds no second copy of anything.

3. Only after 1 and 2 are applied and verified: set
   `programs.repoman.enable = false`. Keep the `rsync`/`rlist`/`rstatus` aliases —
   if disabling the module takes them, re-declare them in the terminal profile.

4. Record the baseline in a comment in `profiles/developer.nix`, and in
   `~/Documents/Projects/repoman/AGENTS.md`:
   > Python baseline: 3.13. Every first-party CLI, the shared toolchain and every
   > devenv target CPython 3.13. pyjutsu ships cp313-abi3, which cannot load on 3.12.

5. In `~/Documents/Projects/repoman/flake.nix`, move `packages.default` and the
   devShell from `python312Packages` to `python313Packages` (~lines 21, 28, 34, 87).
   After step 3 nothing installs this output, so it is cheap to fix now.

## Verification

```bash
sudo nixos-rebuild test --flake .#server     # test first, not switch
zsh -lic 'command -v uv gitman repoman'
zsh -lic 'type -a repoman'                   # exactly ONE line, the toolchain venv
zsh -lic 'repoman --version'                 # 0.7.1
cd ~/Documents/Projects/devman && devenv shell -- repoman doctor
cd ~/Documents/Projects/repoman && nix build .#default --no-link
```
Then `sudo nixos-rebuild switch --flake .#server`. Rollback is
`sudo nixos-rebuild --rollback`.

## Rules

- Do not decide between `pkgs.devenv` (2.1.2) and the `devenv v2.2` this flake
  pins and nothing installs. Ask the owner; moving ~60 devenvs is its own change.
- Do not touch `services.inferference-router`. It is up and correctly declared.

## Stop if

`zsh -lic 'command -v repoman'` finds nothing after step 3 — that means step 2
did not take, and you have removed the only `repoman` on the login PATH.
