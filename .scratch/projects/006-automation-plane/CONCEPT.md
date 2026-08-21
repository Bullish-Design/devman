# devman — Concept (the automation plane)

> **STATUS: PROPOSED (2026-08-21). Replaces the `001`–`005` line.**
>
> `001` through `005` were five drafts of one unanswered question: *what is
> devman?* They are not a supersession chain and this charter does not inherit
> their build orders, their blocked sub-projects, or their "is not" clauses.
> Those were constraints of concepts now discarded. See §2.1.
>
> **This charter answers the question.** devman is the machine-level
> development automation plane: one Dagu control plane, one shared Nix flake,
> one project registry, and one standard workflow vocabulary that every
> devenv-managed repository inherits.
>
> **Source.** `INITIAL_PROPOSAL.md`, in this directory, adopted almost whole.
> The deliberate additions are named in §3.2 so they do not read as scope creep
> later. Where this charter contradicts the guide, §4.2 and §8.1 say so and why.
>
> **What survives from `001`–`005`: measurements only.** A spike result is a
> fact about the world and stays true across concepts. §2.2 lists what carries
> and what is shelved.

---

## 1. One line

> **devman installs one Dagu control plane per machine, and gives every
> devenv-managed repository a shared automation contract through one Nix flake.**

Dagu orchestrates. devenv executes. devman defines the contract between them.

---

## 2. What this replaces

### 2.1 Five drafts of one question

| Draft | Read devman as | Why it is set aside |
|---|---|---|
| `001-recharter` | developer-asset manager | Correct compiler, no automation layer under it |
| `002-agent-surface` | author of every family skill | Blocked on evidence that never arrived; premise unevidenced at 0 drift across 79 references |
| `003-cli-schema` | CLI fact schema | A component, never a charter |
| `004-unified-charter` | asset compiler plus a two-way code mirror | Two large unproven halves; §11 assumed an orchestration layer that does not exist |
| `005-agent-factory` | agents compiling a library | Most ambitious, least supported. Two spikes gate it, both unrun. Its own §10 carries kill criteria |

They are kept on disk as prior art. They are not authority. Raid them for
mechanism; do not treat a decision in one of them as decided here.

### 2.2 What carries forward

Only measurements, and only two of them matter now.

| Spike | Result | Status here |
|---|---|---|
| **A** — devenv eval cache | 5.46s cold, 0.16s warm, 1.44s after a content change, 0.16s warm again | **Load-bearing.** This is the measurement that says devenv is cheap enough to be the plane's executor on a save-triggered path. Keep as a regression baseline (§14 criterion 3). |
| **E** — mirror anchors | 97.7% re-attach on the worst repo, 0 prose lost, 0 ambiguous of 360 | **Shelved, not deleted.** It belongs to the mirror, which is out of scope. It cost a day and costs nothing to keep. |
| B, C, D, F | walker, reference check, collision check, model-owned Python | **Shelved.** They answer questions this charter does not ask. |

Nothing else carries. No asset model, no region kinds, no units, no anchors, no
build order.

### 2.3 The evidence that the plane is the missing layer

`004` and `005` were written independently, months of thinking apart, against
different problems. Both specified an orchestration layer, and they specified
the same one:

| Concern | `004` §11 | `005` §8 |
|---|---|---|
| Orchestrator | Dagu, three DAGs | Dagu, six workflows |
| Execution split | Dagu orchestrates, devenv executes | Dagu orchestrates, devenv executes |
| Workspace vs snapshot | `mirror-sync` / `mirror-full` | implied throughout |
| Resource class | `heavy` on `mirror-full` | queues plus `max_concurrent_agents` |
| Loop-breaking | generation token in `.devman/state/generation.json` | generation token in `.devman/build/generation.json` |
| Agent gating | agent proposes, human approves | stochastic proposes, deterministic disposes |

**Two independent designs hand-rolled the same generation token, in nearly the
same file path.** That is not convergent good taste. It is infrastructure
leaking into consumers because the layer that should own it does not exist.
Every row of that table is plane work done twice.

This charter builds the layer instead. `004` and `005` are then consumers, and
their orchestration sections mostly delete.

---

## 3. What devman is, and is not

### 3.1 Is

The **automation plane**. Three things, and the list is closed:

1. **A shared Nix flake** exposing a machine interface and a repo interface from
   one version (§4).
2. **A project registry** of repositories that opted into automation, keyed by
   project identity, resolving to paths (§6).
3. **A contract** — the structural schema, plus the small reserved vocabulary it
   names: three workflow tiers, two asset workflows, five resource classes (§8).

Item 3 is the product. Strip it and devman is a way to install Dagu, which is
not worth a charter. The ten-line adoption (§6), the cross-repo workflows (§14),
and any generic tooling all rest on the contract being assumable.

**The default workflow library is not on this list.** An earlier draft made it a
fourth item. It is content — an *instance* of the contract, not part of it — so
it ships as the first pack and resolves through the same layer stack as
everything else (§8.3). That keeps §8.2's four-layer hierarchy real instead of
aspirational, and it means a repo may skip packs entirely and declare its own
composition inline.

### 3.2 The deliberate delta from the guide

The guide describes a generic `dagu-automation` flake. devman is that plus one
addition, stated here so it does not read as scope creep later:

> **Asset provisioning is a standard workflow.** Helper scripts, agent skills,
> prompts, and aliases are payload the plane installs and refreshes, through
> `provision` and `refresh` (§9). They are not a separate tool and not a
> separate role.

That is the whole delta. Everything else in §4–§16 is the guide.

### 3.3 Is not

| devman is not | Owner |
|---|---|
| a project index of every repo on disk | **fleetman.** See §6.1 — registration is not discovery, and merging them would break the plane's core premise |
| a workbench | shellij |
| an environment | devenv |
| a source-control tool | jj |
| a scaffolder | copyroom |
| an asset compiler | nothing, deliberately — §9 makes assets payload, not a product |
| a task runner | devenv. devman never re-implements `lint` |

**devman executes nothing itself.** It installs the thing that schedules, and it
defines what the schedule may say. Every command it triggers runs as a devenv
task in the repository that owns it.

---

## 4. One shared flake

### 4.1 The shape

```
devman/
├── flake.nix
├── nix/
│   └── nixos-module.nix       # machine interface
├── modules/                   # repo interface — see §4.2
│   └── default.nix            # the contract: schema + reserved vocabulary
├── packs/                     # content, not contract (§8.3)
│   ├── base/                  # the default tier compositions
│   ├── python/  nix/  rust/   # ecosystem packs
│   └── assets/                # asset packs (§9)
├── dags/                      # machine-level and cross-repo DAGs (§14)
├── lib/                       # shared helpers and metadata schema
└── src/devman/                # the CLI, deferred to stage 3 (§13)
```

Outputs:

| Output | Consumer |
|---|---|
| `nixosModules.default` | the machine's NixOS configuration |
| `modules/` *(a path, not an attribute — §4.2)* | every repo's `devenv.yaml` |
| `homeManagerModules.default` | already present; keeps the CLI on `PATH` |
| `packages.default` | the `devman` CLI |
| `checks` | integration tests for the plane itself |

One flake version defines both interfaces. That is the point: it removes drift
between Dagu configuration, workflow naming, registry layout, resource classes,
and repo integration. Those six things must agree, and nothing else makes them.

### 4.2 Correction to the guide — devenv imports are paths

The guide proposes `devenvModules.default` as a flake output. **devenv does not
consume flake output attributes.** A devenv import resolves to a *directory path
inside a flake input*. This repo already does it:

```yaml
# devenv.yaml, present in this repo today
inputs:
  shellij:
    url: path:/home/andrew/Documents/Projects/shellij
imports:
  - shellij/modules
```

So the repo interface is a `modules/` directory at the flake root, and a
consuming repo writes:

```yaml
inputs:
  devman:
    url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>"
imports:
  - devman/modules
```

The principle in the guide is unchanged — one flake, two interfaces, one
version. Only the mechanism differs.

### 4.3 Delete `src/devman/`

The current source is a tmuxp workspace orchestrator: scan roots, cache an index
at `~/.cache/devman/index.json`, launch sessions. `001` §2.1 already found none
of its 1958 lines load-bearing, and this charter does not rescue it.

The registry looks superficially close, and it is not. v0 **scans**; the plane
**receives registrations** (§6.1). The population rule inverts, so the code
answers the wrong question. Treat this as a rewrite that keeps the repo name.

---

## 5. Machine-level responsibility

The NixOS configuration imports the flake and gets one Dagu instance for the
user or machine.

```nix
# pinned with git+, per the repo's own guidance — a github: input hits the
# GitHub API rate limit on every evaluation
inputs.devman.url = "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>";

imports = [ inputs.devman.nixosModules.default ];
```

The module owns generic infrastructure:

| Owns | Does not own |
|---|---|
| Dagu installation and service lifecycle | which project uses pytest |
| Dagu configuration and workflow discovery | which repo has a benchmark |
| registry paths and state paths | which application has an integration suite |
| queues, concurrency limits, resource-class mapping | any project's task graph |
| log retention | any project's dependency order |
| secret and environment injection | |
| optional worker configuration | |

The split is the load-bearing part. The machine knows *how much* may run at
once. It never knows *what* runs. A machine module that learns one project fact
has started down the path back to a central config file that every repo edits,
which is the failure the plane exists to prevent.

---

## 6. Repo-level responsibility

A repository imports the same flake and declares intent. It should need almost
no boilerplate.

```nix
# devenv.nix
devman = {
  enable = true;
  project = "pyjutsu";          # identity; never a path (§6.2)

  workflows = {
    check.enable = true;
    validate.enable = true;
    full-test.enable = true;
  };

  resources = {
    benchmark = "gpu";
    integration-test = "heavy";
    lint = "light";
  };
};

# the repo still owns its own primitives
tasks."lint".exec = "ruff check .";
tasks."typecheck".exec = "basedpyright";
tasks."test".exec = "pytest";
```

The shared module composes those primitives into workflows. The repo never
writes a Dagu YAML file to enable a default workflow.

### 6.1 Registration, not discovery

This is the distinction that keeps devman and fleetman separate, and it is
worth stating precisely because it is easy to collapse.

| | Mechanism | Population | Payload |
|---|---|---|---|
| **fleetman** | discovery — scan configured roots | every repo found | "this repo exists, here" |
| **devman** | registration — the repo declares itself | only repos with `devman.enable = true` | workflows, resource classes, metadata, identity |

Guide §7 states the premise directly: the registry exists so *Dagu does not need
to understand the developer's project-directory layout*. A scan is exactly that
understanding. Merging the two registries would force the plane back into
scanning and defeat its own design.

They also cannot conflict, because **neither is canonical.** The repository is.
Both registries are derived views, reconstructible by re-reading the repos. If
an integration ever earns its place, it is one reading the other across a
boundary — never a shared store.

### 6.2 Registration is impure, so it runs at shell entry

Nix evaluation cannot write to `~/.local/share/`. Automatic registration is
therefore a side effect, and it needs an explicit home.

> **Registration runs in `enterShell`, guarded by a content hash.** The module
> renders the project's registry entry, compares its hash against the entry on
> disk, and writes only on a difference.

This keeps the common case free — an unchanged repo entering its shell does no
work — and it is the same guard shape as §11's generation token. The cost is
that a repo is registered only after you have entered its shell once.
`devman register <path>` covers the case where that is not acceptable.

---

## 7. Dagu orchestrates, devenv executes

The boundary is strict, and violating it is the main way this design decays.

### 7.1 devenv owns primitive implementation

**The repo names its own tasks.** Task names are pack-local convention, never
reserved — see §8.1 for why.

```
python:  lint  typecheck  test  integration-test
nix:     flake-check  build
rust:    clippy  cargo-check  test
```

One logical task has exactly one implementation, and everything calls it:

```
prefer:  devenv tasks run test

avoid:   Dagu:  pytest
         CI:    uv run pytest
         hook:  devenv shell -- pytest
```

Three call paths mean three things that drift. Spike A is what makes the single
path affordable: 0.16s warm.

### 7.2 Dagu owns composition

```
devenv tasks:              Dagu workflow:

  lint                       lint ───────┐
  typecheck                              ├── validate
  test                       typecheck ──┤
                                         │
                             test ───────┘
```

**Never write the same dependency graph in both.** The rule:

```
repo-internal execution semantics  →  devenv
larger operational orchestration   →  Dagu
```

A repo with a genuinely internal ordering — build before test — expresses it as
a devenv task dependency and exposes one task to the plane. It does not publish
both halves and let Dagu re-derive the order.

---

## 8. The contract

Standardize early — generic tooling is only possible if names are assumable. And
standardize **as little as possible**, because every reserved name is a one-way
door (§19.4).

### 8.1 Reserve the tier, not the technique

An earlier draft reserved eight task names. That was wrong, and Nix is the
counter-example: `nix flake check` is not a lint, and there is no `typecheck`
distinct from `build`. Forcing every ecosystem into a Python-shaped
decomposition produces empty tasks or lies.

| Reserved, cross-ecosystem | Pack-local convention |
|---|---|
| `check` `validate` `full-test` — workflow **tiers** | **task names, entirely** |
| `provision` `refresh` (§9) | python: `lint` `typecheck` `test` |
| `light` `normal` `heavy` `gpu` `exclusive` | nix: `flake-check` `build` |
| | rust: `clippy` `cargo-check` `test` |

Ten reserved words, not sixteen.

Task names need to be stable only *within* a pack, because only the pack
composes them. **Nothing outside a repo ever calls a task** — §14's cross-repo
workflow calls `validate` on three repos, never `pytest` on one.

**One constraint this creates:** a reserved workflow name may not also be a task
name. Rust makes it concrete — `cargo check` is a typecheck and the `check` tier
is fast feedback. The pack maps to the tier; it never exposes a task called
`check`.

### 8.2 The tiers are defined by contract, not content

If content varies by ecosystem, the name needs a language-independent meaning.
Cost and confidence, not technique:

| Tier | Contract | Kind | Default class |
|---|---|---|---|
| `check` | fast feedback, seconds, runs on save. May be incomplete. | workspace | `light` |
| `validate` | the gate. Must pass before you land. Minutes. | workspace | `normal` |
| `full-test` | exhaustive, including slow suites. | snapshot | `heavy` |

```
python pack:  check → lint + typecheck        validate → + test
nix pack:     check → statix + deadnix        validate → nix flake check
rust pack:    check → clippy + cargo check    validate → + cargo test
```

Three fillings, one contract. **Resource class falls out of the tier, not the
language**, which is right — the machine does not care what you write.

### 8.3 Resource classes

The repo declares intent. The machine decides what the intent costs.

| Class | For |
|---|---|
| `light` | lint, formatting, static analysis |
| `normal` | unit tests, ordinary builds |
| `heavy` | integration suites, large compiles, CPU-heavy benchmarks |
| `gpu` | inference, model evaluation, GPU benchmarks |
| `exclusive` | hardware access, destructive database tests, anything that must run alone |

The NixOS module maps classes onto Dagu queues and concurrency limits. A project
never learns the machine's core count.

### 8.4 Four layers, one mechanism

```
base pack  →  ecosystem pack  →  devenv.nix declaration  →  .devman/workflows/*.yaml
```

Later wins. **The default workflow library is the base pack**, not a privileged
built-in (§3.1). A pack is a shared default so five Python repos do not each
write the same six lines — skip it and declare the composition inline for the
same result.

### 8.5 What a repo may name

| The repo decides | |
|---|---|
| its own task names | ✅ always — inline or from a pack |
| which tasks each tier composes | ✅ the project override layer |
| which tiers it has at all | ✅ `full-test.enable = false` |
| brand-new workflow names | ✅ open namespace |
| **what `check` means** | ❌ the one refusal |

```nix
devman = {
  enable = true;
  project = "pyjutsu";

  workflows = {
    check.tasks    = [ "lint" "typecheck" ];
    validate.tasks = [ "lint" "typecheck" "test" ];

    full-test = {
      tasks    = [ "test" "integration-test" ];
      resource = "heavy";
    };

    # new name — yours, nobody else needs to know it
    benchmark-campaign = {
      tasks    = [ "benchmark" ];
      resource = "gpu";
      kind     = "snapshot";
    };

    provision.enable = false;   # not applicable here
  };
};

tasks."lint".exec      = "ruff check .";
tasks."typecheck".exec = "basedpyright";
```

**The one refusal, and the test behind it.** `check` must keep meaning fast
feedback — not because the name is sacred, but because of one question:

> **Can a tool that has never seen this repo do the right thing?**

A watcher firing `check` on save needs seconds. A cross-repo workflow calling
`validate` on three repos needs all three to be gates. Redefine `check` as the
exhaustive suite in one repo and the watcher hangs there — and nothing reports an
error, because nothing can tell.

To *type* something else, use a shell alias or a local devenv task. Free, and it
never reaches the plane.

### 8.6 Raw Dagu YAML — the escape hatch

A Nix task list cannot express everything Dagu can: parallel branches with a
join, preconditions, retries on a flaky step, matrix fan-out. Without an escape
hatch the module grows an option per Dagu feature and ends up re-implementing
Dagu's schema in Nix, badly.

So `.devman/workflows/*.yaml` is the last layer (§8.4).

> **The directory is an input to the registry projection, not a second source
> Dagu reads.** Registration validates the file, resolves project identity, and
> projects it — the same path a generated workflow takes, skipping the Nix
> composition step.

This answers §20's open question: Dagu still reads one place, and hand-written
files still get identity resolution, queue mapping, and the no-absolute-paths
check (criterion 6).

**Rule 1 — the file declares its plane metadata.** Registration refuses one that
does not:

```yaml
# .devman/workflows/validate.yaml
x-devman:
  tier: validate        # or `none` for an open-namespace workflow
  kind: workspace
  resource: normal
steps:
  - name: lint
    run: devenv tasks run lint
```

**Rule 2 — overriding a reserved tier is allowed; the tier contract still
binds.** This differs from §8.5's refusal on purpose. Raw YAML buys *structure*,
and §8.2's contract is about cost and confidence, not structure. A parallel
`validate` with a join is still a gate. What breaks the contract is a `check`
that takes four minutes.

**And the contract becomes measurable.** Run durations are already stored
(§12.2), so this stops being honour-system:

> `devman doctor` reports any tier whose observed runs violate its budget — a
> `check` drifting past seconds, a `validate` past minutes.

Reported, never blocked. Same shape as the guide's "log what was dropped": a
violated contract that nothing mentions reads exactly like a kept one.

**Eject, do not hand-write.**

```
devman show check --format yaml > .devman/workflows/check.yaml
```

Start from the real generated file and edit it. Guide principle 7 is *convention
+ override, not copied workflow boilerplate*, and a raw-YAML directory is exactly
how boilerplate creeps back. Ejecting keeps the hatch cheap without making
from-scratch YAML the normal path.

Honest cost: **every ejected file stops tracking pack improvements.** `doctor`
counts them.

---

## 9. Assets as workflows

The one deliberate addition (§3.2).

`001` and `004` built a compiler for developer assets: scripts, skills, prompts,
aliases. The compiler was the product, and it needed a charter of its own. Under
the plane it does not. **An asset is payload that a workflow installs.**

| Workflow | Does | Blocks? |
|---|---|---|
| `provision` | install this repo's declared assets into their consumer surfaces | no |
| `refresh` | re-install when the source pack or the repo declaration changed | no |

```nix
devman.assets = {
  packs = [ "devenv-literacy" "my-ai" ];
  local = ./.devman/assets;
};
```

Four consequences, all simplifications:

1. **No asset charter is needed.** Provisioning is a devenv task like any other,
   composed by a Dagu workflow like any other.
2. **One pack mechanism carries both kinds of content.** Since §8.4 makes the
   workflow library a pack, workflow packs and asset packs are the same thing
   resolved through the same four layers. There is no second distribution
   system, and `provision` installs from either.
3. **Packs resolve to a machine-wide cache**, never into the repo. This survives
   from `001` §7 because it is the same rule as §12 here: generated state is
   machine-local and reconstructable.
4. **The reverse path disappears.** `004` §10 needed routed change requests
   because its surfaces were compiled from an authored catalog nobody was
   looking at. Assets under the plane are installed, not compiled. Correct the
   source and run `refresh`.

Asset **rendering** — templates, region routing, anchors — is out of scope. If a
pack later needs it, the pack owns it and the plane still only runs the
workflow.

---

## 10. Workspace and snapshot

A first-class distinction, not an implementation detail.

| | Workspace | Snapshot |
|---|---|---|
| Runs against | the live working directory | an immutable jj revision |
| For | lint, format, quick tests, interactive work | full tests, benchmarks, releases, scheduled runs, agent jobs |
| Trigger | file save, debounced | commit, schedule, explicit request |
| Sees your edits mid-run | yes, deliberately | never |

```
snapshot:   revision → temporary jj workspace → devenv → Dagu → artifacts + metadata
```

The reason is not purity. A 40-minute benchmark that observes an edit made at
minute 12 produces a number that describes no revision, and you cannot tell from
the number that this happened.

### 10.1 jj-aware execution

Design for it now, implement it at stage 4. A durable run captures:

```
project   jj commit ID   workflow   parameters   resource class   environment identity   run ID
```

Designing it early costs a metadata field. Retrofitting it means every historical
run is unattributable.

**The open cost is devenv cold start in a fresh workspace.** Spike A measured
5.46s cold in a warm store. A fresh jj workspace per snapshot run may miss the
eval cache every time. §16.1 measures this before stage 4 commits to it.

---

## 11. Triggers, and the loop

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

### 11.1 Loop-breaking is plane infrastructure

Any workflow that writes files a watcher watches will chase itself. `004` and
`005` both discovered this and both wrote the same fix (§2.3). The plane owns it
once:

> **A workflow that writes files records their content hashes to
> `~/.local/share/devman/runs/<project>/<run-id>/generation.json`. A triggered
> workflow skips any file whose hash matches.**

Stateless, no lock, no deadlock, no ordering assumption. A repo never implements
this again.

---

## 12. State, artifacts, and identity

### 12.1 Project identity

Never commit a developer's absolute path.

```
avoid:   working_dir: /home/andrew/Documents/Projects/Pyjutsu
prefer:  project: pyjutsu          → resolved by the registry
```

This is what makes moving a repo, a second machine, a temporary workspace, a jj
workspace, and a future remote worker all work without editing a workflow.

### 12.2 On disk

```
~/.local/share/devman/
├── projects/
│   └── <project>/
│       ├── metadata.json          # identity, path, resource defaults
│       └── workflows/*.yaml       # the projection of the repo's declaration
└── runs/
    └── <project>/<run-id>/
        ├── logs/  artifacts/  reports/
        ├── generation.json
        └── metadata.json
```

and per repository:

```
.devman/
├── devman.toml        # tracked  — this repo's automation declaration
├── workflows/         # tracked  — raw Dagu YAML, the last override layer (§8.6)
├── assets/            # tracked  — local asset payload (§9)
└── state/             # ignored  — local run state
```

`workflows/` is an **input to** the registry projection, never a second source
Dagu reads (§8.6). Every file in it passes through registration and is validated
there.

### 12.3 Canonical and operational

| Canonical — losing it is real loss | Operational — reconstructable |
|---|---|
| git / jj history | Dagu run history and logs |
| the repo's `.devman/` declaration | queues |
| devenv definitions | the registry itself |
| this flake | temporary jj workspaces, ordinary artifacts |

**Rebuilding the Dagu service must be inconvenient, not catastrophic.** That is a
design constraint, not an observation: anything that would make a rebuild
catastrophic does not belong in Dagu state.

### 12.4 Secrets

A workflow references a symbolic name. It never carries a value.

```
GITHUB_TOKEN   HF_TOKEN   DATABASE_URL
```

The NixOS module or the existing secret manager injects them:
`secret manager → Dagu → devenv → task`. The repo declares a dependency on a
secret; it never holds one.

---

## 13. The CLI, deferred

Eventually:

```
devman list      devman register     devman unregister
devman run check devman status       devman doctor
```

**Do not build this at stage 1.** The guide is explicit and it is right: prove
the conventions by hand first. A CLI written before the vocabulary settles
freezes the wrong vocabulary and then defends it.

The one exception is `devman register`, needed at stage 2 for the case §6.2
cannot cover.

---

## 14. Cross-repository workflows

One central instance is what makes these possible at all. They belong to no
single repository, so today they exist nowhere.

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

These live in devman's own `dags/` or a machine-level namespace — never in one
arbitrary participant.

---

## 15. What it refuses to do

| Refuses to | Because |
|---|---|
| Let the NixOS module learn a project fact | it becomes a central config every repo edits, which is the failure being prevented |
| Let a repo learn the machine's concurrency numbers | the repo declares intent; the machine prices it |
| Duplicate a task graph in Dagu and devenv | two graphs drift, and the drift is silent |
| Implement a task itself | devenv owns execution; a second implementation is a second answer |
| Scan the filesystem for projects | registration is the design (§6.1) |
| Reserve a task name | ecosystems decompose differently; Nix has no `typecheck` (§8.1) |
| Let a repo redefine what a tier means | a tool that has never seen the repo could no longer do the right thing (§8.5) |
| Let raw YAML bypass registration | it would lose identity resolution, queue mapping, and the path check (§8.6) |
| Block a run because a tier overran its budget | `doctor` reports it; a plane that blocks on its own heuristic is a worse plane |
| Let an agent block a build | a stochastic gate fails open — it costs autonomy and buys nothing |
| Write into a repo's tracked files without an explicit command | provisioning installs to build outputs and machine caches |
| Treat Dagu state as canonical | §12.3 |
| Ship a default that half the repos override | that is a shared file with a misleading name |
| Build the CLI before the conventions settle | it would freeze the wrong vocabulary |

---

## 16. Riskiest claims

The guide has none, because it is a guide. A charter needs them.

### 16.1 devenv is affordable as the universal executor — **spike, before stage 1**

> Routing every task through `devenv tasks run` costs little enough that nobody
> reaches around it.

Spike A measured the warm path at **0.16s** and a post-change build at 1.44s.
That is the workspace case and it is settled.

**The unmeasured case is a cold devenv in a fresh jj workspace** (§10.1). If a
snapshot run pays 5.46s it is fine. If it pays two minutes because the workspace
misses the eval cache, snapshot workflows are unaffordable and §10 needs a
different mechanism — a reused workspace pool, or a shared eval cache.

*Measure:* create a jj workspace at a revision, enter its devenv, time it. Repeat
cold and warm, ten runs.
*Fails if:* over ~30s repeatedly. Stage 4 then redesigns rather than ships.

### 16.2 One flake serves both interfaces cleanly — **spike, at stage 1**

> A NixOS module and a devenv module can live in one flake, at one version,
> without either constraining the other's nixpkgs.

§4.2 already corrected the mechanism. The residual unknown is input collision: a
repo's devenv pins `devenv-nixpkgs/rolling`, the machine pins its own nixpkgs,
and devman's `modules/` is evaluated under the repo's. If the module needs
packages the repo's nixpkgs does not have, or the two disagree on a shared
input, the single-version premise weakens.

*Measure:* build the smallest real pair — a NixOS module that starts Dagu, a
devenv module that registers one project — and import both from one flake into
this repo and this machine.
*Fails if:* the module must pin its own nixpkgs to work. The plane then ships
two flakes, and §4's anti-drift argument weakens to a convention.

### 16.3 Three tiers cover real repositories

> `check`, `validate`, and `full-test` are enough tiers that no repo needs a
> fourth.

Untestable in advance; measure at stage 2 across five real repos.

**Measure the right thing.** An earlier draft counted *overrides*, which under
§8.4 is the wrong signal — every pack overrides task names by definition, and
that is the design working. The sharp question is narrower:

> Did any repo need a tier that is not `check`, `validate`, or `full-test`?

A repo reaching for raw YAML (§8.6) is fine. A repo wanting a fourth *tier* is
the failure, because tiers are what generic tooling assumes.

The remedy is now cheap in either direction. Under §8.4 a bad default is a pack
fix, not a plane change. Only a wrong *tier set* is expensive — which is a much
smaller thing to be wrong about, and the argument for §13's deferral of the CLI.

Also count ejected files (§8.6). A high eject rate means the Nix composition is
too weak, not that the tiers are wrong.

### 16.4 One instance per machine is a shared failure

A wedged queue blocks every repo, not one. §12.3 bounds the damage — state is
reconstructable, so recovery is a restart — but availability is genuinely
shared. Accepted, with one requirement: **`devman doctor` must diagnose a
wedged plane**, or the shared failure becomes an unexplained one.

---

## 17. Rollout

### Stage 1 — the flake foundation

Spike §16.2 first; it can change the shape. Then:

```
nixosModules.default        one Dagu service, config, state paths
modules/                    the contract — schema + reserved vocabulary (§8.1)
packs/base                  the three tier compositions
packs/python                one ecosystem pack, to prove the layer stack
registration                manual — devman register, or a hand-written entry
```

**Delete `src/devman/` (§4.3).** Adopt in exactly one repo — this one.

### Stage 2 — convention and registration

```
automatic registration (§6.2, enterShell + hash guard)
the metadata schema
resource classes → queues and concurrency
artifact and run-state layout (§12.2)
.devman/workflows/ + devman show --format yaml (§8.6)
```

Adopt across five repos and run §16.3's measurement: **did any repo want a
fourth tier?** Count ejected files alongside it. The tier set is still cheap to
change here and not after.

### Stage 3 — assets and reactivity

```
provision and refresh (§9)
watchexec triggers, VCS hooks
the generation token (§11.1)
retention policy
devman list / status / doctor
```

### Stage 4 — snapshot execution

Spike §16.1 gates this stage.

```
jj-aware isolated workspaces
commit-addressed runs
revision-aware artifacts
cross-repo workflows (§14)
```

### Stage 5 — higher-level automation

Only once every layer below is stable.

```
review workflows      release      maintenance      benchmark campaigns
agent workflows       policy gating
```

**`005`'s agent factory re-enters here, as a consumer**, and it re-enters with
its orchestration sections deleted because the plane supplies them. Its two kill
criteria still gate it. Nothing in this charter argues it will pass them.

---

## 18. Success criteria

| # | Criterion | Measured by |
|---|---|---|
| 1 | One flake, two interfaces, one version | the machine and this repo both import the same rev; `nix flake check` passes |
| 2 | A repo enables automation in under ten lines | `devman.enable` plus workflow toggles; no Dagu YAML written by the repo |
| 2a | A repo may skip packs entirely | declare all three tiers inline in `devenv.nix`; the result matches the pack's |
| 2b | A tier means one thing everywhere | `devman run check` on any registered repo runs that repo's fast-feedback workflow, with no repo-specific knowledge |
| 2c | Ejecting round-trips | `devman show check --format yaml` written to `.devman/workflows/check.yaml` produces an identical projection |
| 2d | Raw YAML cannot bypass the plane | a file without `x-devman`, or with an absolute path, is refused at registration |
| 2e | A violated tier budget is reported | a `check` that runs for minutes appears in `devman doctor`; the run itself is never blocked |
| 3 | devenv stays on the fast path | `devenv shell -- true` ≤ 0.25s warm — Spike A regression |
| 4 | Registration is automatic and idempotent | enter a shell twice; the registry is written once, and the second entry does no work |
| 5 | Registration covers only opted-in repos | a repo without `devman.enable` never appears in the registry, even under a scanned root |
| 6 | No workflow contains an absolute path | grep the registry and `dags/`; zero hits |
| 7 | Identity survives a move | move a repo, re-enter its shell, run `check` — it resolves without editing a workflow |
| 8 | Resource classes reach real queues | mark a task `exclusive`; two concurrent runs serialize |
| 9 | The watchers do not chase each other | a workflow that writes files, plus a watcher on those files, one save, exactly one run |
| 10 | The task graph exists once | no default workflow re-states a dependency devenv already declares |
| 11 | Snapshot runs ignore live edits | start a snapshot run, edit the file mid-run, assert the result matches the revision |
| 12 | A rebuild is inconvenient, not catastrophic | delete Dagu state, re-enter every registered repo's shell, and every workflow runs again |
| 13 | devman adopts itself | this repo carries `.devman/`, `devman doctor` exits 0 |
| 14 | Assets install without touching tracked files | run `provision`; `jj status` is clean |

Criterion 12 is the one that keeps §12.3 honest. Criterion 5 is the one that
keeps devman out of fleetman's job. **Criterion 2b is the one the whole contract
exists for** — if it fails, the reserved vocabulary is buying nothing and §8
should shrink further.

---

## 19. Sharp edges

**19.1 Registration cannot happen at evaluation time.** Nix eval is pure.
§6.2 puts it in `enterShell` behind a hash guard, which means a repo is invisible
to the plane until you have entered its shell once. Do not solve this by
scanning.

**19.2 `.devman/` has carried four meanings.** Workspace descriptor (v0), asset
root (`001`, `004`), unit store (`005`), and now the repo's automation
declaration. **`fsdantic` carries a live `.devman/` of the v0 shape**
(`.devman/store/vendor/agentfs`). Migration must detect the old layout and
report it, never silently adopt it.

**19.3 One instance per machine is a shared availability failure.** §16.4.
`doctor` is the mitigation, and it is required, not optional.

**19.4 The reserved vocabulary is a one-way door once tooling assumes it** —
but a narrow one. §8.1 cut the reserved surface from sixteen names to ten by
un-reserving task names, so only the three tiers, the two asset workflows, and
the five resource classes are hard to change. Everything behind them is pack
content and stays revisable. Renaming `validate` after five repos and a CLI
depend on it is still a migration. This is why §13 defers the CLI and §17 runs
§16.3's measurement at stage 2.

**19.5 devenv and NixOS may want different nixpkgs.** §16.2. If they do, the
single-version guarantee becomes a convention rather than a property.

**19.6 A cold devenv in a fresh jj workspace is unmeasured.** §16.1. Stage 4
depends on the answer.

**19.7 An ejected workflow stops tracking pack improvements.** §8.6's escape
hatch is necessary and it has a cost: a repo that ejects `check` keeps that
version forever. `doctor` counts ejected files, and a rising count is a signal
that the Nix composition is too weak — not that the repos are wrong.

**19.8 The tier budget is a heuristic.** §8.6 has `doctor` compare observed run
times against the tier contract. A slow machine, a cold cache, or one genuinely
large repo will trip it. That is why it reports and never blocks. Resist making
it a gate — a blocking heuristic on a shared plane fails everyone at once.

---

## 20. Open questions

- **Registry root name.** `~/.local/share/devman/` is adopted here, over the
  guide's `dev-dagu`. Confirm nothing else claims it.
- ~~**Does Dagu read `.devman/workflows/` directly?**~~ **Answered — §8.6.** No.
  The directory is an input to the registry projection. Dagu reads one place,
  and hand-written YAML still passes through registration.
- **What is `x-devman` validated against?** §8.6 requires the block but does not
  name a schema. Lean: the same pydantic model that generates a workflow from
  `devenv.nix`, so both paths land in one shape.
- **Do ecosystem packs live in this flake or ship separately?** In-repo is
  simpler and couples pack churn to plane releases. Lean: in-repo until a third
  party wants to publish one.
- **Does the machine module manage a Dagu it did not install?** Some users have
  one already. Lean: no — own the service, and document the conflict.
- **Ecosystem defaults, how many?** Python and Nix first, because that is what
  the family is written in. Rust and TypeScript on demand.
- **Where do machine-level overrides live** (§8.2's fourth layer)? Lean:
  `~/.config/devman/`, resolved after the pack layer and before the repo's.
- **Retention.** Runs under `~/.local/share/devman/runs/` grow without bound.
  Lean: 7 days for logs, keep `metadata.json` indefinitely — it is small and it
  is the run history.
- **Does `provision` need a dry run?** Lean: yes, and it is `doctor`'s job, not
  a separate flag.
- **CI's relationship to the plane.** CI is authoritative remote validation and
  runs the same devenv tasks. Does it read the plane's workflow definitions, or
  restate them? Lean: read them, at stage 3, or the drift the plane prevents
  locally reappears at the remote boundary.

---

## 21. Retired vocabulary

These terms came from `001`–`005` and carry their old concepts back in with
them. Do not reuse them, including as metaphors.

| Retired | Came from | Say instead |
|---|---|---|
| `asset catalog`, `emitter`, `compile` | `001`, `004` | **provision** — assets are installed, not compiled (§9) |
| `mirror`, `surface`, `region`, `anchor` | `004` | nothing — the mirror is out of scope |
| `derived` / `authored` / `chrome` | `004` §6.1 | nothing |
| `change request`, `reverse path`, `ingest` | `004` §10 | nothing — correct the source and `refresh` |
| `unit`, `stage`, `promotion` | `005` | nothing — `005` re-enters at stage 5 with its own words |
| `rung`, `ladder` | the original kickoff | nothing |
| `default workflow library` | this charter's own first draft | **base pack** — it is content, not contract (§3.1, §8.4) |
| **`workflow`, unqualified** | everywhere | say **tier** for a reserved one (`check`/`validate`/`full-test`), **workflow** for any other. §8.1 turns on the difference |
| **`registry`, unqualified** | both fleetman and devman | say **project registry** (devman, opt-in) or **fleet index** (fleetman, scanned). §6.1 |

The last two rows are the traps. Two different things are called a registry, and
the whole of §6.1 depends on not confusing them. And "workflow" now covers both
the three names generic tooling may assume and the open namespace it may not —
§8.5 permits a repo to invent the second freely and forbids it from redefining
the first, so a sentence that blurs them states the opposite of the rule.
