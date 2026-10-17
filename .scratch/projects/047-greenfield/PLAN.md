# 047 — implementation plan

**Status:** draft for the owner, 2026-10-15. The owner decided Q1 to Q10 the
same day (§E; Q11 and Q12 added later that day: Typer and uv2nix). Q7 moved the library into the central overlay. The charter is
[`CONCEPT.md`](CONCEPT.md). Every stage below names the concept section it
implements. Evidence: [`SPIKES.md`](SPIKES.md), [`DAGU_RELEASES.md`](DAGU_RELEASES.md)
and [`MEASUREMENTS.md`](MEASUREMENTS.md) (M1 to M6 on Dagu 2.20.1, all answered).
§B folds each measurement that changes the design into a proposed concept
amendment (B15 to B21).

This plan writes a new core in this repository. It keeps `.scratch/` and the
`.agents` link. It deletes or rewrites everything else. It has no migration code
and no compatibility layer (R12).

## How to use this plan

- Execute one stage per gitman lane. Land each lane when its verify command
  passes. Stages 0 to 9 change only this repository. The live machine keeps
  running devman v0.7.0 from nix-meta until Stage 10, so no earlier stage can
  break it.
- Read §A (interfaces) before any stage. The interfaces are fixed there. A stage
  that needs to change one changes §A and `CONCEPT.md` in the same lane.
- A stage marked **Depends on Mn** builds on that measurement. Each such stage
  states the answer and what the stage does because of it.
- The common verify command, from Stage 0 on, is:

```bash
devenv tasks run -v base:check   # ruff check, ruff format --check, uv lock --check
devenv tasks run -v base:unit    # pytest
devenv tasks run -v base:test    # nix flake check
```

  `devman doctor` is not part of verify until Stage 10, because the new doctor
  arrives in Stage 6 and the new plane runs only after the cutover.

## Where the library lives (decision Q7, 2026-10-15)

The library is **overlay content**, not package content. The package ships the
mechanism only: compiler, router, watcher, CLI, `dagu/config.yaml` and
`dagu/guard.sh`. Layout, under the overlay (`~/.config/devman`):

```
library/
  base.yaml            shared defaults, actions and handlers (a template, see below)
  workflows/<name>.yaml   shared workflows a project can take
  README.md            what each library file does
```

- An edit to the library is live. The watcher sees the change and recompiles.
  No Home Manager switch and no devman release is needed.
- `base.yaml` holds four tokens that only the machine knows: `@bash@`,
  `@guard@`, `@devman@` and `@stateDir@`. `devman compile` fills them from the
  environment (`DEVMAN_BASH`, `DEVMAN_GUARD`, `DEVMAN_BIN`, `DEVMAN_STATE`) and
  writes `<state>/base.yaml`. `config.yaml` sets `paths.base_config` to that
  file. The Home Manager wrapper sets the variables. A running Dagu reads a
  changed `base.yaml` for its next run without a restart (M7, measured in
  Stage 3). So compile restarts nothing, and `devman doctor` needs no finding
  for it.
- `devman doctor` checks that every `action:` a library workflow names exists
  in `base.yaml`.
- `DEVMAN_LIBRARY` stays as a test override. When set, it replaces
  `<overlay>/library`.
- The repository keeps a seed copy of the library under
  `tests/fixtures/library/`. Tests and `checks.library-validate` use it. Stage 7
  writes the live copy into the overlay in one overlay commit.

## Stage list

| # | Stage | Concept | Depends on |
|---|---|---|---|
| 0 | Clear the ground and lay the skeleton | §12 | — |
| 1 | Dagu 2.20.1 and the Home Manager module | R1, R11, §10 | M1 |
| 2 | Parse and validate `projects.toml` | R2, R4, §4 | — |
| 3 | `devman compile` | R5, §3.2, §5 | M1, M2, M4 |
| 4 | `devman emit` and the router | R8, §7 | M2, M4, M6 |
| 5 | The watcher | §7 (`save`), §5 (trigger) | M5 |
| 6 | `run`, `status`, `show`, `doctor` | §6, §11 | — |
| 7 | The library, the `base.yaml` actions and the checkout guard | R6, R7, §7, §8 | M1, M2, M3 |
| 8 | The agent workflow example | R9, §9 | — |
| 9 | Documentation | §1, AGENTS.md law | — |
| 10 | The cutover | R11, R12, §6, §10 | M4 |

---

## Stage 0 — clear the ground and lay the skeleton

**Goal:** delete the old plane and leave a package that builds, tests and
passes `nix flake check` with nothing but `devman --version`.

**Concept:** §12.

### Delete (tracked files)

| Path | Why it goes |
|---|---|
| `src/devman/` (all 15 modules) | the old core: registry, projection, reconcile, agent, linking |
| `src/devman_link/` | linkman owns links (§1, §12) |
| `src/devman_contract/` | the old manifest contract (§12) |
| `nix/devman-cli.nix` | replaced by `nix/package.nix` |
| `nix/nixos-module.nix` | no NixOS module (R11) |
| `nix/registry.nix`, `nix/renderer.nix`, `nix/mk-registry.py` | `mkRegistry` and the store registry (§12) |
| `nix/link-adapter.nix` | linkman's job |
| `nix/tests/` | tests of the registry and the NixOS service |
| `modules/link.nix` | the old repository link module |
| `groups/` (all) | groups, policies, `writes.toml` (§12). Workflow content moves to the overlay `library/` in Stage 7 |
| `packaging/` | the `devman-link` package |
| `tools/cutover/` | an old migration tool (R12) |
| `tests/` (all) | tests of deleted code. Stage 0 writes a new `tests/` |
| `RESEARCH_REPORT.md`, `STEP7_PROMPT.md` | old work notes. Their history stays in git |

### Keep

| Path | Note |
|---|---|
| `.scratch/` | history and stage logs. Never delete |
| `.agents` | an untracked link into the overlay. Do not touch |
| `CLAUDE.md` | a tracked link to `AGENTS.md` |
| `.loci` | a tracked link for another tool. Not devman's |
| `nix/dagu.nix` | Stage 1 bumps it |
| `scripts/gpu_complete.py` | the `gitman:commit-message` task calls it |
| `.gitignore` | trim the old `.devman/.runs` and `devenv.local.nix.devman-promoted` lines |

### Rewrite in Stage 0

- **`AGENTS.md`:** a short interim version. Keep the "Writing style",
  "boundary test" and "Choosing what to automate" content. Replace "What this
  repository is" with three sentences from CONCEPT §1. Replace the properties
  that name deleted parts (registry roots, groups, `writes.toml`, tiers) with one
  line: "The charter is `.scratch/projects/047-greenfield/CONCEPT.md`; the plan is
  `PLAN.md` beside it." Replace "Verify before you save" with the common verify
  command above. Stage 9 writes the full version.
- **`README.md`, `USER.md`, `AGENTS_GUIDE.md`:** replace each with a five-line
  stub that names the charter and the plan. Old text that describes deleted code
  misleads an agent. Stage 9 writes the real files.

### The new skeleton

```
devman/
  pyproject.toml
  flake.nix
  flake.lock                 regenerated
  devenv.nix
  devenv.yaml
  src/devman/
    __init__.py              __version__ = "0.9.0"
    __main__.py              from devman.cli import main; raise SystemExit(main())
    cli.py                   Typer; only --version in Stage 0
  dagu/                      config.yaml arrives in Stage 1, guard.sh in Stage 7 (.gitkeep)
  nix/
    dagu.nix
    package.nix              the CLI package
  tests/
    conftest.py
    test_cli.py              `python -m devman --version` prints the version
```

**The package layout.** One package, `devman`, under `src/`. One module per
concept verb (Stage 2 to Stage 6 add them, §C lists the budget). No
sub-packages. Three packages became one because the other two existed for
linking and the old contract, which both leave.

**The CLI library: Typer (decision 2026-10-15, replaces argparse).** One typed
function per command. The command grammar in §A.5 stays the same. Reasons and
costs:

1. Typed signatures give the argument checks for free, and the help text comes
   from the code.
2. The package has two runtime dependencies: PyYAML and Typer (with click and
   rich below it). The lock file pins all of them.
3. Start-up cost grew. Measured on this machine: Typer 0.24 imports in about
   73 ms against 20 ms for argparse; `devman --version` through the built
   wrapper takes about 70 ms in all. The watcher calls the router in process, so
   only the `handler_on` hook and a person pay it per call. The owner accepted
   the cost.
4. Typer vendors click, and `isinstance` against click fails silently. Code that
   walks a Typer app must duck-type.
5. `main()` calls the Typer app, which exits with the command's code. A command
   raises `typer.Exit(code)` for exit codes 1 and 2.

**Packaging: `pyproject.toml`, `uv` and uv2nix (decision 2026-10-15).** The
repository commits `uv.lock`. `nix/package.nix` builds the package with uv2nix
(`sourcePreference = "wheel"`, interpreter `python313` from nixpkgs), not with
nixpkgs Python packages. `uv2nix`, `pyproject-nix` and `pyproject-build-systems`
are declared in `flake.nix` **only**, each following `nixpkgs`. The old
repository declared them in `devenv.yaml` too, and the two copies broke
independently. The devenv shell uses `uv` directly (`uv run --frozen`) and does
not need uv2nix. `uv lock --check` is part of `base:check`, so a stale lock
fails. `.gitignore` re-includes `uv.lock`.

**`pyproject.toml`:**

```toml
[project]
name = "devman"
version = "0.9.0"
description = "Compile, route and show Dagu workflows across repositories"
requires-python = ">=3.13"          # PurePath.full_match, used for `**` globs
dependencies = ["pyyaml", "typer"]

[dependency-groups]
dev = ["pytest"]

[project.scripts]
devman = "devman.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/devman"]

[tool.ruff]
target-version = "py313"
line-length = 88
src = ["src"]
extend-exclude = [".scratch"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[tool.pytest.ini_options]
addopts = "-v"
pythonpath = ["src", "tests"]
testpaths = ["tests"]
markers = ["e2e: starts a real Dagu server on free loopback ports"]
```

No `[project.optional-dependencies]`, no `tool.uv.sources`, no `linkman`.

**`flake.nix` outputs (complete list after Stage 1):**

| Output | Holds |
|---|---|
| `packages.<system>.dagu` | `nix/dagu.nix` |
| `packages.<system>.devman` and `.default` | `nix/package.nix` |
| `homeManagerModules.default` | `nix/hm-module.nix` (Stage 1) |
| `overlays.default` | adds `dagu` and `devman` to a package set |
| `checks.<system>.python-tests` | pytest over `src/` and `tests/`, with Dagu and watchexec on `PATH`, `-m "not e2e"` |
| `checks.<system>.e2e` | pytest `-m e2e` (Stage 4). Drop it from `checks` if the Nix sandbox refuses loopback ports, and keep it in `base:e2e` |
| `checks.<system>.library-validate` | renders and validates every file in `tests/fixtures/library/` (Stage 7). The live library sits in the overlay, outside the flake |
| `checks.<system>.hm-module` | evaluates the Home Manager module (Stage 1) |

Inputs: `nixpkgs`, `home-manager` (for `checks.hm-module` only), `pyproject-nix`,
`uv2nix` and `pyproject-build-systems`. Each follows `nixpkgs`. Delete the
`mancore` input. `checks.python-tests` runs pytest from a uv2nix virtual
environment of the locked runtime and dev dependencies.

**`nix/package.nix`:** uv2nix. It loads the workspace from a fileset
(`pyproject.toml`, `uv.lock`, `src`, `dagu`), builds a virtual environment of
the locked runtime dependencies, and wraps `bin/devman` with
`--prefix PATH : dagu watchexec`. It installs `dagu/` to `$out/share/devman/`.
It does not install a library (decision Q7). The version comes from
`pyproject.toml`. Install check: `devman --version`.

**`devenv.yaml`:** keep `nixpkgs`, `nixpkgs-python` and `codex-cli`. Delete
`mancore`. Do not declare `pyproject-nix`, `uv2nix` or
`pyproject-build-systems` there; `flake.nix` owns them. Delete `nix2container` and `mk-shell-bin` if nothing reads them.

**`devenv.nix`:**

```nix
packages = [ pkgs.git pkgs.ruff dagu pkgs.watchexec pkgs.hyperfine
             inputs.codex-cli.packages.${pkgs.system}.default ];
languages.python = { enable = true; version = "3.13"; venv.enable = true; uv.enable = true; };
tasks = {
  "base:check".exec = "ruff check . && ruff format --check . && uv lock --check";
  "base:unit".exec  = "uv run --frozen pytest -m 'not e2e'";
  "base:e2e".exec   = "uv run --frozen pytest -m e2e";
  "base:test".exec  = "nix flake check";
  "format:fmt".exec = "ruff format .";
  "release:build".exec = "nix build .#devman --out-link result-devman";
  "agent:review".exec = ...;            # unchanged; an overlay workflow calls it
  "gitman:commit-message".exec = ...;   # unchanged
};
```

The devenv shell does **not** install the devman package. Two `devman`
binaries on one `PATH` was a measured hazard. Tests run the source with
`python -m devman`.

**Tests:** `tests/test_cli.py`: `--version` prints `0.9.0` and exits 0; an
unknown command exits 2.

**Verify:** the common verify command, plus `nix build .#devman && ./result/bin/devman --version`.

**Interfaces fixed:** the package name, the module layout, the CLI library, the
devenv task names `base:check`, `base:unit`, `base:e2e`, `base:test`.

---

## Stage 1 — Dagu 2.20.1 and the Home Manager module

**Goal:** pin Dagu 2.20.1 and ship one Home Manager module that installs the
CLI, the Dagu user service and the watcher user service with a generated
`config.yaml` and `base.yaml`.

**Concept:** R1, R11, §10. **Depends on M1** (see below).

### Files

- `nix/dagu.nix`: version `2.20.1`. Copy the four sha256 sums from the release's
  `checksums.txt`. M-run evidence: `linux_amd64` is
  `0d5c1612cd842931fe6d4e598fc2e43fb912a94122e571c62a8f73691ea49837`. Keep the install check `dagu version`. Update the header
  comment: the Go-version reason may no longer hold; record what does.
- `dagu/config.yaml`: a template. `pkgs.replaceVars` fills `@name@` tokens.
- `base.yaml` is **not** in this repository. It lives in the overlay at
  `library/base.yaml` (decision Q7). Stage 1 writes a seed copy with the
  defaults only, at `tests/fixtures/library/base.yaml`. Stage 7 adds the
  handlers and the actions.
- `nix/hm-module.nix`: the module.
- `flake.nix`: `homeManagerModules.default`, `checks.hm-module`.

### `dagu/config.yaml`

```yaml
# Filled by nix/hm-module.nix. Do not edit the installed copy.
host: "@host@"
port: @port@
coordinator: { host: "@host@", port: @coordinatorPort@ }
auth: { mode: none }
skip_examples: true
default_shell: "@bash@"
dag_discovery: { recursive: true, symlinks: false }
paths:
  dags_dir: "@stateDir@/dags"
  base_config: "@baseConfig@"
queues:
  enabled: true
  config: @queues@          # a JSON list: [{"name": "light", "max_concurrency": 4}, ...]
```

`symlinks: false`: compile writes regular files only. Dagu then ignores any
stray link. `data_dir` and the log paths keep Dagu's defaults under
`DAGU_HOME`. Since 2.17.2 the DAG index lives under `data_dir`.

### `library/base.yaml` (Stage 1 part; the overlay holds the live copy)

```yaml
queue: light
shell: "@bash@"               # Dagu reads $SHELL from the enqueuing process otherwise
hist_retention_days: 7
```

The retention value is plain content now. The module has no
`histRetentionDays` option.

### Module options: `services.devman`

| Option | Type | Default |
|---|---|---|
| `enable` | bool | `false` |
| `package` | package | this flake's `devman` |
| `dagu.package` | package | this flake's `dagu` |
| `host` | str | `"127.0.0.1"` |
| `port` | port | `8080` |
| `coordinatorPort` | port | `50055` |
| `queues` | attrsOf positive int | `{ light = 4; normal = 2; heavy = 1; gpu = 1; exclusive = 1; llm = 2; }` |
| `defaultQueue` | str | `"light"` |
| `overlayDir` | str | `"${config.home.homeDirectory}/.config/devman"` |
| `stateDir` | str | `"${config.home.homeDirectory}/.local/state/devman"` |
| `daguHome` | str | `"${config.home.homeDirectory}/.local/share/dagu"` |
| `servicePath` (profile roots; the module appends `/bin`) | listOf str | `[ "%h/.nix-profile" "/etc/profiles/per-user/%u" "/run/current-system/sw" "/nix/var/nix/profiles/default" ]` |
| `watch.enable` | bool | `true` |
| `watch.debounce` | str | `"300ms"` |

**Assertions** (correctness refusals only):

- `defaultQueue` is a key of `queues`.
- `host` is loopback (`127.0.0.0/8`, `::1`, `localhost`), because `auth.mode`
  is `none`. A non-loopback host would expose an unauthenticated command runner.
- `overlayDir` and `stateDir` differ, and neither contains the other. Stage 41
  of the old plane measured what an overlay that is also an output does.

**What the module writes:**

- The filled `config.yaml` in the store. Its `paths.base_config` is
  `<stateDir>/base.yaml`, which `devman compile` writes from the overlay
  `library/base.yaml` (decision Q7). The module does not generate `base.yaml`.
- `home.packages = [ wrappedDevman cfg.dagu.package ]`. `wrappedDevman` is the
  package wrapped with `--set DEVMAN_OVERLAY`, `DEVMAN_STATE`, `DAGU_HOME`,
  `DEVMAN_DAGU_CONFIG` (the store path of the filled `config.yaml`),
  `DEVMAN_DAGU_VERSION` (`cfg.dagu.package.version`), `DEVMAN_BASH`,
  `DEVMAN_GUARD` (`<package>/share/devman/dagu/guard.sh`; the file arrives in Stage 7, so the path dangles until then)
  and `DEVMAN_BIN` (the wrapped CLI).
- `systemd.user.services.devman-dagu`: `ExecStart = dagu start-all --config
  <config.yaml>`, `Environment = DAGU_HOME=…`, `PATH` from `servicePath` plus
  `wrappedDevman`, `UnsetEnvironment = SHELL`, `Restart = on-failure`,
  `X-Restart-Triggers` on the filled `config.yaml`, `WantedBy = default.target`.
- `systemd.user.services.devman-watch`: `ExecStart = devman watch --debounce
  <watch.debounce>`, `After = devman-dagu.service`, `Restart = on-failure`,
  `X-Restart-Triggers` on the package. Only when `watch.enable`.

The unit names are new on purpose: `devman-dagu` and `devman-watch`. The old
NixOS module owned `dagu.service`, `devman-watch.service` and
`devman-dagu-reload.{path,service}`. Stage 10 removes those in the same switch.

**Linger is not in the module.** Home Manager cannot set it. nix-meta keeps
`users.users.<name>.linger = true` in its machine layer (Stage 10).

### Tests

- **Stage 1 as built (2026-10-15).** Home Manager throws on a failed assertion
  and hides its text, so the negative evaluations read `config.assertions` from
  a bare `lib.evalModules` with stub options. The check lives in
  `nix/hm-module-check.nix`. `dagu validate` runs on a DAG with one step. A
  DAG with no steps is not a useful proof. `guard.sh` is not a `replaceVars`
  input, because the file does not exist before Stage 7.
- `checks.hm-module`: build a `home-manager.lib.homeManagerConfiguration` with
  `services.devman.enable = true`. Assert both unit files exist and that the
  filled `config.yaml` has no `@` token left.
- The same check runs `dagu validate` on an empty DAG under the filled
  `config.yaml` and the seed `base.yaml`, with a temporary `DAGU_HOME`.
- Negative evaluations: `host = "0.0.0.0"` and `defaultQueue = "typo"` each fail
  with their assertion text.
- `nix build .#dagu && ./result/bin/dagu version` prints `2.20.1`.

**Verify:** the common verify command.

**Superseded by project 048 finding F3.** The original decision set `queue: light`
in `base.yaml` as a default. Every workflow now names its queue.

**Depends on M1 (answered: yes).** On 2.20.1 a scheduled run on a queue that
`config.yaml` defines waits for a free slot. A run on an undefined queue skips
the queue and runs at once with no limit. A DAG with no `queue:` uses its own
name as a queue of concurrency 1. So `base.yaml` sets `queue: light` for every
DAG, and Stage 3 refuses an undefined `queue:` (B6). Record the M1 answer in
`library/base.yaml` (overlay and seed) as a comment beside `queue:`.

**Interfaces fixed:** the option names, the unit names, the six queue names,
the environment variables in §A.6.

---

## Stage 2 — parse and validate `projects.toml`

**Goal:** turn `projects.toml` into typed project records, and report each error
against the project it belongs to.

**Concept:** R2, R4, §4.

### Files

- `src/devman/paths.py`: one frozen dataclass `Paths` built from the
  environment (§A.6): `overlay`, `state`, `library` (default `<overlay>/library`),
  `base_src` (`<library>/base.yaml`), `base_out` (`<state>/base.yaml`),
  `dags`, `runs`, `events`, `compile_json`, `lock`, `dagu_config`. No other module reads the
  environment.
- `src/devman/manifest.py`: `load(path) -> Manifest`.
- `tests/test_manifest.py`, `tests/fixtures/manifests/*.toml`.

### Interface

```python
@dataclass(frozen=True)
class OnEntry:
    event: str
    match: tuple[str, ...]
    exclude: tuple[str, ...]
    run: str

@dataclass(frozen=True)
class Project:
    name: str
    path: Path            # expanded, absolute; not checked against the disk here
    take: tuple[str, ...]
    on: tuple[OnEntry, ...]

@dataclass(frozen=True)
class Manifest:
    projects: dict[str, Project]        # the projects that parsed
    errors: dict[str, list[str]]        # project name -> reasons; "" for file-level errors
```

`load` never raises for content. A TOML syntax error gives `errors[""]` and no
projects. A bad table gives `errors[name]` and leaves the other projects intact.
§A.1 lists every rule.

`matches(on: OnEntry, subject: str) -> bool` lives here too, because the router
and the loop check (§A.1, rule 9) both need it. It uses
`PurePosixPath(subject).full_match(glob)` for each glob.

### Tests

- The example in CONCEPT §4 parses to the expected records.
- One test per rule in §A.1, each asserting the exact reason text.
- A bad table refuses only its own project.
- `~` expansion; a relative `path` is refused.
- `matches`: `**/*.py` matches `a.py` and `src/a.py`; `exclude = [".scratch/**"]`
  removes `.scratch/x/a.py`; `main` matches `main` only.
- Loop check: `on = [{event="done", match="check", run="check"}]` is refused.

**As built (2026-10-15).**

- `Paths` also holds `tmp` (`<state>/tmp`), `dagu_version`, and the three token
  values `bash`, `guard` and `bin` (each `None` when unset). `projects_toml` and
  `workflows` are properties. Stage 3 needs all of them, and no other module may
  read the environment.
- The loop check (rule 9) cannot see the files in `workflows/<project>/`. It
  tests each `done`/`failed` `match` against the names the table itself holds:
  `take` and every `run`, in sorted order. A cycle through a workflow that only a
  file defines is found by no one; no real manifest does that.
- A missing or unreadable `projects.toml` gives a file-level error
  (`cannot read <path>: …`), the same as a syntax error.
- Reason texts for rules the plan leaves open: `path is required`, `path must be
  a string`, `path <p> is not absolute`, `take must be a list of workflow names`,
  `on must be an array of tables`, `on[i] is not a table`, `on[i] needs <key>`,
  `on[i] event <e> does not match …`, `on[i] match must be a string or a list of
  strings, none empty`, `on[i] exclude must be a list of non-empty strings`.
  Tests assert each one.

**Verify:** the common verify command.

**Interfaces fixed:** §A.1.

---

## Stage 3 — `devman compile`

**Goal:** resolve, render, validate and publish each project's workflows, refuse
a broken project without touching its files, and record the result.

**Concept:** R5, §3.2, §5. **Depends on M2 and M4.**

### Files

- `src/devman/render.py`: `render(project, workflow, source_path, source_text) ->
  str`, and `check_source(text) -> list[str]` (the reasons a source is refused).
- `src/devman/dagu.py`: `validate(path) -> str | None` (the error text or
  `None`). Stage 4 and Stage 6 add more calls here.
- `src/devman/compile.py`: `compile(paths, names: list[str] | None) -> int`. It
  also fills and writes `base.yaml` (step 1).
- `cli.py`: `devman compile [project…]`.
- `tests/test_render.py`, `tests/test_compile.py`.

### Steps (per project, in this order)

1. **Lock.** Take `fcntl.flock` on `<state>/compile.lock` for the whole run. The
   watcher and a person may compile at the same time.
   **Base.** Fill the four tokens of `<library>/base.yaml` and write the result
   to `<state>/base.yaml` when it differs. Refuse the whole run (exit 1) when
   the file is missing or a token has no value. M7: a running Dagu rereads the
   file for its next run, so nothing restarts.
2. **Parse** the manifest (Stage 2). A project with parse errors is refused.
3. **Resolve.** The workflow set is the union of every `*.yaml` stem in
   `<overlay>/workflows/<project>/` and every name in `take`. For each name, the
   source is `<overlay>/workflows/<project>/<name>.yaml` if it exists, else
   `<library>/workflows/<name>.yaml`. A `take` name with neither file, or an `on.run` name
   outside the set, refuses the project. Files that do not end in `.yaml` are
   ignored (a `README.md` may sit there).
4. **Check** each source (§A.2): a mapping as the first document, no
   header-owned key (`env`, `log_dir`, `shell`, `handler_on.exit`), a `params:`
   (if set) that declares `DEVMAN_EVENT` and `DEVMAN_SUBJECT`, a valid workflow
   name, and an explicit queue string that names a configured queue. The queue
   list comes from `DEVMAN_DAGU_CONFIG`.
5. **Render** each file (§A.2).
6. **Validate** each rendered file whose content differs from the published file.
   Write it to `<state>/tmp/<project>/<project>.<name>.yaml` and run
   `dagu --config $DEVMAN_DAGU_CONFIG validate <file>`. Run the validations in a
   thread pool of 4. `--all` validates every file, changed or not.
7. **Refuse or publish.** Any failure in steps 2 to 6 refuses the project: no
   file under `dags/<project>/` changes. Otherwise create `dags/<project>/` and
   `runs/<project>/`, move each changed file with `os.replace` from `tmp/` (one
   file system), and delete each `dags/<project>/*.yaml` whose workflow left the
   set.
8. **Record** the project in `compile.json` (§A.3).

After all projects:

- **Orphans.** A directory `<overlay>/workflows/<name>/` with no manifest table
  is refused under that name. Compile writes no file for it.
- **Removed projects.** A project in the previous `compile.json` and not in the
  manifest loses `dags/<project>/` and its `compile.json` entry. `runs/<project>/`
  stays; Dagu's retention prunes it. Only a full compile (no `project` argument)
  removes projects.
- Write `compile.json` with `os.replace`.
- Exit 0 when no project was refused, else 1. Print one line per refused project:
  `devman: compile refused <project>: <reason>`.

Compile never touches a file in `dags/` that it did not write. Dagu creates
`dags/wiki/`; compile leaves it.

### Tests

- **Superseded by project 048 findings F1 and F3:** the header always sets
  `working_dir`, and every source names a configured queue. The original source
  work-directory and optional queue rules are historical.
- Header keys are added only when absent; `group` and `labels` set by the source
  win (§A.2).
- A source with `env:` or `log_dir:` is refused with the §A.2 text.
- A source that starts with `---` renders as one document.
- Every refusal in CONCEPT §5 and §A.2: the project's files keep their bytes and
  mtime; `compile.json` holds the reason and `stale: true`; another project in
  the same run publishes.
- A removed workflow file is deleted. A removed project's directory is deleted.
- A second compile with no change writes nothing (mtimes unchanged) and
  validates nothing.
- Two compiles started at once both finish, one after the other.
- With real Dagu 2.20.1 (from `PATH`): a rendered library-style file validates; a
  file with `name:` fails validation and refuses its project.
- A rendered file with `group:` and `labels:` validates (M4 measured both).
- A source that sets `handler_on.exit` is refused with the §A.2 text.
- A `queue: undefinedq` source is refused with the §A.2 text.
- A `path` that names no directory refuses the project, and compile creates no
  directory there.

**Verify:** the common verify command.

**Depends on M2 (answered: Dagu does not fail).** Dagu runs `mkdir -p` on a
missing `working_dir` or `log_dir`, and the run succeeds in an empty directory.
`dagu validate` checks no path. So:

- Compile keeps its `path` refusal, and it checks with `os.path.isdir`, never by
  creating anything. A typo in `path` must not create a directory.
- A checkout that disappears after compile needs a run-time guard. Stage 7
  builds it (§A.8). Stage 3 only renders `DEVMAN_PROJECT_DIR`, which the guard
  reads.

**Depends on M4 (answered: yes).** Both `dags/<project>/` subdirectories load as
`<project>.<name>`. A linkman link to `dags/<project>/` placed outside
`dags_dir` changes nothing. `group:` and `labels:` work, and Dagu lowercases
label values. Two files with one base name hide both and drop both from the
scheduler. The `<project>.<name>` stem and rule 4 (§A.1) prevent that by
construction. Keep the layout of CONCEPT §3.2 unchanged. Never put a link inside
`dags_dir`.

**Depends on M7 (answered: yes).** A running `dagu start-all` applies a changed
`base_config` file to the next run: scheduled, REST-enqueued and CLI-enqueued
runs all did, after an in-place edit and after a rename. Compile therefore
writes `<state>/base.yaml` with `os.replace` and restarts nothing. Doctor needs
no "restart needed" finding for it.

**As built (2026-10-15).** Each item changes or fills in the plan above.

- **Signatures.** `render.check_source(text, queues, label)` takes the queue list
  and the label that prefixes each reason. `render.render(project, workflow,
  project_path, log_dir, origin, source_path, source_text)` takes the facts it
  writes, so it reads neither `Paths` nor the disk. `dagu.validate(config, file)`
  takes the config path, because only `Paths` reads the environment.
  `dagu.configured_queues(config)` reads the queue names.
  `compile.compile(paths, names, validate_all)` returns the exit code.
- **Exit codes.** `2` for no `DEVMAN_DAGU_CONFIG` and for an unknown project
  argument. `1` for everything refused, including the whole-run refusals.
- **Whole-run refusals** (printed as `devman: compile refused library: …`, no
  project touched, no `compile.json` written): a missing or unreadable
  `library/base.yaml`, a token with no value (`@guard@ has no value; set
  DEVMAN_GUARD`), an unknown token, and a `base.yaml` that is not a YAML mapping.
  A token inside a comment needs no value. A bad `base.yaml` is live the moment
  it is written (M7), so compile parses it before it writes. Compile does not
  run `dagu validate` on the base itself; the next step does: a base change
  forces validation of every file (`validate_all`).
- **A broken `projects.toml`** (file-level error) refuses with
  `compile refused projects.toml: …`, and a full compile then removes no
  project, because the file proves nothing about who left.
- **Orphans** are refused only in a full compile. A partial compile keeps the
  previous `orphans` list.
- **A project refused at parse time** has no `Project`, so its record keeps the
  previous `path`, `on` and `workflows` (stale) or none (first compile).
- **No-op compile.** A record that differs from the previous one only in `at`
  keeps the old record, and `compile.json` is rewritten only when something
  other than `compiled_at` changed. So a second compile writes no file at all.
- **Reason texts** the plan leaves open: `path <p> is not a directory`,
  `on entry runs <w>, which is not a workflow of this project`,
  `workflows/<project>/<file>.yaml: workflow name … must not contain a dot`,
  `<project>/<workflow>: top-level env|log_dir|shell is set by devman; <advice>`,
  `<project>/<workflow>: handler_on.exit is set by devman; use handler_on.success
  or handler_on.failure`, `<project>.<workflow>: <dagu validate error>`.
- **`dagu validate` needs `skip_examples: true`** in the config it reads. Without
  it, Dagu writes example DAGs into `dags_dir` on first use. The test config sets
  it, as the real one does.
- **Size.** `compile.py` has 341 lines against a budget of 260 (+31%). It holds
  the base fill, the token rules, the orphan and removed-project handling and the
  no-op rule. No Dagu feature does any of these, so the module stays whole.
  Stage 4 onward keeps the 30% rule.

**Interfaces fixed:** §A.2, §A.3, the compile exit codes.

---

## Stage 4 — `devman emit` and the router

**Goal:** turn one event into zero or more queued Dagu runs, and record every
event and its outcome in `events.jsonl`.

**Concept:** R8, §7. **Depends on M6.**

### Files

- `src/devman/router.py`: `emit(paths, event: Event) -> Outcome`, and
  `find_project(records, cwd) -> str | None`.
- `src/devman/dagu.py`: add `enqueue(dag_file, run_id, params) -> str | None`
  (the error text or `None`).
- `cli.py`: `devman emit` (§A.5).
- `tests/test_router.py`, `tests/fakes/dagu` (a fake `dagu` that appends its
  `argv` to a file and exits with a code taken from an environment variable).
- `tests/e2e/test_plane.py`: the end-to-end harness. It starts
  `dagu start-all` on two free loopback ports with a temporary `DAGU_HOME` and
  state root, compiles a fixture manifest, emits one event, and waits up to 30 s
  for the run to succeed.

### Behaviour

1. Read `compile.json`. The router acts on the published state, not on the
   manifest, so the `on` entries always agree with the files in `dags/`. A
   project that is refused but has old files routes on its old entries; the
   event line carries `"stale": true`.
2. Find the project: `--project`, else the project whose `path` is the deepest
   parent of the resolved current directory. No project: refuse (exit 2).
3. Normalise each subject: an absolute path under the project path becomes
   relative to it.
4. Match: an `on` entry matches when its `event` equals the event and at least
   one subject passes `match` and no `exclude` glob (§A.1). Each matched
   workflow is enqueued **once** per emit, whatever the number of subjects.
5. **Refuse a vanished checkout.** If the project `path` is not a directory,
   refuse the event (exit 2, `refusal` in the event line). Dagu would create the
   directory and succeed (M2).
6. Enqueue each match:

   ```
   dagu --config $DEVMAN_DAGU_CONFIG enqueue \
     --run-id <uuid4> --labels devman.event=<event> \
     <state>/dags/<project>/<project>.<run>.yaml \
     -- DEVMAN_EVENT=<event> DEVMAN_SUBJECT=<first matching subject> <KEY=VALUE…>
   ```

   - **The absolute file path, not the DAG name, and not the REST API.** M4: the
     CLI looks only at the top of `dags_dir`, so `dagu enqueue devman.check`
     fails with "no such file". The path form works with the server down (the
     run waits on disk until the scheduler starts), needs no HTTP client in the
     event path, and uses a path compile already wrote. The REST route needs a
     live server and a request shape that no stage has pinned yet.
   - **`--run-id`:** a `uuid.uuid4()` string that the router makes first, so
     the event line names the run even when Dagu fails. Dagu refuses a
     duplicate ID (M6); a uuid4 never repeats, so a refusal there means a bug and
     shows as `"result": "failed"`.
   - **`--labels devman.event=<event>`:** records why the run started, in the
     Dagu UI. The event grammar (§A.1, rule 7) is inside the label character set
     and is already lower case, so Dagu's lowercasing changes nothing. The
     subject is not a label: a path can hold characters a label refuses.
   - **Never `--name`.** It renames the run, splits the run history and the log
     directory, and changes `DAG_NAME`, which the handler parses (M6).
   - **Never `--default-working-dir`.** `enqueue` ignores it (M6). The header's
     `working_dir` is the only route.
7. Append one line to `events.jsonl` (§A.4) with `O_APPEND` and one `write` call.
8. Print one line per match: `enqueued <dag> run=<id>` or
   `failed <dag>: <error>`. Exit 0 if every enqueue worked (zero matches is
   success), 1 if one failed, 2 for a refusal.

**Loop safety.** Stage 2 refuses a `done`/`failed` cycle at parse time. The
router adds no runtime guard.

### Tests

- Unit (fake `dagu`): match, exclude, deepest-path lookup, absolute subject
  normalisation, one enqueue for many subjects, refusal for no project, the exact
  `argv`, the exact `events.jsonl` line, exit codes.
- Unit: a failed enqueue still writes its event line with `"result": "failed"`.
- Unit: the `argv` holds the absolute file path, `--run-id`, `--labels`, and no
  `--name` and no `--default-working-dir`.
- Unit: an event for a project whose `path` is gone is refused and enqueues
  nothing.
- e2e: the run reaches `succeeded`, and its step sees `DEVMAN_EVENT` and
  `DEVMAN_SUBJECT` (the step echoes them into a file). The run carries the label
  `devman.event=<event>` in the REST record.
- e2e: a scheduled run of the same file (no router) sees both names as empty
  strings, from the declared `params:` defaults.

**Verify:** the common verify command, plus `devenv tasks run -v base:e2e`.

**Depends on M6 (answered: yes).** `-- KEY=value` reaches the run as `${KEY}`,
also when the DAG does not declare it. `--labels` and `--run-id` work. `--name`
works but splits history, so the router never uses it. `enqueue` ignores
`--default-working-dir`. Two quick enqueues of one DAG are both kept and run one
after the other. The router passes `DEVMAN_EVENT` and `DEVMAN_SUBJECT`, and the
rendered file **declares** both (§A.2), so a run that the router did not start
(a schedule, a manual `dagu start`) reads empty strings and not an unset name.
Extra `KEY=VALUE` fields pass through undeclared; a workflow that relies on one
declares it in its own `params:`.

**As built (2026-10-15).**

- **Signatures.** `dagu.enqueue(config, dag_file, run_id, event, params)` takes
  the config path and the event name, because it builds `--labels` itself.
  `router.emit(paths, Event) -> Outcome` returns the exit code, the lines to
  print and the event record. `Event` holds `name`, `project`, `subjects`,
  `source`, `fields` and `cwd`. `router.parse_fields` and `router.check_event`
  hold the §A.5 grammar. A usage error exits 2 and writes no event line; every
  router refusal exits 2 and does write one.
- **Refusals** (each one a line with `refusal` set, `matches: []`): no or bad
  `compile.json`, no project for the directory, unknown `--project`, a project
  `path` that is not a directory, and a match with no `DEVMAN_DAGU_CONFIG`.
  The path check runs before matching, so a vanished checkout is refused even
  when nothing would match. A compiled file missing on disk fails that match
  (`result: failed`, exit 1) and runs no `dagu`.
- **One subject per run.** `DEVMAN_SUBJECT` is the first subject that matches the
  first `on` entry that names the workflow. A later entry for the same workflow
  adds no run. With no subject, the router matches against the empty string.
- **The fake `dagu`** (`tests/fakes/dagu`) also answers `validate` with exit 0
  and no log line, so a router test can compile with it on `PATH`.
- **Labels in the REST record.** The header sets `labels: project=<p>`, so the
  run's `labels` list holds `project=<p>` and `devman.event=<event>`. The e2e
  test asserts membership.
- **The e2e "scheduled run"** is `dagu start <file>` with no parameters. It reads
  the same declared defaults as a schedule, and it needs no wait for a cron tick.
- **Measured latency.** The e2e harness measures 2.8 s from the call of
  `router.emit` to the first step (three runs, 2.76 to 2.78 s). Most of it is
  the scheduler's queue poll.
- **Size.** `router.py` has 182 lines against a budget of 180.

**Interfaces fixed:** §A.4, §A.5.

---

## Stage 5 — the watcher

**Goal:** one long-running process that turns file saves into `save` events and
recompiles when a source changes.

**Concept:** §7 (`save`), §5 (when compile runs). **Depends on M5.**

### Files

- `src/devman/watch.py`: `devman watch [--debounce DURATION]`.
- `tests/test_watch.py`.

### Behaviour

1. **Start:** run a full compile. This picks up library edits made while the
   watcher was down.
2. **Build the watch set** from `compile.json`:
   - every project that has at least one `on` entry with `event = "save"`
     (today: one project, devman);
   - `<overlay>/projects.toml`, `<overlay>/workflows/` and `<overlay>/library/`
     (always; the library is overlay content, so an edit is live).
3. **Start one watchexec** with `--only-emit-events --emit-events-to=json-stdio`,
   `--project-origin=<state>` (without it watchexec walked a common parent at
   99% of a core, old Stage 3 S5), `--debounce <debounce>`, one `--watch` per
   path, and one `--ignore` per fixed pattern (§A.1, rule 8).
4. **Read** the JSON lines. Collect paths for one debounce window. Then:
   - a path under the overlay or the library: run compile (in process, under
     the compile lock);
   - a path under a project: group by project, and call `router.emit` in
     process with `event = "save"`, `source = "watcher"` and the relative paths
     as subjects.
5. **Restart watchexec only when the set of watched paths changes.** Compare
   the sorted path list before and after each compile. A compile that changes
   workflows but not paths leaves watchexec running. M5: a start over 33
   repositories costs about 14 s of one full core and sets about 90,000 inotify
   watches. `save` events are missing during that window; log
   `devman watch: watchexec starting, <n> paths` and `… ready` so the gap is
   visible.
6. **Exit** when watchexec exits, with its exit code. systemd's
   `Restart=on-failure` restarts the service, and a dead watchexec stays visible.

The watcher calls the router and compile as functions, not as processes. One
save costs no extra Python start-up.

### Tests

- Unit: the watch set from a fixture `compile.json`; grouping a batch of paths
  by project; overlay paths trigger compile and not emit; the ignore list is on
  the command line.
- Integration (real watchexec, temporary directories, no Dagu): write a file in
  a fixture project and see one `save` line in `events.jsonl` within 2 s; write
  inside `.git/` and `.worktrees/` and see none; add a project with a `save`
  entry to `projects.toml` and see the watch set grow.

**Verify:** the common verify command.

- Unit: a compile that changes a workflow but no path does not restart
  watchexec; a compile that adds a `save` project does.

**Depends on M5 (answered: affordable).** One watchexec over all 33
repositories sets 90,461 inotify watches (17% of the 524,288 limit), takes about
14 s of one core to start, then holds 75 MB and about 1% of a core when idle.
One touch gave one event. The ignore patterns filter **events**, not watches:
watchexec still watches ignored directories. So:

- One process is enough. Keep the design.
- The watch set holds only projects with a `save` entry (B10). Today that is one
  project, so the real cost is far below the M5 number.
- Restart only on a path-set change (step 5).
- The next limit is the inotify budget, at about 150 repositories that all take
  `save`. `devman doctor` reports the watch count against
  `fs.inotify.max_user_watches` when it passes 50%.

**As built (2026-10-15).** Each item changes or fills in the plan above.

- **The ignore patterns are `**/<name>` and `**/<name>/**`, not `<name>`.**
  Measured with watchexec 2.5.1: with `--project-origin=<state>` a bare `--ignore
  node_modules` or `--ignore .devman` filtered nothing, because watchexec matches
  the pattern against the path relative to the origin, and a project is not under
  the state directory. Only `.git` and `__pycache__` looked ignored, and that was
  watchexec's own default list. The watcher passes two patterns per name (the
  directory and its contents).
- **A missing watch path kills watchexec** (`No such file or directory`). So the
  watch set holds only paths that exist now. `workflows/` and `library/` join the
  set when they exist.
- **The overlay is watched non-recursively** (`--watch-non-recursive <overlay>`),
  in addition to `workflows/` and `library/`. An editor replaces `projects.toml`
  by rename, and a folder created later (`workflows/`) must start a compile. Any
  file directly in the overlay starts a compile, which is a no-op when nothing
  changed. After each compile, the watcher rebuilds the set; a new `workflows/`
  folder then restarts watchexec once.
- **Skipped events.** The watcher ignores `access` and `remove` events and any
  path whose `filetype` is `dir`. A new folder is not a save.
- **No ready signal.** watchexec 2.5.1 logs nothing when its watches are in place
  (checked at `-vvv`). So the watcher watches one more directory, `<state>/watch/`
  (non-recursive), and writes `canary` there every 0.5 s. The first event for it
  logs `devman watch: watchexec ready`. The start line counts the canary:
  `watchexec starting, <n> paths`. The canary proves its own path only; on a large
  tree watchexec may still be setting up another path. Treat `ready` as the
  earliest sign, not as proof.
- **Batches.** The watcher waits for the debounce time with no new line (at most
  5 s), then handles the whole batch. It compiles first, then sends one `save`
  per project, then compares the watch set with the old one.
- **Exit.** When watchexec exits, the watcher exits with its code, and with 1
  when that code is 0 or a signal, so `Restart=on-failure` always restarts it. It
  exits 1 when the overlay does not exist, and 2 when `watchexec` is not on `PATH`.
  SIGTERM stops watchexec and exits 143.
- **Compile errors do not stop the watcher.** A refused compile logs
  `devman watch: compile exited 1`. A Python error in compile logs its traceback.
- **Option.** `--debounce` takes a watchexec duration (`300ms`, `2s`, `1m`; a bare
  number is ms). The default is `300ms`. The watcher passes it to watchexec and
  uses it as its own quiet time.
- **Tests.** The integration tests start `devman watch` as a child process, with
  the fake `dagu` on `PATH`. `tests/conftest.py` now holds the `fake` fixture.
- **Size.** `watch.py` has 256 lines against a budget of 200 (+28%). It holds the
  canary, the batch reader and the restart logic.

**Interfaces fixed:** the watcher command line, the fixed ignore list.

---

## Stage 6 — `run`, `status`, `show`, `doctor`

**Goal:** the person-facing commands that start a run and show what runs where,
and a doctor that checks the whole plane.

**Concept:** §6, §11.

### Files

- `src/devman/dagu.py`: add `last_run(dag_name) -> dict | None` (Dagu REST
  `GET /api/v1/dags/<file>/dag-runs`, one result, through `urllib`; host and
  port from `DEVMAN_DAGU_CONFIG`) and `version() -> str`.
- `src/devman/status.py`: `status` and `show`.
- `src/devman/doctor.py`.
- `cli.py`: the four commands (§A.5).
- `tests/test_status.py`, `tests/test_doctor.py`, e2e additions.

### `devman run <workflow> [--project P] [KEY=VALUE…]`

A manual event: `router.emit(event="manual", subjects=[workflow], implicit=True)`.
`implicit` skips the `on` table and matches the named workflow directly. Refuse
(exit 2) when the project has no such workflow in `compile.json`. When the
project is stale, print a warning to stderr and run the old file.

**Doctor and the library (decision Q7).** Add a check: every `action:` named in
`<library>/workflows/*.yaml` exists as a key under `actions:` in
`<library>/base.yaml`. A missing action fails the check and names the file and
the action. The count of doctor checks rises by one.

### `devman status [project] [--json]`

Default project: found from the current directory. With no project and no
match, show every project, one line each. For one project, print per workflow:
source (`project` or `library`), triggers (`event match`), schedule (read from
the compiled file), queue (the file's `queue:`), last run
(time and status from Dagu), and the compile state. `--json` prints §A.7. When
Dagu does not answer, print `last run: Dagu unreachable` and exit 0 — status
still has local facts to show.

### `devman show <workflow> [--project P]`

Print `# compiled: <path>` and `# source: <path>`, then the compiled file.

### `devman doctor`

One line per check, `ok` or `FAIL <reason>`. Exit 0 only when every check passes.

| Check | How |
|---|---|
| services | `systemctl --user is-active devman-dagu devman-watch` |
| Dagu version | `dagu version` equals `DEVMAN_DAGU_VERSION` |
| Dagu answers | the REST API on the configured port |
| compile clean | `compile.json` has no refused project and no orphan |
| `dags/` matches | every file in `compile.json` exists with its sha256; no other `*.yaml` under `dags/` |
| Dagu sees every DAG | the REST DAG list contains every compiled DAG name. This catches the "No DAGs found" collision |
| project paths | every `path` exists |
| repository view | for each project, `<path>/.devman/workflows` and `<path>/.devman/runs` resolve to the expected targets (warn only before Stage 10) |
| checkout markers | every `path` holds `.git` or `.jj`, so the guard (§A.8) passes |
| handler log | `<state>/handler.log` is empty or holds no line newer than the last doctor run |
| watch budget | the watcher's inotify watch count is under 50% of `fs.inotify.max_user_watches` (M5) |

### Tests

- Unit with a fake REST server (`http.server` on a free port): status text and
  JSON, unreachable Dagu, doctor pass and each doctor failure.
- e2e: `devman run` then `devman status --json` shows `succeeded` for that run.

**Verify:** the common verify command, plus `devenv tasks run -v base:e2e`.

**Risk:** the REST shape of a run on 2.20.1 is read from the API file, not run.
The first task of this stage is one `curl` against the e2e server. If the shape
differs, adapt `last_run` and nothing else.

**As built (2026-10-15).** Each item changes or fills in the plan above.

- **The REST shape of a run, confirmed on 2.20.1 with one real call** against a
  temporary Dagu (ports 18120 and 51120). `GET /api/v1/dag-runs?name=<dag>&limit=5`
  returns `{"dagRuns": [...]}`, newest first. A run holds `dagRunId`, `name`,
  `statusLabel` (`succeeded`), `status` (4), `startedAt`, `finishedAt`, `queuedAt`,
  `params`, `labels` and `triggerType`. `GET /api/v1/dags/<file>/dag-runs` answers
  404. `last_run` filters on the exact `name`, because `name` is a filter and the
  plan does not rely on it being exact. The plan's path (`/dags/<file>/dag-runs`)
  was wrong; the code uses `/dag-runs?name=`.
- **`dagu.get(config, path)`** is the one REST call. It reads host and port from
  the Dagu config (defaults `127.0.0.1:8080`). `last_run`, `version` and doctor's
  API check use it.
- **`Event.implicit`** carries `devman run`. The router then skips the `on` table
  and matches `subjects[0]` against `compile.json` `workflows`. An unknown name
  is a refusal (exit 2) and writes an event line. `run` prints a warning on stderr
  when the project is stale.
- **Doctor has eight checks, not eleven.** The watcher check scans `/proc` for a
  `watchexec` process that carries `--project-origin=<state>`; it needs no
  `systemctl`, so it works in tests and in any shell. The watch budget sums the
  `inotify wd:` lines of that process's inotify descriptors and compares them
  with `fs.inotify.max_user_watches` (fails above 50 %, M5). The checks:
  Dagu answers, Dagu version (skipped without `DEVMAN_DAGU_VERSION`), watcher
  runs, watch budget, compile clean, `dags/` matches `compile.json` (hash per
  file, no stray file), checkouts hold `.git` or `.jj` (the guard's condition),
  library actions. Dropped: "Dagu sees every DAG", "repository view" (Stage 10
  adds the links), and "handler log" (Stage 7 adds it with the handler).
- **`status` with no project and no match** prints one line per project; `--json`
  prints the full list. A missing `compile.json` exits 2.
- **Size.** `status.py` 148 (budget 160), `doctor.py` 176 (budget 160, +10 %),
  `dagu.py` 101 (budget 130), `cli.py` 181 (budget 170). `src/devman/` totals
  1,781 lines against 1,600 (+11 %). No module passes its budget by 30 %.

**Interfaces fixed:** §A.5, §A.7, doctor exit codes.

---

## Stage 7 — the library and the `base.yaml` actions

**Goal:** the shared workflows and the shared actions that every project can
take, and the `done`/`failed` event source. The library is overlay content
(decision Q7); this repository ships the guard and a seed copy for tests.

**Concept:** R6, R7, §7 (`done`, `failed`), §8. **Depends on M1, M2 and M3.**

### Files

- `dagu/guard.sh` (this repository): the checkout guard (§A.8). It is
  mechanism. `nix/hm-module.nix` installs it with `pkgs.replaceVars` (fills
  `@bash@`) and sets `DEVMAN_GUARD` to its store path.
- In the overlay, one commit: `library/base.yaml` (add `handler_on` and
  `actions`, and point `shell` at `@guard@`), `library/workflows/check.yaml`,
  `test.yaml`, `format.yaml`, `release.yaml`, and `library/README.md` (what each
  file does and what it asks of a repository; the content README).
- In this repository: the same files under `tests/fixtures/library/` as the
  seed, and `flake.nix` `checks.library-validate`.
- `devman doctor` already checks the action names (Stage 6).

### `library/base.yaml` additions

```yaml
# no `shell:` here: the compiled header sets the guard shell (see "As built")

handler_on:
  exit:
    shell: "@bash@"         # the handler must not depend on the guard
    run: |
      case "$DAG_RUN_STATUS" in
        succeeded) ev=done ;;
        failed)    ev=failed ;;
        *)         exit 0 ;;
      esac
      setsid -f "@devman@" emit "$ev" \
        --project "${DAG_NAME%.*}" --subject "${DAG_NAME##*.}" --source dagu \
        </dev/null >>"@stateDir@/handler.log" 2>&1 || true
      exit 0

actions:
  devman.task:
    input_schema:
      type: object
      required: [task]
      properties: { task: { type: string, minLength: 1 } }
    template:
      run: |
        devenv tasks run -v "<task input>" || {
          echo "devman.task: task <task input> failed" >&2; exit 1; }
```

**The handler rules (M3).** A base `handler_on` reaches every DAG, from `start`
and from the queue. The run's final status waits for the handler, and a failing
handler turns a succeeded run into a failed one. So the handler:

- uses one key, `exit`, and maps `DAG_RUN_STATUS` to the event. `succeeded`
  gives `done`, `failed` gives `failed`, any other status (aborted, partially
  succeeded) gives no event;
- detaches the emit with `setsid -f` and closes its input, so the run never
  waits for the router (M3 round 4: a detached child ended 10 s after the run);
- always exits 0, so a router failure never changes the run's result. The
  router writes its own event line, and `handler.log` holds its stderr;
- runs with plain bash, not the guard. A run in a vanished checkout is already
  failed by the guard; the handler must still report `failed`.

**The merge rule (M3).** A DAG's own `handler_on` replaces the base handler **of
the same key only**. Base keys the DAG does not set stay. devman uses only
`exit`, so a source may set `success`, `failure` and `cancel` freely. Compile
refuses a source that sets `handler_on.exit` (§A.2), because it would drop the
`done`/`failed` event silently.

`<task input>` stands for the input reference that `dagu schema dag` documents
for `actions.*.template` on 2.20.1. The stage test proves it with one real run.
`${DAG_NAME%.*}` works because a workflow name has no dot (§A.1, rule 4). M3
confirmed that the handler sees `DAG_NAME`, `DAG_RUN_STATUS` and `DAG_RUN_ID`.

### The library

| File | Queue | Steps |
|---|---|---|
| `check.yaml` | `light` | `action: devman.task`, `task: base:check` |
| `test.yaml` | `normal` | `action: devman.task`, `task: base:test` |
| `format.yaml` | `light` | `action: devman.task`, `task: format:fmt` |
| `release.yaml` | `heavy` | step 1 `devman.task base:test`; step 2 `devman.task release:build`; `type: chain` |

**`format` has no loop receipt.** The old file stored a tree hash in
`.devman/.runs/`. That path goes. `format:fmt` is idempotent: a format that
writes files causes one more `save`, the second run changes nothing, writes
nothing, and the loop ends. The cost is one extra light run per save.

**`release` runs the test itself.** The old gate read `metadata.jsonl` to find
the last test run. That file goes (§12). Running the test as step 1 gives the
gate something that can fail, with no state to read. `release` builds and does
not publish (AGENTS.md: irreversible work stays out).

No library file has a `schedule:`. Fleet upkeep is one overlay workflow (Stage 10).

### Tests

- `checks.library-validate`: render each file in `tests/fixtures/library/` for a
  fixture project and run `dagu validate` with the filled `config.yaml` and the
  compiled `base.yaml`.
- A test edits a file in a temporary overlay `library/workflows/` while the
  watcher runs and sees a recompile (the live-edit property of Q7).
- e2e: a fixture project (made with `git init`, so the guard passes) with a
  `devenv`-free stand-in for `devenv tasks run` (a script named `devenv` first
  on `PATH` that exits with a set code). A
  passing `check` emits `done`; a failing one emits `failed` and names the task
  on stderr. Both lines appear in `events.jsonl`.
- e2e: an `on` entry `event = "done", match = "check", run = "test"` makes a
  `check` run start a `test` run.
- e2e: with `devman` replaced by a script that sleeps 10 s and exits 1, a
  passing `check` still ends `succeeded` in under 2 s.
- e2e, the guard: compile a fixture project, then rename its checkout away. A
  `check` run ends **`failed`** and its log names the missing checkout. Dagu
  does create an empty directory at the old path (M2); the guard fails anyway,
  because that directory has no `.git` and no `.jj`. Delete it, restore the
  checkout, and the run succeeds.
- e2e, the guard: a project workflow with a plain `run:` step (no action) fails
  the same way.

**Verify:** the common verify command, plus `devenv tasks run -v base:e2e`.

**Depends on M3 (answered: inherited; blocking; can fail the run).** The handler
rules and the merge rule above are the result.

**Depends on M2 (answered: Dagu creates the directory and succeeds).** The
guard in §A.8 is the result.

**Depends on M1:** see Stage 1.

**As built (2026-10-15).** Each item changes or fills in the plan above.

- **A `shell:` in `base.yaml` is ignored by 2.20.1.** Measured with a probe step
  (`echo $0`) on `dagu start` and on a server run: with `shell: <guard>` in the base
  config, the step still ran under `$SHELL` (zsh) and the guard never ran. `env`
  and `handler_on` from the same base config did reach the DAG. `default_shell` in
  `config.yaml` only sets the `SHELL` variable of the step. A `shell:` in the DAG
  file itself works (`-c <script>` for a `run:` step, a script path for `script:`).
  So **the compiled header sets `shell:` to `DEVMAN_GUARD`** (`render` takes a
  `guard` argument), the seed `base.yaml` has no `shell:` line, and the `@guard@`
  token is gone (three tokens remain). Compile refuses with exit 2 when
  `DEVMAN_GUARD` is not a file, because every step would fail. CONCEPT §3.1, §5
  and §5.1 say the same. Stage 1's `shell: "@bash@"` base line is dropped: the
  header's shell makes it dead.
- **The package substitutes the guard's `@bash@`.** `nix/package.nix` runs
  `substituteInPlace` on the installed copy and its install check runs the guard
  on a directory with `.git` (passes) and one without (fails, names the marker).
  The source file in `dagu/guard.sh` keeps the token, so tests fill it with the
  test bash (`tests/conftest.py`, `standin`).
- **The action input reference is `{{ .input.<name> }}`.** Dagu 2.20.1 expands a
  custom action template with Go template syntax at build time, so the plan's
  `<task input>` became `{{ .input.task }}`. `input_schema` is required. Because
  the value lands in script text, the schema limits `task` to
  `^[A-Za-z0-9][A-Za-z0-9:_.-]*$` and refuses other keys.
- **The handler uses the legacy `command:` form.** Dagu 2.20.1 rejects `run`
  together with `shell` ("run cannot be used together with shell"). The handler
  needs its own `shell` to opt out of the guard, so it is `shell:` plus
  `command:`. It validates and runs, and `DAG_RUN_STATUS` is `succeeded` or
  `failed` as the plan says.
- **Dagu lists runs by start second.** `GET /dag-runs?name=...&limit=1` is not a
  safe "newest" when two runs start in one second. `last_run` takes the first of
  five, which is newest to the second. The e2e tests pick a run by ID.
- **Doctor gains no `handler.log` check.** The tail check needs a "last doctor
  run" marker the plane does not keep. `handler.log` holds the stderr of a failed
  emit; read it when a `done` event is missing. The router writes its own line for
  every call it receives.
- **e2e results** (real Dagu 2.20.1, temporary directories, ports from 18110/51110):
  a library `check` through `devman run` ends `succeeded` and writes a `done` line
  with `source: dagu`; a failing task ends `failed`, names `base:check` on stderr
  and writes `failed`; `done` on `check` starts `test`; a handler that sleeps 10 s
  and exits 1 leaves the run `succeeded` in under 8 s; a checkout renamed away
  makes both a library step and a plain `run:` step fail with the guard message,
  Dagu leaves an empty directory at the old path (M2), the handler still writes
  `failed`, and the restored checkout runs green.
- **The live library** is in the overlay, committed as `d72e3980` in
  `~/.config/devman` (only `library/`; that repository is on a detached HEAD, so
  the commit has no branch). It equals `tests/fixtures/library/`.
- **Size.** Stage 7 added 9 lines to `src/devman/` (the guard check in `compile.py`,
  the `shell` header line in `render.py`; the `guard` token left `compile.py`).
  The total is 1,790 lines against 1,600 (+12 %). No module passes its budget by
  30 %.
- **`checks.library-validate`** compiles the seed library for a fixture project with
  the packaged guard, the real `config.yaml` template and `dagu validate`.

**Interfaces fixed:** the action name `devman.task` and its input, the library
names, the library layout in the overlay, the `done`/`failed` subject.

---

## Stage 8 — the agent workflow example

**Goal:** prove the Dagu-native agent pattern with one example workflow and a
test, with no devman code.

**Concept:** R9, §9.

### Files

- `library/examples/agent-task.yaml` in the overlay (and a copy under
  `tests/fixtures/library/examples/`): not a library workflow (compile reads
  only `library/workflows/*.yaml`, so `examples/` is never taken). An owner copies it into
  `workflows/<project>/`. Steps: `git.worktree.add` on a new branch with a fixed
  `path` under `.worktrees/`; `harness.run` with `provider`, `model`,
  `max-budget-usd` and `permission-mode`, with an explicit `working_dir` (the
  built-in actions do not pass through the guard shell, §A.8); a step
  that commits the work tree to the branch; `human.task` for review;
  `git.worktree.remove`.
- `library/README.md`: one section on the pattern and the reason for step 3
  (SPIKES spike 3: `remove` with `force: true` deleted uncommitted output).

### Tests

- `checks.library-validate` validates the example.
- No test calls a real model. A manual check before landing: one run with
  `model: haiku` and `max-budget-usd: 0.25` in a scratch repository. Record the
  result in the lane description.

**Verify:** the common verify command.

**As built (2026-10-16).** Each item changes or fills in the plan above.

- **`human.task` needs `id:`.** Dagu 2.20.1 refuses the step without an explicit
  `id` ("action human.task requires an explicit id"). The example sets `id: review`.
- **A step uses `run:`, not `command:`.** Dagu 2.20.1 warns that `command:` is
  deprecated.
- **`remove` never sets `force`.** The example is stricter than the plan: a work
  tree with uncommitted output fails the remove step. The branch stays.
- **A relative `path` for the git actions resolves from the repository root**
  (`dagu schema dag`). The example uses `.worktrees/agent-task`. The `harness.run`
  and `commit` steps use `${DEVMAN_PROJECT_DIR}/.worktrees/agent-task` as their
  `working_dir`.
- **The commit step fails when the agent changed nothing.** A run that succeeds
  with no work would break property 4.
- **`checks.library-validate`** copies the example into the fixture project's own
  `workflows/p/` and expects five compiled files. Compile never takes the example
  from the library (a unit test proves it).
- **Manual check.** No model call. A stub `claude` first on `PATH` ran the example
  on real Dagu 2.20.1 in a scratch repository. `harness.run` built
  `claude -p <prompt> --max-budget-usd 2 --model sonnet --permission-mode
  acceptEdits`. The commit step made one commit on `agent/task`. `human-task
  complete` then `dagu retry` ran `remove`: the work tree went, the branch and its
  commit stayed. The plan asked for a real `haiku` call; spike 3 already covers it.
- **Unit tests.** `tests/test_library.py` gains three: the step order and the
  commit guard, compile of the example as a project workflow, and refusal to take
  it from the library.
- **No change to `src/devman/`.**

---

## Stage 9 — documentation

**Goal:** rewrite every document to describe the new design and nothing else.

**Concept:** §1; AGENTS.md law (library versus content split).

### Files in this repository

| File | Content |
|---|---|
| `README.md` | what devman is (§1), install (§10), the manifest (§4), the CLI (§11), the files (§3). Under 200 lines |
| `USER.md` | the developer view: read `.devman/workflows`, read `.devman/runs`, `devman status`, `devman run`, add a workflow, take a library workflow, add an event source |
| `AGENTS_GUIDE.md` | the map: modules and their budget, the data flow (manifest → compile → `dags/` → Dagu; event → router → `dagu enqueue`), the interfaces in §A, how to test, how to diagnose |
| `AGENTS.md` | the law, rewritten: what the repository is, the scope table (mechanism docs here; `library/README.md` for content; the overlay for per-project workflows), the properties that still hold (boundary test, property 4, Python for logic, secrets declared, STE writing, read the log before you delete a line), verify, choosing what to automate (drop the tier table; keep the questions and the measured trade-offs that still apply) |
| overlay `library/README.md` | already written in Stage 7 and Stage 8, in the overlay |

Delete any statement about registries, generations, groups, tiers, link
modules, `.devman/project.toml` or `triggers.toml`.

### The skills

The `devman`, `devman-workflow` and `devman-adopt` skills are **not** in this
repository. They live in the overlay at
`~/.config/devman/projects/devman/agents/skills/`, and `.agents` links to them.
Rewrite them in an overlay commit in the same stage:

- `devman`: the concept in one page, the CLI, the diagnosis order (`devman
  status`, `devman doctor`, `events.jsonl`, the Dagu UI).
- `devman-workflow`: how to write `workflows/<project>/<name>.yaml`, the header
  rules (§A.2), the `on` entries, a test loop (`devman compile <p>`, `devman run`,
  `devman status`).
- `devman-adopt`: becomes "add a project": one table in `projects.toml`, the
  task names the library calls, the linkman lines. A repository commits nothing.

**Verify:** the common verify command; read each document once against §A.

**As built (2026-10-16).** Each item changes or fills in the plan above.

- **Files.** `README.md` (175 lines), `USER.md`, `AGENTS_GUIDE.md` and `AGENTS.md`
  describe the new design only. `AGENTS.md` keeps the charter pointer, the verify
  commands, the version-control rules and the writing rule. It drops the tier
  table and the properties of the old design.
- **The skills** are real directories in the overlay, not links:
  `~/.config/devman/projects/devman/agents/skills/{devman,devman-workflow,devman-adopt}/SKILL.md`.
  One overlay commit rewrites all three.
- **The overlay `library/README.md`** had its content in Stage 7 and Stage 8.
  Stage 9 changes nothing there.
- **Deferred to Stage 10.** The view links. `projects/devman/links.yaml` still
  links `.devman/workflows` to the old `projects/devman/workflows/`, and that
  directory still holds the old overlay README. `devman-adopt` step 5 says the
  new links arrive with the cutover. The skills name no `devman` repository file
  that Stage 10 removes.
- **No change to `src/devman/`.** Verify ran `base:check`, `base:unit`,
  `base:e2e`, `base:test` and `nix build .#devman`.

---

## Stage 10 — the cutover

**Status: done, 2026-10-16.** See `CUTOVER_LOG.md`.

**Goal:** switch the machine to the new plane, remove every trace of the old
one, and prove one run per event source.

**Concept:** R11, R12, §6, §10. **Depends on M4** (answered: a linkman link to
`dags/<project>/` outside `dags_dir` is safe, so the links in step 3 point
straight at the compiled directory).

Run it as one session. Steps 2 to 5 change other repositories; each is its own
lane in that repository.

1. **Release.** Tag this repository `v0.9.0` and push the tag (open question
   Q3).
2. **Overlay content** (`~/.config/devman`, one commit):
   - Copy the Stage 7 library into `library/` (`base.yaml`, `workflows/`,
     `README.md`). A library edit is live from here on.
   - Move `projects/devman/workflows/*.yaml` to `workflows/devman/`. Rewrite
     each to the new contract: no `.devman/.runs/` path, no `env:`, steps through
     `devman.task` where a task exists. Drop the ones that only served the old
     plane (`plane-report`, `stack-validate` if it checks the old registry).
   - Add `workflows/devman/upkeep.yaml`: `schedule: "20 0 * * *"`, `queue:
     light`. It runs `devman doctor` and loops over `devman status --json` to
     list failed last runs. It exits 0 when it ran. Findings go to a notification
     (open question Q2).
   - Delete `dags/` (the old link farm) and every `projects/*/workflows/`.
   - Remove the `dags/` and `**/.runs/` lines from the overlay `.gitignore`.
3. **linkman declarations:** in each `projects/<p>/links.yaml`, set
   `.devman/workflows` to `${env.HOME}/.local/state/devman/dags/${repo.name}/`
   and add `.devman/runs` with `${env.HOME}/.local/state/devman/runs/${repo.name}/`.
   Confirm for all 33 projects that `repo.name` equals the manifest name. A
   mismatch needs an explicit target, not `${repo.name}`. Add the commit and land
   hook links only if Q1 is answered.
4. **nix-meta** (one lane):
   - Bump the `devman` input to the tag. Check that `vendomat`'s
     `inputs.devman.follows` still evaluates. If vendomat reads a deleted devman
     file, drop that `follows` line.
   - Replace `profiles/devman.nix`: import `inputs.devman.homeManagerModules.default`
     into `home-manager.users.${username}`, set `services.devman.enable = true`,
     and set `users.users.${username}.linger = true` at the machine level.
     Delete the `nixosModules` import and `registryDir`.
   - `profiles/devlayer.nix` reads `share/devman/link-module.nix`, which no
     longer exists. Remove its pointer step after `grep -r current.nix
     ~/.config/devman` shows no reader (open question Q5).
5. **Stop the old plane:** `systemctl --user stop devman-watch dagu
   devman-dagu-reload.path`. Wait for no `dagu` process (`pgrep -u $USER dagu`).
6. **Delete the old state** (R12):
   - `~/.local/share/devman`
   - `~/.local/state/vendomat/devman`
   - everything in `~/.local/state/devman` (the old `projects/`, `watch/`,
     `reload.target`)
   - `~/.local/share/dagu` (old history and DAG index; open question Q4)
   - in each of the 33 repositories: `.devman/.runs/`, the old
     `.devman/workflows` link, and the `.devman/.runs/` line in
     `.git/info/exclude`
7. **Switch:** `sudo nixos-rebuild switch --flake ~/Documents/Projects/nix-meta#server`
   (Home Manager still runs as a NixOS module on this machine). Then
   `systemctl --user list-unit-files 'dagu*' 'devman*'` shows only
   `devman-dagu` and `devman-watch`.
8. **Links:** run linkman's reconcile for each repository. Check that
   `.devman/workflows` and `.devman/runs` resolve and are in `.git/info/exclude`.
9. **Prove it:**
   - `devman doctor` exits 0.
   - `devman status` in this repository lists check, test, format and release.
   - `devman run check` in this repository succeeds; its log is under
     `.devman/runs/`.
   - Save a `.py` file here: one `save` line and one `format` run in
     `events.jsonl`. A save under `.scratch/` gives a `save` line with no match.
   - The `check` run's `done` event appears in `events.jsonl`.
   - The Dagu UI groups the workflows by project.
10. **Record** the dated machine evidence in `AGENTS.md` (number of projects,
    number of DAG files, Dagu version) and write `CUTOVER_LOG.md` in this
    directory. Restore `devman doctor` in the AGENTS.md verify section.

**Rollback:** pin nix-meta's `devman` input back to `v0.7.0` and switch. The
old state is gone, so the old plane would start empty. R12 accepts this.

---

## A. Interfaces

### A.1 `projects.toml`

```toml
# ~/.config/devman/projects.toml

[devman]                                  # table key = project name
path = "~/Documents/Projects/devman"      # required
take = ["check", "test", "format", "release"]   # optional, default []

[[devman.on]]                             # optional, any number
event   = "save"                          # required
match   = "**/*.py"                       # required: a glob or a list of globs
exclude = [".scratch/**"]                 # optional: a list of globs
run     = "format"                        # required
```

Rules. Each broken rule refuses that project only, with the quoted reason.

1. Every top-level item is a table. Else: file-level error `"<key> is not a
   table"`.
2. The project name matches `^[A-Za-z0-9][A-Za-z0-9._-]*$`. Else `"project name
   <name> does not match [A-Za-z0-9][A-Za-z0-9._-]*"`. TOML needs quotes for a
   name with a dot: `["loci.nvim"]`.
3. Allowed keys: `path`, `take`, `on`. In `on`: `event`, `match`, `exclude`,
   `run`. Else `"unknown key <key>"`. A typo must not become a silent no-op.
4. A workflow name (in `take`, in `run`, or a file stem in `workflows/<project>/`)
   matches `^[A-Za-z0-9][A-Za-z0-9_-]*$` — **no dot**. Else `"workflow name
   <name> must not contain a dot"` or the grammar text.
5. `path` is a string. After `~` expansion it is absolute. Compile (not the
   parser) refuses a path that is not a directory.
6. Two projects with the same resolved `path` are both refused: `"path shared
   with <other>"`. A nested path is allowed; the deepest match wins.
7. `event` matches `^[a-z][a-z0-9._-]*$`. `match` is a non-empty string or a
   non-empty list of non-empty strings. `exclude` is a list of non-empty strings.
8. **The watcher ignores these directories in every project, always:** `.git`,
   `.jj`, `.devenv`, `.direnv`, `.venv`, `node_modules`, `__pycache__`, `.gitman`,
   `.worktrees`, `.devman`. They are generated or tool-owned in every repository,
   and `.devman` holds the links to compiled files and run logs.
9. **Loop refusal.** Build a graph: an `on` entry with event `done` or `failed`
   is an edge from each workflow its `match` accepts to its `run`. A cycle refuses
   the project: `"on entries form a loop: check -> test -> check"`.

Glob semantics: `PurePosixPath(subject).full_match(glob)`. `*` does not cross
`/`. `**` matches zero or more path parts. There is no brace expansion; use a
list.

What each event's subject is:

| Event | Subject |
|---|---|
| `save` | a path relative to the project |
| `commit`, `land` | a ref name, such as `main` |
| `done`, `failed` | the workflow name, without the project prefix |
| `manual` | the workflow name (implicit match) |
| any other | whatever the source passes |

### A.2 The rendered file

File: `<state>/dags/<project>/<project>.<workflow>.yaml`. The DAG name is the
stem, `<project>.<workflow>`. Rule 4 makes it unique and splittable at the last
dot.

```yaml
# devman: compiled file. Do not edit. Edit the source and run `devman compile`.
# devman: project=devman workflow=check origin=library
# devman: source=/home/andrew/.config/devman/library/workflows/check.yaml
# devman: source-sha256=3f1c…
working_dir: "/home/andrew/Documents/Projects/devman"
log_dir: "/home/andrew/.local/state/devman/runs/devman"
shell: "/nix/store/…-devman-0.9.0/share/devman/dagu/guard.sh"
group: "devman"
labels:
  project: "devman"
env:
  - DEVMAN_PROJECT_DIR: "/home/andrew/Documents/Projects/devman"
params:
  - DEVMAN_EVENT: ""
  - DEVMAN_SUBJECT: ""
# devman: source text follows
queue: light
steps:
  - action: devman.task
    with: { task: base:check }
```

Rules:

- The header is comments, then the keys, then the source text unchanged.
  Values are JSON strings (valid YAML), so any path is quoted correctly.
- Compile parses the source's first YAML document to learn its top-level keys.
  The first document must be a mapping. Else refuse: `"<file>: the first document
  is not a mapping"`.
- **No `name:`.** The header never sets `name:`, and a source that sets it fails
  `dagu validate` ("entrypoint document must not define name", M2), which
  refuses the project. The DAG name is the file stem.
- **Header-owned keys:** `env`, `log_dir` and `shell` at the top level (the header
  sets `shell` to `DEVMAN_GUARD`; Stage 7 moved it there from `base.yaml`), and
  `handler_on.exit`. A source that sets one is refused:
  `"<file>: top-level env is set by devman; use step env or params"`, and the
  same form for the others. The reasons: without the header `env`,
  `DEVMAN_PROJECT_DIR` is silently missing and the guard cannot work; without
  the header `log_dir`, the run logs leave `.devman/runs`; a top-level `shell`
  replaces the base guard shell (§A.8); a DAG `handler_on.exit` replaces the base
  handler and drops the `done`/`failed` event (M3: the merge is per key).
- **`params`:** the header declares `DEVMAN_EVENT` and `DEVMAN_SUBJECT` with
  empty defaults (M6: declared names give a run that the router did not start a
  defined empty value). A source that sets its own `params:` must declare both
  names in it, in list or map form. Else refuse: `"<file>: params must declare
  DEVMAN_EVENT and DEVMAN_SUBJECT"`. Compile cannot merge two `params:` keys
  without rewriting the source.
- **Superseded by project 048 finding F1:** `working_dir` is header-owned and
  always comes from the manifest. A source that sets it is refused. **Source-wins
  keys:** `group` and `labels`. The header adds each only when the source does
  not set it.
- **Labels are lowercased by Dagu** (M4). The header writes the project name as
  given; a filter on the REST API uses the lowercase form,
  `project=<project, lowercased>`.
- A source whose first non-blank, non-comment line is `---` loses that line, so
  the header and the source stay one document. Later `---` documents (local
  sub-DAGs) stay as written.
- **Superseded by project 048 finding F3:** a source queue was optional and
  could inherit the base queue. Every source now requires a nonempty string
  queue. It must name a queue in Dagu config. An unknown queue refuses the
  source: `"<file>: queue <q> is not configured; configured: light, normal, …"`.
  M1: an undefined queue skips the limit, and Dagu accepts the file silently.

### A.3 `compile.json`

```json
{
  "version": 1,
  "compiled_at": "2026-10-15T21:04:11+00:00",
  "devman": "0.9.0",
  "orphans": ["oldproject"],
  "projects": {
    "devman": {
      "status": "ok",
      "stale": false,
      "at": "2026-10-15T21:04:11+00:00",
      "path": "/home/andrew/Documents/Projects/devman",
      "reasons": [],
      "on": [
        {"event": "save", "match": ["**/*.py"], "exclude": [".scratch/**"], "run": "format"}
      ],
      "workflows": {
        "check": {
          "dag": "devman.check",
          "file": "/home/andrew/.local/state/devman/dags/devman/devman.check.yaml",
          "origin": "library",
          "source": "/home/andrew/.config/devman/library/workflows/check.yaml",
          "sha256": "9a0e…"
        }
      }
    },
    "broken": {
      "status": "refused",
      "stale": true,
      "at": "2026-10-15T21:04:11+00:00",
      "path": "/home/andrew/Documents/Projects/broken",
      "reasons": ["take names check2, which is neither in workflows/broken/ nor in the library"],
      "on": [],
      "workflows": {}
    }
  }
}
```

- `status`: `"ok"` or `"refused"`.
- `stale`: `true` when refused and the project still has files from an earlier
  compile. Then `on` and `workflows` keep the values of the last good compile, so
  the router and status describe the files Dagu runs. A project refused on its
  first compile has `stale: false`, empty `on` and empty `workflows`.
- `sha256` is the hash of the rendered file.

### A.4 `events.jsonl`

One JSON object per line, one line per `devman emit` or `devman run` call:

```json
{"at": "2026-10-15T21:05:02.114+00:00", "event": "save", "project": "devman", "source": "watcher", "subjects": ["src/devman/compile.py"], "fields": {}, "stale": false, "matches": [{"workflow": "format", "dag": "devman.format", "run_id": "0b6c…", "result": "enqueued"}], "refusal": null}
```

- `source`: the `--source` value; default `"cli"`. The watcher writes
  `"watcher"`, the base handlers `"dagu"`, `devman run` writes `"manual"`.
- `fields`: the `KEY=VALUE` arguments.
- `matches[].result`: `"enqueued"` or `"failed"`; a failed one adds `"error"`.
- `refusal`: `null`, or a string when the router refused the whole event (no
  project found, unknown project, unknown workflow for `run`). Then `project` may
  be `null` and `matches` is `[]`.
- An event with no match has `"matches": []` and `"refusal": null`.

Nothing rotates the file. Open question Q6.

### A.5 The CLI

```
devman --version
devman compile [--all] [PROJECT ...]
devman emit EVENT [--project P] [--subject S]... [--source NAME] [KEY=VALUE]...
devman run WORKFLOW [--project P] [KEY=VALUE]...
devman status [PROJECT] [--json]
devman show WORKFLOW [--project P]
devman doctor
devman watch [--debounce DURATION]
```

`emit` grammar:

- `EVENT`: `^[a-z][a-z0-9._-]*$`.
- `--subject` repeats. Zero subjects is allowed; then only an `on` entry with
  `match = "**"` can match, because `full_match` needs a subject. In that case
  the router matches against the empty string, which `**` accepts.
- `KEY=VALUE`: `KEY` matches `^[A-Za-z_][A-Za-z0-9_]*$`. The prefix `DEVMAN_` is
  reserved and refused. `VALUE` is passed as given.
- The router adds `DEVMAN_EVENT` and `DEVMAN_SUBJECT` (the first subject that
  matched; empty when there is none).

Exit codes for every command: `0` success; `1` the work ran and something failed
(a refused project, a failed enqueue, a doctor finding); `2` a usage error or a
refusal before any work (bad arguments, no project for the current directory).

`watch` is the service entry point. A person does not type it.

### A.6 Environment

The Home Manager wrapper sets these. Each has a default, so the CLI also runs
from a checkout for tests.

| Variable | Default |
|---|---|
| `DEVMAN_OVERLAY` | `~/.config/devman` |
| `DEVMAN_STATE` | `~/.local/state/devman` |
| `DEVMAN_LIBRARY` | `<overlay>/library`. A test override only |
| `DEVMAN_BASH`, `DEVMAN_GUARD`, `DEVMAN_BIN` | none; fill the `base.yaml` tokens. `compile` refuses without them |
| `DEVMAN_DAGU_CONFIG` | none; commands that need Dagu refuse without it |
| `DEVMAN_DAGU_VERSION` | none; doctor skips the version check without it |
| `DAGU_HOME` | Dagu's own default |

A run sees `DEVMAN_PROJECT_DIR` (header), `DEVMAN_EVENT` and `DEVMAN_SUBJECT`
(router).

### A.7 `devman status --json`

```json
{
  "project": "devman",
  "path": "/home/andrew/Documents/Projects/devman",
  "compile": {"status": "ok", "stale": false, "at": "…", "reasons": []},
  "dagu": "reachable",
  "workflows": [
    {
      "name": "check",
      "dag": "devman.check",
      "origin": "library",
      "source": "/home/andrew/.config/devman/library/workflows/check.yaml",
      "triggers": [{"event": "land", "match": ["main"], "exclude": []}],
      "schedule": null,
      "queue": "light",
      "last_run": {"run_id": "…", "status": "succeeded", "started_at": "…", "finished_at": "…"}
    }
  ]
}
```

With no project, the output is a list of these objects.

---

### A.8 The checkout guard

**Problem (M2).** Dagu runs `mkdir -p` on a missing `working_dir` and the run
succeeds in an empty directory. A checkout that is moved or deleted after the
last compile then gives green runs that did nothing. This is the failure that
property 4 exists to prevent.

**Mechanism: a guard shell.** The compiled header sets the DAG shell to
`dagu/guard.sh` (Stage 7 as built: a `shell:` in `base.yaml` did not reach a
step on Dagu 2.20.1):

```bash
#!@bash@
# devman checkout guard (PLAN §A.8, MEASUREMENTS M2). Do not edit the installed copy.
if [ -n "${DEVMAN_PROJECT_DIR:-}" ] \
   && [ ! -e "$DEVMAN_PROJECT_DIR/.git" ] && [ ! -e "$DEVMAN_PROJECT_DIR/.jj" ]; then
  echo "devman: checkout $DEVMAN_PROJECT_DIR is gone (no .git, no .jj); refusing to run" >&2
  exit 1
fi
exec "@bash@" "$@"
```

It checks for `.git` or `.jj`, not for the directory, because Dagu creates the
directory before the first step. An empty directory has neither marker.

**Why this mechanism:**

| Option | Verdict |
|---|---|
| A DAG-level `preconditions:` in `base.yaml` or the header | Rejected. Dagu's documentation says an unmet precondition **skips** the DAG or step; it does not fail it. M2 did not measure it. A skip is a quiet non-result, not a loud failure. |
| A first step in the header | Impossible. The header cannot add to the source's `steps:` without rewriting the source. |
| A check inside `devman.task` only | Covers library workflows only. A project workflow with a plain `run:` step would still succeed in an empty directory. |
| The router refuses an event for a missing path | Kept (Stage 4), but it does not cover a scheduled run, which never passes the router. |
| **A guard shell in `base.yaml`** | **Chosen.** Every `run:` step of every workflow passes through the DAG shell, from any trigger, schedule included. It fails the step with a reason on stderr. It is one file of seven lines and needs no change to any source. |

**Limits, stated in `library/README.md`:**

- A step that sets its own `shell:` opts out of the guard. Compile refuses a
  top-level `shell:` (§A.2); a step-level `shell:` is the owner's explicit choice.
- Built-in action steps (`git.worktree.*`, `harness.run`) do not use the shell.
  The agent pattern (Stage 8) starts with `git.worktree.add`, which fails in a
  directory that is not a repository, so it is loud there too.
- The stage-7 e2e test confirms how Dagu calls the shell (`-c <script>` or a
  script path). `exec "@bash@" "$@"` passes both forms through.

---

## B. Proposed concept amendments

Each resolves an ambiguity in `CONCEPT.md`. Apply each to `CONCEPT.md` in the
stage that first depends on it.

**Applied 2026-10-15.** The owner accepted B1 to B22. The author applied them to
`CONCEPT.md` the same day, with B11 changed by decision Q7 (the library lives in
the overlay; see R13 there). A later stage that changes one still edits both files.

| # | Section | Amendment | Reason | Stage |
|---|---|---|---|---|
| B1 | §4 | A workflow name matches `[A-Za-z0-9][A-Za-z0-9_-]*`: no dot. | Project `a.b` with workflow `c` and project `a` with workflow `b.c` both give stem `a.b.c`. Without a dot in workflow names the stem is unique and splits at the last dot. | 2 |
| B2 | §4 | `on.match` takes a glob or a list of globs. `on.exclude` is an optional list of globs. | No brace expansion in the glob engine. The old `format` trigger excluded `.scratch/**`; 16 of 252 fires there did nothing. | 2 |
| B3 | §7 | The watcher ignores a fixed list in every project: `.git .jj .devenv .direnv .venv node_modules __pycache__ .gitman .worktrees .devman`. | See below. | 5 |
| B4 | §4 | Unknown keys refuse the project. Two projects with one `path` are both refused. A `done`/`failed` cycle refuses the project. | A typo or a loop would otherwise fail silently or run forever (property 4). | 2 |
| B5 | §5 | Top-level `working_dir`, `env`, `log_dir` and `shell`, and `handler_on.exit`, are mechanism-owned; a source that sets one is refused. The manifest supplies `working_dir`. `group` and `labels` follow "the source wins". | F1: a source work directory can create a wrong successful run. Skipping `env` would drop `DEVMAN_PROJECT_DIR`; skipping `log_dir` would hide the logs; `shell` and `handler_on.exit` would remove the guard and the `done`/`failed` event (B17, B18). | 3 |
| B6 | §5 | Every workflow source must name a nonempty queue string that `config.yaml` defines; compile refuses a missing or unknown queue. | F3 and M1: an undefined queue skips the limit, and Dagu accepts the file silently. An omitted queue can inherit an unsafe default. | 3 |
| B7 | §5 | A full compile deletes `dags/<p>/` of a project that left the manifest, using the previous `compile.json`. `runs/<p>/` stays. | §5 covers removed workflows and orphan sources, not removed projects. | 3 |
| B8 | §7 | The router reads `compile.json`, not `projects.toml`. | The `on` entries then always match the files Dagu runs, also for a stale project. | 4 |
| B9 | §7 | One emit enqueues each matched workflow once, however many subjects match. The run gets `DEVMAN_EVENT` and `DEVMAN_SUBJECT`. `DEVMAN_` is a reserved parameter prefix. | A save of 20 files must give one format run, not 20. | 4 |
| B10 | §7 | The watcher watches only projects with a `save` entry, compiles at start, and recompiles on a change to `projects.toml`, `workflows/` or `library/`. | Start-up compile picks up edits made while it was down. A smaller watch set lowers the M5 cost. | 5 |
| B11 | §3.1, §10 | The library and `base.yaml` live in the overlay at `library/` (`library/base.yaml`, `library/workflows/<name>.yaml`). The package ships the mechanism and `dagu/guard.sh`. `compile` fills the `base.yaml` tokens and writes `<state>/base.yaml`. `doctor` checks that every named action exists. `DEVMAN_LIBRARY` is a test override. (Q7, decided 2026-10-15.) | A library edit is live, with no switch and no release. The library is per-user content (boundary test). | 0, 3, 7 |
| B12 | §7 | `done` is Dagu success and `failed` is Dagu failure. The subject is the workflow name; the project comes from the DAG name. | §7 names the events but not their subject. | 7 |
| B13 | §8 | `format` keeps no loop receipt; `release` runs the test as its first step. | The `.devman/.runs` receipt and `metadata.jsonl` go (§12). | 7 |
| B14 | §12 | The cutover deletes `~/.local/share/dagu` too. | Old history and a 2.15 DAG index have no value (R12). | 10 |
| B15 | §5 | Compile checks `path` with a read-only test and never creates it. State the reason: Dagu creates a missing `working_dir` or `log_dir` and the run succeeds (M2). | M2. | 3 |
| B16 | §5, new §5.1 | A run-time checkout guard: `base.yaml` sets the DAG shell to a guard that fails a step when `DEVMAN_PROJECT_DIR` has neither `.git` nor `.jj` (§A.8). The router also refuses an event for a missing path. | M2: compile's check holds only at compile time. A precondition would skip, not fail. | 4, 7 |
| B17 | §7 | The `done`/`failed` source is one base `handler_on.exit` that maps `DAG_RUN_STATUS`, detaches `devman emit` with `setsid -f`, and always exits 0. | M3: the run waits for its handler, and a failing handler fails the run. | 7 |
| B18 | §5, §7 | Merge rule: a DAG's own `handler_on.<key>` replaces the base handler of that key only. devman uses `exit` only, so compile refuses a source that sets `handler_on.exit`; other keys are free. | M3. | 3, 7 |
| B19 | §7 | The router calls `dagu enqueue` with the absolute path of the compiled file, `--run-id <uuid4>` and `--labels devman.event=<event>`, and passes fields as `-- KEY=value`. It never uses `--name` or `--default-working-dir`. | M4: the CLI does not find a subdirectory DAG by name. M6: `--name` splits history; `enqueue` ignores `--default-working-dir`; a duplicate run ID is refused. | 4 |
| B20 | §5 | The header never sets `name:`; it declares `params:` `DEVMAN_EVENT` and `DEVMAN_SUBJECT` with empty defaults. A source with its own `params:` must declare both. Label values are lowercased by Dagu; filters use the lowercase form. | M2 (`validate` rejects `name:`), M4 (lowercase labels), M6 (undeclared params pass silently). | 3 |
| B21 | §7, §10 | The watcher restarts watchexec only when the watched path set changes. A start costs about 14 s of one core and about 90,000 inotify watches for 33 repositories; ignore patterns filter events, not watches. | M5. | 5 |
| B22 | §13 | Close M1 to M6 with the answers in `MEASUREMENTS.md`. | All six are measured on 2.20.1. | 1 |

**B3, the exclusion decision.** Two layers, each for one job:

- **The fixed watcher ignore list** holds directories that are generated or
  owned by a tool in *every* repository. A write there is never a save. Filtering
  them in watchexec means no event, no Python work and no `events.jsonl` line.
  The old watcher had the same list and needed it, because `--project-origin`
  turns off `.gitignore` discovery (old Stage 3 S5). `.devman` is new: it holds
  the links to run logs, and a run that writes a log must not become its own
  next event. The list is fixed in code, not configurable, because no project
  wants a save event from these directories.
- **`exclude` on an `on` entry** holds what is true for one project and one
  trigger, such as devman's `.scratch/**`. It lives in the router, so it works for
  every event type, not only `save`, and `events.jsonl` still records the event
  with no match. That record answers "why did this not run?".

One layer alone fails: a fixed list cannot know `.scratch/`, and an `exclude` on
every entry would repeat `.git/**` in 33 tables. `.gitman` and `.worktrees` go
in the fixed list because gitman and agent work trees create them in every
repository. The devman entry then needs only `exclude = [".scratch/**"]`.

---

## C. Size budget

Core Python in `src/devman/`, counted by `wc -l`, comments included:

| Module | Budget | As built | Holds |
|---|---|---|---|
| `cli.py` | 170 | 182 | Typer app, one function per command, exit codes |
| `paths.py` | 50 | 78 | `Paths` from the environment |
| `manifest.py` | 180 | 208 | TOML load, rules 1 to 9, `matches` |
| `render.py` | 110 | 117 | the header, source checks |
| `compile.py` | 260 | 329 | resolve, validate, publish, record, lock |
| `dagu.py` | 130 | 90 | `validate`, `enqueue`, `last_run`, `version`, config read |
| `router.py` | 180 | 191 | find project, match, enqueue, record |
| `watch.py` | 200 | 251 | watchexec, batching, restart |
| `status.py` | 160 | 135 | `status`, `show`, `run` |
| `doctor.py` | 160 | 168 | the eleven checks |
| **Total** | **1,600** | **1,749** (plus 6 in `__init__` and `__main__`) | concept target ~1,500 |

Other files: `dagu/guard.sh` ~10, `nix/hm-module.nix` ~160, `nix/package.nix` ~70, `nix/dagu.nix`
~70, `flake.nix` ~120, `dagu/config.yaml` ~20; the overlay library ~60 (outside this repository). Tests ~1,200.

If a module passes its budget by more than 30%, stop and look for a Dagu feature
that does the same job before you continue.

---

## D. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| The guard shell is called in a form `exec bash "$@"` does not pass through | Every step fails, or the guard is skipped | The Stage 7 e2e tests run a passing and a failing case through the real scheduler before landing |
| A step-level `shell:` bypasses the guard | A run in a vanished checkout can succeed | Documented as an explicit opt-out (§A.8); the router refusal and `devman doctor` still report the missing path |
| The REST shape of a run differs on 2.20.1 | `status` and `doctor` misread | Stage 6 starts with one `curl`; only `dagu.last_run` adapts |
| The action template input syntax is unknown | `devman.task` fails to validate | Stage 7 reads `dagu schema dag` first; the library check catches it |
| A live library edit breaks every project at once | One bad `base.yaml` or action name fails all compiles or runs | Compile refuses a bad `base.yaml` before publishing; `doctor` names a missing action; the library is a git repository, so `jj undo` reverts |
| Old and new unit names coexist during the switch | Two Dagu servers on one port | New names; Stage 10 stops the old units first |
| vendomat's `inputs.devman.follows` reads a deleted file | nix-meta fails to evaluate | Stage 10 step 4 checks; drop the `follows` |
| The devlayer pointer imports a garbage-collected store path | Shell entry breaks in some repositories | Q5; remove the pointer step in the same nix-meta lane |
| `events.jsonl` grows without bound | Disk use | Q6 |
| A detached `handler_on` emit fails | `done`/`failed` lost; the run result stays correct | `@devman@` is an absolute store path; the router writes an event line for every call it receives, and `handler.log` holds the stderr of a call that died earlier. `devman doctor` reports a non-empty `handler.log` tail |
| A burst of events queues many runs of one workflow | M6: Dagu keeps every enqueue and runs them one after another | Q10 |

---

## E. Open questions for the owner

| # | Question | Options | Decision |
|---|---|---|---|
| Q1 | What emits `commit` and `land`? jj runs no hooks, and a git hook does not fire on a jj operation. | 1. A git hook linked by linkman (misses jj). 2. gitman calls `devman emit land --subject <trunk>` after it lands. 3. The watcher watches `.git/refs/heads/<trunk>`. | **Decided 2026-10-15: the recommendation stands.** 2 for `land`. Drop `commit` until a workflow needs it. Stage 10 ships without both if this is open. |
| Q2 | Where does a fleet upkeep finding go? | 1. A Dagu notification channel (Telegram, email, webhook). 2. Only the upkeep log and `devman status`. | **Decided 2026-10-15: the recommendation stands.** 2 now; add 1 when a channel exists. |
| Q3 | How does nix-meta pin the new devman? | 1. Tag `v0.9.0` and pin `git+https…?ref=refs/tags/v0.9.0`. 2. Pin a `git+file:` revision. | **Decided 2026-10-15: the recommendation stands.** 1. It matches the current pin style and gives a rollback name. |
| Q4 | Delete `~/.local/share/dagu` at the cutover? | 1. Yes. 2. Keep the old history. | **Decided 2026-10-15: the recommendation stands.** 1 (R12). |
| Q5 | Remove the devlayer pointer step in nix-meta `profiles/devlayer.nix`? It names the devman link module, which goes. | 1. Remove it with the cutover. 2. Leave it; it only warns. | **Decided 2026-10-15: the recommendation stands.** 1, after a grep shows no reader of `current.nix`. |
| Q6 | Rotate `events.jsonl`? | 1. No rotation now. 2. The upkeep workflow keeps the last 30 days. | **Decided 2026-10-15: the recommendation stands.** 1 now; 2 when the file passes 50 MB. |
| Q7 | Library from the store, the live checkout, or the overlay? | 1. The store (pinned), with `DEVMAN_LIBRARY` for development. 2. The live checkout (unpinned). 3. The central overlay (added by the owner). | **Decided 2026-10-15: option 3, the central overlay.** The library lives in `~/.config/devman/library/`. The package ships the mechanism only. Edits are live. Neither option 1 nor option 2 stands. |
| Q8 | Refuse a top-level `env` in a source (B5)? | 1. Refuse. 2. Merge into the source by rewriting its YAML (loses comments). | **Decided 2026-10-15: option 1, refuse.** |
| Q9 | Home Manager as a NixOS module now, or standalone first? | 1. Import into today's `home-manager.users.andrew`. 2. Wait for vendomat 22 phase 4 (standalone home). | **Decided 2026-10-15: the recommendation stands.** 1. The module is the same in both; phase 4 moves one import line. |
| Q10 | Coalesce a burst? M6: two quick enqueues of one DAG both run, one after the other. | 1. No coalescing; accept the extra runs. 2. The router skips an enqueue when the same DAG already has a run in state `queued` (not running), and records `"result": "coalesced"`. The queued run sees the newer files anyway. | **Decided 2026-10-15: the recommendation stands.** 1 now. 2 after Stage 6 pins the REST shape, if `events.jsonl` shows bursts. |
| Q11 | Which CLI library? | 1. argparse (standard library, 20 ms import). 2. Typer (typed functions, 73 ms import). | **Decided 2026-10-15: option 2, Typer.** The grammar in §A.5 stays. The cost is accepted. |
| Q12 | How is the package built for Nix? | 1. nixpkgs Python packages. 2. `pyproject.toml` plus `uv`, built with uv2nix. | **Decided 2026-10-15: option 2.** `uv.lock` is committed. The three uv2nix inputs live in `flake.nix` only. The shell uses `uv`. `uv lock --check` is in `base:check`. |
