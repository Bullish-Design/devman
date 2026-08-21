# devman — Concept (the automation plane)

> **STATUS: PROPOSED (2026-08-21).**
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

### 2.1 Is

Three things, and the list is closed:

1. **A shared Nix flake** exposing a machine interface and a repo interface from
   one version (§3).
2. **A project registry** of repositories that opted into automation, keyed by
   identity, resolving to paths (§5).
3. **A contract** — a declaration schema, five resource classes, and two
   execution kinds. Nothing about what a repository's work should be (§7).

Item 3 is deliberately thin. The plane needs a name it can resolve, a class it
can queue, and a kind it can isolate. Anything more is an opinion about your
repositories, and devman does not have those.

Default workflows are **not** on this list. They are content, so they ship as
the base pack and resolve through the same layers as everything else (§7.4).

### 2.2 Is not

| Not | Owner |
|---|---|
| an index of every repo on disk | **fleetman** — §5.1 |
| a workbench | shellij |
| an environment | devenv |
| a source-control tool | jj |
| a scaffolder | copyroom |
| a task runner | devenv. devman never re-implements `lint` |

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
├── modules/default.nix        # repo interface — the contract
├── packs/                     # content, not contract (§7.4)
│   ├── base/                  # default workflows
│   ├── python/ nix/ rust/     # ecosystem packs
│   └── assets/                # asset packs (§8)
├── dags/                      # machine-level and cross-repo DAGs (§13)
├── lib/                       # metadata schema, helpers
└── src/devman/                # the CLI, deferred to stage 3 (§12)
```

| Output | Consumer |
|---|---|
| `nixosModules.default` | the machine's NixOS configuration |
| `modules/` *(a path — §3.2)* | every repo's `devenv.yaml` |
| `homeManagerModules.default` | keeps the CLI on `PATH` |
| `packages.default` | the `devman` CLI |
| `checks` | integration tests for the plane |

One flake version defines both interfaces. That is the point: it removes drift
between Dagu config, workflow naming, registry layout, resource classes, and
repo integration. Those five must agree, and nothing else makes them.

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

`src/devman/` is a tmuxp workspace orchestrator: scan roots, cache an index,
launch sessions. None of it is load-bearing here.

The registry looks close and is not. That code **scans**; the plane **receives
registrations** (§5.1). The population rule inverts, so the code answers the
wrong question. This is a rewrite that keeps the repo name.

---

## 4. Machine responsibility

```nix
# pinned with git+ — a github: input hits the API rate limit on every eval
inputs.devman.url = "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>";

imports = [ inputs.devman.nixosModules.default ];
```

One Dagu instance per machine or user.

| Owns | Never knows |
|---|---|
| Dagu installation, service, config | which project uses pytest |
| workflow discovery, registry paths | which repo has a benchmark |
| queues, concurrency, resource mapping | any project's task graph |
| state paths, log retention | any project's dependency order |
| secret and environment injection | |

The split is load-bearing. The machine knows *how much* may run at once, never
*what* runs. A machine module that learns one project fact has started back
toward a central config every repo edits — the failure the plane prevents.

---

## 5. Repo responsibility

```nix
devman = {
  enable = true;
  project = "pyjutsu";          # identity, never a path (§11.1)
  packs = [ "python" ];

  workflows = {
    check.enable = true;
    validate.enable = true;
    full-test.enable = true;
  };

  resources.benchmark = "gpu";
};

tasks."lint".exec      = "ruff check .";
tasks."typecheck".exec = "basedpyright";
tasks."test".exec      = "pytest";
```

The repo declares intent and owns its primitives. The module composes them. A
repo never writes Dagu YAML to enable a default workflow.

### 5.1 Registration, not discovery

| | Mechanism | Population | Payload |
|---|---|---|---|
| **fleetman** | scan configured roots | every repo found | "this repo exists, here" |
| **devman** | the repo declares itself | only `devman.enable = true` | workflows, classes, metadata |

The registry exists so Dagu never needs to understand the developer's directory
layout. A scan is exactly that understanding, so merging the two would defeat
the design.

They cannot conflict, because **neither is canonical.** The repository is. Both
are derived views, reconstructible by re-reading the repos. If an integration
earns its place, it is one reading the other — never a shared store.

### 5.2 Registration runs at shell entry

Nix evaluation cannot write to `~/.local/share/`, so registration is a side
effect and needs an explicit home.

> **Registration runs in `enterShell`, guarded by a content hash.** The module
> renders the registry entry, compares its hash against disk, and writes only on
> a difference.

The common case costs nothing. The cost is that a repo is registered only after
you enter its shell once; `devman register <path>` covers the rest.

---

## 6. Dagu orchestrates, devenv executes

Violating this boundary is the main way the design decays.

**devenv owns implementation.** The repo names its own tasks — task names are
pack-local convention, never reserved (§7.1):

```
python:  lint  typecheck  test  integration-test
nix:     flake-check  build
rust:    clippy  cargo-check  test
```

One logical task has one implementation, and everything calls it:

```
prefer:  devenv tasks run test

avoid:   Dagu:  pytest
         CI:    uv run pytest
         hook:  devenv shell -- pytest
```

Three call paths mean three things that drift. Spike A makes the single path
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

### 7.1 What is global, and why

| Global | Because |
|---|---|
| resource class names (§7.3) | the machine maps them to queues; a class it does not know has no queue |
| execution kinds — `workspace`, `snapshot` | snapshot isolation is machinery the plane provides (§9), not a label |
| the declaration schema (§7.2) | registration validates against it |

| Not global | |
|---|---|
| task names | the repo's business, entirely |
| workflow names | a convention the base pack follows; nothing enforces it |
| what any workflow does, or how long it takes | the repo's business, entirely |

**Task names cannot be reserved**, because ecosystems decompose differently.
`nix flake check` is not a lint, and Nix has no `typecheck` distinct from
`build`. Forcing every ecosystem into a Python-shaped split produces empty tasks
or lies. They need to be stable only *within* a pack, because only the pack
composes them.

**Workflow names are not reserved either.** The base pack ships `check`,
`validate`, and `full-test` because most repos want a fast one, a gate, and an
exhaustive one — so `devman run check` usually resolves. A repo that wants
`smoke` and `ci` instead gets them. The plane does not police what a name means,
because a rule it cannot check is a rule it should not have.

### 7.2 Declaring a workflow

Four fields. Everything else is the repo's.

```nix
devman.workflows.validate = {
  tasks    = [ "lint" "typecheck" "test" ];   # devenv task names, yours
  kind     = "workspace";                     # workspace | snapshot
  resource = "normal";                        # a class from §7.3
  enable   = true;
};
```

Ecosystem packs fill the same shape:

```
python pack:  check → lint + typecheck        validate → + test
nix pack:     check → statix + deadnix        validate → nix flake check
rust pack:    check → clippy + cargo check    validate → + cargo test
```

`kind` and `resource` are declared, never derived from a name. A repo whose
`check` is genuinely expensive marks it `heavy` and nothing objects.

### 7.3 Resource classes

The repo declares intent. The machine prices it.

| Class | For |
|---|---|
| `light` | lint, formatting, static analysis |
| `normal` | unit tests, ordinary builds |
| `heavy` | integration suites, large compiles, CPU-heavy benchmarks |
| `gpu` | inference, model evaluation, GPU benchmarks |
| `exclusive` | hardware access, destructive database tests, anything that must run alone |

The NixOS module maps classes onto queues and concurrency limits. A project
never learns the machine's core count.

### 7.4 Four layers, one mechanism

```
base pack  →  ecosystem pack  →  devenv.nix declaration  →  .devman/workflows/*.yaml
```

Later wins. A pack is a shared default so five Python repos do not each write
the same six lines. Skip it and declare the composition inline for the same
result.

### 7.5 What a repo controls

Everything except the three global items in §7.1.

```nix
devman.workflows = {
  check.tasks    = [ "lint" "typecheck" ];      # inherited name, own content
  validate.tasks = [ "lint" "typecheck" "test" ];

  full-test = {
    tasks    = [ "test" "integration-test" ];
    kind     = "snapshot";
    resource = "heavy";
  };

  benchmark-campaign = {                         # a name of your own
    tasks    = [ "benchmark" ];
    kind     = "snapshot";
    resource = "gpu";
  };

  provision.enable = false;                      # drop one you do not want
};
```

Rename, redefine, drop, or invent. The plane resolves a name to a workflow and
runs it at the declared class. It has no opinion about what the work is.

### 7.6 Raw Dagu YAML

A Nix task list cannot express everything Dagu can: parallel branches with a
join, preconditions, retries on a flaky step, matrix fan-out. Without an escape
hatch the module grows an option per Dagu feature and re-implements Dagu's
schema in Nix, badly.

So `.devman/workflows/*.yaml` is the last layer.

> **The directory is an input to the registry projection, not a second source
> Dagu reads.** Registration validates the file, resolves identity, and projects
> it — the same path a generated workflow takes, minus the Nix composition.

Dagu still reads one place, and hand-written files still get identity
resolution, queue mapping, and the no-absolute-paths check.

**The one rule — declare `kind` and `resource`.** Registration refuses a file
without them, because those are the two things the plane acts on (§7.1):

```yaml
# .devman/workflows/validate.yaml
x-devman:
  kind: workspace
  resource: normal
steps:
  - name: lint
    run: devenv tasks run lint
```

Anything Dagu accepts below that block is yours.

**Eject, do not hand-write.**

```
devman show check --format yaml > .devman/workflows/check.yaml
```

Start from the real generated file and edit it. A raw-YAML directory is how
copied boilerplate creeps back, and ejecting keeps the hatch cheap without
making from-scratch YAML normal.

Honest cost: **every ejected file stops tracking pack improvements.** `doctor`
counts them.

---

## 8. Assets

Helper scripts, agent skills, prompts, and aliases are **payload a workflow
installs** — not a compiler, and not a product needing its own charter.

| Workflow | Does | Blocks? |
|---|---|---|
| `provision` | install this repo's declared assets into their consumer surfaces | no |
| `refresh` | re-install when the source pack or the declaration changed | no |

```nix
devman.assets = {
  packs = [ "devenv-literacy" "my-ai" ];
  local = ./.devman/assets;
};
```

Three consequences, all simplifications:

1. **One pack mechanism carries both kinds of content.** Since the workflow
   library is a pack (§7.4), workflow packs and asset packs are the same thing
   over the same four layers. There is no second distribution system.
2. **Packs resolve to a machine-wide cache**, never into the repo — the same
   rule as §11.3: generated state is machine-local and reconstructable.
3. **No reverse path is needed.** Assets are installed, not compiled. Correct
   the source and run `refresh`.

Asset **rendering** — templates, anchors, projections — is out of scope. If a
pack needs it, the pack owns it and the plane still only runs the workflow.

---

## 9. Workspace and snapshot

A first-class distinction, not an implementation detail.

| | Workspace | Snapshot |
|---|---|---|
| Runs against | the live working directory | an immutable jj revision |
| For | lint, format, quick tests | full tests, benchmarks, releases, scheduled runs |
| Trigger | file save, debounced | commit, schedule, explicit request |
| Sees your edits mid-run | yes, deliberately | never |

```
snapshot:  revision → temporary jj workspace → devenv → Dagu → artifacts + metadata
```

The reason is not purity. A 40-minute benchmark that observes an edit made at
minute 12 produces a number describing no revision — and the number does not
say so.

### 9.1 jj-aware execution

Design for it now, implement at stage 4. A durable run captures:

```
project   jj commit ID   workflow   parameters   resource class   environment identity   run ID
```

Designing it early costs a metadata field. Retrofitting it makes every
historical run unattributable.

**The open cost is devenv cold start in a fresh workspace.** Spike A measured
5.46s cold in a warm store. A fresh jj workspace per snapshot run may miss the
eval cache every time. §15.1 measures this before stage 4 commits.

---

## 10. Triggers

Dagu orchestrates. It does not detect.

```
filesystem change → watchexec → Dagu
commit / push     → hook      → Dagu
schedule          → Dagu's own timer
```

| Layer | Job |
|---|---|
| watchexec, hooks | detect that something happened |
| Dagu | decide and orchestrate what happens next |
| devenv | execute the repo's tasks |

### 10.1 Loop-breaking is plane infrastructure

Any workflow that writes files a watcher watches will chase itself. The plane
owns the fix once, so no repo implements it again:

> **A workflow that writes files records their content hashes to
> `~/.local/share/devman/runs/<project>/<run-id>/generation.json`. A triggered
> workflow skips any file whose hash matches.**

Stateless. No lock, no deadlock, no ordering assumption.

---

## 11. State

### 11.1 Identity

Never commit a developer's absolute path.

```
avoid:   working_dir: /home/andrew/Documents/Projects/Pyjutsu
prefer:  project: pyjutsu          → resolved by the registry
```

This is what makes moving a repo, a second machine, a temporary workspace, a jj
workspace, and a future remote worker all work without editing a workflow.

### 11.2 On disk

```
~/.local/share/devman/
├── projects/<project>/
│   ├── metadata.json          # identity, path, resource defaults
│   └── workflows/*.yaml       # the projection of the repo's declaration
└── runs/<project>/<run-id>/
    ├── logs/  artifacts/  reports/
    ├── generation.json
    └── metadata.json
```

```
.devman/
├── devman.toml        # tracked  — this repo's automation declaration
├── workflows/         # tracked  — raw Dagu YAML, the last layer (§7.6)
├── assets/            # tracked  — local asset payload (§8)
└── state/             # ignored  — local run state
```

`workflows/` is an input to the projection, never a second source Dagu reads.

### 11.3 Canonical and operational

| Canonical — losing it is real loss | Operational — reconstructable |
|---|---|
| git / jj history | Dagu run history and logs |
| the repo's `.devman/` declaration | queues |
| devenv definitions | the registry itself |
| this flake | temporary workspaces, ordinary artifacts |

**Rebuilding the Dagu service must be inconvenient, not catastrophic.** That is
a design constraint: anything that would make a rebuild catastrophic does not
belong in Dagu state.

### 11.4 Secrets

A workflow references a symbolic name and never carries a value.

```
GITHUB_TOKEN   HF_TOKEN   DATABASE_URL
```

Injection runs `secret manager → Dagu → devenv → task`. The repo declares a
dependency on a secret; it never holds one.

---

## 12. The CLI, deferred

```
devman list      devman register     devman unregister
devman run check devman show         devman status      devman doctor
```

**Do not build this at stage 1.** Prove the conventions by hand first. A CLI
written before the vocabulary settles freezes the wrong vocabulary and then
defends it.

The exception is `devman register`, needed at stage 2 for the case §5.2 cannot
cover.

---

## 13. Cross-repository workflows

One central instance is what makes these possible. They belong to no single
repository, so today they exist nowhere.

```
              Dagu
                │
   ┌────────────┼────────────┐
library A   library B   application
   └────────────┼────────────┘
                ▼
       integration workflow
```

Uses: validating dependent libraries together, synchronized releases, nightly
stack validation, cross-repo benchmarks, coordinated migrations.

These live in devman's `dags/` or a machine-level namespace — never in one
arbitrary participant.

---

## 14. What it refuses to do

| Refuses to | Because |
|---|---|
| Let the NixOS module learn a project fact | it becomes a central config every repo edits |
| Let a repo learn the machine's concurrency numbers | the repo declares intent; the machine prices it |
| Duplicate a task graph in Dagu and devenv | two graphs drift, and the drift is silent |
| Implement a task itself | devenv owns execution; a second implementation is a second answer |
| Scan the filesystem for projects | registration is the design (§5.1) |
| Reserve a task or workflow name | ecosystems and repos differ; a rule the plane cannot check is a rule it should not have (§7.1) |
| Hold an opinion about what a workflow costs or contains | that is the repository's business |
| Let raw YAML bypass registration | it would lose identity, queue mapping, and the path check (§7.6) |
| Let an agent block a build | a stochastic gate fails open — it costs autonomy and buys nothing |
| Write into a repo's tracked files without an explicit command | provisioning installs to build outputs and caches |
| Treat Dagu state as canonical | §11.3 |
| Ship a default that half the repos override | that is a shared file with a misleading name |
| Build the CLI before the conventions settle | it would freeze the wrong vocabulary |

---

## 15. Riskiest claims

### 15.1 devenv is affordable as the universal executor — spike, before stage 4

> Routing every task through `devenv tasks run` costs little enough that nobody
> reaches around it.

Spike A settled the workspace case: **0.16s warm**, 1.44s after a change.

**The unmeasured case is a cold devenv in a fresh jj workspace** (§9.1). At
5.46s a snapshot run is fine. At two minutes, snapshot workflows are
unaffordable and §9 needs a different mechanism — a reused workspace pool, or a
shared eval cache.

*Measure:* create a jj workspace at a revision, enter its devenv, time it. Cold
and warm, ten runs.
*Fails if:* over ~30s repeatedly. Stage 4 redesigns rather than ships.

### 15.2 One flake serves both interfaces cleanly — spike, at stage 1

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

### 15.3 The schema is expressive enough

> Four fields — `tasks`, `kind`, `resource`, `enable` — describe most workflows,
> and raw YAML covers the rest without becoming the normal path.

Measure at stage 2 across five real repos: **how many workflows ejected to raw
YAML (§7.6), and what did each need that the schema lacked?**

A high eject rate is the signal, and it points at the schema, not the repos. The
remedy is cheap — add a field. This risk is mild by construction, because §7.1
made the plane's vocabulary small enough to have little to be wrong about.

### 15.4 One instance per machine is a shared failure

A wedged queue blocks every repo, not one. §11.3 bounds the damage — state is
reconstructable, so recovery is a restart — but availability is genuinely
shared. Accepted, with one requirement: **`devman doctor` must diagnose a wedged
plane**, or the shared failure becomes an unexplained one.

---

## 16. Rollout

### Stage 1 — the flake foundation

Spike §15.2 first; it can change the shape. Then:

```
nixosModules.default    one Dagu service, config, state paths
modules/                the contract — schema, classes, kinds
packs/base              default workflows: check, validate, full-test
packs/python            one ecosystem pack, to prove the layer stack
registration            manual — devman register, or a hand-written entry
```

**Delete `src/devman/` (§3.3).** Adopt in exactly one repo — this one.

### Stage 2 — convention and registration

```
automatic registration (§5.2, enterShell + hash guard)
the metadata schema
resource classes → queues and concurrency
artifact and run-state layout (§11.2)
.devman/workflows/ + devman show --format yaml (§7.6)
```

Adopt across five repos and run §15.3's measurement: **how many workflows
ejected to raw YAML, and what did the schema lack?**

### Stage 3 — assets and reactivity

```
provision and refresh (§8)
watchexec triggers, VCS hooks
the generation token (§10.1)
retention policy
devman list / status / doctor
```

### Stage 4 — snapshot execution

Spike §15.1 gates this stage.

```
jj-aware isolated workspaces
commit-addressed runs
revision-aware artifacts
cross-repo workflows (§13)
```

### Stage 5 — higher-level automation

Only once every layer below is stable.

```
review workflows   release   maintenance   benchmark campaigns
agent workflows    policy gating
```

---

## 17. Success criteria

| # | Criterion | Measured by |
|---|---|---|
| 1 | One flake, two interfaces, one version | the machine and this repo import the same rev; `nix flake check` passes |
| 2 | A repo enables automation in under ten lines | `devman.enable` plus workflow toggles; no Dagu YAML written by the repo |
| 3 | A repo may skip packs entirely | declare its workflows inline; the result matches the pack's |
| 4 | **A repo may rename or replace every default** | drop `check`, define `smoke` and `ci`; both run, and nothing in devman objects |
| 5 | Ejecting round-trips | `devman show check --format yaml` saved to `.devman/workflows/` produces an identical projection |
| 6 | Raw YAML cannot bypass the plane | a file without `x-devman`, or with an absolute path, is refused at registration |
| 7 | devenv stays on the fast path | `devenv shell -- true` ≤ 0.25s warm — Spike A regression |
| 8 | Registration is automatic and idempotent | enter a shell twice; the registry is written once |
| 9 | Registration covers only opted-in repos | a repo without `devman.enable` never appears, even under a scanned root |
| 10 | No workflow contains an absolute path | grep the registry and `dags/`; zero hits |
| 11 | Identity survives a move | move a repo, re-enter its shell, run `check` — no workflow edited |
| 12 | Resource classes reach real queues | mark a task `exclusive`; two concurrent runs serialize |
| 13 | The watchers do not chase each other | a file-writing workflow plus a watcher on those files, one save, exactly one run |
| 14 | The task graph exists once | no default workflow re-states a dependency devenv already declares |
| 15 | Snapshot runs ignore live edits | edit a file mid-run; the result matches the revision |
| 16 | A rebuild is inconvenient, not catastrophic | delete Dagu state, re-enter every registered shell, every workflow runs again |
| 17 | devman adopts itself | this repo carries `.devman/`, `devman doctor` exits 0 |
| 18 | Assets install without touching tracked files | run `provision`; `jj status` is clean |

**Criterion 4 is the one that keeps §7 honest.** If a repo cannot rename or
replace a default without something in devman objecting, the plane has grown an
opinion it should not have. Criterion 16 keeps §11.3 honest. Criterion 9 keeps
devman out of fleetman's job.

---

## 18. Sharp edges

**18.1 Registration cannot happen at evaluation time.** Nix eval is pure, so
§5.2 puts it in `enterShell` behind a hash guard. A repo is invisible until you
enter its shell once. Do not solve this by scanning.

**18.2 `.devman/` has carried other meanings.** `fsdantic` carries a live
`.devman/` of an older shape (`.devman/store/vendor/agentfs`). Migration must
detect the old layout and report it, never silently adopt it.

**18.3 One instance per machine is a shared availability failure.** §15.4.
`doctor` is the mitigation, and it is required.

**18.4 The five resource classes are the one-way door.** They are the only
global names, and the machine's queue mapping depends on them. Adding a sixth is
cheap; renaming one is a migration across every repo. Everything else in §7 is
schema or convention and stays revisable.

**18.5 devenv and NixOS may want different nixpkgs.** §15.2. If they do, the
single-version guarantee becomes a convention rather than a property.

**18.6 A cold devenv in a fresh jj workspace is unmeasured.** §15.1. Stage 4
depends on the answer.

**18.7 An ejected workflow stops tracking pack improvements.** A repo that
ejects `check` keeps that version forever. `doctor` counts ejected files, and a
rising count means the schema is too weak — not that the repos are wrong.

**18.8 Nothing checks that a default still fits.** Since the plane holds no
opinion about what a workflow costs, a `check` that grows to four minutes is
invisible to devman. That is the deliberate trade: no policing, and no false
alarms from a heuristic that cannot know your machine. Notice it yourself.

---

## 19. Open questions

- **Registry root.** `~/.local/share/devman/`. Confirm nothing else claims it.
- **What validates `x-devman`?** §7.6 requires the block but names no schema.
  Lean: the same pydantic model that generates a workflow from `devenv.nix`, so
  both paths land in one shape.
- **Do ecosystem packs ship in this flake?** In-repo is simpler and couples pack
  churn to plane releases. Lean: in-repo until a third party wants to publish
  one.
- **Does the machine module manage a Dagu it did not install?** Lean: no — own
  the service, and document the conflict.
- **How many ecosystem packs at first?** Python and Nix. Rust and TypeScript on
  demand.
- **Where do machine-level overrides live?** Lean: `~/.config/devman/`, resolved
  after the pack layer and before the repo's.
- **Retention.** Runs grow without bound. Lean: 7 days for logs, keep
  `metadata.json` indefinitely — it is small and it is the run history.
- **Does `provision` need a dry run?** Lean: yes, and it is `doctor`'s job.
- **CI's relationship to the plane.** CI is authoritative remote validation and
  runs the same devenv tasks. Does it read the plane's definitions or restate
  them? Lean: read them, at stage 3, or the drift the plane prevents locally
  reappears at the remote boundary.

---

## 20. One word to keep straight

**`registry`** — say **project registry** (devman, opt-in, §5.1) or **fleet
index** (fleetman, scanned). Two different things, and §5.1 depends on not
confusing them.
