# 045 — Personal toolbelt cutover

Date: 2026-10-13.

This project moves personal development tools to the canonical `nix-meta`
machine config. It removes personal tool pins and stale config from project
repositories while keeping project-owned tasks and tool contracts.

See `ISSUES.md` for findings that change the cleanup scope.

## Step 2: install the machine toolbelt

`nix-meta` is the canonical machine config for the personal toolbelt. It now
pins RepoMan `v0.14.1`, LinkMan `v0.1.1`, Mancore `v0.1.0`, and Testee `v0.7.0`
in `flake.nix` and `flake.lock`. The developer Home Manager profile installs
RepoMan, LinkMan, Testee, and Gitman `0.13.1`; CopyRoom remains in Vendomat's
shared command closure. Testee project pins remain valid and stay in place
where the project's own tests use Testee's Nix module and checks.

The built system publishes these stable module paths:

- `/run/current-system/sw/share/repoman/module/devenv.nix`
- `/run/current-system/sw/share/devman/link-module.nix`
- `/run/current-system/sw/share/vendomat/consumer-module.nix`

The RepoMan module path resolves to a regular file in the built system. The
developer PATH uses a filtered Vendomat command directory. It excludes the
Vendomat RepoMan and Gitman entrypoints because Home Manager installs those
tools directly, and it omits archived DocMan. CopyRoom remains available from
Vendomat. The AgentMan service still uses the original Vendomat closure path.

Verification on 2026-10-13:

- The final `nix build --no-link --print-out-paths .#nixosConfigurations.server.config.system.build.toplevel`
  passed and returned
  `/nix/store/8qniji16qglv6x43xcki973xnymdg9xp-nixos-system-server-26.11.20260705.d407951`.
- Nix evaluation listed `gitman-0.13.1`, `repoman-0.14.1`, `linkman-0.1.1`,
  and `testee-0.7.0` in the developer Home Manager packages.
- The built system contains the RepoMan, devman, and Vendomat module paths
  above. The generated filtered command path is
  `/nix/store/hhz4p4fbwlxi4fdgksx2wpzj3yhv1b3f-developer-toolchain-commands/bin`.
- `git diff --check` passed in `nix-meta`.

LinkMan's upstream Nix package omits its declared Mancore runtime dependency.
The machine profile adds the pinned Mancore package to LinkMan during package
construction. The full system build succeeds with that adjustment. This is a
recorded upstream packaging issue, not a blocked install.

## 2026-10-13: nix-terminal owner audit

The nix-meta flake makes nix-terminal's DevMan and RepoMan inputs follow the
canonical root inputs. `nix flake lock` removed the old nix-terminal DevMan and
RepoMan lock nodes and their unused nested inputs. Nix-terminal's DevMan
integration remains disabled by `profiles/terminal.nix`; Home Manager evaluation
shows no second DevMan package. The server still exposes the current DevMan
package from its NixOS module.

The developer profile no longer imports nix-terminal's RepoMan Home Manager
module or exposes its inactive `programs.repoman` options. No RepoMan accounts,
global TOML, or activation were active in nix-meta. RepoMan v0.14.1 has no
global `repoman.toml` reader. The active `rsync`, `rlist`, and `rstatus` aliases
remain and call the directly installed RepoMan v0.14.1 package.

The complete server build passed after this change and returned
`/nix/store/1q0m9bdlxqc64bby68pdlajfh66xnd8q-nixos-system-server-26.11.20260705.d407951`.
Evaluation confirmed one Home Manager RepoMan package, no generated
`repoman/repoman.toml`, no `repomanSetup` activation, and all three aliases.

## Vendomat input alignment

The final `nix-meta` change makes Vendomat's DevMan and RepoMan inputs follow
the canonical root inputs. The lock no longer contains duplicate
`devman_2` or `repoman_2` nodes. RepoMan remains a source-only input for
Vendomat's builder. The final system build passed and returned the store path
above. The built Vendomat manifest uses RepoMan 0.14.1 and the matching DevMan
renderer and runtime.

Vendomat's older RepoMan and Gitman commands remain filtered from interactive
PATH. Its DevMan runtime stays inside Vendomat's plane closure. The active
Vendomat generation is still generation 4; no plane plan or update was run.

## Activation

The system build is ready, but the live system still points to
`/nix/store/bqm07rlvmdavvpm52hsarww8x22q520r-nixos-system-server-26.11.20260705.d407951`.
Noninteractive sudo authentication was unavailable, so the system switch and
Vendomat plane update were not run. To activate the built configuration, run:

```sh
sudo nixos-rebuild switch --flake /home/andrew/Documents/Projects/nix-meta#server
```
