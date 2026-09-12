# Prompt: implement the Devman machine-plane redesign

You are the implementation agent for a full refactor of Devman.

Work in a clean session. Do not limit the work to analysis. Inspect the current
implementation, make the required changes, run the proof, and leave the
repositories in a usable state.

The user owns all three libraries in scope. You may refactor Devman, Vendomat,
and RepoMan when the refactor needs it.

## Mission

Replace the current per-repository Devman update model with a machine-level
Devman plane.

The target user experience is:

~~~
vendomat plane plan devman --to VERSION
vendomat plane update devman --to VERSION
vendomat plane rollback --to GENERATION
~~~

One machine operation must build one immutable Devman plane generation, render
all registered projects, validate the generated Dagu files, activate the new
generation, and retain the previous generation for rollback.

A normal Devman update must not require this repeated consumer workflow:

~~~
update Devman in every repository
update every devenv.lock
evaluate every repository
enter every repository shell
register every repository
render every repository
verify every repository
~~~

The refactor must preserve correctness. It must not hide a stale renderer,
silently use the wrong project, execute repository tasks from Devman, or edit
tracked repository files from an unattended plane update.

## Repositories

The primary repositories are:

- Devman: /home/andrew/Documents/Projects/devman
- RepoMan: /home/andrew/Documents/Projects/repoman
- Vendomat: /home/andrew/Documents/Projects/vendomat

Start by inspecting each repository's current branch, worktree, project
instructions, tests, command surface, and package layout.

Do not assume that the existing concept matches the current code. Measure the
difference.

## Required reading

Read these files before changing code:

1. Each repository's AGENTS.md and AGENTS_GUIDE.md, when present.
2. The applicable local skills for Devman, RepoMan, Vendomat, writing, and Git.
3. Devman's current concept and incident report:
   - .scratch/projects/038-devman-plane-redesign/CONCEPT.md
   - .scratch/projects/038-devman-plane-redesign/issue.md
4. Devman's current charter and amendments:
   - .scratch/projects/006-automation-plane/CONCEPT.md
   - .scratch/projects/007-standard-workflows/PROPOSAL.md
   - .scratch/projects/025-the-link-plane/CONCEPT.md
5. The stage logs cited by Devman's AGENTS.md.
6. The current Devman renderer and repository module:
   - nix/renderer.nix
   - modules/devenv.nix
   - src/devman/
7. Devman's groups, overlays, triggers, and projection documentation.
8. The current RepoMan and Vendomat command and library documentation.

Read the source for the current update path. Find every caller of:

- the Devman Nix input;
- devenv update operations;
- renderer construction;
- shell-entry projection;
- registry updates;
- project adoption;
- workflow resolution;
- Dagu activation or reload;
- RepoMan repository mutation;
- Vendomat package or generation activation.

Use the existing names and interfaces when they are sound. Replace them when
the current boundary makes the target model unsafe or needlessly complex.
## User's standing decisions

Treat these decisions as part of the task:

- The three libraries are owned by the user.
- A clean architectural boundary is more important than preserving an
  accidental current interface.
- The user wants a full refactor, not a wrapper around the old fan-out.
- Use raw Git for version control in this refactor.
- Do not let the current GitMan off-canonical state block the work.
- Never run a destructive recovery command for unrelated work.
- Preserve unrelated worktree changes in every repository.
- Stage only files that belong to the current change.
- Commit and push completed work unless a repository instruction or a concrete
  safety problem prevents it.
- Do not ask for permission for normal in-scope implementation work.
- Ask only when a decision would materially change the architecture and the
  available evidence cannot resolve it.

## Target ownership model

Use these ownership rules as the default design.

### Devman owns

- the stable project contract;
- project identity validation;
- group and policy resolution;
- workflow projection;
- renderer behavior;
- projection metadata;
- central reconciliation;
- adoption;
- stale detection;
- fleet health and doctor output;
- compatibility checks;
- the contract between Dagu and devenv.

Devman must not execute repository tasks.

### Vendomat owns

- machine plane builds;
- immutable plane generations;
- Devman runtime packaging;
- renderer packaging;
- Dagu packaging;
- shared toolchain closure;
- build and render cache;
- staging;
- activation;
- rollback;
- generation lifecycle;
- machine-level update and plan commands.

Vendomat must consume the Devman renderer. It must not copy or fork the
renderer implementation. Vendomat must not become the owner of workflow
semantics or repository task definitions.

### RepoMan owns

- one repository's lifecycle;
- repository-specific migrations;
- manifest creation and editing;
- repository-specific validation;
- repository lanes, commits, and publish operations;
- controlled application of changes to repository worktrees.

RepoMan must not own the machine plane generation. RepoMan must not own the
renderer. A fleet migration may call RepoMan once per repository, but the
repository mutation must remain a RepoMan operation with its own review and
recovery semantics.

If the implementation needs a coordinator for many repository migrations,
design the coordinator explicitly. Do not hide repository writes inside
Vendomat plane activation.

### Dagu owns

- queues;
- ordering;
- retries;
- schedules;
- run history;
- workflow execution orchestration.

### devenv owns

- repository task definitions;
- repository task environments;
- task dependency graphs;
- task execution when Dagu invokes a task.

### Nix owns

- immutable builds;
- package closures;
- machine configuration;
- reproducible artifacts.

## Non-negotiable invariants

Keep these invariants throughout the migration.

1. Dagu orchestrates. devenv executes. Devman is the contract.
2. Devman never executes a repository task to render a workflow.
3. The plane contains no project-specific absolute path in workflow source.
4. A repository manifest contains portable project facts.
5. Machine-local paths, overlays, secrets, ports, and user names stay out of
   tracked repository contracts.
6. The registry is derived. The repository manifest and central policy are
   canonical.
7. Generated Dagu files are projections. They are not policy source.
8. A renderer change must always be visible to stale-renderer protection.
9. A shared renderer is safe only when it has an immutable generation identity
   and every projection records that identity.
10. A machine PATH change must never be the only renderer version signal.
11. A plane update must not edit tracked repository files.
12. A tracked manifest migration must use RepoMan and a reviewable Git lane.
13. A failed render must not destroy the last valid active projection.
14. Activation must support a clear rollback path.
15. Path traversal, nested checkouts, duplicate project identities, and path
    collisions must fail loudly.
16. Group resolution must have one implementation.
17. Shared queue names and environment names remain deliberate contract surface.
18. A command that reports success must have performed the requested work.
19. No silent default may turn a missing project fact into a literal path.
20. Secrets are declared and supplied by the machine. The libraries do not hold
    secret values.

## Target architecture

Implement this conceptual flow:

~~~
repository manifest
        |
        v
central policy and group source
        |
        v
Devman contract, resolver, and renderer
        |
        v
Vendomat plane generation
        |
        +--> immutable renderer
        +--> Dagu
        +--> shared toolchain
        +--> generation metadata
        |
        v
staging and validation
        |
        v
atomic active projection
        |
        v
Dagu control plane
        |
        v
devenv task execution in the target repository
~~~

The repository carries a small stable manifest. The machine carries the active
generation. The central state records each projection.

Use a manifest similar to this as the starting point:

~~~
schema = 1
project = "repoman"
groups = ["base", "python"]
policy = "stable"
~~~

The exact filename and fields are an implementation decision. The current
proposal is .devman/project.toml. Preserve the distinction between portable
repository facts and machine-local facts.
Use a generation record similar to this:

~~~
generation = 42
devman_runtime = "v0.6.0"
renderer_digest = "sha256:..."
policy_digest = "sha256:..."
dagu_digest = "sha256:..."
toolchain_digest = "sha256:..."
contract_schema = 1
~~~

Use a projection record similar to this:

~~~
{
  "project": "repoman",
  "manifest_digest": "sha256:...",
  "policy_digest": "sha256:...",
  "plane_generation": 42,
  "renderer_digest": "sha256:...",
  "source_digest": "sha256:..."
}
~~~

Add overlay and local-source digests when the actual implementation needs them.

The reconciler must render when any relevant input changes. It must make a
no-op decision when all relevant inputs match.

## Required user operations

Implement or refine a coherent command surface.

### Plane operations

The exact CLI namespace must match existing Vendomat conventions. The behavior
must support these operations:

1. Plan a target plane generation without mutating state.
2. Build a target generation once.
3. Show the projects in scope.
4. Show policy, renderer, Dagu, and toolchain changes.
5. Report unsupported manifests and invalid workflows.
6. Stage project projections.
7. Validate every generated Dagu file before activation.
8. Activate one generation pointer or equivalent atomic generation directory.
9. Record project-level results.
10. Roll back to a prior generation.
11. Recover after an interrupted build, render, or activation.
12. Run a no-op update without rebuilding unchanged projects.

### Devman operations

The exact names must fit the current Devman CLI. The behavior must support:

- adopt a repository;
- reconcile registered repositories;
- inspect projection state;
- detect stale projections;
- report project-level health;
- validate manifest and policy compatibility;
- show the source and identity for a resolved workflow;
- retain devman doctor as the human-facing health report.

The compatibility shell hook may remain during migration. It must call one
reconciler. It must not contain a second projection implementation.

### RepoMan operations

The exact names must fit the current RepoMan CLI. The behavior must support:

- create a manifest migration for one repository;
- validate a repository before migration;
- apply the migration in a reviewable lane;
- report repositories that need migration;
- support a controlled multi-repository migration by invoking repository
  operations one at a time;
- preserve per-repository failure, review, and recovery state.

Do not make a machine plane update silently edit all repositories.

## Execution plan

Follow these phases. Keep a dated implementation log in project 038. Record
decisions, measurements, failed attempts, and changes to the concept.

### Phase 0: audit the current system

Before writing implementation code:

1. Record the worktree state in all three repositories.
2. Record the current branches and remotes.
3. Inventory the current command surfaces.
4. Trace the current per-repository Devman update path.
5. Measure a representative update with warm and cold caches.
6. Measure shell-entry projection time.
7. Count the repositories that use Devman.
8. Record which repositories have local overlays.
9. Identify every current stale-renderer check.
10. Identify every generated file and its active location.
11. Identify how Dagu reloads or discovers changed DAGs.
12. Identify how RepoMan can mutate one repository safely.
13. Identify how Vendomat builds and activates packages.
14. List all current compatibility constraints.

Produce a scope matrix with these columns:

- current owner;
- current input;
- current output;
- current state location;
- current command;
- target owner;
- target state location;
- migration needed;
- test needed.

Do not remove the old path during this phase.

### Phase 1: define the stable contract

Implement the contract before changing the plane lifecycle.

1. Define the manifest schema.
2. Define schema validation and error messages.
3. Define project identity rules.
4. Define group and policy references.
5. Define contract compatibility rules.
6. Define generation metadata.
7. Define projection metadata.
8. Define digest inputs and canonical serialization.
9. Define state locations and permissions.
10. Define collision and nested-checkout behavior.
11. Add fixture manifests for valid and invalid cases.
12. Add compatibility tests for the old repository options.

Make the contract library usable without starting Dagu and without executing a
repository task.

If a separate substrate package improves ownership, use it. If it adds more
versioning and packaging cost than it removes, keep the contract inside Devman
and document the choice.

### Phase 2: refactor Devman around central reconciliation

Build the new Devman core.

1. Extract pure contract, resolution, digest, and projection logic.
2. Keep I/O and machine activation at clear boundaries.
3. Make one resolver authoritative.
4. Make one renderer authoritative.
5. Add central adoption.
6. Add central reconciliation.
7. Add staging and validation.
8. Write projection metadata only after successful validation.
9. Preserve the last valid projection during failure.
10. Add explicit stale findings.
11. Add generation and source identity to every finding.
12. Add structured per-project results.
13. Keep devman doctor as the aggregate report.
14. Make the operations idempotent.
15. Make all path checks explicit and testable.

The new renderer must be safe to package once. It must not discover its version
through PATH. It must receive or read an immutable plane identity.
### Phase 3: integrate Vendomat

Add machine-plane lifecycle support to Vendomat.

1. Package the Devman runtime and renderer.
2. Package Dagu and the shared toolchain.
3. Build one immutable generation.
4. Record separate runtime, renderer, policy, Dagu, toolchain, and schema
   identities.
5. Reuse the build closure across all projects.
6. Add plan output.
7. Add a build lock.
8. Add staging output.
9. Validate staged DAGs.
10. Activate atomically.
11. Keep the previous generation.
12. Add rollback.
13. Add interrupted-operation recovery.
14. Add no-op detection.
15. Add project-level failure reporting.
16. Reload Dagu without losing active run history.
17. Define behavior for a project that is offline or unreadable.

Vendomat should call Devman's public renderer and reconciliation APIs. Do not
duplicate policy resolution in Vendomat.

Choose the activation mode with evidence:

- atomic activation gives one simple machine state;
- best-effort activation keeps one broken project from blocking all others.

If the implementation supports both, choose and document the default.

### Phase 4: integrate RepoMan

Add repository migration support to RepoMan.

1. Detect repositories that lack the new manifest.
2. Derive initial manifest data from current Devman options.
3. Validate the derived identity and groups.
4. Create a reviewable repository change.
5. Keep the migration idempotent.
6. Preserve local repository choices.
7. Refuse ambiguous identity or nested-checkout cases.
8. Report repositories that need a migration.
9. Support a controlled migration wave.
10. Keep each repository's result independent.
11. Never let one repository's failure erase another repository's lane.
12. Keep plane activation separate from repository mutation.

If a fleet command is needed, make the ownership explicit:

- Vendomat updates the machine plane.
- RepoMan performs repository-specific migration.
- Devman validates the resulting contract.
- No layer silently assumes ownership of the other two.

### Phase 5: dual projection and comparison

Do not switch the default after the first implementation.

1. Render through the current path.
2. Render through the new machine-plane path.
3. Compare resolved workflow identity.
4. Compare source and policy identity.
5. Compare parameters and defaults.
6. Compare trigger mappings.
7. Compare generated Dagu content.
8. Compare log and run path behavior.
9. Compare queue behavior.
10. Record every mismatch.

Add a compatibility mode. Keep it explicit. Make mismatches visible.

Do not weaken old stale-renderer protection until the new generation identity
and projection metadata prove equivalent or stronger behavior.

### Phase 6: canary activation

Use a small canary set.

Start with Devman, RepoMan, and Vendomat. Then add repositories with:

- local workflow overlays;
- multiple groups;
- cross-repository workflows;
- scheduled workflows;
- writes;
- unusual project paths;
- different Nix inputs;
- known adoption edge cases.

For every canary, verify:

- generated DAGs;
- Dagu discovery;
- queue names;
- schedules;
- run logs;
- project paths;
- task execution;
- stale detection;
- rollback;
- recovery after an interrupted render.

### Phase 7: switch the default

Switch only after the acceptance measurements pass.

1. Make the machine plane the default projection source.
2. Keep the old Nix projection behind an explicit compatibility flag.
3. Stop requiring routine consumer Devman lock updates.
4. Keep the repository task interface.
5. Keep a clear rollback to the old projection.
6. Publish migration guidance.
7. Record the cutover generation.

### Phase 8: remove obsolete fan-out

Remove the old path only after the migration has evidence.

1. Remove direct Devman runtime pins from consumer repositories.
2. Remove shell-entry projection code that the central reconciler replaces.
3. Remove duplicate resolver and renderer code.
4. Remove compatibility code only when no supported consumer needs it.
5. Keep stable manifest and task integration.
6. Keep migration and rollback tools.
7. Update all architecture and operations documentation.

## Performance design

The refactor must improve wall time and reduce state transitions.

Measure these values before and after:

1. cold plane build time;
2. warm plane build time;
3. first projection time;
4. projection time per project;
5. full-fleet staging time;
6. no-op reconciliation time;
7. shell-entry time;
8. cache reuse across different repository Nix inputs;
9. activation time;
10. rollback time;
11. interrupted-render recovery time;
12. CI setup time;
13. number of repository lock changes;
14. number of repository shell entries;
15. number of independent failure points.

Use content-addressed caching with a key that includes every input that can
change generated output:

~~~
plane digest
policy digest
manifest digest
workflow source digest
overlay digest
contract schema
~~~

Never omit an input to make the cache appear faster.
## Required tests

Build tests at four levels.

### Unit tests

Test:

- manifest parsing;
- manifest validation;
- identity rules;
- path safety;
- group resolution;
- policy resolution;
- canonical serialization;
- digest calculation;
- projection records;
- stale detection;
- no-op detection;
- structured result states;
- error classification.

### Contract tests

Test:

- every supported manifest schema;
- old repository options;
- invalid and missing fields;
- unknown groups;
- unknown policy channels;
- duplicate project identity;
- nested repository paths;
- unsupported schema;
- compatibility reporting.

### Integration tests

Test:

- Devman renderer output;
- Vendomat generation metadata;
- RepoMan manifest migration;
- Dagu validation;
- central registry update;
- atomic projection swap;
- Dagu reload;
- queue preservation;
- active run preservation;
- rollback;
- offline project behavior;
- interrupted operation recovery.

### End-to-end tests

Use temporary fixture repositories.

Prove that:

1. a machine update builds one generation;
2. multiple repositories reuse one renderer and toolchain closure;
3. unchanged projects are no-ops;
4. changed policy renders only affected projects;
5. renderer changes make every affected projection stale;
6. a failed project keeps its last valid projection;
7. an invalid DAG prevents activation;
8. rollback restores the previous generation;
9. no repository task runs during render;
10. Dagu later invokes the repository's own devenv task;
11. a migration changes only the selected repository;
12. unrelated worktree changes remain untouched.

Add failure injection for:

- renderer failure;
- policy parse failure;
- invalid manifest;
- invalid DAG;
- missing repository;
- permission failure;
- interrupted staging;
- interrupted activation;
- Dagu reload failure;
- rollback failure.

## Documentation requirements

Update documentation as the implementation changes.

At minimum, update:

- Devman architecture;
- Devman user operations;
- Vendomat plane operations;
- RepoMan migration operations;
- manifest schema;
- generation metadata;
- projection metadata;
- stale protection;
- cache rules;
- activation and rollback;
- failure states;
- compatibility mode;
- migration guide;
- troubleshooting;
- performance measurements;
- ownership boundaries.

Keep mechanism and content documentation separate.

Update the project 038 concept when implementation evidence changes a decision.
Record the reason and the measurement. Do not leave a proposed architecture that
contradicts the shipped behavior.

Add examples that show:

- a plan with no mutations;
- a successful update;
- a partial failure;
- a rollback;
- a stale project;
- a manifest migration;
- a no-op reconciliation.

## Git and worktree rules

Use raw Git in this task.

Before changing any repository:

~~~
git status --short --branch
git diff --stat
~~~

Preserve all pre-existing worktree changes. Do not use:

- git reset --hard;
- git checkout --;
- git clean;
- GitMan abandon or equivalent destructive recovery;
- broad staging commands that include unrelated files.

Stage explicit paths. Before every commit, run:

~~~
git diff --cached --check
git diff --cached --name-status
git status --short
~~~

Commit related changes in small, reviewable commits. Use a message that states
the change. Push completed commits to the current branch.

When a repository is dirty, do not assume that all changes belong to this task.
Keep unrelated edits out of the commit. If safe isolation is not possible,
stop that repository's mutation and report the exact files involved.

Do not commit:

- secrets;
- local credentials;
- generated caches;
- machine-only state;
- unreviewed generated artifacts;
- unrelated user work.

## Verification commands

Use each repository's own devenv environment.

For Devman, run at least:

~~~
devenv tasks run -v base:check
devenv tasks run -v base:test
devman doctor
~~~

For RepoMan and Vendomat, run the equivalent documented checks. Also run:

- unit tests;
- integration tests;
- contract tests;
- end-to-end fixture tests;
- Nix evaluation or flake checks;
- CLI help checks;
- plan, update, and rollback smoke tests;
- old/new projection comparison;
- performance measurements.

Run the full proof after the final integration. Do not report success from a
partial test run.
## Definition of done

Do not mark the work complete until all applicable criteria hold:

- one Vendomat command updates the machine Devman plane;
- the command builds one immutable generation;
- the generation records all relevant identities;
- the renderer is shared through the generation, not through PATH;
- every projection records the generation and source digests;
- stale output is visible and actionable;
- normal updates do not edit consumer Devman locks;
- projection does not require entering every repository shell;
- unchanged projects are no-ops;
- failed projects keep their previous valid projection;
- activation is atomic or has a documented and tested partial-failure model;
- rollback works;
- interrupted operations recover;
- repository migrations use RepoMan;
- repository migrations remain reviewable;
- RepoMan remains repository-specific;
- Vendomat remains the machine-plane owner;
- Devman remains the contract and renderer owner;
- Devman executes no repository task;
- Dagu still owns orchestration and history;
- devenv still owns task execution;
- no workflow contains a machine path;
- path and identity safety checks pass;
- old and new projection output matches during migration;
- benchmark results show a material reduction in update cost;
- all required documentation is updated;
- all relevant tests pass;
- every changed repository has a pushed commit;
- no unrelated worktree change was staged or committed.

## Working style

Start by reporting:

1. the current branch and worktree state in each repository;
2. the current update path;
3. the first measured bottlenecks;
4. the files and interfaces that define the current boundaries;
5. the staged implementation plan;
6. the first safe milestone.

Then implement the smallest complete vertical slice:

1. one manifest;
2. one generation;
3. one project adoption;
4. one rendered projection;
5. one validation;
6. one activation;
7. one rollback;
8. one proof.

Use that slice to validate the architecture before expanding to the full
repository set.

Keep the user informed at meaningful milestones. Report evidence, not intent.
When a decision remains open, choose the option that best preserves correctness,
rollback, and ownership. Record the decision in the implementation log.

At the end, report:

- what changed in each repository;
- the ownership boundary;
- the user commands;
- the migration state;
- the benchmark before and after;
- the tests run;
- the commits and pushed branches;
- known limitations;
- the next safe step.
