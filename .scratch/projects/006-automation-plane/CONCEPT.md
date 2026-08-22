# devman — Concept (the automation plane)

> **STATUS: PROPOSED (2026-08-21). Reconciled against Investigations A and E
> (2026-08-22).**
>
> Every edit made by that reconciliation rests on a measurement recorded in
> `FINDINGS.md`. One section was deleted outright: §8.1, because Dagu already
> does what it described. Investigations B, C, and D1–D6 are still open; D7 is
> answered, in §8.
>
> `001`–`005` were earlier attempts to define devman. They are superseded and
> carry no authority here. Nothing in this charter depends on them.
>
> Spike results in `../../spikes/SPIKES.md` stay valid, because a measurement
> outlives the concept that motivated it. Spike A is the only one this charter
> uses.

---

## 1. One line

> **devman installs one Dagu control plane per machine, and gives every
> devenv-managed repository a shared automation contract through one Nix flake.**

Dagu orchestrates. devenv executes. devman defines the contract between them.

---

## 2. What devman is

Three things, and the list is closed:

1. **A shared Nix flake** exposing a machine interface and a repo interface from
   one version (§3).
2. **A project registry** of repositories that opted into automation, keyed by
   identity, resolving to paths (§5).
3. **A contract** — three names, and nothing else (§7).

Item 3 is deliberately thin. The plane needs a name it can resolve, a queue it
can run in, and one variable naming where the work happens. That is the whole of
what it understands, and the machine states all three once (§7.1).

Default workflows are content, not contract — files in a group directory,
shadowed by name (§7.2).

**devman executes nothing.** It installs the thing that schedules, and defines
what the schedule may say. Every command it triggers runs as a devenv task in
the repository that owns it.

---

## 3. The flake

### 3.1 Shape

```
devman/
├── flake.nix
├── nix/nixos-module.nix       # machine interface
├── modules/default.nix        # repo interface — selection and identity
├── groups/                    # content, not contract (§7.2)
│   ├── base/                  # check, validate, full-test
│   ├── python/ nix/ rust/     # ecosystem groups
├── lib/                       # registry schema, registration helpers
└── src/devman/                # the CLI, deferred to stage 3 (§10)
```

| Output | Consumer |
|---|---|
| `nixosModules.default` | the machine's NixOS configuration |
| `modules/` *(a path — §3.2)* | every repo's `devenv.yaml` |
| `packages.default` | the `devman` CLI — put on `PATH` by the NixOS module |
| `checks` | integration tests for the plane |

One flake version defines both interfaces. That is the point: it removes drift
between Dagu config, queue names, registry layout, and repo integration. Those
four must agree, and nothing else makes them.

### 3.2 A devenv import is a path, not an output

devenv does not consume flake output attributes. An import resolves to a
directory inside an input, so the repo interface is a `modules/` directory at
the flake root:

```yaml
# a consuming repo's devenv.yaml
inputs:
  devman:
    url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>"
imports:
  - devman/modules
```

Pin with `git+`. A `github:` input hits the API rate limit on every evaluation.

### 3.3 The current source is deleted

`src/devman/` predates this charter and shares none of its model. Delete it
rather than porting it; the CLI (§10) starts from the registry.

---

## 4. Machine responsibility

```nix
# pinned with git+ — a github: input hits the API rate limit on every eval
inputs.devman.url = "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>";

imports = [ inputs.devman.nixosModules.default ];
```

**One Dagu instance per user, as a systemd user service.** Every workflow step
runs a developer's own `devenv` in a developer's own checkout, so the service
needs that developer's `$HOME`, Nix profile, `~/.cache`, git credentials, and SSH
agent. A system service needs all of that plumbed explicitly; a user service has
it already, and it puts `DAGU_HOME` at `~/.local/share/dagu`, beside §9.2's
registry rather than in `/var/lib`. The module writes
`systemd.user.services.dagu`.

**One instance, not one per project**, and queues are the reason. A queue's
concurrency limit is per instance, so ten project daemons each holding
`exclusive: max_concurrency 1` would give ten concurrent "exclusive" runs, and
success criterion 12 could not hold. Per-project instances would also need four
ports allocated each, and would not remove anything from §7.2.

nixpkgs packages no Dagu at any version, so the plane carries its own package
expression, and both interfaces call the same file.

| Owns | Never knows |
|---|---|
| Dagu installation, service, config | which project uses pytest |
| workflow discovery, registry paths | which repo has a benchmark |
| Dagu queues and concurrency limits | any project's task graph |
| state paths, log retention | any project's dependency order |
| secret and environment injection | |

The split is load-bearing. The machine knows *how much* may run at once, never
*what* runs. A machine module that learns one project fact has started back
toward a central config every repo edits — the failure the plane prevents.

---

## 5. Repo responsibility

```nix
devman = {
  enable  = true;
  project = "pyjutsu";                # identity, never a path (§9.1)
  groups  = [ "base" "python" ];      # workflows to inherit (§7.3)
};

tasks."lint".exec      = "ruff check .";
tasks."typecheck".exec = "basedpyright";
tasks."test".exec      = "pytest";
```

Three lines plus the repo's own primitives. `project` is stated, never inferred
from the directory name — identity that depends on where a checkout sits changes
when you rename the directory, and re-registers the repo as new.

Workflows arrive as files (§7.2); a repo writes YAML only to change one.

### 5.1 A repo enters the registry by declaring itself

`devman.enable = true` is the whole membership rule. The registry holds exactly
the repositories that set it, along with their workflows and their path.

This is what frees Dagu from understanding the developer's directory layout: the
repo supplies its own location at registration, so nothing has to go looking.

**The registry is derived, and the repository is canonical.** Re-reading every
registered repo rebuilds it entirely (§9.3).

### 5.2 Registration runs at shell entry

Nix evaluation cannot write to `~/.local/share/`, so registration is a side
effect and needs an explicit home.

> **Registration runs in `enterShell`, guarded by a content hash.** The module
> renders the registry entry, compares its hash against disk, and writes only on
> a difference.

The common case costs nothing. The cost is that a repo joins the registry only
after you enter its shell once, and that is the only way in — there is no manual
register command and no hand-written entry. A repo you have never entered is not
set up anyway.

**Adding a workflow needs no restart. Changing Dagu's config does.** A new file
in the DAG directory is picked up by the already-running service, so registration
can project a repo's workflows and have them runnable immediately. But the
instance `config.yaml` is read only at startup, and until the service restarts
the CLI honours the new config while the server does not — reporting an error
that names the very setting you already added. **A machine module that rewrites
`config.yaml` must restart the service in the same activation.**

That module must also set `dag_discovery.recursive: true` and
`dag_discovery.symlinks: true`. Both default to off, and §9.2's per-project
projection directories need both. Neither failure announces itself: an
undiscovered workflow is simply absent from `dagu ls`, from the web UI, and from
the scheduler, while remaining runnable by name.

---

## 6. Dagu orchestrates, devenv executes

Violating this boundary is the main way the design decays.

**devenv owns implementation.** The repo names its own tasks — task names are
group-local convention, never reserved (§7.1):

```
python:  lint  typecheck  test  integration-test
nix:     flake-check  build
rust:    clippy  cargo-check  test
```

One logical task has one implementation, and every caller reaches it the same
way — a workflow step, a hook, a person at a prompt:

```
prefer:  devenv tasks run test

avoid:   workflow:  pytest
         hook:      devenv shell -- pytest
```

Two call paths mean two things that drift. Spike A makes the single path
affordable: **0.16s warm**, 5.46s cold, 1.44s after a content change.

**Dagu owns composition.**

```
devenv tasks:              Dagu workflow:

  lint                       lint ───────┐
  typecheck                              ├── validate
  test                       typecheck ──┤
                                         │
                             test ───────┘
```

**Never write the same dependency graph in both.**

```
repo-internal execution semantics  →  devenv
larger operational orchestration   →  Dagu
```

A repo with genuinely internal ordering — build before test — expresses it as a
devenv task dependency and exposes one task. It does not publish both halves and
let Dagu re-derive the order.

---

## 7. The contract

The plane defines **the smallest vocabulary the machine has to implement**, and
nothing about what any repository's work should be.

### 7.1 What is global

**Three names, and the list is closed.** The machine and every workflow must
agree on exactly these:

| What | Whose field | Where the machine states it, once |
|---|---|---|
| the queue names | Dagu's `queue:` | `config.yaml`, with each queue's limit |
| the variable `DEVMAN_PROJECT_DIR` | a name, not a field | `base.yaml`; the trigger supplies the value |
| the `.devman/.runs/` path shape | Dagu's `log_dir:` | `base.yaml` |

**Queue names.** The machine module creates Dagu queues and sets what each
costs; a workflow names one. It is Dagu's own field, not a devman word for it.

```
light   normal   heavy   gpu   exclusive
```

An earlier draft of this section claimed queue names were the *entire* shared
vocabulary. They never were: §7.2's portable workflow also rests on one agreed
variable name and one agreed path shape. What is true, and better, is that **the
machine states all three in one file it writes**, rather than every workflow
repeating them.

**Everything else belongs to the repository** — task names, workflow names, what
a workflow does, how long it takes, and every line of the file, which is Dagu's
schema throughout.

**Task names cannot be reserved**, because ecosystems decompose differently.
`nix flake check` is not a lint, and Nix has no `typecheck` distinct from
`build`. Forcing every ecosystem into a Python-shaped split produces empty tasks
or lies. They need to be stable only *within* a group, because only that group's
files call them.

**Workflow names are not reserved either.** The base group ships `check`,
`validate`, and `full-test` because most repos want a fast one, a gate, and an
exhaustive one — so `devman run check` usually resolves. A repo that wants
`smoke` and `ci` renames the files. The plane does not police what a name means,
because a rule it cannot check is a rule it should not have.

### 7.2 A workflow is a Dagu file

One file, one workflow. **The directory names the group; the file names the
workflow.**

```
devman/groups/
├── base/workflows/           # group: base
│   ├── check.yaml
│   ├── validate.yaml
│   └── full-test.yaml
├── python/workflows/         # group: python
│   ├── check.yaml
│   └── validate.yaml
├── nix/
└── rust/
```

A repo overrides by putting a file of the same name in its own directory:

```
<repo>/.devman/workflows/check.yaml       # shadows every group's check.yaml
```

There is no second representation, and **no devman-specific key anywhere in the
file.** A workflow is Dagu configuration from the first line to the last:

```yaml
# groups/python/workflows/check.yaml
queue: light
steps:
  - name: lint
    run: devenv tasks run lint
  - name: typecheck
    run: devenv tasks run typecheck
```

`queue` is Dagu's, and it stays in the file because it is the one thing that
genuinely varies from workflow to workflow. **`working_dir` and `log_dir` are
deliberately absent.** They are identical in every workflow, so the machine
writes them once into Dagu's `base.yaml`, which every DAG inherits:

```yaml
# base.yaml — written by the machine module, never by a repo
working_dir: ${DEVMAN_PROJECT_DIR}
log_dir: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs
queue: light          # the default, so a workflow naming none is still governed
```

A DAG that sets either field overrides the inherited value, so nothing is lost.
A workflow file that needs neither is `steps:` and a queue.

Three things about that variable, each of which cost a measurement:

1. **The key is `working_dir`, not `workingDir`.** Dagu's schema is snake_case
   throughout and sets `additionalProperties: false`, so camelCase is not a
   nuisance — it fails to load.
2. **The value arrives as a trigger-time parameter**, not from the service
   environment. One daemon serves every project (§4), so a variable in that
   daemon's environment holds one value for the whole machine and can never be
   per project.
3. **`log_dir` reads a different source than `working_dir` does** — the
   environment of the process that *enqueues*, not the parameter. So a trigger
   must **export the variable and pass it as a parameter** (§8). One is not a
   substitute for the other, and no arrangement of instances, profiles, or flags
   removes the pair.

The machine module must also set `env_passthrough_prefixes: [DEVMAN_]`. Dagu
filters the process environment against an allowlist, and without that line a
`DEVMAN_*` variable never reaches a DAG at all.

**An unresolved variable is not an error.** Dagu creates a directory named
literally `${DEVMAN_PROJECT_DIR}`, in whatever tree the daemon was started in,
and carries on — which is why §10 makes `doctor` go looking for one.

**§7.2's claim survives all of that**, and it is the claim that mattered: one
group file, unedited, serves every repo that takes the group, and devman still
never parses a workflow. The path arrives as a parameter, so nothing rewrites the
file.

**devman never parses a workflow.** It resolves which file wins (§7.3) and
projects it. An earlier draft added an `x-devman` block carrying `kind` and
`resource`; both duplicated a Dagu feature, so the block is gone and the plane
reads nothing.

**A group is a directory, and devman reads only `workflows/*.yaml` in it.**
Everything else there is inert to the plane and belongs to that group's own
workflows:

```
groups/my-ai/
├── workflows/provision.yaml    # devman reads this
└── skills/**                   # inert; the workflow knows where its files are
```

Installing files is a workflow that writes files. It needs no concept of its
own, so the plane has none. A group arrives through a flake input, so its files
are already in the Nix store — content-addressed and machine-wide without devman
arranging it.

### 7.3 Resolution

Groups resolve in the order the repo lists them, then the repo's own directory:

```nix
devman.groups = [ "base" "python" ];
```

```
groups/base/workflows/check.yaml
  → groups/python/workflows/check.yaml   (shadows base)
    → .devman/workflows/check.yaml       (shadows both)
```

**Shadowing is whole-file, never a field merge.** A file either wins or it does
not. Defining merge semantics over Dagu YAML would be more machinery than the
problem deserves, and the result would be hard to predict from either file
alone. The cost is §15.7: overriding one step means copying the file.

### 7.4 What a repo controls

Nix declares **selection and identity**. YAML declares **workflows**. One job
each, so no workflow is expressible two ways.

```nix
devman = {
  enable  = true;
  project = "pyjutsu";
  groups  = [ "base" "python" ];
};

tasks."lint".exec      = "ruff check .";  # your primitives, your names
tasks."typecheck".exec = "basedpyright";
```

Three keys. There is no per-workflow Nix option, because an inherited workflow
you never trigger costs nothing — it sits in the registry unrun. To be rid of
one, do not take its group.

Everything else is a file. Rename by naming the file differently, replace by
shadowing, invent by adding `.devman/workflows/benchmark-campaign.yaml`.

The plane resolves a name to a file and runs it at the declared class. It has no
opinion about what the work is.

---

## 8. Triggers

Dagu orchestrates. It does not detect.

```
filesystem change → watchexec → devman run → dagu enqueue
commit / push     → hook      → devman run → dagu enqueue
schedule          → Dagu's own timer
```

| Layer | Job |
|---|---|
| watchexec, hooks | detect that something happened |
| `devman run` | resolve the project, export the variable, pass the parameter |
| Dagu | decide and orchestrate what happens next |
| devenv | execute the repo's tasks |

**The arrow into Dagu is a local `dagu enqueue`, and that is a decision, not an
omission.** Dagu also offers an HTTP API, a webhook endpoint, and an MCP
endpoint. All three accept parameters and all three respect queues — but all
three resolve `log_dir` in the *server* process, so a run triggered through them
cannot write its logs into the project that triggered it (§7.2, §9.2). Only a
local process can, because only a local process supplies the environment.

`enqueue` rather than `start`, because **`dagu start` ignores queues entirely.**
Only enqueued runs are governed, and queue names are the plane's whole lever on
concurrency (§7.1).

So the middle layer is not a thin detector. It resolves the project, exports
`DEVMAN_PROJECT_DIR`, and passes it as a parameter. That is §10's `devman run`,
and it is the reason there is exactly one place that triggers a workflow.

**Loop-breaking belongs to the workflow, and Dagu supplies the mechanism.** Any
workflow that writes files a watcher watches will chase itself: you save
`foo.py`, the watcher fires `format`, `format` rewrites `foo.py`, the watcher
sees that write and fires again. Two Dagu features stop it, and the plane owns
neither:

- **`type: build`** — a step declaring `inputs:` and `outputs:` is skipped when
  neither changed, and the output file is left byte- and timestamp-identical, so
  no watcher event is produced at all.
- **step-level `preconditions:`** — a command comparing a content hash, which
  covers rewriting a file in place, the case `type: build` cannot express.

Use a content hash rather than a timer or a suppression window, because a hash
gives the property that matters: **your own edit still fires.** Edit `foo.py`
right after the formatter touched it and the hash no longer matches, so the work
runs. A window would have swallowed it. This is stated once, here, because it is
narrow — it applies only where a workflow writes inside its own trigger's watch
scope — and because it is silently wrong when reinvented badly.

---

## 9. State

### 9.1 Identity

Never commit a developer's absolute path.

```
avoid:   working_dir: /home/andrew/Documents/Projects/Pyjutsu
prefer:  project: pyjutsu          → resolved by the registry
```

Identity defaults to the repo's directory name. Registration refuses a duplicate,
which is when you set `project` by hand.

This is what makes moving a repo, a second machine, a second checkout, and a
future remote worker all work without editing a workflow.

### 9.2 On disk

Machine-side holds the registry, and nothing else:

```
~/.local/share/devman/projects/<project>/
├── metadata.json              # identity and path
└── workflows/*.yaml           # the projection
```

Everything a run produces stays with the checkout that produced it:

```
<repo>/.devman/
├── workflows/                 # tracked — Dagu YAML, the last layer (§7.3)
└── .runs/                     # ignored
    ├── metadata.jsonl         # one line per run — written by Dagu, see below
    └── logs/ artifacts/ reports/
```

**`metadata.jsonl` is written by Dagu, and no workflow carries a line of it.**
The machine puts a `handler_on.exit` block in `base.yaml`; it runs for every DAG,
on both the success and the failure path, and appends one record to the
triggering project's `.runs/`. It is named `.jsonl` to keep it distinct from the
registry's own `metadata.json` above, which holds identity and path.

**Dagu's run history stays machine-side**, under `DAGU_HOME/data/`, and no
per-DAG field relocates it. Logs follow the project; history does not. That is
also why a cross-repo run (§11) does not appear in each participating project's
history — a child run is stored nested under its parent's record, not as an
independent run of the child DAG.

**Two locations, one rule each.** The registry is machine-side because it is
machine-wide. Run output is repo-side because you read it from inside the repo
you were working in, and because it belongs to a **working tree, not a
project** — one project can be checked out twice, and each checkout runs and
fails on its own.

`.devman/workflows/` is tracked; `.devman/.runs/` is not. The devenv module adds
the ignore rule at registration, because an un-ignored `.runs/` turns the first
failed run into a dirty tree.

`workflows/` is an input to the projection, never a second source Dagu reads.

Dagu reads exactly one DAG directory — there is no list form — so the projection
reaches per-project files by subdirectory or by symlink, and §5.2's two
`dag_discovery` knobs are what make either visible. A directory symlink is not
followed at all, at any setting; only file symlinks are.

### 9.3 Canonical and operational

> **Everything under `~/.local/share/devman/` is reconstructable by re-entering
> every registered repo's shell.** The registry, the queues, the run history, the
> logs, the temporary workspaces.

Canonical state is the repo's history, its `.devman/workflows/`, its devenv
definitions, and this flake. **Rebuilding the Dagu service must be inconvenient,
not catastrophic** — a design constraint, not an observation. Anything that
would make a rebuild catastrophic does not belong in Dagu state.

### 9.4 Secrets

A workflow references a symbolic name and never carries a value. **That is Dagu's
own `secrets:` field, not a devman convention** — the same win §7.1 claims for
`queue:`:

```yaml
# in the workflow that needs it
secrets:
  - name: GITHUB_TOKEN
    provider: env
    key: GITHUB_TOKEN
```

The module reads values from the machine's secret manager and sets them on the
Dagu **user service** (§4); Dagu resolves each declared secret at run time and
hands it to devenv, devenv to the task. One path, one place to look. **The repo
declares a dependency on a secret and never holds one** — and that declaration is
now machine-checkable, because it is a field rather than an assumption.

Two properties a plain injected environment variable does not have, and both are
reasons to declare secrets this way even though the module still supplies the
values:

- **Dagu masks a resolved secret in logs and output.** The step receives the true
  value; the log holds `*******`. Without this, any step can echo a token into a
  log that lands in `.devman/.runs/`, and from there into a screenshot or a bug
  report.
- **A missing secret fails the run before any step runs**, naming the secret and
  the provider. Contrast an unresolved path variable (§7.2), which fails silently
  and creates a wrongly-named directory.

The block is **per workflow**, so a workflow reaches only the secrets it
declares. Dagu will also accept a `secrets:` block in `base.yaml`, which would
remove these lines from every workflow at the cost of granting every workflow on
the machine every secret. Do not: it would delete the sentence this section
exists for.

---

## 10. The CLI, deferred

Three commands.

| Command | Does |
|---|---|
| `devman run <workflow>` | trigger a workflow in the current project |
| `devman show <workflow>` | print the resolved file, to start an override (§7.3) |
| `devman doctor` | diagnose the plane, and report shadowed files and their drift |

No `list`, `status`, `register`, or `unregister`. Registration is automatic
(§5.2) and has no manual path; the rest is what `doctor` reports.

**`doctor` reads far more than it computes.** Dagu already diagnoses the failure
§15.3 accepts as the price of one shared instance:

| Symptom | Where it comes from |
|---|---|
| a wedged queue, and *why* | `GET /queues/{name}/items` — every waiting item carries a reason and a message |
| what holds the slot, and since when | the same call's `running[]` |
| a run whose process is gone | `dagu ps`, the `FRESH` column — but not for the first 90 seconds |
| whether the plane is up at all | `GET /health` |

Four things it must compute itself, because nothing in Dagu reports them:

1. **A workflow that fails to load.** `dagu ls` lists it with no indication at
   all. Run `dagu validate` over each projected file; it exits 1 and names the
   problem.
2. **A misspelled queue name.** Dagu accepts an undefined queue silently and
   applies no limit (§15.4). Check every resolved `queue:` against the queue list
   the machine declares.
3. **An unresolved `DEVMAN_PROJECT_DIR`.** Look for a directory named literally
   `${DEVMAN_PROJECT_DIR}`. It is the visible symptom of a trigger that passed the
   parameter but forgot the environment variable (§7.2).
4. **Shadowed files and their drift** (§15.6).

Three of those four are file checks over the projection rather than queries
against a running service. `doctor` should therefore still work with the daemon
down, and say plainly which checks it could not run.

**`devman run` and `devenv tasks run` are not alternatives.** They are two
levels of one stack: `devman run` triggers a workflow, and that workflow's steps
call `devenv tasks run` (§6). You reach for the first to run a pipeline and the
second to run one step.

**Do not build any of it at stage 1.** Prove the conventions by hand first. A CLI
written before the vocabulary settles freezes the wrong vocabulary and then
defends it.

---

## 11. Cross-repository workflows

A workflow spanning several projects belongs to none of them. It belongs to
**this repository** — devman registers itself like any other project, so a
cross-repo workflow is simply one of devman's own files:

```
devman/.devman/workflows/stack-validate.yaml
```

```
              Dagu
                │
   ┌────────────┼────────────┐
library A   library B   application
   └────────────┼────────────┘
                ▼
       integration workflow
```

Its steps trigger other projects' workflows rather than running commands, so it
resolves nothing itself. Nothing needs a path — but one rule is what makes that
true, and without it every parent-child pair in this design collides silently:

> **`DEVMAN_PROJECT_DIR` names the project a run targets, and is set only by
> whatever triggers the run.** A workflow that triggers other workflows must not
> hold that name itself. If it needs its own directory for local steps, it uses a
> second name. A parent directs a child with `with.params`.

A parent exports its parameters into each child's environment, and that
environment outranks the child's own `params:`, its `env:` block, and even an
explicit `with.params` override — whenever the names collide. Once the names
differ, `with.params` works exactly as documented, and a parent can deliberately
point a child at a different project, which synchronized releases and coordinated
migrations will want.

The collision is worth stating plainly because of how it fails: the child runs,
succeeds, and does the work in the wrong directory. Nothing reports it. `doctor`
checks it mechanically (§10) — any workflow containing `action: dag.run` must not
also mention `DEVMAN_PROJECT_DIR`.

Uses: validating dependent libraries together, synchronized releases, nightly
stack validation, cross-repo benchmarks, coordinated migrations.

**This closes the one exception the layout had.** Run output goes to
`devman/.devman/.runs/` (§9.2), by the same rule as every other project. There
is no `machine` group and no machine-side run store.

---

## 12. Riskiest claims

### 12.1 Dagu supports what the design assumes — spike, before stage 1

> Dagu accepts a named queue on a DAG, interpolates an environment variable in
> `working_dir`, can be told where to write a run's logs, and lets one DAG trigger
> another.

§7.2 rests on the first two, §9.2 on the third, §11 on the fourth. If
`working_dir` does not interpolate, one group file cannot
serve many repos and registration has to rewrite each projection — recoverable,
but it makes the plane parse files it currently never touches. If queues are not
named per DAG, the first of §7.1's three global names has nothing to bind to.

*Measure:* write one DAG naming a queue with an interpolated `working_dir`, run it
against two projects, and confirm its logs land under each project's
`.devman/.runs/`.
*Fails if:* interpolation or per-DAG queues are unsupported — the plane then
rewrites files at projection, and §7.2's "devman never parses a workflow"
becomes false. If only the log path is fixed machine-wide, §9.2 moves run output
back beside the registry.

This spike is first because it is cheap and because the charter assumed a
feature set it never checked.

> **Settled, and it passed.** All four hold: a DAG names a queue, `working_dir`
> interpolates at run time, `log_dir` is per DAG, and one DAG triggers another
> and waits. The measurement ran — one unedited file, two projects, logs under
> each project's own `.devman/.runs/`. What changed was never the shape, only the
> detail: the spelling of the key, the source of the variable, and §11's rule.

### 12.2 devenv is affordable as the universal executor

> Routing every task through `devenv tasks run` costs little enough that nobody
> reaches around it.

Spike A settled this: **0.16s warm**, 5.46s cold, 1.44s after a content change.
Recorded here because the whole single-implementation rule (§6) rests on it, and
because it is a regression test (§14, criterion 7), not because it is open.

### 12.3 One flake serves both interfaces cleanly — spike, at stage 1

> A NixOS module and a devenv module can live in one flake, at one version,
> without either constraining the other's nixpkgs.

The residual unknown is input collision. A repo's devenv pins
`devenv-nixpkgs/rolling`, the machine pins its own nixpkgs, and `modules/` is
evaluated under the repo's. If the module needs packages the repo's nixpkgs
lacks, or the two disagree on a shared input, the single-version premise
weakens.

*Measure:* build the smallest real pair — a NixOS module that starts Dagu, a
devenv module that registers one project — and import both from one flake into
this repo and this machine.
*Fails if:* the module must pin its own nixpkgs. The plane then ships two
flakes, and §3.1's anti-drift argument weakens to a convention.

### 12.4 Whole-file shadowing is coarse enough to live with

> Repos override whole workflow files rarely enough that the copied duplication
> does not accumulate.

§7.3 refuses field merging, so changing one step of `check` means copying
`check.yaml` into the repo, where it stops tracking upstream (§15.7).

Measure at stage 2 across five real repos: **how many files were overridden, and
how much of each is unchanged from the group version?**

A file copied to change one line is the failure mode. If it is common, the fix
is smaller group files — split `check.yaml` into what varies and what does not —
not a merge algorithm.

---

## 13. Rollout

### Stage 1 — the flake foundation

Spikes §12.1 and §12.3 first; either can change the shape. Then:

```
nixosModules.default    one Dagu service, config, state paths
modules/                selection and identity
workflows/base          check, validate, full-test
workflows/python        one ecosystem group, to prove shadowing
registration            enterShell, hash-guarded (§5.2)
```

**Delete `src/devman/` (§3.3).** Adopt in exactly one repo — this one.

### Stage 2 — convention and registration

```
automatic registration (§5.2, enterShell + hash guard)
the metadata schema
Dagu queues and concurrency limits
artifact and run-state layout (§9.2)
.devman/workflows/ shadowing + devman show (§7.4)
```

Adopt across five repos and run §12.3's measurement: **how many files were
overridden, and how much of each is unchanged?**

### Stage 3 — reactivity

```
watchexec triggers, VCS hooks
retention policy
devman run / show / doctor (§10)
```

### Stage 4 — higher-level automation

Only once every layer below is stable.

```
review workflows   release   maintenance   benchmark campaigns
agent workflows    policy gating
```

---

## 14. Success criteria

| # | Criterion | Measured by |
|---|---|---|
| 1 | One flake, two interfaces, one version | the machine and this repo import the same rev; `nix flake check` passes |
| 2 | A repo adopts the plane in three lines | `enable`, `project`, `groups`; no Dagu YAML and no per-workflow config |
| 3 | A repo may take no groups at all | `groups = []` plus its own `.devman/workflows/`; every workflow runs |
| 4 | **A repo may rename or replace every default** | drop `check`, define `smoke` and `ci`; both run, and nothing in devman objects |
| 5 | Shadowing is exact | `devman show check` saved to `.devman/workflows/check.yaml` projects identically; edit one step and only that step changes |
| 6 | A workflow is portable Dagu | one group file, unedited, runs correctly in every repo that takes the group |
| 7 | devenv stays on the fast path | `devenv shell -- true` ≤ 0.25s warm — Spike A regression |
| 8 | Registration is automatic and idempotent | enter a shell twice; the registry is written once |
| 9 | Registration covers only opted-in repos | a repo without `devman.enable` never appears in the registry |
| 10 | No workflow contains an absolute path | grep the registry and `workflows/`; zero hits |
| 11 | Identity survives a move or a rename | move and rename the directory, re-enter its shell — same project, same run history |
| 12 | Queues are real | two workflows naming the `exclusive` queue serialize **when enqueued** — `dagu start` bypasses queues entirely, so the measurement must use the real trigger path (§8) |
| 13 | The watchers do not chase each other | a file-writing workflow plus a watcher on those files, one save, exactly one run |
| 14 | The task graph exists once | no default workflow re-states a dependency devenv already declares |
| 15 | A rebuild is inconvenient, not catastrophic | delete Dagu state, re-enter every registered shell, every workflow runs again |
| 16 | devman adopts itself | this repo registers as a project, and its cross-repo workflows run from `.devman/workflows/` (§11) |
| 17 | There is one way in | no manual register path exists; deleting the registry and re-entering every shell restores it exactly |

**Criterion 4 is the one that keeps §7 honest.** If a repo cannot rename or
replace a default without something in devman objecting, the plane has grown an
opinion it should not have. Criterion 16 keeps §9.3 honest.

---

## 15. Sharp edges

**15.1 Registration cannot happen at evaluation time.** Nix eval is pure, so
§5.2 puts it in `enterShell` behind a hash guard. A repo is invisible until you
enter its shell once. Do not solve this by scanning.

**15.2 `.devman/` has carried other meanings.** Some repositories already hold a
`.devman/` of an older shape. Registration must detect a directory it does not
recognize and report it, never silently adopt it.

**15.3 One instance per machine is a shared availability failure.** A wedged
queue blocks every repo, not one. §9.3 bounds the damage — state is
reconstructable, so recovery is a restart — but availability is genuinely
shared. Accepted, with one requirement: **`devman doctor` must diagnose a wedged
plane**, or a shared failure becomes an unexplained one.

**15.4 Queue names are the one-way door, and a typo is invisible.** Adding a
queue name is cheap; renaming one is a migration across every workflow that names
it. Worse, Dagu accepts a queue name that does not exist **silently** — no error,
no warning, nothing in the logs — and runs the workflow with no concurrency limit
at all. A misspelled queue is not a migration problem, it is an unobservable one,
which is why §10 makes `doctor` check every resolved `queue:` against the
machine's list, and why §7.2 has the machine set a default queue in `base.yaml`.

**15.5 devenv and NixOS may want different nixpkgs.** §12.3. If they do, the
single-version guarantee becomes a convention rather than a property.

**15.6 An overriding file stops tracking its group.** A repo that shadows
`check.yaml` keeps that version forever, and §7.3 offers no partial override.
`doctor` counts shadowed files and reports how far each has diverged from the
group version.

**15.7 Nothing checks that a default still fits.** Since the plane holds no
opinion about what a workflow costs, a `check` that grows to four minutes is
invisible to devman. That is the deliberate trade: no policing, and no false
alarms from a heuristic that cannot know your machine. Notice it yourself.

---

## 16. Open questions

- **Registry root.** `~/.local/share/devman/`. Confirm nothing else claims it.
- **Do ecosystem groups ship in this flake?** In-repo is simpler and couples
  group churn to plane releases. Lean: in-repo until a third party wants to
  publish one.
- **Does the machine module manage a Dagu it did not install?** Lean: no — own
  the service, and document the conflict.
- **How many ecosystem groups at first?** Python and Nix. Rust and TypeScript
  on demand.
- **Retention.** `.devman/.runs/` grows inside the repo, where it is at least
  visible. Lean: 7 days for logs and artifacts, keep `metadata.jsonl`
  indefinitely — it is small and it is the run history. **Partly settled:** Dagu's
  `hist_retention_days` is set once in `base.yaml` and governs its own
  machine-side history. It does **not** prune the log tree under `log_dir`, so
  the log half of this lean still needs an owner.

---
