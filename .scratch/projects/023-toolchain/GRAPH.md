# Dependency and propagation graphs

## 1. Package dependency graph

```
                 nixpkgs (nix-meta flake.lock)
                        |
        +---------------+----------------+
        |                                |
   NixOS system                    Home Manager
   git, nix, dagu 2.15,            python3 3.13.13, gh, nodejs,
   devman CLI, nix-ld              devenv, ruff, ty, repoman 0.7.0
        |                                |
        +---------------+----------------+
                        |
                   PATH of every process
                        |
                        |          nix profile (imperative): devenv 2.1.2  <-- shadows HM
                        |
        +---------------+---------------------------+
        |                                           |
  Dagu daemon                              interactive zsh
  (systemd --user)                         (no gitman, no uv, no jj)
        |
   workflow step  --(re-derives env from /etc/profile)-->  step shell
        |
   `devenv shell -- ...`
        |
   +----+--------------------------------+
   |                                     |
 devenv nix packages               project uv venv
 uv 0.11.25, ruff, dagu,           python 3.13.14
 hyperfine, watchexec,             devman deps
 codex, claude-code
   |
 repoman devenv module
   |  prepends $REPOMAN_TOOLCHAIN_VENV/bin to PATH
   v
 ~/.local/share/repoman/venv   (python 3.13.13, uv 0.9.18)
   gitman 0.6.0  --editable--> ~/Documents/Projects/gitman/src
   pyjutsu 0.20.0 (wheel, GitHub release, native .so)
   repoman 0.7.1 --editable--> ~/Documents/Projects/repoman/src
   copyroom, docman, copier

 templateer 0.3.0
   NOT in any of the above.
   Reaches devman two ways today, both undeclared or path-bound:
     (a) `_agent_factory_spike_siblings.pth` in devman's devenv venv (residue)
     (b) `PYTHONPATH=$TEMPLATEER_PATH/src` + `uv run --project $TEMPLATEER_PATH`
         in groups/changelog/workflows/changelog.yaml
```

The critical edge is the one that does not exist: the toolchain venv is joined
to a devenv by `PATH` only. `PATH` carries console scripts. `sys.path` is set
by the interpreter that starts. `devenv shell -- python3` starts the *project*
interpreter, so the toolchain venv's libraries are invisible to it.

## 2. Environment propagation, measured boundary by boundary

```
systemd --user manager
  |  Environment= lines in dagu.service only:
  |  DAGU_HOME, PATH (no toolchain venv, no uv), LOCALE_ARCHIVE, TZDIR
  |  UnsetEnvironment=SHELL
  v
Dagu daemon (pid 1234, cwd=/home/andrew)
  |  env: DAGU_HOME, PATH, HOME, XDG_RUNTIME_DIR, NIX_*, locale. Nothing else.
  |  config: env_passthrough_prefixes: [DEVMAN_]
  |  => only DEVMAN_* survives from the process that ran `dagu enqueue`
  v
step shell  (default_shell = bash-interactive from config.yaml)
  |  MEASURED SURPRISE: the step env is NOT the daemon env.
  |  It contains __HM_SESS_VARS_SOURCED, __NIXOS_SET_ENVIRONMENT_DONE,
  |  FZF_*, EDITOR, PAGER, NIXBUILD_* — the step shell re-derives the
  |  environment from /etc/profile + the Home Manager session vars.
  |  PATH becomes: /run/wrappers/bin:~/.nix-profile/bin:...:/etc/profiles/per-user/andrew/bin:...
  |  Result: python3 = HM 3.13.13; gitman MISSING; uv MISSING; jj MISSING.
  v
`devenv shell -- ...`
  |  PATH gains, in order:
  |    .devenv/state/venv/bin        <- project venv, FIRST
  |    ~/.local/share/repoman/venv/bin  <- toolchain venv, SECOND
  |    nix store paths for uv, ruff, dagu, git, ...
  |  VIRTUAL_ENV = .devenv/state/venv
  |  PYTHONPATH = /nix/store/...-sitecustomize.py   (devenv's own, single entry)
  |  REPOMAN_TOOLCHAIN_VENV = ~/.local/share/repoman/venv
  |  GPU_LLM_BASE_URL, GPU_LLM_MODEL from devenv.nix env.*
  v
  `gitman ...`   -> toolchain venv script, shebang pins its own 3.13.13. WORKS.
  `python3 -c 'import pyjutsu'` -> project venv 3.13.14. FAILS.
```

### Variable survival table

| Variable | daemon | raw step | inside `devenv shell --` |
|---|---|---|---|
| `PATH` | service-defined | re-derived from profile | devenv-prefixed |
| `DEVMAN_PROJECT_DIR` | unset | set, if the enqueuer exported it | set |
| `GPU_LLM_BASE_URL` | unset | only from DAG `params:` | set by devman's `devenv.nix` |
| `GPU_LLM_MODEL` | unset | only from DAG `params:` | set by devman's `devenv.nix` |
| `VIRTUAL_ENV` | unset | unset | project venv |
| `PYTHONPATH` | unset | unset | devenv `sitecustomize` only |
| `REPOMAN_TOOLCHAIN_VENV` | unset | unset | set |
| `UV_FIND_LINKS` | unset | unset | **unset** (only repoman's own devenv sets it) |

### Two propagation facts worth keeping

1. `env_passthrough_prefixes: [DEVMAN_]` means a workflow cannot inherit
   `GPU_LLM_*` from the enqueuing shell. Declaring them as `params:` is the
   only mechanism that works. The changelog workflow does this correctly.
2. `log_dir: ${DEVMAN_PROJECT_DIR}/...` in `base.yaml` fails **loudly** when
   the variable is unset: `failed to create/open log file
   ${DEVMAN_PROJECT_DIR}/.devman/...: no such file or directory`. Measured. The
   run records `Failed`. This is the correct behaviour and it is worth keeping.
   (Counter-example on the same machine: a root-owned file literally named
   `$h` sits in `/home/andrew`, left by some unit that expanded `%h` wrongly.)
