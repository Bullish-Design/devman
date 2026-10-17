# devman — guide for agents

Read [`AGENTS.md`](AGENTS.md) first for the rules. `README.md` describes the
mechanism. This file is the map.

## Data flow

```
projects.toml, workflows/, library/ --compile--> state/dags/<project>/*.yaml --> Dagu
event --> emit --> router --> dagu enqueue (absolute path of a compiled file)
run ends --> handler_on.exit in packaged base.yaml --> emit done|failed
```

Compile is the only writer of `dags/`. The router is the only enqueuer.

## Modules

| File | Holds |
|---|---|
| `src/devman/cli.py` | the Typer app, one function per command, exit codes |
| `paths.py` | `Paths`, built from the environment |
| `manifest.py` | read `projects.toml`, the rules, event matching |
| `render.py` | the header, the source checks |
| `compile.py` | resolve, validate, publish, record, lock |
| `dagu.py` | the calls to the `dagu` command and its REST API |
| `router.py` | find the project, match, enqueue, write `events.jsonl` |
| `watch.py` | one `watchexec`, batching, restart, recompile |
| `status.py` | `status`, `show` |
| `doctor.py` | the health checks |

| Other file | Holds |
|---|---|
| `dagu/config.yaml` | the Dagu config template. Nix fills it |
| `dagu/guard.sh` | the checkout guard shell |
| `src/devman/base.yaml` | the packaged required Dagu base template |
| `nix/hm-module.nix` | the Home Manager module and the two services |
| `nix/package.nix`, `nix/dagu.nix` | the package (uv2nix) and Dagu 2.20.1 |
| `tests/fixtures/library/` | seed workflow and example files for tests |

`PLAN.md` section C, in `.scratch/projects/047-greenfield/`, holds the size
budget. If a module passes its budget by more than 30 percent, look for a Dagu
feature that does the job.

## Interfaces

`PLAN.md` section A fixes them: `projects.toml` (A.1), the rendered file (A.2),
`compile.json` (A.3), `events.jsonl` (A.4), the commands (A.5), the environment
(A.6), `status --json` (A.7) and the guard (A.8). A change to one changes
section A and `CONCEPT.md` in the same commit.

## Where content lives

- Workflow content (`~/.config/devman/library/workflows/`) is overlay content.
  Its README says what each file does. Never copy that detail into a mechanism
  document.
- A per-project workflow lives in `~/.config/devman/workflows/<project>/`.
- The manifest owns `working_dir`. Every workflow source names a configured
  queue. Compile refuses a source that omits either contract.
- The packaged `base.yaml` owns `handler_on.exit` and `devman.task`. Compile
  fills its three tokens. `DEVMAN_GUARD` goes in the header, not in the base.
- The three devman skills live in the overlay at
  `~/.config/devman/projects/devman/agents/skills/`. `.agents` links to them.

## Test

```bash
devenv tasks run -v base:check   # ruff check, ruff format --check, uv lock --check
devenv tasks run -v base:unit    # pytest, with a fake dagu
devenv tasks run -v base:e2e     # pytest, with a real Dagu on loopback ports
devenv tasks run -v base:test    # nix flake check
nix build .#devman
```

- Run `git add -A` before `nix build` or `nix flake check` in a gitman workspace.
  Nix reads the index and ignores untracked files.
- `base:unit` uses a fake `dagu`. Only `base:e2e` and `checks.library-validate`
  prove a file against the real one.
- `checks.library-validate` compiles the seed library, and the agent example as a
  project workflow, with the real Dagu and the packaged guard.
- E2E tests start Dagu on free ports from 18110. They never touch the live Dagu.
- A test must be able to fail. Start a negative case from a passing one.

## Diagnose

1. `devman status` and `compile.json`: a refusal has a reason.
2. `devman doctor`: one line per check.
3. `events.jsonl`: one line per event, with the matches and the run IDs.
4. `~/.local/state/devman/handler.log`: the stderr of a failed `emit` in the
   exit handler.
5. The compiled file: `devman show <workflow>`.
6. The Dagu UI or API: the run itself.

## Facts measured on Dagu 2.20.1

`MEASUREMENTS.md` and `SPIKES.md` hold the evidence. The ones that shape code:

- Dagu creates a missing `working_dir` and the run succeeds. The guard exists
  for this.
- A `shell:` in the base config does not reach a step. The header sets it.
- A base `handler_on` reaches every DAG. A DAG's own `handler_on.exit` replaces
  it, so compile refuses that key.
- A queue name that the config does not define runs with no limit and no error.
- Under `recursive: true`, two files with one base name in two subdirectories
  hide every DAG. The `<project>.` prefix prevents it.
- `git.worktree.remove` with `force: true` deletes uncommitted output.
