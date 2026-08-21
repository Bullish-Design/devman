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

Three things, and the list is closed:

1. **A shared Nix flake** exposing a machine interface and a repo interface from
   one version (§3).
2. **A project registry** of repositories that opted into automation, keyed by
   identity, resolving to paths (§5).
3. **A contract** — a queue name, and nothing else (§7).

Item 3 is deliberately thin. The plane needs a name it can resolve and a queue
it can run in. That is the whole of what it understands.

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
│   └── machine/               # cross-repo and machine-level DAGs (§11)
├── lib/                       # registry schema, registration helpers
└── src/devman/                # the CLI, deferred to stage 3 (§10)
```

| Output | Consumer |
|---|---|
| `nixosModules.default` | the machine's NixOS configuration |
| `modules/` *(a path — §3.2)* | every repo's `devenv.yaml` |
| `homeManagerModules.default` | keeps the CLI on `PATH` |
| `packages.default` | the `devman` CLI |
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
  groups = [ "base" "python" ];       # workflows to inherit (§7.4)
};

tasks."lint".exec      = "ruff check .";
tasks."typecheck".exec = "basedpyright";
tasks."test".exec      = "pytest";
```

Two lines plus the repo's own primitives. `project` defaults to the directory
name and is worth setting only when that is wrong or already taken —
registration refuses a duplicate identity (§9.1).

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

The common case costs nothing. The cost is that a repo is registered only after
you enter its shell once; `devman register <path>` covers the rest.

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

### 7.1 What is global

**Queue names.** The machine module creates Dagu queues and sets what each
costs; a workflow names one. That is the entire shared vocabulary, and it is
Dagu's own field, not a devman word for it.

```
light   normal   heavy   gpu   exclusive
```

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
workingDir: ${DEVMAN_PROJECT_DIR}
steps:
  - name: lint
    run: devenv tasks run lint
  - name: typecheck
    run: devenv tasks run typecheck
```

`queue` is Dagu's. `workingDir` is Dagu's, and the variable is what keeps the
file portable — the machine module sets `DEVMAN_PROJECT_DIR` per project from
the registry, so one file serves every repo that takes the group (§9.1).

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
  enable = true;
  groups = [ "base" "python" ];           # what to inherit
  project = "pyjutsu";                    # optional; defaults to the dir name

  workflows.full-test.enable = false;     # drop one you do not want
};

tasks."lint".exec      = "ruff check .";  # your primitives, your names
tasks."typecheck".exec = "basedpyright";
```

Everything else is a file. Rename by naming the file differently, replace by
shadowing, drop with `enable = false`, invent by adding
`.devman/workflows/benchmark-campaign.yaml`.

The plane resolves a name to a file and runs it at the declared class. It has no
opinion about what the work is.

---

## 8. Triggers

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

### 8.1 Loop-breaking is plane infrastructure

Any workflow that writes files a watcher watches will chase itself. The plane
owns the fix once, so no repo implements it again:

The loop is concrete. You save `foo.py`; the watcher fires `format`; `format`
rewrites `foo.py`; the watcher sees that write and fires `format` again.

> **A workflow that writes files records their content hashes to
> `.devman/.runs/generation.json`. A trigger skips any file whose current hash
> matches.**

It is a note saying *I did that* — nothing more. Stateless, so no lock, no
deadlock, and no ordering assumption.

Hashes rather than a timer or a flag, because hashes give the property that
matters: **your own edit still fires.** Edit `foo.py` right after the formatter
touched it and the hash no longer matches, so the trigger runs. A suppression
window would have swallowed it.

The token is only needed where a workflow writes inside its own trigger's watch
scope. That is a narrower case than it sounds — but it is silently wrong when
reinvented badly, so the rule is stated once here.

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
    ├── generation.json        # the loop-breaking token (§8.1)
    └── <run-id>/logs/ artifacts/ reports/ metadata.json
```

**Two locations, one rule each.** The registry is machine-side because it is
machine-wide. Run output is repo-side because you read it from inside the repo
you were working in, and because it belongs to a **working tree, not a
project** — one project can be checked out twice, and each checkout runs and
fails on its own.

`.devman/workflows/` is tracked; `.devman/.runs/` is not. The devenv module adds
the ignore rule at registration, because an un-ignored `.runs/` turns the first
failed run into a dirty tree.

`workflows/` is an input to the projection, never a second source Dagu reads.

### 9.3 Canonical and operational

> **Everything under `~/.local/share/devman/` is reconstructable by re-entering
> every registered repo's shell.** The registry, the queues, the run history, the
> logs, the temporary workspaces.

Canonical state is the repo's history, its `.devman/workflows/`, its devenv
definitions, and this flake. **Rebuilding the Dagu service must be inconvenient,
not catastrophic** — a design constraint, not an observation. Anything that
would make a rebuild catastrophic does not belong in Dagu state.

### 9.4 Secrets

A workflow references a symbolic name and never carries a value.

```
GITHUB_TOKEN   HF_TOKEN   DATABASE_URL
```

Injection runs `secret manager → Dagu → devenv → task`. The repo declares a
dependency on a secret; it never holds one.

---

## 10. The CLI, deferred

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

## 11. Cross-repository workflows

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

These live in devman's `machine` group — never in one arbitrary participant.

---

---

## 12. Riskiest claims

### 12.1 Dagu supports what the design assumes — spike, before stage 1

> Dagu accepts a named queue on a DAG, interpolates an environment variable in
> `workingDir`, and can be told where to write a run's logs.

§7.2 rests on the first two; §9.2 rests on the third. If `workingDir` does not interpolate, one group file cannot
serve many repos and registration has to rewrite each projection — recoverable,
but it makes the plane parse files it currently never touches. If queues are not
named per DAG, §7.1's only global vocabulary has nothing to bind to.

*Measure:* write one DAG naming a queue with an interpolated `workingDir`, run it
against two projects, and confirm its logs land under each project's
`.devman/.runs/`.
*Fails if:* interpolation or per-DAG queues are unsupported — the plane then
rewrites files at projection, and §7.2's "devman never parses a workflow"
becomes false. If only the log path is fixed machine-wide, §9.2 moves run output
back beside the registry.

This spike is first because it is cheap and because the charter assumed a
feature set it never checked.

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

§7.4 refuses field merging, so changing one step of `check` means copying
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
registration            manual — devman register, or a hand-written entry
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
the generation token (§8.1)
retention policy
devman list / status / doctor
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
| 2 | A repo adopts the plane in two lines | `devman.enable` and `devman.groups`; no Dagu YAML, no identity, no per-workflow config |
| 3 | A repo may take no groups at all | `groups = []` plus its own `.devman/workflows/`; every workflow runs |
| 4 | **A repo may rename or replace every default** | drop `check`, define `smoke` and `ci`; both run, and nothing in devman objects |
| 5 | Shadowing is exact | `devman show check` saved to `.devman/workflows/check.yaml` projects identically; edit one step and only that step changes |
| 6 | A workflow is portable Dagu | one group file, unedited, runs correctly in every repo that takes the group |
| 7 | devenv stays on the fast path | `devenv shell -- true` ≤ 0.25s warm — Spike A regression |
| 8 | Registration is automatic and idempotent | enter a shell twice; the registry is written once |
| 9 | Registration covers only opted-in repos | a repo without `devman.enable` never appears in the registry |
| 10 | No workflow contains an absolute path | grep the registry and `workflows/`; zero hits |
| 11 | Identity survives a move | move a repo, re-enter its shell, run `check` — no workflow edited |
| 12 | Queues are real | two workflows naming the `exclusive` queue serialize |
| 13 | The watchers do not chase each other | a file-writing workflow plus a watcher on those files, one save, exactly one run |
| 14 | The task graph exists once | no default workflow re-states a dependency devenv already declares |
| 15 | A rebuild is inconvenient, not catastrophic | delete Dagu state, re-enter every registered shell, every workflow runs again |
| 16 | devman adopts itself | this repo carries `.devman/`, `devman doctor` exits 0 |

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

**15.4 Queue names are the one-way door.** They are the only global names.
Adding one is cheap; renaming one is a migration across every workflow that names
it.

**15.5 devenv and NixOS may want different nixpkgs.** §12.2. If they do, the
single-version guarantee becomes a convention rather than a property.

**15.6 An overriding file stops tracking its group.** A repo that shadows
`check.yaml` keeps that version forever, and §7.4 offers no partial override.
`doctor` counts shadowed files and reports how far each has diverged from the
group version.

**15.7 Renaming a repo's directory changes its identity.** `project` defaults
to the directory name (§9.1), so a rename detaches the repo from its run
history and re-registers it as new. Set `project` explicitly in any repo whose
directory name you expect to change.

**15.8 Nothing checks that a default still fits.** Since the plane holds no
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
- **Where do machine-level overrides live?** Lean: `~/.config/devman/`, resolved
  after the group layer and before the repo's.
- **Retention.** `.devman/.runs/` grows inside the repo, where it is at least
  visible. Lean: 7 days for logs and artifacts, keep `metadata.json`
  indefinitely — it is small and it is the run history.
- **Where does a cross-repo run log go?** §11's workflows belong to no single
  repo, so repo-side has no home for them. Lean: `~/.local/share/devman/runs/`
  for the `machine` group only — accepting one exception rather than pushing
  every repo's logs machine-side to avoid it.

---
