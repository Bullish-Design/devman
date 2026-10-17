# devman

devman runs Dagu workflows across many repositories. Dagu does the work.
devman does three jobs:

1. **Compile.** It turns central workflow sources into files that Dagu runs, one
   project at a time.
2. **Route.** It turns an event (a save, a finished run, a landed change) into a
   queued Dagu run.
3. **Show.** It tells each repository what runs in it, when, and with what result.

Dagu does scheduling, queues, execution, history, the web interface (UI),
retries and agent steps. If Dagu has a feature, devman uses it.

The charter is [`.scratch/projects/047-greenfield/CONCEPT.md`](.scratch/projects/047-greenfield/CONCEPT.md).
The interfaces are in `PLAN.md` section A, beside it.

## How it works

```
projects.toml + workflows/ + library/    (the overlay, ~/.config/devman)
        |  devman compile
        v
~/.local/state/devman/dags/<project>/    (the files Dagu runs)

event --> devman emit --> router --> dagu enqueue --> Dagu --> run
                                                      |
                                    handler_on.exit --+--> done / failed event
```

A repository tracks nothing for devman. Which workflows run in a checkout is a
fact about this machine, so it lives in the overlay. This is the boundary test:
*would this still be true for someone who cloned the repository?*

## Install

The flake exports one Home Manager module, `services.devman`. It installs:

- the `devman` command;
- Dagu 2.20.1, built by `nix/dagu.nix`;
- the user service `devman-dagu`, which runs `dagu start-all`;
- the user service `devman-watch`, which runs `devman watch`.

| Option | Default |
|---|---|
| `enable` | `false` |
| `host`, `port` | `127.0.0.1`, `8080`. The host must be loopback, because Dagu runs with no login |
| `queues` | `light` 4, `normal` 2, `heavy` 1, `gpu` 1, `exclusive` 1, `llm` 2 |
| `defaultQueue` | `light` |
| `overlayDir` | `~/.config/devman` |
| `stateDir` | `~/.local/state/devman` |
| `watch.enable`, `watch.debounce` | `true`, `300ms` |

A change to devman needs a Home Manager switch. A change to the overlay does not:
the watcher recompiles it.

## The overlay

```
~/.config/devman/
  projects.toml                    the one manifest
  workflows/<project>/<name>.yaml  workflows for one project
  library/base.yaml                shared defaults, actions and the exit handler
  library/workflows/<name>.yaml    shared workflows a project can take
  library/examples/                examples to copy, never taken
  library/README.md                what each library file does
```

The library is content. It documents itself in `library/README.md`. This
repository documents the mechanism only.

## The manifest

```toml
[devman]                          # the table key is the project name
path = "~/Documents/Projects/devman"
take = ["check", "test", "format"]    # library workflows

[[devman.on]]
event   = "save"                  # an open string
match   = "**/*.py"               # a glob or a list of globs
exclude = [".scratch/**"]         # optional
run     = "format"                # a workflow the project has
```

- A project name matches `[A-Za-z0-9][A-Za-z0-9._-]*`. A workflow name matches
  `[A-Za-z0-9][A-Za-z0-9_-]*`, with no dot.
- A file in `workflows/<project>/` replaces the library file of the same name.
  A project file needs no `take` entry.
- `match` tests the subject of the event. `*` does not cross `/`. `**` crosses
  it. There is no brace expansion.
- Each project has two levels only: its own files, then the library.
- The manifest path owns `working_dir`. A source that sets `working_dir` is
  refused. Every source must name a nonempty queue from `services.devman.queues`.

| Event | Subject | Source |
|---|---|---|
| `save` | a path inside the project | the watcher |
| `land`, `commit` | a ref name | a hook that calls `devman emit` |
| `done`, `failed` | a workflow name | the exit handler in `base.yaml` |
| `manual` | a workflow name | `devman run` |
| any other | what the sender passes | any script that calls `devman emit` |

## Commands

| Command | Does |
|---|---|
| `devman compile [--all] [project...]` | Resolve, render, validate and publish workflows |
| `devman emit EVENT [--project P] [--subject S]... [--source NAME] [KEY=VALUE...]` | Route one event |
| `devman run WORKFLOW [--project P] [KEY=VALUE...]` | Run one workflow now |
| `devman status [project] [--json]` | Show workflows, triggers, queue and last run |
| `devman show WORKFLOW [--project P]` | Print the compiled file and its source path |
| `devman doctor` | Check the plane |
| `devman watch [--debounce D]` | Run the watcher. The service runs this |

Without `--project`, a command finds the project whose `path` holds the current
directory. Exit codes: `0` success, `1` the work ran and something failed, `2` a
usage error or a refusal before any work.

## Refusals

Compile refuses one project and leaves its files unchanged when:

- its `path` is not a directory;
- a source sets a key the header owns: top-level `env`, `log_dir` or `shell`, or
  `handler_on.exit`, or sets `working_dir`;
- a source omits `queue:`, sets a non-string or empty queue, or names a queue
  that the Dagu config does not define;
- a `take` or `run` entry names a workflow that does not exist;
- a rendered file fails `dagu validate`;
- `on` entries form a `done`/`failed` loop;
- `workflows/<project>/` exists and the manifest has no table for it.

The project keeps its earlier files, and `devman status` shows them as stale.
Compile refuses all projects, with exit 2, when `DEVMAN_GUARD` is not a file.

The router refuses an event when the project is unknown or its path is missing.

## Files that devman writes

```
~/.local/state/devman/
  dags/<project>/<project>.<name>.yaml   compiled files; Dagu's dags_dir
  runs/<project>/                        run logs of one project
  base.yaml                              library/base.yaml with its tokens filled
  compile.json                           the last compile result per project
  events.jsonl                           every event and what the router did
  handler.log                            stderr of the exit handler
```

`events.jsonl` answers "why did this run?". Nothing rotates it.

## The checkout guard

A compiled file sets the DAG shell to `dagu/guard.sh`. The guard fails a step when
`DEVMAN_PROJECT_DIR` has neither `.git` nor `.jj`. Without it, Dagu creates a
missing `working_dir` and the run succeeds in an empty directory. A step with its
own `shell:` and a built-in action step skip the guard.

## Environment

The Home Manager wrapper sets these. Each has a default, so the command also runs
from a checkout.

| Variable | Meaning |
|---|---|
| `DEVMAN_OVERLAY`, `DEVMAN_STATE` | the two roots |
| `DEVMAN_LIBRARY` | replaces `<overlay>/library`. For tests |
| `DEVMAN_BASH`, `DEVMAN_GUARD`, `DEVMAN_BIN` | fill the `base.yaml` tokens. Compile refuses without them |
| `DEVMAN_DAGU_CONFIG`, `DEVMAN_DAGU_VERSION` | the Dagu config and the pinned version |

A run sees `DEVMAN_PROJECT_DIR`, `DEVMAN_EVENT` and `DEVMAN_SUBJECT`.

## More

- [`USER.md`](USER.md): daily use.
- [`AGENTS_GUIDE.md`](AGENTS_GUIDE.md): the code map, the tests and diagnosis.
- [`AGENTS.md`](AGENTS.md): the rules for agents.
