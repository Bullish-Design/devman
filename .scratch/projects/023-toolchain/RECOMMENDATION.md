# Recommended target architecture

> **Superseded in part by `TARGET.md` (2026-09-06).** Measurement showed the
> vendomat wheelhouse is two mechanical steps from producing the published
> artifact, so "Face A was retired correctly" is too strong. Read `TARGET.md`
> before acting on the Face A / `[tool.uv.sources]` guidance here.


## The rule, in one line

**A console script is a property of the machine. An import is a property of the
repository that imports it.**

Everything below follows from that line and from the measurement that produced
it: `PATH` carries console scripts, `sys.path` carries imports, and the shared
toolchain venv is joined to a devenv by `PATH` alone (M3, M4).

## Architecture E, with the boundary stated

| Category | Owner | Where it is declared | Example |
|---|---|---|---|
| System binaries and build tools | NixOS + Home Manager | `nix-meta/profiles/*` | `git`, `nix`, `dagu`, `devman`, `devenv`, `uv`, `python3`, `gh`, `node`, `ruff`, `maturin`, `rustc` |
| Cross-repository **CLIs** | RepoMan shared toolchain venv | `repoman/repoman.lock` | `gitman`, `repoman`, `copyroom`, `docman` |
| Project **libraries**, including native extensions | the repository's own `uv.lock` | `<repo>/pyproject.toml` | `pyjutsu`, `templateer`, `pydantic` |
| Build-only dependencies | that repository's `devenv.nix` | `packages = [...]` | `maturin`, `pytest`, `hyperfine` |
| Automation-only dependencies | the group's declared contract | group README + adopter's `pyproject.toml` | `templateer` for the `changelog` group |
| Local services | NixOS user services | `nix-meta/profiles/*`, `nix-meta/machines/server.nix` | `dagu`, `inferference-router` |
| Disposable experiments | `uv run --with`, or a scratch devenv | nothing persistent | one-off scripts |

The shared toolchain venv **stays**, and its job narrows: it is the machine's
CLI shelf, and it is never a source of imports. That is what it is already good
at, and the only thing it can be good at.

## The five changes

### R1 — a workflow may call a CLI; it may not import a manager's library

`changelog.yaml` currently does `devenv shell -- python3 - <<PYEOF ... import
pyjutsu`. That is the broken line. Two ways to fix it, and the investigation
found the first is not yet available:

- **R1a (preferred): add `gitman log` to gitman.** Measured: `gitman` has no
  `log` command, so the direct `pyjutsu` import **is** justified by a real API
  gap today. A `gitman log --revset '<a>..<b>' --json` emitting change id and
  description would close it, and the workflow would then need no interpreter of
  its own at all — just a console script that carries its own shebang. This is
  the cheapest correct answer and it removes one `devenv shell --` wrapper.
- **R1b (fallback, and needed anyway for `templateer`): the adopter declares the
  library.** A repository that takes the `changelog` group adds `pyjutsu` and
  `templateer` to its own `pyproject.toml`, pinned the way
  `gitman/uv.lock` already pins `pyjutsu` — exact GitHub release URL plus
  sha256. Then `devenv shell -- python3 -c 'import pyjutsu'` works because the
  project interpreter owns it.

Do R1a for `pyjutsu`. Do R1b for `templateer`. They are not alternatives.

### R2 — `templateer` becomes a versioned dependency, not a path

Today: `PYTHONPATH=$TEMPLATEER_PATH/src` plus `uv run --project
$TEMPLATEER_PATH`, with `TEMPLATEER_PATH` defaulting to an absolute sibling
checkout, plus an undeclared `.pth` that makes it importable by accident (P2).

Target: `templateer_v2` tags a release and publishes a wheel to the same
wheelhouse `pyjutsu` uses. The `changelog` group's README states `templateer
>= x.y` as a cost of taking the group; the adopter declares it in
`pyproject.toml`. `TEMPLATEER_PATH` and `PYTHONPATH` both disappear from the
workflow. `TEMPLATEER_TEMPLATE_PATH` stays, but resolves through
`$DEVMAN_SELF_DIR`, not an absolute path, since the templates are group assets.

Call the **Python API** (`TemplateRegistry.from_paths`, `generate`), not the
CLI, through a small adapter in `groups/changelog/`. Reason: the CLI path
currently costs a `uv run --project` against a foreign project inside a
`devenv shell` inside a Dagu step — four nested environment managers, measured
at 0.5-1.4 s and dependent on a sibling checkout. The API path is one import.

### R3 — the model endpoint stays in workflow params

This is already correct and the measurement confirms why: Dagu's
`env_passthrough_prefixes: [DEVMAN_]` means `GPU_LLM_*` cannot be inherited from
the enqueuing shell. A DAG `params:` entry is the only mechanism that reaches a
step. Keep the group default in the workflow, keep this machine's value in
`devenv.nix` `env.*`, and put nothing in Nix. Endpoint and model name are not
secrets; they need no secrets path.

The endpoint itself needs no change. It is up, it is declared in
`nix-meta/machines/server.nix` through the pinned `inferference` flake input,
and a real completion succeeded (see P6). The one thing the workflow must add
is a `finish_reason` check: gemma returns `content: ""` with
`finish_reason: "length"` when the token budget is short, which is a 200 that
carries nothing.

### R4 — one owner per name

- Remove `devenv` from `nix profile` (P4). Keep the Home Manager one, and decide
  deliberately whether it is `pkgs.devenv` or the flake's pinned `devenv v2.2`;
  right now the flake pins a version that nothing installs.
- Remove `repoman` from `profiles/developer.nix` `home.packages` (P3). The
  toolchain venv is the one that is current and editable.
- `uv tool uninstall gitman` (P7).
- Add **`uv`** to `home.packages`. It is missing from every login shell today
  and it is the one tool that makes an ad-hoc `uv run --with` possible without
  entering a devenv.

### R5 — the toolchain venv reaches an interactive shell, declaratively

Add one line to the Home Manager configuration:

```nix
home.sessionPath = [ "${config.home.homeDirectory}/.local/share/repoman/venv/bin" ];
```

placed **after** the Nix profile entries, so it can never shadow a Nix-managed
binary. This closes P9 — `gitman status` works from any directory, at the 1.07 s
measured cost of the CLI itself rather than 2.02 s through a devenv wrapper —
without creating a second copy of anything. It is the same venv the devenv
module already prepends.

## What this does not change

- The five queue names, `DEVMAN_PROJECT_DIR`, `DEVMAN_SELF_DIR`, `.devman/.runs/`.
- The plane's refusal-over-default rule. The measured `${DEVMAN_PROJECT_DIR}`
  log-path failure is a loud refusal and stays.
- The `git+file:` inputs. They are a real cost (P5, 6.05 s vs 0.755 s) but
  fixing them is a separate project with its own risk; see `MIGRATION.md` step 7.
