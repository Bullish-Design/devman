# The devman library

This directory is overlay content (`~/.config/devman/library/`). It is true for
this user, not for every clone of a repository, so it lives here and not in the
devman package. An edit is live: the watcher sees it and recompiles.

`tests/fixtures/library/` in the devman repository holds an identical seed copy.
Tests and `checks.library-validate` use the seed. Keep the two the same.

## `base.yaml`

Shared defaults, one handler and one action. `devman compile` fills three tokens
(`@bash@`, `@devman@`, `@stateDir@`) and writes the result to
`~/.local/state/devman/base.yaml`, which Dagu reads as its base config. A running
Dagu rereads it for the next run.

| Part | What it does |
|---|---|
| `queue: light` | A DAG with no `queue:` uses its own name as a queue of limit 1. This default gives every DAG a queue that the Dagu config defines. |
| `hist_retention_days: 7` | Dagu prunes run history and logs after seven days. |
| `handler_on.exit` | Maps the run status to the `done` or `failed` event and starts `devman emit` detached. It always exits 0, so a router problem never changes a run. Other statuses (aborted, partially succeeded) send no event. |
| `actions: devman.task` | Runs `devenv tasks run -v <task>`. A failure names the task on stderr and fails the step. |

The handler uses plain bash, not the guard. A run in a vanished checkout is
already failed, and the handler must still report `failed`.

## The checkout guard

`dagu/guard.sh` in the devman package is the DAG shell. The compiled header sets
`shell:` to it, because a `shell:` in `base.yaml` does not reach a step on Dagu
2.20.1. The guard fails a step when `DEVMAN_PROJECT_DIR` has neither `.git` nor
`.jj`. Without it, Dagu creates a missing `working_dir` and the run succeeds in an
empty directory.

Two things opt out of the guard:

- a step with its own `shell:` (the owner's explicit choice);
- a built-in action step such as `git.worktree.add` or `harness.run`, which does
  not use a shell. The agent pattern starts with `git.worktree.add`, which fails in
  a directory that is not a repository.

## `workflows/`

Each file is short, and each calls `devman.task`. A project takes one with
`take = ["check"]` in `projects.toml`. A file of the same name in
`workflows/<project>/` replaces it for that project.

| File | Queue | Asks of the repository |
|---|---|---|
| `check.yaml` | `light` | a devenv task `base:check` |
| `test.yaml` | `normal` | a devenv task `base:test` |
| `format.yaml` | `light` | a devenv task `format:fmt`, idempotent |
| `release.yaml` | `heavy` | tasks `base:test` and `release:build`; builds and does not publish |

- `format` keeps no loop receipt. A format that writes files causes one more
  `save`. The second run changes nothing, and the loop ends.
- `release` runs the test as its first step, so the gate holds something that can
  fail. Publishing is irreversible outside this machine, so no library file does it.
- No file has a `schedule:`. Fleet upkeep is one workflow in `workflows/devman/`.

## `examples/`

`examples/agent-task.yaml` is not a library workflow. Compile reads only
`workflows/`, so a project cannot take it. Copy it to
`workflows/<project>/agent-task.yaml` and edit the prompt.

It runs one agent task on its own branch:

1. `git.worktree.add` makes the branch `agent/task` and a work tree under
   `.worktrees/`.
2. `harness.run` runs `claude` in the work tree. The file sets a model, a cost cap
   (`max-budget-usd`) and a permission mode. Dagu does not report cost, so the
   cap is the only limit.
3. A `run` step commits the work tree to the branch. It fails when the agent
   changed nothing.
4. `human.task` waits for a person. Complete it in the Dagu UI or with
   `dagu human-task complete`.
5. `git.worktree.remove` deletes the work tree. The branch stays. A person lands it
   with gitman or by hand.

**Step 3 is required.** `git.worktree.remove` with `force: true` deleted
uncommitted output in the spike (SPIKES, spike 3). The example never sets `force`,
so an uncommitted work tree also fails the remove step.

The git and harness steps do not use the guard shell. A second run fails at step 1,
because the branch exists. Add `.worktrees` to the repository's `.git/info/exclude`.

## Rules for a change

- `devman doctor` checks that every `action:` a workflow here names exists in
  `base.yaml`.
- A workflow may not set a top-level `env`, `log_dir` or `shell`, or
  `handler_on.exit`. Compile refuses it.
