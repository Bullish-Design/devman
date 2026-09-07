# Inventory: what owns what, measured 2026-09-06

Host: `server`, NixOS 26.11.20260705.d407951, x86_64-linux, user `andrew`.
System closure: `/nix/store/j42qw2ixzam8pazssgkr78k87g9929kx-nixos-system-server-...`

## 1. Ownership layers, top to bottom

| Layer | Config file | What it owns today | Reaches a shell | Reaches a Dagu step | Reaches `import` |
|---|---|---|---|---|---|
| NixOS system | `nix-meta/machines/server.nix` + `profiles/*` | `git`, `nix`, `dagu`, `devman` CLI, nix-ld | yes | yes | no |
| Home Manager (via `profiles/developer.nix`) | `nix-meta/profiles/developer.nix` | `python3` 3.13.13, `gh`, `nodejs`, `devenv`, `ruff`, `repoman` 0.7.0, `ty`, `atuin`, `zsh` | yes | yes | only nixpkgs modules |
| `nix profile` (imperative) | none — mutable state | `devenv` 2.1.2, `act` | yes, **first on PATH** | yes, **first on PATH** | no |
| Shell startup | `~/.zshrc`, `~/.zprofile` (HM-generated, store symlinks) | aliases, direnv hook, atuin. **No PATH edits.** | yes | no | no |
| RepoMan machine toolchain | `repoman/repoman.lock` -> `~/.local/share/repoman/venv` | `gitman` 0.6.0, `pyjutsu` 0.20.0, `repoman` 0.7.1, `copyroom`, `docman`, `copier` | **no** | **no** | **no** |
| RepoMan devenv module | `repoman/modules/devenv.nix` | prepends the toolchain venv `bin` to `PATH` inside an adopting devenv | inside `devenv shell` only | inside `devenv shell --` only | **no** |
| Per-repository devenv | `<repo>/devenv.nix` | nix packages, `uv`, a project venv, tasks, `env.*` | inside `devenv shell` only | inside `devenv shell --` only | yes, for that repo's own deps |
| Project `uv` venv | `<repo>/uv.lock` -> `.devenv/state/venv` | that repo's Python dependency tree | inside `devenv shell` | inside `devenv shell --` | yes |
| `uv tool` (imperative) | `~/.local/share/uv/tools/*` | `gitman` (editable), `git-filter-repo` | **no** (`~/.local/bin` is not on PATH) | no | no |
| Stray `.pth` | `.devenv/state/venv/.../_agent_factory_spike_siblings.pth` | injects four sibling repos into `sys.path` | inside devman's devenv | inside devman's devenv | **yes — undeclared** |
| Dagu daemon | `nix-meta/profiles/devman.nix` -> devman `nixosModules.default` | the plane, `DAGU_HOME`, five queues, `env_passthrough_prefixes: [DEVMAN_]` | n/a | yes | no |
| Workflow params | `groups/*/workflows/*.yaml` | `GPU_LLM_BASE_URL`, `GPU_LLM_MODEL`, `TEMPLATEER_PATH`, `TEMPLATEER_TEMPLATE_PATH` | no | yes | no |
| Inference | `nix-meta/machines/server.nix` -> `services.inferference-router` (module from the pinned `inferference` input); resident set in `~/.config/inferference/placement.yaml` (`port: 8100`, `model: gemma`) | the local OpenAI-compatible endpoint | n/a | over TCP | n/a |

## 2. Command resolution, measured

`command -v` in a login shell (`zsh -lic`):

| Command | Resolves to | Manager |
|---|---|---|
| `python` / `python3` | `/etc/profiles/per-user/andrew/bin/python3` (3.13.13) | Home Manager |
| `repoman` | `/etc/profiles/per-user/andrew/bin/repoman` -> **0.7.0** | Home Manager |
| `devenv` | `/home/andrew/.nix-profile/bin/devenv` -> **2.1.2** | `nix profile`, imperative |
| `dagu` | `/run/current-system/sw/bin/dagu` -> 2.15.0 | NixOS |
| `devman` | `/run/current-system/sw/bin/devman` | NixOS |
| `git`, `ruff` | system / Home Manager | Nix |
| `gitman` | **MISSING** | — |
| `uv` | **MISSING** | — |
| `jj` | **MISSING** (by design; gitman uses `pyjutsu`) | — |
| `templateer` | **MISSING** | — |

Inside `devenv shell` at `~/Documents/Projects/devman`:

| Command | Resolves to | Manager |
|---|---|---|
| `python3` | `.devenv/state/venv/bin/python3` (**3.13.14**) | devenv/uv |
| `gitman` | `~/.local/share/repoman/venv/bin/gitman` (shebang: **3.13.13**) | RepoMan toolchain |
| `repoman` | `~/.local/share/repoman/venv/bin/repoman` -> **0.7.1** | RepoMan toolchain |
| `uv` | `/nix/store/...-uv-0.11.25/bin/uv` | devenv |
| `templateer` | **MISSING** | — |

## 3. Import resolution, measured

| Environment | interpreter | `pyjutsu` | `gitman` | `templateer` |
|---|---|---|---|---|
| login shell | HM 3.13.13 | FAIL | FAIL | FAIL |
| devman `devenv shell` | devenv venv 3.13.14 | **FAIL** | **FAIL** | OK — through the stray `.pth` |
| Dagu step, raw | HM 3.13.13 | FAIL | FAIL | FAIL |
| Dagu step, `devenv shell --` | devenv venv 3.13.14 | **FAIL** | FAIL | OK — stray `.pth` |
| toolchain venv python | 3.13.13 | OK 0.20.0 | OK 0.6.0 | FAIL |
| gitman's own devenv | its uv venv | OK (own `uv.lock`) | OK editable | FAIL |

`templateer` and `pydantic` and `yaml` resolve in devman's devenv only through
`_agent_factory_spike_siblings.pth`, which no file in any repository writes. It
is residue from project 005. It is inside `.devenv/`, which is gitignored, so
it is invisible to every check.

## 4. Version pinning, by source

| Package | Source of record | Form | Reproducible |
|---|---|---|---|
| `pyjutsu` in gitman's `uv.lock` | GitHub release wheel URL + `sha256:06f669…` | exact + hashed | **yes** |
| `pyjutsu` in `repoman.lock` | `wheel:pyjutsu>=0.20.0` via `UV_FIND_LINKS` | **floor, not a pin** | no — resolves to whatever the wheelhouse holds |
| `gitman` in `repoman.lock` | `path:/home/andrew/Documents/Projects/gitman`, installed `--editable` | **live working tree** | no |
| `repoman`, `copyroom`, `docman` | same `path:` editable form | live working tree | no |
| `templateer` | `PYTHONPATH=$TEMPLATEER_PATH/src` in a workflow param | **absolute path, no version** | no |
| `repoman` 0.7.0 (Home Manager) | nixpkgs-built derivation, python 3.12 | pinned by `flake.lock` | yes |
| `devenv` 2.1.2 | `nix profile install nixpkgs#devenv` | **imperative** | no |
| Dagu 2.15.0 | `devman/nix/dagu.nix` | pinned | yes |
| shellij, repoman, atuout, nix-paseo, nix-terminal inputs | `git+file:///home/andrew/Documents/Projects/...` | **reads the dirty working tree** | no |

Measured: a `devenv shell` in devman prints
`warning: Git tree '/home/andrew/Documents/Projects/repoman' is dirty`.

## 5. Duplicate installs, measured

Eight copies of `pyjutsu`'s 20 MB native extension exist on disk:

```
86,615,960  ~/Documents/Projects/pyjutsu/python/pyjutsu/_pyjutsu.abi3.so   (debug, built)
19,964,296  ~/.local/share/repoman/venv/.../pyjutsu/_pyjutsu.abi3.so
19,964,296  ~/.local/share/uv/tools/gitman/.../pyjutsu/_pyjutsu.abi3.so
19,964,296  ~/Documents/Projects/gitman/.devenv/state/venv/...
18,554,896  ~/Documents/Projects/gitman/.devenv/test-state/venv/...
18,554,896  ~/Documents/Projects/gitman/.worktrees/loci-adoption-fixes/...
17,028,624  ~/Documents/Projects/repoman/tests/consumer-example/...
18,304,944  ~/Documents/Projects/.scratch/projects/019-millrace/spike/...
```

Three different builds are represented (19.9 MB, 18.5 MB, 17.0 MB). Supporting
state: `~/.cache/uv` is 43 GB; `pyjutsu/target` is 6.9 GB.

## 6. Duplicate ownership, by name

| Name | Copy A | Copy B | Which one wins |
|---|---|---|---|
| `repoman` | Home Manager 0.7.0 (python 3.12) | toolchain venv 0.7.1 (python 3.13) | login shell -> A; inside a devenv -> B. **PATH order decides.** |
| `devenv` | `nix profile` 2.1.2 | Home Manager `pkgs.devenv` 2.1.2 | `~/.nix-profile` is earlier -> the imperative one. Same version today, by luck. |
| `gitman` | toolchain venv (editable) | `uv tool` at `~/.local/bin/gitman` (editable) | toolchain venv, because `~/.local/bin` is not on `PATH`. Dormant trap. |
| `python3` | HM 3.13.13 | devenv venv 3.13.14 | context-dependent — this is the defect in §3 |
| `pyjutsu` | 8 copies | | whichever interpreter is running |
