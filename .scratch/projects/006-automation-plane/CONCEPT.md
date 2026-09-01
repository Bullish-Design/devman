# devman — Concept (the automation plane)

> **STATUS: PROPOSED (2026-08-21). Reconciled against Investigations A, E, B, C
> and D (2026-08-22). Amended twice during stage 1, twice during stage 2, twice
> during stage 3, twice during stage 4, once during stage 5 and three times
> during stage 6 (2026-08-22), each time because building the thing measured
> something the investigations had not. **Stage 6's three, and they are one
> change: §9.2's projection is a generated file rather than a symlink, §7.2 says
> so, and §8's third trigger arrow is therefore Dagu's own scheduler reading the
> workflow's own `schedule:` key. A schedule is content, it adopts itself with
> the group, and no systemd unit holds a project name any more
> (`STAGE_6_LOG.md`, S2 and S3).** **Stage 5's one: §9.2 now says the flat DAG key `<project>-<workflow>` is
> not injective — two projects can render one name, the second projection takes
> the link, and the measured result was a run that executed another
> repository's workflow and reported success (`STAGE_5_LOG.md`, S6).**
> **Stage 4's
> two: §8's third trigger arrow is a user timer running `devman run` rather than
> Dagu's own scheduler, because a scheduled run leaves both directory fields
> literal and then fails on the machine's exit handler; and §9.2 now says that a
> workflow defining its own `handler_on` silently stops recording its runs
> (`STAGE_4_LOG.md`, S2 and S3).** Stage 3's two: §8 now names
> **two** loops rather than one, because removing the watcher's ignore of
> `.devman/.runs/` produced 107 dispatches and 60 runs from one save, and no
> workflow-level mechanism can stop that (`STAGE_3_LOG.md`, S8); and criterion 13
> counts runs that **do work**, because E1 measured that Dagu skips after
> enqueueing rather than before, so a correct plane produces one run that formats
> and one that skips (S6). §11's `doctor` check now distinguishes a workflow that
> *holds* `DEVMAN_PROJECT_DIR` from one that *passes* it to a child, because the
> rule as written reported the first real cross-repo workflow as broken
> (`STAGE_2_LOG.md`, S8). And §7.1's closed list is **four** names rather than
> three: running that workflow made its exit handler fail and fail the whole
> run, so `DEVMAN_SELF_DIR` had to become a name the machine states rather than
> one each workflow picks (S12, changing §7.1, §9.2 and §11).
> §9.2 gains the `dags/` directory, because a DAG is keyed by its file's base
> name and the layout as written made two projects' `check` invisible
> (`STAGE_1_LOG.md`, S1). And every task name gains its group as a namespace,
> because devenv rejects a bare one and the charter's own examples therefore
> did not evaluate (`STAGE_1_LOG.md`, S7).**
>
> Every edit made by that reconciliation rests on a measurement recorded in
> `FINDINGS.md`. **All five investigations are closed**, and
> `KICKOFF_PROMPT.md` §6's five gates are met, so planning may start.
>
> One section was deleted outright: §8.1, because Dagu already does what it
> described. **Nothing was killed** — no finding forced a redesign.
>
> Three claims in the previous reconciliation were later measured to be false,
> and are corrected here rather than merely amended: the symptom of a stale
> `config.yaml` (§5.2), retention's reach over the log tree (§16), and whether
> NixOS restarts a systemd user service on activation (§5.2). `FINDINGS.md`
> records them as supersessions.
>
> `001`–`005` were earlier attempts to define devman. They are superseded and
> carry no authority here. Nothing in this charter depends on them. **The
> `devman` binary they produced is a different matter — see §3.3.**
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
3. **A contract** — four names, and nothing else (§7).

Item 3 is deliberately thin. The plane needs a queue it can run in, a path shape
it can write to, and a variable naming where the work happens — plus a second
variable for the one workflow that targets no project because it directs others
(§11). That is the whole of what it understands, and the machine states all four
once (§7.1).

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
├── modules/devenv.nix         # repo interface — the name is required (§3.2)
├── groups/                    # content, not contract (§7.2)
│   ├── base/                  # check, validate, full-test
│   ├── python/ nix/ rust/     # ecosystem groups
└── src/devman/                # the CLI — run, show, doctor, and the watcher (§10)
```

| Output | Consumer |
|---|---|
| `nixosModules.default` | the machine's NixOS configuration |
| `modules/` *(a path — §3.2)* | every repo's `devenv.yaml` |
| `packages.default` | the `devman` CLI — put on `PATH` by the NixOS module |
| `checks` | integration tests for the plane |

There is no `lib/`. An earlier draft of this diagram gave one to the registry
schema and to registration helpers; three stages ran without it. The schema is
text, stated once in `modules/devenv.nix` where the hook renders it, and the CLI
reads that text back. Shared *code* between the two interfaces is the one thing
§3.1's second rule warns against (`STAGE_3_LOG.md`, S17).

One flake version defines both interfaces. That is the point: it removes drift
between Dagu config, queue names, registry layout, and repo integration. Those
four must agree, and nothing else makes them.

**Two rules keep that a property rather than a convention**, and Investigation B
measured both. **The modules take `pkgs` from their consumer** — the devenv
module from the repo's `devenv-nixpkgs/rolling`, the NixOS module from the
machine — never from this flake's own `nixpkgs` input, which serves `packages`
and `checks` only. That is what lets one flake serve two nixpkgs without either
constraining the other. And **what the two interfaces share must be text**:
queue names, `DEVMAN_PROJECT_DIR`, `DEVMAN_SELF_DIR`, the `.devman/.runs/` path
shape, and the registry schema. `nix/dagu.nix` is the single exception, and it costs two store
paths holding one identical binary. Any *other* shared package would pay the
same duplication with no such guarantee — the machine and a repo differ by
hundreds of attributes, and `sed`, `git`, `python3` and `bash` all differ in
version between them, silently.

> **AMENDMENT — the second exception is `nix/renderer.nix`** (project 009,
> stage 3, `STAGE_9_LOG.md` S-3). The projection's renderer is a Python program,
> which this rule says must not be shared; it is built under each consumer's
> nixpkgs anyway, on the same terms as `nix/dagu.nix` and from the same source
> tree as `packages.default`.
>
> **The deciding argument is the shell-entry guard, not the charter.** The
> alternative was for the devenv module to call `devman` from the machine's
> PATH, which works — a devenv shell inherits the machine profile's PATH. It
> fails for one reason: a PATH lookup is a **run-time** fact, so the devenv
> module cannot know the renderer's identity at evaluation time, so it cannot
> put that identity into `planFile`, so **the guard cannot observe it**. Upgrade
> the machine's `devman` and the rendering rules change while every repository
> keeps a projection produced by the old renderer — the entry still matches,
> nothing re-projects, and Dagu keeps reading stale bytes. That is
> `STAGE_7_LOG.md` S-5a exactly.
>
> It would also invent a version-skew axis the plane does not have. The devenv
> module comes from the repository's pinned rev and the CLI from the machine's;
> today they share only `metadata.json`, a text schema with a version number and
> soft degradation. Moving rendering *semantics* across that boundary turns a
> soft-degrading schema into a hard shell-entry dependency between two
> independently-pinned components.
>
> §3.1's second rule exists to stop silent drift between the two interfaces.
> Sharing the renderer as a machine-side binary **creates** that drift, in the
> one form the guard cannot see: an unversioned run-time dependency whose
> identity is not an evaluation-time fact. Building it under each consumer's
> nixpkgs makes the renderer's identity observable to the guard. The exception
> applies §3.1's own reasoning to a case its text did not anticipate.

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

> **The file inside must be named `devenv.nix`.** devenv resolves
> `<input>/<subdir>` to `inputs.<input> + /<subdir>` and then requires a
> `devenv.nix` inside it. A `default.nix` is **never** consulted, and the error
> names a file you did not write: `devman/modules/devenv.nix file does not
> exist`.

Pin with `git+`, and know the local-source constraint. A `github:` input hits
the API rate limit on every evaluation. **Both `git+https:` and `git+file:`
record `rev` and `narHash` in `devenv.lock`.** A `git+file:` input reads
committed files only, so a consumer does not see an uncommitted local edit.
Use `path:` for the one repository under active edit; use `git+file:` for every
other local consumer.

**A devenv input is not free.** Declaring and importing the plane costs about
20 ms on every shell entry, before registration does anything (§14, criterion
7). That number is why groups ship inside this flake rather than beside it
(§16).

### 3.3 The current source is deleted — the installed binary is not

`src/devman/` predates this charter and shares none of its model. Delete it
rather than porting it; the CLI (§10) starts from the registry.

**Deleting a repository does not uninstall a profile.** `devman 0.2.0` is
installed on the development machine today, at
`/etc/profiles/per-user/andrew/bin/devman`, and it owns the `devman` command. It
ships its own `up`, `down`, `switch`, `bootstrap`, `index`, **`doctor`** and
**`init`** — the last two meaning something entirely different from §10's. It
also writes a `.devman/` of its own shape and, with `--force`, **deletes one it
does not recognise** (§15.2).

**Removing `devman-0.2.0` from the profile is a stage-1 task, not a cleanup.**
Until it is gone, `devman doctor` resolves by profile order rather than by
intent.

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

**A user service needs `users.users.<name>.linger = true`.** Without lingering,
the user manager exists only while that user is logged in, so the plane is not
running on a machine nobody has logged into — and, more subtly, activation
cannot restart it either. `switch-to-configuration` reaches exactly the users
`logind` lists (§5.2). Lingering is what makes the plane a machine service
rather than a session service.

**One instance, not one per project**, and queues are the reason. A queue's
concurrency limit is per instance, so ten project daemons each holding
`exclusive: max_concurrency 1` would give ten concurrent "exclusive" runs, and
success criterion 12 could not hold. Per-project instances would also need four
ports allocated each, and would not remove anything from §7.2.

nixpkgs packages no Dagu at any version, so the plane carries its own package
expression, and both interfaces call the same file.

**The module owns the service, and does not manage a Dagu it did not install.**
It cannot: the scarce resource is **ports, not state**. A second instance with
its own `DAGU_HOME` still fails, because Dagu binds a coordinator port and a web
port:

```
Error: failed to initialize coordinator: failed to create listener on
       127.0.0.1:50055: listen tcp 127.0.0.1:50055: bind: address already in use
```

That is the whole conflict, and it is **loud** — a named port, a named error,
exit 1, visible in `systemctl --user status dagu`. It is the reason "own the
service, document the conflict" is safe rather than reckless. Two requirements
follow:

- **The module exposes the ports as options**, so a developer running a
  project-local Dagu can move one of the two rather than choose between them.
  Dagu's defaults are **8080** (web) and **50055** (coordinator).
- **`Restart=on-failure` is bounded.** A port conflict never resolves on its
  own, so an unbounded restart loop retries every five seconds forever and fills
  the journal. Cap it with `StartLimitBurst`, or treat a bind failure as fatal.

**This repository is the first conflict to reconcile.** Its own `devenv.nix`
carries `processes.dagu.exec = "dagu start-all"`, which holds both ports
whenever `devenv up` is running. Criterion 16 says devman adopts itself, so
stage 1 removes that process rather than working around it.

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

tasks."python:lint".exec      = "ruff check .";
tasks."python:typecheck".exec = "basedpyright";
tasks."python:test".exec      = "pytest";
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

**Every entry path takes it.** `devenv shell`, `devenv shell -- cmd`, an
interactive shell, `devenv test`, `devenv tasks run`, `devenv up`, `devenv
processes up`, direnv's `use devenv`, and `devenv hook`'s auto-activation all
run `enterShell` and all register. The commands that do not — `info`, `eval`,
`build`, `repl`, `search`, `version` — build or inspect the configuration and
never place you in the environment, so a repo cannot silently miss registration
through them. Criterion 17 rests on this, and it holds on devenv 2.1.2 and
2.2.2 alike.

**`enterShell` runs twice per `devenv shell`, and the guard is what makes that
free.** devenv runs the whole hook once in a throwaway subprocess whose only
purpose is to snapshot `env`, then again for real. `devenv up` and `devenv tasks
run` fire it once. Two rules follow, and both are requirements rather than
observations:

- **A registration hook must be idempotent.** Every side effect happens twice.
- **A registration hook must fork nothing.** It sits on the critical path of
  every shell the developer opens and its cost is charged twice, so a `sed` and
  a `cat` cost four processes per entry. Bash parameter expansion and
  `$(<file)` do the same work without forking, and the difference is 8.36 ms
  per call against 0.12 ms (§14, criterion 7).

**A registration hook cannot report anything on the path that writes.** The
firing that performs the write is the throwaway subprocess, and devenv discards
its stdout and its stderr; by the time the real shell runs the hook, the entry
on disk already matches and the guard takes the silent branch. So there is no
"devman: registered" line and there cannot be one. **Anything the developer must
see belongs on a path that does not write** — a refusal (§9.1), or `devman
doctor` (§10). This is also why §9.1 refuses a duplicate rather than replacing
it: refusing is the branch that stays visible.

**Restoring a deleted registry means entering a shell.** `cd`-ing back into a
directory whose direnv environment is already loaded in the current process is
not an entry and runs nothing. Open a new shell, leave and return, or `direnv
reload` — all three re-run the hook. Criterion 17's promise is about shell
entry, not about the working directory.

**Adding a workflow needs no restart. Changing Dagu's config does.** A new file
in the DAG directory is picked up by the already-running service, so registration
can project a repo's workflows and have them runnable immediately. But the
instance `config.yaml` is read only at startup. **A machine module that rewrites
`config.yaml` must restart the service in the same activation.**

> **What a missed restart looks like is worse than an error.** It is not an
> error at all. The CLI reads the new `config.yaml` and enqueues happily, the
> run runs, `dagu ps` prints the new queue's name as though it were real, and
> every exit code is zero. The only trace is one `INFO` line in the server's own
> log giving the wrong number — `max-concurrency=1` for a queue configured with
> 4. A queue silently running at the wrong concurrency is §15.4's unobservable
> failure arriving by a second route.

**NixOS does restart a user service on activation, and `restartTriggers` is the
whole mechanism.** `switch-to-configuration` visits the user scope, spawns
itself once per user `logind` lists, and applies the same unit-file comparison
it applies to system units. A `restartTriggers` change rewrites the unit's
`X-Restart-Triggers=` line, so the unit differs, so it stops and starts inside
the activation — before `switch-to-configuration` returns. Measured on nixpkgs
`26.11.20260705.d407951`; name the revision, because this is a property of
`switch-to-configuration` rather than of NixOS in general. **No path unit, no
`daemon-reload` hook, and no re-readable config file is needed.** What *is*
needed is §4's `linger = true`, because the restart reaches exactly the users
`logind` lists.

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
python:  python:lint  python:typecheck  python:test  python:integration-test
nix:     nix:flake-check  nix:build
rust:    rust:clippy  rust:cargo-check  rust:test
```

**The prefix is devenv's requirement, not the plane's.** devenv rejects a bare
name outright — `Invalid task name: lint. Task names must be in format
'namespace:name'` — so a group's workflows have to carry one. The group's own
name is the namespace, which is what "group-local" above means made literal,
and it is what stops two groups' `lint` from colliding in a repo that takes
both. The cost is that such a repo defines both sets, which §7.4 already
answers: to be rid of one, do not take its group.

One logical task has one implementation, and every caller reaches it the same
way — a workflow step, a hook, a person at a prompt:

```
prefer:  devenv tasks run python:test

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

**Four names, and the list is closed.** The machine and every workflow must
agree on exactly these:

| What | Whose field | Where the machine states it, once |
|---|---|---|
| the queue names | Dagu's `queue:` | `config.yaml`, with each queue's limit |
| the variable `DEVMAN_PROJECT_DIR` | a name, not a field | `base.yaml`; the trigger supplies the value |
| the variable `DEVMAN_SELF_DIR` | a name, not a field | `base.yaml`'s exit handler, as a fallback (§11) |
| the `.devman/.runs/` path shape | Dagu's `log_dir:` | `base.yaml` |

**The fourth name was three until stage 2 ran a cross-repo workflow.** §11
already required a workflow that triggers other workflows to name its own
directory with "a second name", and never said which. That was survivable only
while nobody wrote one: `base.yaml`'s exit handler writes to
`$DEVMAN_PROJECT_DIR`, which such a workflow must not hold, so the handler
expanded to `/.devman/.runs/…`, failed, and failed the whole run **after both
children had succeeded**. A workflow picking its own second name would be
silently unrecorded, because the machine's handler has to know the name. So the
machine states it, once, like the other three (`STAGE_2_LOG.md`, S12).

**Queue names.** The machine module creates Dagu queues and sets what each
costs; a workflow names one. It is Dagu's own field, not a devman word for it.

```
light   normal   heavy   gpu   exclusive
```

An earlier draft of this section claimed queue names were the *entire* shared
vocabulary. They never were: §7.2's portable workflow also rests on one agreed
variable name and one agreed path shape. What is true, and better, is that **the
machine states all four in one file it writes**, rather than every workflow
repeating them.

**Everything else belongs to the repository** — task names, workflow names, what
a workflow does, how long it takes, and every line of the file, which is Dagu's
schema throughout.

**Task names cannot be reserved**, because ecosystems decompose differently.
`nix flake check` is not a lint, and Nix has no `typecheck` distinct from
`build`. Forcing every ecosystem into a Python-shaped split produces empty tasks
or lies. They need to be stable only *within* a group, because only that group's
files call them.

**Workflow names are not reserved either.** The base group ships `check` and
`test` because most repos want a fast one and a gate — so `devman run check`
usually resolves. There is no third rung: an exhaustive tier was measured to
carry no information in more than half the population (stage 7). A repo that
wants `smoke` and `ci` renames the files. The plane does not police what a name means,
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
    run: devenv tasks run python:lint
  - name: typecheck
    run: devenv tasks run python:typecheck
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

**devman never parses a workflow, and since stage 6 it writes four lines above
one.** It resolves which file wins (§7.3) and projects it, and the projection is
a generated file: a header stating this project's `working_dir`, `log_dir` and
directory variable, then the source body byte for byte. The plane still reads
nothing out of the body and rewrites nothing in it — §12.1 named this exact
fallback in advance, and what forced it was §8's third arrow rather than a
failure of interpolation.

An earlier draft added an `x-devman` block carrying `kind` and `resource`; both
duplicated a Dagu feature, so the block is gone and the plane invents no key of
its own. Every line the header writes is Dagu's.

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

tasks."python:lint".exec      = "ruff check .";  # your primitives, your names
tasks."python:typecheck".exec = "basedpyright";
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
filesystem change → watchexec       → devman run → dagu enqueue
commit / push     → hook            → devman run → dagu enqueue
schedule          → Dagu's own scheduler, from the workflow's own `schedule:`
```

**The first two arrows reach Dagu through `devman run`. The third does not, and
it took two stages to get there.**

A schedule is declared **in the workflow file**, in Dagu's own `schedule:` key,
and Dagu's own scheduler fires it. That is only possible because the projection
**states** each project's `working_dir`, `log_dir` and directory variable rather
than interpolating them: under `schedule:` the enqueueing process is the daemon,
which has one environment for the whole machine and no parameter to fill, so a
projection that interpolated `${DEVMAN_PROJECT_DIR}` produced a run in a
directory of that literal name, in `$HOME`, and then failed on `base.yaml`'s
exit handler (`STAGE_4_LOG.md`, S2). With a generated per-project file the same
daemon dispatches correctly, works in the project, writes its logs there and
records the run (`STAGE_5_LOG.md` S12, `STAGE_6_LOG.md` S3).

**Between stage 4 and stage 6 this arrow was a systemd user timer running
`devman run --project <name>`**, and that is still a legal way to schedule
anything. It is no longer the recommended one, because it holds project names
outside every repository: a repository that adopted a scheduled group was not
scheduled until somebody edited a unit, and nothing reported the gap
(`STAGE_5_LOG.md`, S9). A schedule in the file adopts itself.

**A schedule is content, exactly as a queue name is** — so it is shadowed by
§7.3 like everything else in the file, and a repository refuses one by shadowing
the workflow or by not taking the group.

So a schedule is **selection**, like a VCS hook, and it belongs to whoever wants
it: a systemd user timer running `devman run <workflow> --project <name>`. devman
supplies no option and no command for it, for the reasons S9 gives about hooks —
a machine-side schedule option would make the machine hold a project name and a
workflow name, which is the one thing §4 says it never learns. What the local
trigger buys is every refusal in `devman run`: a schedule that cannot be
resolved gets a non-zero exit and a message naming what is missing, instead of a
successful run in a garbage directory.

| Layer | Job |
|---|---|
| watchexec, hooks, timers | detect that something happened |
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

**One watcher per machine, not one per repository.** The watcher is a systemd
user service from the same module that installs Dagu, running `watchexec`, and
it reads the registry (§9.2) for the paths to watch. Per event it invokes
`DEVMAN_PROJECT_DIR=<path> dagu enqueue …` locally, which is what keeps `log_dir`
resolving into the right project.

**The reason is lifetime, not capability.** A per-repo watcher has exactly one
plausible home — a `processes.` entry in that repo's own devenv — and devenv
processes start under `devenv up` and nothing else. Not `devenv shell`, not
direnv entry, not `devenv test`. A per-repo watcher would therefore be alive
only while the developer is running `devenv up` in the foreground, and §8's
reactivity would silently apply to whichever repos someone happened to have open.
devenv has no watch primitive of its own to fall back on.

**The watcher is plane machinery; the mapping is group content.** Which glob
triggers which workflow is data the single watcher reads, so a group still
declares its own reactivity and §7.1's "the machine states how much, never what"
stays intact.

> **The mapping is `groups/<group>/triggers.toml`** — a table of
> `<glob> = <workflow>`, resolved at evaluation time by the devenv module,
> whole-file and in the order the repository lists its groups, and recorded in
> the registry entry. Three other homes are closed: a workflow file may not carry
> it, because Dagu rejects an unknown top-level key and §7.2 makes a workflow
> Dagu configuration throughout; a Nix option may not, because §7.4 has no
> per-workflow option and a machine-side one would teach the machine a project
> fact; and a file the watcher reads at run time may not, because the watcher
> would then need §7.3's resolution too.
>
> **A workflow that writes the repository's own files without being asked is its
> own group.** §7.4's "an inherited workflow you never trigger costs nothing"
> does not carry over — such a workflow rewrites the developer's files while
> they are editing them — so the group that ships it ships the workflows it
> fires and nothing else. Taking it is the opt-in; not taking it is the whole
> opt-out (`STAGE_3_LOG.md`, S4). **What fires it is not the test; what it
> touches is.** A self-firing workflow that writes only under `.devman/.runs/`,
> which the plane created and the watcher ignores, may ride in a general group.
> `maintain` is the worked example, and its schedule is why the distinction had
> to be stated (stage 7).

The cost is honest and already accepted elsewhere: one watcher is a second
shared-availability failure alongside the one instance (§15.3). It is also why
loop-breaking below is now a question inside one process rather than between
many.

**There are two loops, and only one of them belongs to the workflow.**

The first is the plane's own. Every run creates a log directory under
`.devman/.runs/` inside the project (§9.2), so a watcher watching that project
sees its own runs. **The watcher must ignore the run-state directory**, and
nothing a workflow declares can substitute: a run whose every step is skipped
still creates its log directory. Measured — with that one ignore removed, a
single save produced 107 dispatches and 60 runs in 45 seconds, from a workflow
that writes none of the files it watches (`STAGE_3_LOG.md`, S8). The watcher
also ignores `.git`, `.devenv`, `.direnv`, `.venv`, `__pycache__` and
`node_modules`, and a group's glob is the first filter: a tool's own cache
directory is not on any list somebody can finish.

The second is the workflow's, and **Dagu supplies the mechanism.** Any
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

**Identity is stated, never defaulted from the directory name** (§5). A
directory-name default breaks criterion 11 by construction: rename the directory
and the default changes, so the repo re-registers as new and loses its run
history. `project` is a required option with no default, and omitting it is an
evaluation error rather than a surprise later.

**Registration refuses a duplicate — when, and only when, the recorded path
still exists.**

| recorded `path` | this checkout | reading | action |
|---|---|---|---|
| not on disk | anywhere | the project moved or was renamed | **replace** the entry |
| exists, same as `$DEVENV_ROOT` | same | nothing changed, or the groups did | write if different |
| exists, differs | different | two live checkouts claim one identity | **refuse and report** |

One `[ -d ]` is the whole test, and it costs no fork. It is what makes refusal
compatible with criterion 11: to the registry, "the same project entered from a
new path" and "two different projects sharing a name" look identical, and
whether the old path is still there is what separates them.

**Refuse rather than replace, for a reason that is not symmetry.** Replacing is
silent by construction — §5.2 explains why a hook cannot report on the branch
that writes — so two repos sharing a name would flip the registry's `path` on
every shell entry with nothing said. Refusing is the branch that does not write,
so it is the branch the developer actually sees:

```
devman: refusing to register 'test'
devman:   already registered at /tmp/c5-refA, which still exists
devman:   this repo is        /tmp/c5-refB
devman:   set a different devman.project in one of them
```

A refusal does not stop the shell from opening. The repo simply is not in the
plane, which is right for a repo whose identity is taken.

**Two live checkouts of the genuinely same project are also refused**, and that
is correct: the registry holds one `path` per project, so two checkouts cannot
both be it. Run output is unaffected, because it is repo-side and belongs to the
working tree (§9.2). The second checkout states a distinct `project`.

One limit worth stating: this test cannot tell a deleted repository from an
unmounted one. An unmounted checkout is replaced and drops out of the registry
until it is next entered — recoverable rather than lossy, because the registry
is derived (§9.3).

This is what makes moving a repo, a second machine, a second checkout, and a
future remote worker all work without editing a workflow.

### 9.2 On disk

Machine-side holds the registry, and nothing else:

```
~/.local/share/devman/
├── projects/<project>/
│   ├── metadata.json                    # identity and path
│   └── workflows/<workflow>.yaml        # the projection
└── dags/<project>.<workflow>.yaml       # Dagu's flat view of it
```

**`dags/` is Dagu's view, and `projects/` is devman's.** The second directory
is not a convenience — see the measurement at the end of this section.

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

> **A workflow that defines its own `handler_on` takes the writer away.**
> `base.yaml` is inherited whole-field, so such a DAG replaces the machine's
> handler and its runs are never recorded. Measured: the run succeeds, the logs
> land in the right project, `dagu status` is clean, and `metadata.jsonl` gains
> no line (`STAGE_4_LOG.md`, S3). That is §7.3's whole-file shadowing arriving
> one level below a group, in the machine's own defaults. **No workflow should
> define `handler_on`**, and one that must has to re-state the machine's
> `printf` as well — a promise no repository can keep across a change to the
> module.

**Dagu's run history stays machine-side**, under `DAGU_HOME/data/`, and no
per-DAG field relocates it. Logs follow the project; history does not. That is
also why a cross-repo run (§11) does not appear in each participating project's
history — a child run is stored nested under its parent's record, not as an
independent run of the child DAG.

> **For a child run, the logs do not follow the project either.** Measured: a
> step using `action: dag.run` leaves no log tree and no `metadata.jsonl` line
> in the project it ran in; both land in the parent's. `log_dir` is resolved by
> the process that enqueues, and for a child that process is the parent's — the
> same rule that stops any HTTP surface from writing per-project logs (A3, E2,
> `STAGE_2_LOG.md` S12). The sentence above therefore reads "everything a run
> produces stays with the checkout that produced it", where *produced it* means
> the checkout that owns the workflow, not the checkout the work happened in.

**`hist_retention_days` in `base.yaml` prunes both halves — the machine-side
history *and* the per-project log tree under `log_dir`.** The log half needs no
separate owner. **`metadata.jsonl` survives every retention setting**, because
nothing in Dagu writes or owns it: it is appended by `base.yaml`'s
`handler_on.exit`, which is a workflow handler rather than part of the run
store. That is the intended asymmetry — the logs age out, the record of what ran
does not — and it holds by construction rather than by configuration, so do not
look for a knob.

The trap is scope: **retention is per DAG and runs when that DAG runs.** A
project whose workflows stop running keeps its `.runs/` forever. That is a
`doctor` check (§10), not a setting.

> **A missing `working_dir` is not an error. Dagu creates the directory and
> reports success.** `dagu validate` exits 0 on such a DAG. So a workflow
> projected from a registry entry whose repository has been deleted keeps
> passing — vacuously, in a freshly created empty directory, at the path where
> the repository used to be. Nothing except §10's stale-entry check will ever
> notice.

**Two locations, one rule each.** The registry is machine-side because it is
machine-wide. Run output is repo-side because you read it from inside the repo
you were working in, and because it belongs to a **working tree, not a
project** — one project can be checked out twice, and each checkout runs and
fails on its own.

`.devman/workflows/` is tracked; `.devman/.runs/` is not. The devenv module adds
the ignore rule at registration, because an un-ignored `.runs/` turns the first
failed run into a dirty tree. **In this repository it did worse than that: two
Dagu run logs were committed** before anyone noticed, which is the strongest
argument available that the rule cannot be left to a hand-maintained file.

> **The rule goes in `.git/info/exclude`, not in `.gitignore`.** Locate it with
> `git rev-parse --git-path info/exclude` rather than by literal path, because
> in a linked `git worktree` the repo's `.git` is a file and the literal path
> does not exist.

Three reasons, in order. `.gitignore` may be a **read-only symlink into the Nix
store**, in which case the append fails with a permission error on every shell
entry, forever, and never becomes idempotent. `.gitignore` is **tracked**, so
writing the rule dirties the very tree the rule exists to keep clean. And devenv
writes to `.gitignore` too, from `devenv init`, appending its own block.

Two consequences to accept. A repository with no `.git` gets no rule, which is
correct — there is nothing to ignore. And git treats `info/` as a *common* path,
so a linked worktree shares its main repository's exclude file: "per checkout"
is really **per clone**. The rule is `.devman/.runs/`, which is right in every
worktree of the same repository, so sharing it is harmless. A fresh clone gets
the rule when it registers, which is what §9.3 buys.

`workflows/` is an input to the projection, never a second source Dagu reads.

Dagu reads exactly one DAG directory — there is no list form — so the projection
reaches per-project files by subdirectory or by symlink, and §5.2's two
`dag_discovery` knobs are what make either visible. A directory symlink is not
followed at all, at any setting; only file symlinks are.

> **A DAG is keyed by its file's base name, not by its path under the DAG
> directory. That is why `dags/` exists.** Pointing `dags_dir` at
> `projects/` directly looks right and fails: two projects both taking `base`
> both project a `check.yaml`, Dagu reports `duplicate DAG name "check"`, and
> **both disappear** from `dagu ls`, from the web UI and from the scheduler
> while staying runnable by path. That is §5.2's silent-absence hazard arriving
> by a third route, and it fires the moment a second repository adopts the
> plane.
>
> `dagu enqueue` compounds it. It resolves a name as a path under the DAG
> directory, so a nested DAG is enqueued as `<project>/workflows/<file>` while
> `dagu ls` prints `<file>`: one DAG with two names, and §8's trigger has to
> know which is which.
>
> **A DAG name is machine-global, so the projection gives it a machine-global
> key** — `<project>.<workflow>`, in one flat directory, which `ls`, the
> scheduler and `enqueue` all agree on. Each entry is a file symlink to
> `projects/<project>/workflows/<workflow>.yaml`, which **since stage 6 is a
> generated file** rather than a symlink to the group file: four lines of header
> naming this project's `working_dir`, `log_dir` and directory variable, then the
> source body unchanged. Dagu follows the link to it. The per-project projection
> is still what §7.3 resolves and what `doctor` unprojects when it prunes a stale
> entry (§10).
>
> **CORRECTION, S-12 — the key was not injective, and the separator is now a
> dot.** `<project>-<workflow>` renders one name for two pairs whenever one
> project name is a prefix of another: `devman-b` + `check` and `devman` +
> `b-check` collide. The second projection takes the first's link with `ln -sfn`
> and Dagu runs **one** file under a name two projects believe is theirs —
> measured in `STAGE_5_LOG.md` S6, where a run executed another project's
> workflow, in this project's directory, and reported success. That is §12 rule
> 4's failure exactly, and the plane had a check for it (§10's projection check)
> rather than a key that could not produce it.
>
> The key is now `<project>.<workflow>`, and **a workflow name may not hold a
> dot** — that refusal is what makes the last dot always the separator, so the
> pair reads back with no registry lookup. A project name may hold as many dots
> as it likes; `loci.nvim` is registered on this machine and keeps its spelling.
>
> The separator is measured, not chosen. Dagu 2.15.0 allows alphanumerics,
> dashes, dots and underscores in a DAG name and refuses everything else
> (`STAGE_7_LOG.md`, S-11), and of those `-` and `_` are both already in use
> inside project names on this machine while `.` is not used in any workflow
> name. `dagu ls`, `dagu enqueue` and `dagu status` all resolve the dotted name
> (S-12).
>
> **One thing does not follow the key.** Dagu rewrites `.` as `_` for the log
> directory, so `<project>.<workflow>` writes into
> `.devman/.runs/logs/<project>_<workflow>/`. Three distinct DAG names can share
> one such directory — but never two of one project, because the workflow half
> holds no dot, and `log_dir` is per project (§7.2). The codec's safety on the
> log side therefore rests on that, and `tests/conformance/` measures it.
>
> **Two consequences, and both are paid deliberately.** `devman show` prints the
> *source* — the group file or the repository's own override — because that is
> the file a person copies, and because a saved copy of the projection would
> carry one machine's absolute paths. And a repository's own
> `.devman/workflows/x.yaml` is no longer read live by Dagu: editing it needs one
> shell entry to re-project. What it buys is §8's third arrow — a schedule in the
> workflow's own file, fired by Dagu's own scheduler, with no unit to maintain
> anywhere (`STAGE_6_LOG.md`, S2 and S3).
>
> **That key is machine-global and it is not injective.** `<project>` and
> `<workflow>` are both free text with a hyphen allowed in each, so two
> different pairs can render one name — `devman-b` + `check` and `devman` +
> `b-check`. The projection is `ln -sfn`, so the second one written takes the
> link, and every trigger for that name then runs **one** file: measured, the
> run succeeded, worked in the directory of the project that asked, wrote its
> logs there, and `devman show` printed the file that did not run
> (`STAGE_5_LOG.md`, S6). **`doctor` checks it, and `devman run` refuses it**,
> by comparing the link's target against the project's own file. The plane
> cannot choose which project owns a name — identity is the repository's own
> statement (§9.1) — so both surfaces report and a person renames.

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
(§5.2) and has no manual path; the rest is what `doctor` reports. There is still
no `unregister`, and none is needed: the way out is deleting the repository, and
`doctor` reconciles the derived state afterwards.

> **The `devman` command name is already taken.** `devman 0.2.0` is installed on
> the development machine and ships its own `doctor`, `init`, `up`, `down`,
> `switch`, `bootstrap` and `index` (§3.3). Shipping both puts two different
> `devman doctor` commands on one `PATH`, and which one answers depends on
> profile order. Stage 1 either replaces 0.2.0 in the profile or takes a
> different name; it does not ship alongside it.

**`doctor` reads far more than it computes.** Dagu already diagnoses the failure
§15.3 accepts as the price of one shared instance:

| Symptom | Where it comes from |
|---|---|
| a wedged queue, and *why* | `GET /queues/{name}/items` — every waiting item carries a reason and a message |
| what holds the slot, and since when | the same call's `running[]` |
| a run whose process is gone | `dagu ps`, the `FRESH` column — but not for the first 90 seconds |
| whether the plane is up at all | `GET /health` |

Six things it must compute itself, because nothing in Dagu reports them:

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
5. **A stale registry entry**, and `doctor` may **prune** it rather than only
   report it. Any entry whose `path` is not a directory is stale. This is not
   §15.1's forbidden scan: it reads devman's own state and is O(registered
   projects), one `stat` each. **Pruning is safe because the registry is derived
   (§9.3)** — an entry pruned wrongly, because a disk was unmounted, restores
   itself the next time that repo's shell is entered (§5.2). `doctor` must also
   unproject the pruned project's workflows, because a projection outliving its
   repository still passes every other check above.
6. **A `.runs/` that has stopped ageing out.** Retention is per DAG and runs when
   that DAG runs (§9.2), so a project whose workflows no longer run keeps its run
   output forever.

Five of those six are file checks over the projection rather than queries against
a running service. `doctor` should therefore still work with the daemon down, and
say plainly which checks it could not run.

**Check 5 is the only thing that ever notices a deleted repository.** Nothing
else does: registration only ever sees the repo that is entering, and a deleted
repo never enters a shell again; Dagu creates the missing `working_dir` and
reports success (§9.2); `dagu validate` exits 0. A stale entry is a workflow
that keeps passing in an empty directory, and it is invisible everywhere else.

**`doctor` is also where the developer learns anything at all**, because §5.2
establishes that registration cannot report on the path that writes. A quiet
shell entry is the design, not a symptom.

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
> hold that name itself. It names its own directory **`DEVMAN_SELF_DIR`** — the
> name is fixed, not free, because `base.yaml`'s exit handler falls back to it
> (§7.1). A parent directs a child with `with.params`.

Such a workflow also states its own `working_dir` and `log_dir`, because the
inherited ones name `DEVMAN_PROJECT_DIR`. It cannot delegate that to a default:
**Dagu does not support shell-style defaults.** `working_dir:
${DEVMAN_PROJECT_DIR:-$DEVMAN_SELF_DIR}` is kept literal and resolved as a
*relative path* — the same documentation gap that swallows `$(…)` and backticks
(`STAGE_2_LOG.md`, S12). Only the handler gets a fallback, and only because a
handler's `run:` is a shell script.

**A child's work lands in the child's project; a child's run output does not.**
A step using `action: dag.run` runs in the directory `with.params` gives it, and
leaves nothing behind there — no log tree and no `metadata.jsonl` line. Both go
to the parent's project, because `log_dir` is resolved by the process that
enqueues and for a child that process is the parent's (A3, E2). §9.2 predicted
this for run *history* and it is equally true of logs. One cross-repo run
produces one set of output, in the repository that owns the workflow, which is
defensible — but somebody debugging a failed stack validation will look in the
wrong repository first unless this is said out loud.

A parent exports its parameters into each child's environment, and that
environment outranks the child's own `params:`, its `env:` block, and even an
explicit `with.params` override — whenever the names collide. Once the names
differ, `with.params` works exactly as documented, and a parent can deliberately
point a child at a different project, which synchronized releases and coordinated
migrations will want.

The collision is worth stating plainly because of how it fails: the child runs,
succeeds, and does the work in the wrong directory. Nothing reports it.

> **`doctor` checks it mechanically (§10): a workflow containing
> `action: dag.run` must not define `DEVMAN_PROJECT_DIR` *for itself* — not in
> top-level `params:`, not in `env:`, not in `working_dir`, not in `log_dir`.
> Inside a step's `with.params` the name is correct, because that is how a
> parent directs a child.**

**Holding the name and passing it are opposite acts, and the check has to tell
them apart.** A parent that holds it drags every child into its own directory,
silently. A parent that passes it in `with.params` directs one child
deliberately, which is what synchronized releases and coordinated migrations
need. An earlier draft of this line forbade mentioning the name at all — A4's
rule, which A6 superseded — and that version reports the only correct cross-repo
workflow in this repository as broken (`STAGE_2_LOG.md`, S8).

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
named per DAG, the first of §7.1's four global names has nothing to bind to.

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

**0.16s is not reproducible as an absolute number, and that is the machine's
doing rather than devman's.** The same bare devenv repository measures 0.164s on
a quiet machine and 0.231s under ordinary desktop load. Criterion 7 is therefore
stated as a *delta* against the same repo with `devman.enable = false`, because
the absolute figure is dominated by devenv and by whatever else is running, and
neither is the plane's to defend.

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

> **Settled, and it passed.** Both modules evaluate, each under its own nixpkgs,
> and the module needs no pin of its own — so the plane ships **one** flake and
> §3.1's anti-drift argument stays a property. `nix/dagu.nix` resolves under both
> trees to a byte-identical binary, at the cost of two store paths.
>
> One thing the spike found that the claim did not anticipate: when the two
> trees disagree on something shared, an **absent** attribute fails evaluation
> loudly, while a merely **different** one is silent. That is what §3.1's two
> rules now guard.

### 12.4 Whole-file shadowing is coarse enough to live with

> Repos override whole workflow files rarely enough that the copied duplication
> does not accumulate.

§7.3 refuses field merging, so changing one step of `check` means copying
`check.yaml` into the repo, where it stops tracking upstream (§15.7).

Measured at stage 2 across five real repos: **one override in eighteen
workflows**, keeping 7 of its 9 executable lines, and the change was a deletion
of a step that did not apply rather than an edit (`STAGE_2_LOG.md`, S14).

> **Closed by decision (2026-08-22).** Whole-file shadowing stays. **A repository
> that must change a default writes a whole workflow file of its own**, and that
> is the whole of the answer. Neither remedy this section reserved will be
> applied: not smaller group files split for the purpose, and not a merge
> algorithm — §7.3 refused the second already, and the one real override was a
> deletion, which merge semantics express badly. The cost is paid once, by the
> repository, in its own tree; every alternative moves complexity into the plane
> (`STAGE_3_LOG.md`, S14).

§15.6 is unaffected: an overriding file stops tracking its group, and `devman
doctor` reports how far each has diverged. That stays visible without anybody
running a study.

---

## 13. Rollout

### Stage 1 — the flake foundation

**Spikes §12.1 and §12.3 are both settled and both passed**, so stage 1 no
longer waits on them. Then:

```
nixosModules.default    one Dagu service, config, state paths, ports as options
modules/devenv.nix      selection and identity — the file name is required (§3.2)
workflows/base          check, validate, full-test
workflows/python        one ecosystem group, to prove shadowing
registration            enterShell, hash-guarded, fork-free (§5.2)
```

**Four cleanups that are stage-1 work, not housekeeping**, because each one
breaks something if it is left:

1. **Delete `src/devman/` (§3.3)**, and **remove `devman-0.2.0` from the
   profile**. The binary outlives the source, owns the `devman` command, and its
   `init --force` deletes a `.devman/` it does not recognise (§15.2).
2. **Remove `processes.dagu` from this repository's `devenv.nix`** (§4). It holds
   the ports the plane's own service needs, and criterion 16 says devman adopts
   itself.
3. **Excise the committed run logs** under `.devman/.runs/` from this
   repository, and let registration add the exclude rule (§9.2).
4. **Set `users.users.<name>.linger = true`** for the user that owns the plane
   (§4), or neither the service nor its activation restart works on a machine
   nobody has logged into.

Adopt in exactly one repo — this one.

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
one watchexec user service, reading the registry (§8)
VCS hooks
retention policy — hist_retention_days in base.yaml (§9.2)
devman run / show / doctor (§10)
```

### Stage 4 — higher-level automation

Only once every layer below is stable.

```
review workflows   release   maintenance   benchmark campaigns
agent workflows    policy gating
```

### Stage 7 — the standard set

Nine workflows in four groups become five in three. The ladder is two rungs. The
universal contract is `base:check` and `base:test`. `devman doctor` moves out of
`maintain` and into one plane report. The plane goes from 6 registered
repositories to 58, in four waves.

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
| 7 | devenv stays on the fast path | the module adds **≤ 10 ms** to a warm `devenv shell -- true`, as a **paired** difference against the same repo with `devman.enable = false` |
| 8 | Registration is automatic and idempotent | enter a shell twice; the registry is written once |
| 9 | Registration covers only opted-in repos | a repo without `devman.enable` never appears in the registry |
| 10 | No workflow contains an absolute path | grep the registry and `workflows/`; zero hits |
| 11 | Identity survives a move or a rename | move and rename the directory, re-enter its shell — same project, same run history |
| 12 | Queues bind the enqueue path | two workflows naming the `exclusive` queue serialize **when enqueued** — `dagu start` and Dagu's own scheduler both bypass queues entirely, so the measurement must use `dagu enqueue`, which is the path §8's first two arrows take |
| 13 | The watchers do not chase each other | a file-writing workflow plus a watcher on those files: one save, exactly one run **that does work**, and the sequence stops within one further run, which skips. A workflow that does not write its watched files produces exactly one run. Then edit again immediately — it must run again |
| 14 | The task graph exists once | no default workflow re-states a dependency devenv already declares |
| 15 | A rebuild is inconvenient, not catastrophic | delete Dagu state, re-enter every registered shell, every workflow runs again |
| 16 | devman adopts itself | this repo registers as a project, and its cross-repo workflows run from `.devman/workflows/` (§11) |
| 17 | There is one way in | no manual register path exists; every devenv entry path registers, and deleting the registry then entering every shell restores it exactly |

**Criterion 4 is the one that keeps §7 honest.** If a repo cannot rename or
replace a default without something in devman objecting, the plane has grown an
opinion it should not have. Criterion 16 keeps §9.3 honest.

**Criterion 7 is a delta, and criterion 8 is what makes it affordable.** The
absolute wall-clock figure moves with machine load by more than the plane costs,
so measuring it absolutely measures the machine. Two notes for whoever runs it:
interleave the two variants one entry at a time rather than running each to
completion, because ordinary load drift is larger than the effect and a
sequential run has reported the enabled repo as the faster one. And remember
`enterShell` fires twice per entry (§5.2), so the per-firing budget is half of
whatever the criterion says.

**Criterion 13 counts runs that do work, and that wording is a correction rather
than a softening.** It was written before E1 measured *where* Dagu skips: §8.1
proposed skipping before anything is enqueued, and Dagu skips after, so a
loop-breaking hash produces one run that formats and one run that finds nothing
to do. Counting every run, the failure this criterion exists to catch is
**unbounded** — run, write, run, write, forever — and what a correct plane
produces is **bounded and self-stopping**. Measured at stage 3, in both shapes,
with the control (`STAGE_3_LOG.md`, S6). The last clause is not decoration: a
suppression window passes "one save, one run" and fails "edit again
immediately", which is the whole reason §8 requires a content hash.

**Criterion 12 is narrower than it read, and the narrowing is measured.** It
said "queues are real" without saying which path they bind. **Queues bind the
enqueue path.** `devman run`, a VCS hook and the watcher all reach Dagu through
`dagu enqueue`, and a queue's `max_concurrency` holds exactly: 58 enqueued runs
on `light` never exceeded 4 concurrent and drained in 311 s (stage 7, S-1). **A
run started by Dagu's own scheduler does not pass through the queue** — 58 DAGs
sharing one `schedule:` all ran at once with queue depth 0, and on the installed
plane two DAGs on `exclusive` with a limit of 1 both started in the same second.
So a `schedule:` is throttled by nothing, and the rule follows: **what the plane
schedules must be cheap by construction** (`PROPOSAL.md` §12, rule 8). This
distinction has existed since stage 6 put schedules in workflow files; stage 7 is
where it was measured.

**Criterion 14 holds by construction since stage 7.** A default workflow runs
exactly one `devenv tasks run`, so it declares no order and cannot re-state one.
Before that it held only because almost no repository declared a task
dependency — and `pyjutsu` already declared one, so the criterion was one
ordinary `devenv.nix` edit away from being false.

**Criterion 17 is the load-bearing one.** It is what lets the registry be
derived, lets §9.3 promise reconstruction, and lets §5.2 have no manual register
command. Every ordinary entry path was enumerated and tested against it.

---

## 15. Sharp edges

**15.1 Registration cannot happen at evaluation time.** Nix eval is pure, so
§5.2 puts it in `enterShell` behind a hash guard. A repo is invisible until you
enter its shell once. Do not solve this by scanning.

**15.2 `.devman/` belongs to the repository. The plane reserves two names in
it and ignores everything else.**

> **devman reserves `.devman/workflows/` and `.devman/.runs/`. Every other entry
> under `.devman/` is the repository's, and the plane never reads, writes or
> inspects it.**

`.devman/` is open for whatever else a repository or an add-on keeps there — a
vendored store, agent reference material, a future tool nobody has written yet.
Adopting the plane costs a repository two reserved names, not a directory.

**This reverses an earlier rule, by decision at stage 7.** Registration used to
carry a whitelist: any top-level entry under `.devman/` other than `workflows/`
and `.runs/` made it refuse and report. A survey of 77 checkouts had found four
shapes — a `devman 0.2.0` workspace (`devman.toml`, `interaction.md`, `nvim/`),
agent reference material (`context/`), a vendored store (`store/`), and the
plane's own — and the whitelist existed so the plane never silently adopted one
of the others.

**It was removed because it contradicted §7.4.** The plane's claim is that it
names the smallest vocabulary it has to and leaves everything else to the
repository. A directory the repository already owned is the wrong place to make
an exception, and "refuse to register until you move your files" is an opinion
about a repository's layout — the exact kind §7.1 says the plane does not hold.
`fsdantic`, which carries `.devman/store/vendor/agentfs`, is the worked example:
it now adopts the plane and keeps its store, and the two do not interact.

**Nothing replaces it, deliberately.** A `doctor` check listing unrecognised
entries would be the same opinion in a softer voice, and §15.7 says `doctor`
does not guess.

**What the reversal gives up, stated.** A repository holding a `devman 0.2.0`
workspace now registers silently, and the two tools share a directory without
either knowing. The older tool is the destructive one: its `init` refuses a
non-empty `.devman/`, and `--force` calls `shutil.rmtree`, which would delete
the tracked `workflows/` this charter calls canonical. **§3.3's removal of that
binary is what makes this safe**, and it is no longer merely a tidiness task —
it is the mitigation. Nothing in the plane can defend against a tool that
deletes the directory out from under it.

**15.3 One instance per machine is a shared availability failure.** A wedged
queue blocks every repo, not one. §9.3 bounds the damage — state is
reconstructable, so recovery is a restart — but availability is genuinely
shared. Accepted, with one requirement: **`devman doctor` must diagnose a wedged
plane**, or a shared failure becomes an unexplained one.

**15.4 Queue names are the one-way door, and a typo is invisible.** Adding a
queue name is cheap; renaming one is a migration across every workflow that names
it. Worse, Dagu accepts a queue name that does not exist **silently** — no error,
no warning, nothing in the logs. A misspelled queue is not a migration problem,
it is an unobservable one, which is why §10 makes `doctor` check every resolved
`queue:` against the machine's list, and why §7.2 has the machine set a default
queue in `base.yaml`.

> **This section said the undeclared name runs "with no concurrency limit at
> all", and against the pinned Dagu 2.15.0 that is wrong in the direction that
> matters.** Measured (`STAGE_7_LOG.md`, S-9): the name becomes a real queue at
> concurrency **1**, shared by every DAG that names it. Two different DAGs both
> naming `typoqueue` serialised against each other; a DAG naming no queue at all
> got a queue named after itself, also at 1. So a typo **throttles** — a
> misspelt `light` runs one at a time instead of four, and drags unrelated
> workflows into the same serial lane.
>
> **Every conclusion above survives, and one gets a second reason.** The failure
> is still silent, `doctor` must still check every name, and §7.2's default
> queue is still required — because a per-DAG queue bounds a DAG against itself
> and the machine against nothing. §5.2's missed-restart note already recorded
> this number by another route: a scheduler that has not re-read `config.yaml`
> logs "`max-concurrency=1` for a queue configured with 4". The two entries
> agree; only this sentence did not.

**15.5 devenv and NixOS do want different nixpkgs, and it is survivable.**
§12.3 measured it: `devenv.lock` carries both trees as separate nodes, neither
constrains the other, and the single-version guarantee stays a property. What
keeps it that way is §3.1's two rules, and the sharp edge is the second one —
when the two trees disagree on something shared, an **absent** attribute fails
evaluation loudly while a merely **different** one is silent. Sharing anything
but text, or anything but `nix/dagu.nix`, spends that silence.

**15.6 An overriding file stops tracking its group.** A repo that shadows
`check.yaml` keeps that version forever, and §7.3 offers no partial override.
`doctor` counts shadowed files and reports how far each has diverged from the
group version.

**15.7 Nothing checks that a default still fits.** Since the plane holds no
opinion about what a workflow costs, a `check` that grows to four minutes is
invisible to devman. That is the deliberate trade: no policing, and no false
alarms from a heuristic that cannot know your machine. Notice it yourself.

---

## 16. Settled questions

**All five are closed.** Every recorded lean survived measurement; what changed
is that each now has a reason rather than a preference.

- **Registry root — free.** Nothing claims `~/.local/share/devman/`; the
  directory does not exist and `XDG_DATA_HOME` is unset. **The `devman`
  *command* is a different matter** — see §3.3 and §10.
- **Ecosystem groups ship in this flake.** Not merely simpler: a second flake
  would be a second devenv input in every repo that takes a group, and an input
  costs about 20 ms on every shell entry, forever (§3.2). A groups flake would
  also need its own `devenv.nix` shim purely to be importable (§3.2), and a
  second lock file and rev to keep aligned — the drift §3.1 exists to prevent.
  Groups are text, and §3.1's second rule says text costs nothing to share.
  Revisit only when a third party wants to publish one.
- **The machine module does not manage a Dagu it did not install.** It cannot:
  the conflict is a port collision, and it is loud (§4).
- **There are no ecosystem groups.** A language differs in what a task *is*, and
  `devenv.nix` already holds that. A language group's whole content, once a
  workflow is one step calling one task, is a namespace prefix — which §7.3
  cannot promote and no second repository can want. The `python` group was
  deleted at stage 7 for this reason, and `rust`, `node` and `lua` were never
  created: each would serve one repository (`pyjutsu`,
  `paloma-story-generation`, `loci.nvim`). The surviving groups are named for
  what taking them costs — a task name, or a write to your own files — and the
  highest-coverage marker is still `devenv.nix` at 58 of 68, which is why `base`
  carries the leverage.
- **Retention — settled, and the earlier caveat was wrong.**
  `hist_retention_days: 7` in `base.yaml` prunes **both** Dagu's machine-side
  history and the per-project log tree under `log_dir`. The log half needs no
  separate owner. `metadata.jsonl` survives every setting because nothing in
  Dagu owns it (§9.2). The one trap is scope, not policy: retention is per DAG
  and runs when that DAG runs, so a project whose workflows stop running keeps
  its `.runs/` forever — a `doctor` check (§10), not a setting.

**Nothing is open.** §12.4 — whether whole-file shadowing is coarse enough to
live with — was measured at stage 2 (one override in eighteen workflows) and
closed by decision at stage 3: it stays as §7.3 defines it, and a repository that
must change a default writes its own workflow file.

---
