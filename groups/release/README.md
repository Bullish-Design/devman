# release — the group that builds a release, and refuses to when it should not

`devman.groups = [ "base" "release" ]`

One workflow, one task name, and a policy gate that fails rather than skips.

## Why this is its own group

`base` reaches five of the six registered repositories, and three of them have
nothing to release: a Hugo module, a flake of NixOS modules, and the plane
itself before stage 4. Putting `release.yaml` in `base` would give each of them
a workflow that fails on a task they have no reason to define.

§16's promotion rule is the test — **a group begins when a second repository
wants the same file** — and two do: `devman` builds a package, `observantic`
builds a wheel. Taking the group is the opt-in, exactly as it is for
`python-format`.

Unlike `python-format`, this group is safe to inherit and never trigger: nothing
fires it. §7.4's "an inherited workflow you never trigger costs nothing" holds
here, and the reason it does not hold for reactivity is that a *triggered*
workflow rewrites your files while you edit them (S4). A release is triggered by
a person, or by a timer that person wrote.

## The task name this group calls

| Task | What the repository puts in it |
|---|---|
| `release:build` | build the artifact, and put it under `.devman/.runs/artifacts/` |

```nix
tasks."release:build".exec = "uv build --out-dir .devman/.runs/artifacts";
```

`.devman/.runs/artifacts/` is §9.2's own name for the place a run's output goes.
It is created at registration, it is git-ignored, and retention does not touch
it. A task addresses it relatively — `working_dir` is already the project — or
through `$DEVMAN_PROJECT_DIR`, which is one of §7.1's four global names. Neither
puts an absolute path anywhere.

**It builds. It does not publish.** Pushing a tag, uploading a wheel or cutting
a GitHub release are each irreversible and each want a credential; this group
does none of them, and §9.4 stays unused because of it (`STAGE_4_LOG.md`, S7).
A repository that wants to publish adds the step to its own shadowing copy and
accepts what that means.

## The policy gate

The first step is a gate, and it **fails** when it refuses. It never skips.

| Condition | Why |
|---|---|
| the working tree is clean | a release built from uncommitted work cannot be rebuilt from the commit it claims |
| the last recorded run of this project's `validate` succeeded | the plane already records every run, per working tree, in `.devman/.runs/metadata.jsonl` |

The second one names the DAG exactly — `<project>-validate`, with the project
taken from the run's own `${context.dag.name}`. **Matching the suffix
`-validate` is not enough**, and running it is what proved so: it also matches
`stack-validate`, the cross-repo workflow (§11), so the gate reported a
different workflow's success as this one's (`STAGE_4_LOG.md`, S5). A repository
that renames `validate` finds no line and is refused, which is correct and
loud.

Both are read out of files this repository already has, so gating needs no
fifth entry in §7.1's closed list of global names and no new devman command.

```
$ devman run release
$ cat .devman/.runs/reports/release-<run id>.md
## gate
- clean tree: yes
- last validate: **NONE RECORDED** — refusing. Run `devman run validate` first
```

The run reports `Failed` and `metadata.jsonl` records `"status":"failed"`. That
is deliberate and it is the opposite of what `python-format` does: a
loop-breaking precondition records `Succeeded` with a skipped step, because a
self-stopping loop must not look like a failure. **A refused release must**, or
the plane has produced a successful run that did the wrong thing.

**What the gate cannot check.** `metadata.jsonl` records a run's dag, id, status
and time — and no commit. So the gate can say *the last validate succeeded*, and
cannot say *the last validate succeeded on this commit*. The report prints the
matched line so a person can judge how old it is. That limit is stated rather
than papered over: a freshness rule the data cannot support is §15.7 with extra
steps.

## What a run leaves behind

```
.devman/.runs/reports/release-<run id>.md    the gate's findings and the artifact listing
.devman/.runs/artifacts/                     whatever `release:build` wrote
.devman/.runs/logs/<project>-release/…       each step's own output
.devman/.runs/metadata.jsonl                 one line: dag, run id, status, log path
```

## Running it on a schedule

Do not use Dagu's `schedule:` — see the recipe and the reason in
`groups/base/README.md`. A timer runs `devman run release --project <name>`, and
inherits every refusal `devman run` already makes.
