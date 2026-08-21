# Dagu + devenv Automation Flake Concept Guide

## Overview

The recommended architecture is a **single shared automation flake** that defines the contract between:

- the machine-level Dagu control plane,
- repo-level devenv environments,
- shared workflow conventions,
- automatic project registration,
- and future higher-level development automation.

The core model is:

```text
                   dagu-automation flake
                            │
              ┌─────────────┴─────────────┐
              │                           │
      nixosModules.default        devenvModules.default
              │                           │
              ▼                           ▼
       machine-level Dagu            repositories
              │                           │
              │                    standard tasks
              │                    default workflows
              │                    project metadata
              │                    local overrides
              │                           │
              └─────────────┬─────────────┘
                            ▼
                    workflow registry
                            │
                            ▼
                          Dagu
                            │
                            ▼
                         devenv
                            │
                            ▼
                    actual development tools
```

The key principles are:

> **Dagu orchestrates. devenv executes. The shared flake defines the contract between them.**

and:

> **Use convention + override, not copied workflow boilerplate.**

---

# 1. One Shared Automation Flake

Create a dedicated repository such as:

```text
dagu-automation/
├── flake.nix
├── nix/
│   ├── nixos-module.nix
│   └── devenv-module.nix
├── dagu/
│   ├── workflows/
│   └── config/
├── packages/
│   └── devflow/
└── lib/
```

The flake should expose several interfaces:

```text
outputs
│
├── nixosModules.default
│      machine-level Dagu control plane
│
├── devenvModules.default
│      repo-level integration
│
├── packages
│      helper CLI / registration tooling
│
├── lib
│      shared Nix helpers and schemas
│
└── checks
       integration tests for the automation system
```

The same flake version defines both the infrastructure and repo-facing behavior.

This prevents drift between:

- Dagu configuration,
- workflow naming,
- registry layout,
- resource classes,
- default workflows,
- metadata schemas,
- and repo integration.

---

# 2. Machine-Level Responsibility

The NixOS configuration should import the automation flake directly.

Conceptually:

```nix
inputs.dagu-automation.url = "github:example/dagu-automation";
```

and:

```nix
imports = [
  inputs.dagu-automation.nixosModules.default
];
```

The machine-level module owns the **single Dagu instance for the user or machine**.

It should manage:

- Dagu installation,
- Dagu service lifecycle,
- Dagu configuration,
- workflow discovery,
- workflow registry paths,
- queues,
- concurrency limits,
- resource classes,
- logs and state paths,
- retention policy,
- secrets/environment injection,
- optional worker configuration.

The NixOS module should remain generic infrastructure.

It should know:

```text
where the registry lives
where Dagu state lives
which resource queues exist
how Dagu is configured
how the service starts
```

It should not know:

```text
which project uses pytest
which project has a benchmark
which repo needs code generation
which application has an integration-test workflow
```

Those are repo-level concerns.

---

# 3. Repo-Level Responsibility

Each devenv-managed repository imports the same automation flake.

Conceptually:

```text
project/
├── devenv.yaml
├── devenv.nix
├── src/
├── tests/
└── optional repo-specific automation
```

The shared devenv module provides:

- default task conventions,
- default Dagu workflows,
- standard project metadata,
- automatic registration,
- resource-class defaults,
- common workflow naming,
- repo-level override points.

A project should need very little boilerplate.

Conceptually:

```nix
automation = {
  enable = true;

  workflows = {
    check.enable = true;
    validate.enable = true;
    benchmark.enable = true;
  };
};
```

The project still defines its actual primitive tasks.

For example:

```nix
tasks."lint".exec = "ruff check .";
tasks."typecheck".exec = "basedpyright";
tasks."test".exec = "pytest";
```

The shared automation layer then composes those tasks into higher-level workflows.

---

# 4. Dagu Orchestrates; devenv Executes

This responsibility boundary should remain strict.

## devenv owns primitive task implementation

Examples:

```text
format
lint
typecheck
test
integration-test
build
codegen
benchmark
```

These tasks should be the canonical implementation used by:

- Dagu,
- local developers,
- hooks,
- CI.

Prefer:

```text
devenv tasks run test
```

everywhere.

Avoid:

```text
Dagu:  pytest
CI:    uv run pytest
hook:  devenv shell -- pytest
```

The same logical task should have one implementation.

## Dagu owns workflow composition

Examples:

```text
check
validate
full-test
review
benchmark campaign
release
nightly validation
cross-repo integration
agent workflows
```

Example:

```text
devenv tasks:
    lint
    typecheck
    test

Dagu workflow:
    lint ───────┐
                ├── validate
    typecheck ──┤
                │
    test ───────┘
```

Do not duplicate the same dependency graph in both Dagu and devenv.

Use this rule:

```text
repo-internal execution semantics → devenv
larger operational orchestration → Dagu
```

---

# 5. Convention + Override

The shared library should define defaults without forcing every repository into the same shape.

A useful merge hierarchy is:

```text
global defaults
      ↓
ecosystem/language defaults
      ↓
project overrides
      ↓
local machine overrides
```

Example:

```text
global:
    check
    validate
    full-test

Python defaults:
    lint
    typecheck
    pytest

project:
    integration-test
    benchmark

machine:
    gpu queue available
    heavy concurrency = 1
```

The default workflow library should stay intentionally small at first.

Recommended initial workflows:

```text
check
validate
full-test
```

Possible later additions:

```text
review
benchmark
release
maintenance
agent
```

Repo-specific workflows can extend or replace defaults where needed.

---

# 6. Automatic Registration

Projects should not manually copy workflows into the central Dagu configuration.

The devenv module should automatically register enabled projects with a well-known machine-level registry.

Conceptually:

```text
repo
  ↓
shared devenv module
  ↓
registration
  ↓
canonical workflow registry
  ↓
Dagu discovery
```

A possible registry layout:

```text
~/.local/share/dev-dagu/
├── projects/
│   ├── pyjutsu/
│   │   ├── metadata.json
│   │   └── workflows/
│   │       ├── check.yaml
│   │       └── validate.yaml
│   │
│   ├── scippy/
│   └── testee/
│
└── runs/
```

The repository remains canonical.

The registry is a machine-local projection of the repo's automation configuration.

This removes the need for Dagu itself to understand the developer's project-directory layout.

---

# 7. Project Identity and Paths

Do not hard-code developer-specific absolute paths into committed workflows.

Avoid:

```yaml
working_dir: /home/user/Documents/Projects/Pyjutsu
```

Prefer a project identity:

```text
project = pyjutsu
```

with machine-level resolution:

```text
pyjutsu → /actual/path/to/Pyjutsu
```

The automatic registry can provide that mapping.

This supports:

- moving repos,
- multiple machines,
- temporary workspaces,
- jj workspaces,
- cross-repo automation,
- future distributed workers.

---

# 8. Standard Workflow Naming

Standardize names early so tooling can make assumptions.

Suggested devenv task names:

```text
format
lint
typecheck
test
integration-test
build
codegen
benchmark
```

Suggested Dagu workflow names:

```text
check
validate
full-test
review
benchmark
release
maintenance
```

This enables generic tooling such as:

```text
devflow run check
devflow run validate
devflow run benchmark
```

without each repository inventing a different vocabulary.

---

# 9. Resource Classes

Define a machine-wide resource vocabulary in the shared flake.

Recommended initial classes:

```text
light
normal
heavy
gpu
exclusive
```

Example semantics:

## light
- lint
- formatting
- static analysis

## normal
- unit tests
- ordinary builds

## heavy
- integration suites
- large compiles
- CPU-heavy benchmarks

## gpu
- inference
- model evaluation
- GPU benchmarks

## exclusive
- hardware access
- destructive database tests
- workloads that must run alone

The NixOS module maps these conventions onto Dagu queues and concurrency limits.

The repo simply declares intent.

Example:

```text
benchmark → gpu
integration-test → heavy
lint → light
```

The project should not need to know the machine's exact concurrency configuration.

---

# 10. Workspace vs Snapshot Workflows

This distinction should become a first-class concept.

## Workspace workflows

Operate directly on the active working directory.

Examples:

- lint
- format
- quick tests
- interactive inspection

```text
active checkout
      ↓
    Dagu
      ↓
   devenv
```

These intentionally operate on mutable local state.

## Snapshot workflows

Operate against a specific immutable revision.

Examples:

- full tests
- benchmarks
- releases
- scheduled workflows
- agent jobs
- expensive experiments

```text
project
   +
jj commit ID
      ↓
isolated workspace
      ↓
   devenv
      ↓
    Dagu task execution
```

This prevents a long-running workflow from observing unrelated source changes after it starts.

---

# 11. jj-Aware Execution

Commit-addressed execution should be designed for early, even if implemented later.

A durable workflow run should eventually capture:

```text
project
jj commit ID
workflow
parameters
resource class
environment identity
run ID
```

Snapshot execution then becomes:

```text
revision
   ↓
temporary jj workspace
   ↓
devenv environment
   ↓
Dagu workflow
   ↓
artifacts + result metadata
```

This is particularly important for:

- benchmarks,
- autonomous agents,
- scheduled jobs,
- revision comparisons,
- reproducible failures,
- cross-project validation.

---

# 12. Reactive Triggers

Dagu should orchestrate work, not detect every possible event itself.

Use specialized tools for detection.

Example:

```text
filesystem change
      ↓
  watchexec
      ↓
trigger workflow
      ↓
    Dagu
```

and:

```text
commit / push / PR event
        ↓
       hook
        ↓
      Dagu
```

Responsibility:

```text
watchexec / hook:
    detect that something happened

Dagu:
    decide and orchestrate what happens next

devenv:
    execute the repo tasks
```

This keeps each layer simple.

---

# 13. Artifacts and Run State

Generated outputs should not be scattered throughout source trees.

Use predictable per-run storage.

Example:

```text
~/.local/share/dev-dagu/
└── runs/
    └── <project>/
        └── <run-id>/
            ├── logs/
            ├── artifacts/
            ├── reports/
            └── metadata.json
```

Typical artifacts:

- pytest reports
- coverage data
- benchmark output
- profiling traces
- generated patches
- agent reports
- build metadata

Treat Dagu state as operational, not canonical.

Canonical:

```text
Git / jj history
repo automation definitions
devenv definitions
shared automation flake
```

Operational/reconstructable:

```text
Dagu run history
logs
queues
temporary workspaces
ordinary artifacts
```

Rebuilding the Dagu service should be inconvenient, not catastrophic.

---

# 14. Secrets

Do not commit secrets into Dagu workflows.

Workflows should reference symbolic names:

```text
GITHUB_TOKEN
HF_TOKEN
DATABASE_URL
```

The machine-level module or existing secret-management system should inject them.

Conceptually:

```text
Nix / secret manager
        ↓
      Dagu
        ↓
     devenv
        ↓
      task
```

The repo declares dependency on a secret, not the secret itself.

---

# 15. Cross-Repository Workflows

A single central Dagu instance enables workflows that should not belong to one arbitrary repository.

Example:

```text
                Dagu
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
   library A   library B   application
       │          │          │
     devenv     devenv     devenv
       └──────────┼──────────┘
                  ▼
          integration workflow
```

Potential uses:

- validating dependent libraries together,
- synchronized releases,
- nightly dev-stack validation,
- cross-repo benchmarks,
- coordinated migrations,
- agent workflows spanning multiple projects.

These workflows can live in the shared automation repository or a dedicated machine-level automation namespace.

---

# 16. Helper CLI

The flake can eventually package a small CLI.

Possible interface:

```text
devflow list
devflow register
devflow unregister
devflow run check
devflow run validate
devflow status
```

Its responsibilities could include:

- project discovery,
- registry updates,
- workflow invocation,
- source-revision selection,
- workspace creation,
- run metadata,
- future higher-level automation.

Do not build this too early.

First prove the conventions manually.

---

# 17. Future Typed Configuration

Once the system has stabilized, the repo-facing configuration can gain a typed representation.

For example:

```python
from pydantic import BaseModel


class ProjectAutomation(BaseModel):
    name: str
    default_workflow: str
    workflows: list[str]
    resource_class: str
```

A typed layer could later:

- validate project metadata,
- generate Dagu definitions,
- generate registry entries,
- expose a stable CLI/API,
- build cross-project workflows,
- support agent automation.

The important early investment is not code generation.

It is defining conventions that can later be represented cleanly.

---

# 18. Recommended Rollout

## Stage 1 — Shared Flake Foundation

Build:

```text
dagu-automation flake
├── nixosModules.default
├── devenvModules.default
└── minimal default workflows
```

Enable:

```text
one Dagu service
+
repo imports
+
devenv tasks
+
manual/simple registration
```

Initial workflows:

```text
check
validate
full-test
```

## Stage 2 — Convention + Registration

Add:

```text
automatic project registration
standard workflow names
resource classes
queues/concurrency
project metadata
artifact conventions
```

At this stage the shared flake becomes the canonical development-automation contract.

## Stage 3 — Reactive Automation

Add:

```text
watchexec triggers
VCS hooks
standard run metadata
retention policies
helper CLI
```

Keep event detection separate from orchestration.

## Stage 4 — Reproducible Snapshot Execution

Add:

```text
jj-aware isolated workspaces
commit-addressed workflows
revision-aware artifacts
cross-repo workflows
```

Long-running work no longer depends on a mutable active checkout.

## Stage 5 — Agentic / Higher-Level Automation

Add only once the lower layers are stable:

```text
agent workflows
automated review
benchmark campaigns
workflow generation
typed configuration
policy/gating
cross-project planning
```

The same architecture should support these without changing the responsibility boundaries.

---

# Final Architecture

```text
                      dagu-automation flake
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
         NixOS module                 devenv module
                 │                           │
                 ▼                           ▼
          Dagu installation              repositories
          service/config                 standard tasks
          queues/resources               default workflows
          registry paths                 project overrides
                 │                           │
                 └─────────────┬─────────────┘
                               ▼
                       project registry
                               │
                               ▼
                             Dagu
                               │
                    workflow orchestration
                               │
                               ▼
                            devenv
                               │
                               ▼
                    repo-specific commands
```

Supporting layers:

```text
jj
    → immutable source identity and isolated workspaces

watchexec / hooks
    → event detection and workflow triggering

CI
    → authoritative remote validation

Nix / secrets
    → machine-level configuration and credentials
```

---

# Core Principles

1. **Use one central Dagu instance per machine/user.**
2. **Package the entire integration as one shared Nix flake.**
3. **Expose separate NixOS and devenv interfaces from the same flake.**
4. **Let the NixOS module own generic machine-level Dagu infrastructure.**
5. **Let repo-level devenv modules own project semantics.**
6. **Dagu orchestrates; devenv executes.**
7. **Use convention + override rather than copied workflow files.**
8. **Automatically register participating repositories.**
9. **Keep project identity separate from absolute filesystem paths.**
10. **Standardize workflow names and resource classes early.**
11. **Do not duplicate task graphs between Dagu and devenv.**
12. **Separate mutable workspace workflows from immutable snapshot workflows.**
13. **Use jj revision identity for durable or long-running execution.**
14. **Use hooks/watchers for detection and Dagu for orchestration.**
15. **Treat Dagu state as operational and reconstructable.**
16. **Keep secrets outside committed workflow definitions.**
17. **Delay custom typed abstractions until real usage proves the conventions.**

The desired end state is a **single reusable development-automation platform** that is installed once through NixOS, imported into every devenv-managed project, automatically discovers/registers those projects, and gives them a consistent orchestration vocabulary without taking ownership away from the repositories themselves.
