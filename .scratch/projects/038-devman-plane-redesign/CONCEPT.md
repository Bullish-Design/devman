# Devman plane redesign — concept

> **STATUS: IMPLEMENTING (2026-09-12).** This document defines the new boundary
> for Devman, Vendomat, RepoMan, and the repository contract. The implementation
> log records the measurements and decisions that start the migration.

## 1. Decision summary

Make Devman a machine-level control plane.

Vendomat builds and manages the installed plane. Devman owns the automation
contract and projection. RepoMan manages one repository at a time. A repository
declares a stable project manifest instead of pinning the Devman implementation
in its own `devenv.lock`.

The target update is one machine operation:

```text
vendomat plane update devman --to v0.6.0
```

The operation builds one immutable plane generation, renders registered
projects, validates the generated Dagu files, and activates the new generation.
It keeps the previous generation for rollback.

This is a deeper change than a fleet command that updates many repositories.
The fleet command keeps the current dependency boundary. This concept changes
that boundary.

## 2. The problem

Devman is a machine-wide automation plane. One Dagu service, one watcher, one
registry, and one queue set serve all repositories on a machine.

The current repository interface also imports Devman as a Nix input. Each
consumer stores its own Devman reference and lock entry. A Devman change then
requires work in every consumer.

The current update path has these stages:

```text
change Devman
  → update the source reference in each repository
  → update each devenv.lock
  → evaluate each repository's Nix plan
  → enter each devenv
  → register and project each repository
  → verify the plane
```

The work is correct but the ownership is split. The machine plane has one
runtime. The repositories carry many copies of its version.

The measured rollout showed the cost. Updating 46 repositories took about
15.7 minutes. The cost repeated per repository. The current projection also
runs through `enterShell`, which `devenv` runs twice for a normal shell entry.

The goal is not only to hide these commands behind one CLI. The goal is to
remove the repeated dependency update from the repository boundary.

## 3. Design goals

The redesign must achieve these goals:

1. Update the Devman plane once per machine.
2. Reuse one immutable renderer and toolchain closure.
3. Render projects without entering their interactive shells.
4. Detect stale projections without an implicit `PATH` dependency.
5. Keep repository tasks in the repository's `devenv`.
6. Keep Dagu as the workflow engine.
7. Keep Devman as the contract between Dagu and devenv.
8. Preserve project identity and path safety.
9. Support preview, validation, rollback, and recovery.
10. Keep repository migrations in GitMan lanes.

The redesign must not make Devman execute repository tasks. Dagu still
orchestrates. devenv still executes.

## 4. Non-goals

This concept does not make Vendomat a general workflow engine.

This concept does not make RepoMan a fleet controller.

This concept does not move repository task definitions into the machine plane.

This concept does not put absolute repository paths in workflow source.

This concept does not remove GitMan lanes for tracked repository changes.

This concept does not require one global version for every machine or CI
environment. Each machine may install its own immutable plane generation.

## 5. The current model and its protection

The current Devman concept has two interfaces from one flake:

| Interface | Consumer | Current role |
|---|---|---|
| machine interface | NixOS | Dagu, queues, watcher, CLI, state paths |
| repository interface | devenv | project identity, groups, registration, projection |

The current renderer is built under the consuming repository's `nixpkgs`.
Its store path enters the repository's `planFile`. The shell guard compares the
recorded plan with the evaluated plan. A renderer change therefore forces a new
projection.

That protection prevents this failure:

1. A repository records a projection made by renderer version 1.
2. The machine upgrades a renderer found through `PATH` to version 2.
3. The repository's Nix plan still compares equal.
4. The shell guard skips projection.
5. Dagu continues to use bytes produced by version 1.

The old bytes may still validate. The failure can stay silent.

The current design chose a per-consumer renderer because the repository's Nix
plan could observe its store path. See [`nix/renderer.nix`](../../../nix/renderer.nix)
and [`modules/devenv.nix`](../../../modules/devenv.nix).

The redesign keeps the protection. It changes the identity source from a
repository Nix plan to a machine plane generation.

## 6. The target model

The target system has four layers.

```text
┌────────────────────────────────────────────────────────────┐
│ Repository                                                 │
│ project manifest, task definitions, project workflow data  │
└──────────────────────────────┬─────────────────────────────┘
                               │ stable contract
┌──────────────────────────────▼─────────────────────────────┐
│ Central policy                                             │
│ groups, shared workflows, machine-local overlays            │
└──────────────────────────────┬─────────────────────────────┘
                               │ selected policy
┌──────────────────────────────▼─────────────────────────────┐
│ Vendomat plane generation                                  │
│ Devman runtime, renderer, Dagu, shared *man toolchain      │
└──────────────────────────────┬─────────────────────────────┘
                               │ projection
┌──────────────────────────────▼─────────────────────────────┐
│ Dagu                                                      │
│ queues, runs, history, schedules, and execution            │
└────────────────────────────────────────────────────────────┘
```

### 6.1 The repository contract

Each repository carries a small tracked manifest.

```toml
schema = 1
project = "repoman"
groups = ["base", "python"]
policy = "stable"
```

The filename is `.devman/project.toml`. RepoMan creates it from the existing
`devman` options during migration.

The manifest contains project facts that remain true when another person
clones the repository:

- stated project identity;
- selected groups;
- selected policy channel or generation;
- contract capabilities, if required later.

The manifest does not contain:

- absolute paths;
- machine-specific overlays;
- secrets;
- current renderer paths;
- Dagu ports;
- user names;
- local tool paths.

Repository `devenv.nix` files continue to define task names and task commands.
The workflows call those tasks. Devman does not need to evaluate the whole
repository environment to render a workflow.

### 6.2 The central policy

Policy contains workflow content and group selection rules.

Policy may live in a versioned central configuration repository. It may also
ship as an immutable Vendomat artifact. The two forms have the same rule:

> Policy is source content. A generated Dagu file is projection.

Policy needs its own identity. A Devman runtime upgrade should not silently
change every workflow body. The plane should record separate runtime and policy
identities.

The initial implementation may ship both in one plane generation. The metadata
must still record them separately.

### 6.3 The plane generation

Vendomat builds an immutable generation with these fields:

```text
generation = 42
devman_runtime = v0.6.0
renderer_digest = sha256:...
policy_digest = sha256:...
dagu_digest = sha256:...
toolchain_digest = sha256:...
contract_schema = 1
```

The generation has a store path or equivalent immutable identity. The active
generation is a machine fact. It belongs in central state, not in a project
repository.

### 6.4 The project projection record

Each projected project records the inputs that produced it.

```json
{
  "project": "repoman",
  "manifest_digest": "sha256:...",
  "policy_digest": "sha256:...",
  "plane_generation": 42,
  "renderer_digest": "sha256:...",
  "source_digest": "sha256:..."
}
```

The reconciler compares this record with the active generation and current
source. It renders when any input changes.

This replaces the current `planFile` comparison as the primary stale check.
The current plan remains supported during migration.

## 7. Why the shared renderer becomes safe

The current design rejects a machine-side renderer because the shell guard
cannot observe a runtime `PATH` change.

The redesign removes that hidden dependency. Vendomat publishes an immutable
renderer as part of the active plane generation. The central reconciler records
its digest for every projection.

The safe model is:

```text
Vendomat builds one renderer
  → the plane records its digest
  → the reconciler records the digest per project
  → a generation change triggers projection
```

The unsafe model remains forbidden:

```text
machine PATH changes
  → repository plan stays unchanged
  → shell guard does not notice
```

The redesign does not weaken stale protection. It makes the protection belong
to the authority that owns the renderer.

## 8. The update lifecycle

The user-facing operation is:

```text
vendomat plane plan devman --to v0.6.0
vendomat plane update devman --to v0.6.0
vendomat plane rollback --to 41
```

### 8.1 Plan

The plan command reads the active registry and project manifests. It reports:

- projects in scope;
- current plane generation;
- target generation;
- policy changes;
- unsupported manifest schemas;
- invalid workflows;
- duplicate identities;
- local paths that cannot be read;
- repositories that need a RepoMan migration.

The plan command does not mutate repositories or central state.

### 8.2 Build

Vendomat builds the target generation once.

The build includes the renderer, Dagu, and the shared command toolchain. Nix
can reuse the closure across all projects. Vendomat does not copy renderer
source into each repository.

### 8.3 Stage

The reconciler renders projects into a staging area.

Each projected file passes `dagu validate` before activation. The old active
projection remains in place until the new projection passes.

The reconciler writes metadata last. An interrupted render therefore leaves the
previous active projection usable.

### 8.4 Activate

The plane activates the target generation after staging succeeds.

Activation should switch one central pointer or one generation directory. It
should not update dozens of files one at a time without a recovery record.

The system should support two policies:

| Policy | Result |
|---|---|
| `atomic` | activate only when every selected project passes |
| `best-effort` | activate the plane and mark failed projects stale |

The implementation chooses `atomic`. It gives one machine state and makes a
failed project visible before activation. Best-effort activation remains a
future option only if a measured fleet need outweighs its mixed-state cost.

### 8.5 Verify

The plane verifies:

- active generation identity;
- Dagu service state;
- loaded DAGs;
- queue names;
- projection digests;
- stale projects;
- invalid source workflows;
- path collisions;
- project manifest compatibility.

`devman doctor` remains the user-facing report.

## 9. Registration and reconciliation

The current registration path is shell entry. The target design adds explicit
adoption and central reconciliation.

```text
devman adopt /path/to/repository
devman reconcile
devman doctor
```

`devman adopt` should:

1. Read the stated project identity.
2. Refuse a missing or duplicate identity.
3. Refuse a checkout inside another registered checkout.
4. Validate the manifest.
5. Add derived registry metadata.
6. Render the project with the active plane.

The registry remains derived. Adoption does not create a second source of
truth. The repository manifest and central policy remain canonical.

The existing shell hook may continue during migration. It should call the
reconciler, not contain a second projection implementation.

## 10. Component ownership

| Component | Owns | Does not own |
|---|---|---|
| `substrate` or `devman-contract` | stable schemas, identity rules, exit contract | Dagu, Nix builds, repository tasks |
| Devman | resolution, projection, registry, reconciliation, doctor | task execution, repository dependency updates |
| Vendomat | plane builds, artifacts, cache, activation, rollback | workflow semantics, repository lanes |
| RepoMan | one-repository lifecycle and migration | machine-wide fleet state |
| Copyroom | tracked template content | generated runtime projection |
| GitMan | lanes, commits, publish, land | workflow resolution |
| Testee | repository verification | plane activation |
| Dagu | queues, order, retries, history, schedules | project identity |
| devenv | repository task environment | workflow definitions |
| Nix | immutable builds and machine configuration | runtime reconciliation |

Vendomat should consume Devman's renderer output. It should not copy or fork
the renderer implementation.

## 11. Pros

### 11.1 Lower update cost

A runtime Devman update becomes one plane build and one reconciliation pass.
Repositories do not need individual Devman lock changes.

### 11.2 Correct ownership

Devman is a machine-wide control plane. The redesign stores its runtime version
in the machine plane.

Project facts remain in repositories. Machine facts remain central.

### 11.3 One renderer and one Dagu dependency

Vendomat builds the renderer and its Dagu dependency once. Nix and the binary
cache reuse that closure.

The system removes per-repository renderer derivations and their version skew.

### 11.4 Better rollback

The plane retains old generations. A failed generation can roll back without
reverting many repository lock files.

### 11.5 Better visibility

The plane can report one fleet view:

- current generation;
- stale projects;
- failed projects;
- policy drift;
- unsupported contracts;
- invalid workflows.

### 11.6 Faster normal use

Project projection no longer waits for shell entry. A central watcher can
reconcile only projects whose inputs changed.

The shell hook no longer carries the normal deployment cost.

### 11.7 Cleaner repository adoption

A new repository needs a manifest and task definitions. It does not need a
Devman input update for every machine-plane release.

### 11.8 Better policy promotion

Separate runtime and policy identities allow candidate policy testing before a
machine-wide promotion.

## 12. Cons and risks

### 12.1 A larger impact range

A broken plane generation can affect every project on one machine.

The system needs canaries, staging, validation, and rollback before activation.

### 12.2 Less repository-level version isolation

Projects no longer choose an arbitrary Devman runtime by default.

The system needs contract compatibility and an escape path for projects that
cannot move with the active plane.

### 12.3 Policy can change many projects

If groups ship with the plane, a plane update can change workflow behavior.

Separate policy identity, preview, and promotion reduce this risk.

### 12.4 More central state

The machine needs generation state, projection records, and rollback metadata.

The state must remain derived or recoverable. It must not become a hidden
project configuration database.

### 12.5 A larger migration

The current `devman.groups` and `devman.project` options live in the devenv
module. The target manifest becomes the source for project identity and group
selection.

The migration needs dual-read or dual-write support. It must compare old and
new projections before it removes the old path.

### 12.6 More CI design work

CI must select a plane generation. It cannot rely on the developer's active
machine plane without losing reproducibility.

Vendomat should provide a locked plane input for CI and local use.

### 12.7 Partial repository failure remains possible

A project may contain an invalid local workflow or an unsupported manifest.

The plane needs an explicit policy for whether that blocks all activation.

### 12.8 The central service becomes more important

The reconciler must recover after a restart. It must not leave a half-written
projection or delete the previous working state.

## 13. Implications

### 13.1 Versioning

The system needs separate identities for:

- contract schema;
- Devman runtime;
- renderer;
- policy;
- Dagu;
- shared toolchain;
- project manifest;
- local overlay.

One version number cannot describe all of these safely.

### 13.2 Nix module design

The current repository module becomes a compatibility adapter.

The final module may only provide:

- stable contract values;
- task integration;
- optional local development helpers.

It should not build the machine renderer or register the project as a side
effect of every shell entry.

### 13.3 Group resolution

Group resolution must have one implementation.

The target implementation should read the manifest and policy source directly.
It should not resolve groups once in Nix and again in Python.

### 13.4 Workflow overlays

The link-plane design already moves machine-local per-project workflows into a
central configuration repository. The redesign should keep that direction.

Repository-owned workflow source remains tracked. Machine-local workflow source
remains central and linked. Generated Dagu files remain projections.

### 13.5 Repository writes

A plane update should not edit tracked repository files.

If a manifest migration changes a tracked file, RepoMan must create a GitMan
lane. An unattended write to repository trunk remains forbidden.

### 13.6 Security

The central reconciler reads every registered repository and central overlay.
It must validate paths and refuse traversal outside the declared project root.

Devman still does not execute workflow steps. Dagu and devenv execute them when
the workflow runs.

### 13.7 Multi-machine use

Each machine can select a plane generation. A team or CI machine can pin a
different generation from a developer machine.

The project manifest remains portable. Machine paths and overlays do not enter
the repository.

### 13.8 Failure reporting

The plane needs a structured result for each project.

```text
planned
staged
activated
blocked
failed
stale
rolled_back
```

The report must name the generation, project, source, and failure.

## 14. Opportunities

### 14.1 Preview generated changes

Add a diff command that shows workflow and projection changes before activation.

### 14.2 Canary projects

Promote a plane or policy through candidate projects before the full machine.

### 14.3 Content-addressed render cache

Cache a projection by:

```text
plane digest
policy digest
manifest digest
source digest
overlay digest
```

Unchanged projects become no-ops.

### 14.4 Fast recovery

Keep the prior generation and prior project projections. Roll back one pointer
instead of rebuilding every project.

### 14.5 Fleet health as a first-class report

`devman doctor` can report one machine view without scanning arbitrary folders.

### 14.6 Remote or shared planes

The generation model can support a team-managed or CI-managed plane later.

The local user plane remains the first implementation because it owns the
developer's credentials and Nix profile.

### 14.7 Contract tests

The substrate can provide compatibility fixtures. A new Devman plane can test
old manifests before activation.

### 14.8 Policy channels

Projects can select `stable`, `candidate`, or an explicit policy digest.

### 14.9 Better adoption

`devman adopt` can create a manifest, validate task names, and render the first
projection in one operation.

## 15. Alternatives

| Design | Update cost | Isolation | Change size | Assessment |
|---|---:|---:|---:|---|
| Current per-repository pins | high | strong | none | correct but slow |
| Vendomat fleet updater over current pins | medium | strong | medium | useful transition design |
| Shared renderer with per-repository plan pins | medium | medium | medium | safe, but keeps lock fan-out |
| Machine plane with stable project contract | low | controlled | high | recommended target |

The fleet updater remains useful during migration. It should not become the
final architecture if the machine plane becomes the version authority.

## 16. Migration plan

### Stage 0 — amend the charter

Record the new ownership model in the Devman concept and the link-plane
concept.

Record which current rules remain invariant and which rules change.

Define the contract schema, generation metadata, policy identity, and rollback
semantics before implementation.

### Stage 1 — define the contract

Add a manifest schema and validation library.

Add a RepoMan migration command that reads the current `devman.project` and
`devman.groups` values.

Do not remove the current Nix options.

### Stage 2 — dual projection

The first implementation slice has started this stage with the new
manifest-derived renderer. Vendomat can build and activate a temporary
generation, but the old Nix path remains the default until comparison tests
cover the full canary set.

Render each project through both paths:

1. the current Nix-derived plan;
2. the manifest-derived plan.

Compare the selected workflow, source, trigger, and projection identities.

Record every mismatch. Do not switch the active projection until the mismatch
set is understood.

### Stage 3 — build the machine plane

Add a Vendomat plane package with:

- Devman runtime;
- renderer;
- Dagu;
- policy input;
- generation metadata;
- staging and activation;
- rollback.

Keep Devman as the canonical renderer source.

### Stage 4 — central reconciliation

Add central adoption, reconciliation, and project health reporting.

Keep shell entry as a compatibility path. Make it call the central reconciler.

### Stage 5 — canary activation

Run the new plane against Devman, RepoMan, and Vendomat first.

Compare generated files, Dagu discovery, scheduled runs, queue behavior, and
run logs.

Use a small project wave before the full fleet.

### Stage 6 — switch the default

Make the machine plane the default source for projection.

Keep the old Nix projection behind an explicit compatibility mode.

### Stage 7 — remove the fan-out

Remove direct Devman runtime inputs from consumer repositories.

Retain only the stable contract adapter if the repository still needs one.

Stop requiring `devenv update devman` for routine plane updates.

### Stage 8 — separate policy release

Move group and policy identity from the runtime identity.

Add policy preview and promotion.

## 17. Measurements required before adoption

The redesign should not rely on the existing rollout timing alone.

Measure:

1. cold and warm plane build time;
2. projection time per project;
3. full-fleet staging time;
4. no-op reconciliation time;
5. shell-entry time before and after removal;
6. cache reuse across different repository `nixpkgs` values;
7. activation and rollback time;
8. failure recovery after an interrupted render;
9. output equality between the old and new projection paths;
10. CI setup time for a locked plane generation.

The target is not only lower wall time. The target is fewer independent state
transitions and a smaller chance of silent stale output.

## 18. Success criteria

The redesign succeeds when:

- one command updates the machine Devman plane;
- normal updates do not edit consumer Devman locks;
- projection does not require entering every repository shell;
- one renderer generation serves the machine;
- every projection records its generation and source digests;
- stale projections produce a visible finding;
- failed projects retain their previous valid projection;
- rollback restores the previous generation;
- repository migrations use GitMan lanes;
- no workflow contains a machine path;
- Devman still executes no repository task;
- Dagu still enforces queues and records runs;
- RepoMan remains repository-specific;
- the old and new projection paths produce equivalent output during migration.

## 19. Open decisions

1. **Resolved:** the manifest is `.devman/project.toml`.
2. The first policy source is the central Devman policy checkout. A versioned
   immutable policy artifact remains a later Vendomat packaging choice.
3. **Resolved:** the default activation mode is `atomic`.
4. How many prior contract schemas should the plane support?
5. How should a project request an older plane generation?
6. Should CI receive a full Vendomat generation or a smaller Devman-only plane?
7. **Resolved for migration:** RepoMan owns one repository's adoption and
   manifest migration. Devman owns central reconciliation.
8. Which generated files need atomic directory swaps?
9. How should Dagu reload a new generation without losing active runs?
10. Which policy changes require a GitMan lane instead of central activation?
11. How should the plane handle a repository that is offline during activation?
12. What evidence permits removal of the current shell-entry projection path?

## 20. Recommendation

Adopt the machine-plane direction.

Do not stop at a parallel fleet updater. Use that updater as a migration tool
while the system gains a stable repository contract and a generation-based
machine plane.

The clean target is:

```text
one machine plane
one renderer generation
one policy identity
many repository manifests
many repository task environments
```

This design matches Devman's role, reduces update fan-out, preserves stale
projection protection, and creates a clear boundary between machine policy and
repository content.
