# base — the group every repository takes by default

`devman.groups = [ "base" ]` is the default, because `devenv.nix` is the
highest-coverage marker in the surveyed repositories — 57 of 71 (D4). This group
therefore holds the leverage, and it must stay small.

## The task names this group calls

A group's workflows call task names, and **task names are group-local
convention** (`CONCEPT.md` §7.1). Taking a group is an agreement to define that
group's names:

| Task | What the repository puts in it |
|---|---|
| `base:lint` | the fast check that needs no build |
| `base:test` | the test suite |

Two names, and the list is closed. `full-test` reaches further by calling
`devenv test`, which every devenv repository already has, so the exhaustive
workflow costs a repository no third task.

```nix
tasks."base:lint".exec = "ruff check .";
tasks."base:test".exec = "pytest";
```

**The `base:` prefix is not decoration — devenv requires it.** An un-namespaced
name is an evaluation error:

```
× Invalid task name: lint. Task names must be in format 'namespace:name'
```

The namespace is the group's own name, which is what "group-local" means made
literal. A repository taking two groups defines both sets; if the two mean the
same command, it should take one group rather than both (§7.4 — "to be rid of
one, do not take its group").

**Two groups cost two names, not two bodies.** A devenv task needs no `exec` at
all: one with only `after` runs its dependency and then does nothing itself, and
a failure in the dependency still fails the run. So a repository that genuinely
wants both groups aliases rather than duplicates:

```nix
tasks."python:lint".exec = "ruff check .";
tasks."base:lint".after  = [ "python:lint" ];   # one line, no second body
```

Measured on devenv 2.1.2 (`STAGE_2_LOG.md`, S5). It does not change §7.4's
advice — an inherited workflow you never trigger still costs nothing, and the
cheapest way to be rid of one is still not to take its group — but it removes
the "five names for three commands" objection from the case where you do want
both.

A repository that decomposes differently takes a different group, or shadows the
file (§7.3). The plane does not police what a name means.

## The workflows

| File | Queue | Steps |
|---|---|---|
| `check.yaml` | `light` | `base:lint` |
| `validate.yaml` | `normal` | `base:lint`, `base:test` |
| `full-test.yaml` | `heavy` | `base:lint`, `base:test`, `devenv test` |
| `review.yaml` | `normal` | what changed, `base:lint`, `base:test` — and a report |

`review` is the only one that produces a document rather than an exit code. It
writes `.devman/.runs/reports/review-<run id>.md` holding the head commit, the
uncommitted files, the diffstat, the last five commits and one verdict line per
check. It needs no task beyond the two above, so every repository taking this
group has it already.

**It finishes even when a check fails.** Both check steps carry
`continue_on: {failure: true}`, so the chain reaches the end and the report gets
its verdict — and the run still reports `Partially Succeeded`, which is not
`succeeded` in `metadata.jsonl`. A review that found something is not a success.

## Why every step says `devenv tasks run -v`

`-v` is load-bearing and must not be tidied away. Without it `devenv tasks run`
captures the task's stdout and prints none of it, on the success path and the
failure path alike, so a step running `ruff check .` writes a log holding `{}`
and nothing else. `-v` is the only flag that restores it — `--show-output`
documents itself as equivalent and, measured, is not.

**Which stream the output lands on depends on the devenv version**, so no group
file should depend on one:

| devenv | plain | `-v` |
|---|---|---|
| 2.1.2 | stdout lost | task stdout on **stdout**, debug log on stderr |
| 2.2.0 | stdout lost | task stdout on **stderr**, beside the debug log |

Dagu writes a step's two streams to separate files, so on 2.1.2 the findings
arrive clean and on 2.2.0 they arrive next to devenv's own 40-odd lines. Either
way they arrive, which is the whole point.

`full-test.yaml`'s third step is the exception, and it is devenv's limit rather
than the plane's: `devenv test` captures **both** of `enterTest`'s streams and
prints neither, with `-v` or without. Its exit code is correct, so the gate
works; the reason has to be found by re-running `devenv test` by hand. Measured
on devenv 2.1.2 (`STAGE_2_LOG.md`, S4).

## What is deliberately absent from every file

`name`, `working_dir`, and `log_dir`.

- A top-level `name:` makes `dagu validate` fail — "entrypoint document must not
  define name". A DAG's identity is its file name (A5).
- `working_dir` and `log_dir` are identical in every workflow, so the machine
  writes them once into Dagu's `base.yaml` and every DAG inherits them (E4).

`queue` stays, because it is the one thing that genuinely varies from workflow to
workflow (§7.2).

## Triggering one of these on a commit

The plane supplies `devman run`. The hook that calls it is the repository's own,
and it is devenv's `git-hooks` module rather than anything of devman's:

```nix
git-hooks.hooks.devman-validate = {
  enable = true;
  name = "devman validate";
  entry = "devman run validate";
  stages = [ "post-commit" ];
  pass_filenames = false;
  always_run = true;
};
```

devenv 2.1.2 first needs the input:

```bash
devenv inputs add git-hooks github:cachix/git-hooks.nix --follows nixpkgs
```

Three things to know before taking it (measured in `STAGE_3_LOG.md`, S9):

- **It is not a gate.** `devman run` enqueues and returns, so the commit is not
  blocked and the workflow starts a second or two later. A repository that wants
  to stop a bad commit wants a `pre-commit` hook that runs the task directly.
- **The run reads the tree it finds**, which is the tree after the commit rather
  than the tree that was committed.
- **It costs a devenv input** — about 20 ms on every shell entry — and a
  generated `.pre-commit-config.yaml` in the working tree.

## Running one of these on a schedule

**Not with Dagu's `schedule:` key.** It is Dagu's own timer, and the daemon that
fires it has one environment for the whole machine and no parameter to fill, so
`working_dir` **and** `log_dir` both stay literal: the run works inside a
directory named `${DEVMAN_PROJECT_DIR}` in the daemon's own tree — `$HOME` on a
normal machine — and then fails on the exit handler. Measured in
`STAGE_4_LOG.md`, S2.

A schedule reaches the plane the same way a commit does, through `devman run`.
The timer is the developer's own, exactly as the hook is the repository's own,
and devman supplies no option and no command for it (CONCEPT.md §8):

```ini
# ~/.config/systemd/user/devman-nightly.service
[Service]
Type=oneshot
ExecStart=/run/current-system/sw/bin/devman run validate --project siteman
```

```ini
# ~/.config/systemd/user/devman-nightly.timer
[Timer]
OnCalendar=daily
Persistent=true
[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload && systemctl --user enable --now devman-nightly.timer
```

`--project` is what makes this work from a timer, which has no working
directory in any repository. Everything else `devman run` already does: it
resolves the path from the registry, exports `DEVMAN_PROJECT_DIR`, passes it as
a parameter, and **refuses with a message** when it cannot — which is the whole
difference from the Dagu scheduler, whose failure is a directory named after the
variable that did not resolve.

## Why the multi-step files say `type: chain`

`chain` runs the steps in order. `graph`, Dagu's default, runs steps with no
`depends` at the same time, and two `devenv tasks run` invocations in one
checkout then contend for one devenv state directory. Order is the workflow's
own business, so the key sits in the file rather than in the machine's
`base.yaml`.
