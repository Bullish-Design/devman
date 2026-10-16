# devman — daily use

## See what runs in a repository

Run `devman status` in the repository. It prints each workflow with its source
(project or library), its triggers, its schedule, its queue and its last result.
A compile refusal or a stale file shows at the top.

```bash
devman status            # the project of this directory
devman status gitman     # another project
devman status --json     # for scripts
```

Two links in the repository show the same facts as files. linkman makes them.

| Link | Shows |
|---|---|
| `.devman/workflows` | the files Dagu runs. The header names the source file |
| `.devman/runs` | the run logs of this project |

The Dagu UI (`http://127.0.0.1:8080`) groups the same workflows by project.

## Run a workflow now

```bash
devman run check
devman run check KEY=VALUE     # an extra field for the run
```

The run waits in its queue. Watch it in the Dagu UI.

## Ask why a run started

Read `~/.local/state/devman/events.jsonl`. Each line holds one event, the
workflows it matched and the run IDs. A scheduled run has no line, because it
never passes the router.

## Take a library workflow

Add its name to `take` in `~/.config/devman/projects.toml`:

```toml
[myproject]
path = "~/Documents/Projects/myproject"
take = ["check", "test"]
```

The watcher recompiles. `library/README.md` lists each workflow and the repository
task it needs, such as `base:check`.

## Add a project

Add one table to `projects.toml`. Define the repository tasks that the library
calls. Run `devman compile myproject` or wait for the watcher. The repository
commits nothing.

## Write a workflow for one project

Put a file at `~/.config/devman/workflows/<project>/<name>.yaml`. Use a library
name to replace the library file for that project. Name a new workflow in an `on`
entry to run it on an event. The `devman-workflow` skill has the rules.

## Run a workflow on an event

Add an `on` entry to the project:

```toml
[[myproject.on]]
event = "save"
match = "**/*.py"
run   = "format"
```

To chain two workflows, use the `done` event. The subject is the workflow name:

```toml
[[myproject.on]]
event = "done"
match = "check"
run   = "test"
```

A loop of `done`/`failed` entries refuses the project.

## Add an event source

Any command can send an event:

```bash
devman emit deploy-ready --project myproject --subject staging
```

Add an `on` entry with `event = "deploy-ready"`. devman needs no other change.

## Run an agent task

Copy `~/.config/devman/library/examples/agent-task.yaml` to
`workflows/<project>/agent-task.yaml`. Edit the prompt. Run `devman run
agent-task`. The workflow commits the agent's work to the branch `agent/task`
and waits for you in the Dagu UI. Complete the task to remove the work tree.
Land the branch with gitman.

## When something looks wrong

1. `devman status`: a refusal or a stale file shows here.
2. `devman doctor`: it checks Dagu, the watcher, `dags/` and the library.
3. `events.jsonl`: did the event arrive, and what did the router do?
4. The Dagu UI or `.devman/runs`: the log of the run.

After a compile refusal, fix the source. The watcher recompiles at once.
