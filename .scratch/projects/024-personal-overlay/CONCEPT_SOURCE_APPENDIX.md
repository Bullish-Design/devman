# Appendix: Copier Integration and Boundaries in Devman

## Purpose

Copier provides the **template-generation and template-evolution layer** inside Devman.

It does not replace Devman, Dotbot, devenv, or Git isolation. Its role is narrowly defined:

> **Copier generates and updates the canonical per-project personal configuration stored inside the central Devman repository.**

The resulting files are then projected into the actual working repository by Dotbot and consumed by devenv.

---

## Architectural Position

```text
                    Devman
                      │
             project orchestration
                      │
          ┌───────────┴───────────┐
          │                       │
        Copier                  Dotbot
          │                       │
   generate/update            project links
 personal project config      into real repo
          │                       │
          ▼                       ▼
~/.config/devman/         ~/Documents/Projects/
projects/<project>/          <project>/
          │                       │
          └──────────┬────────────┘
                     ▼
                   devenv
```

The high-level rule is:

```text
Copier creates state.
Dotbot projects state.
devenv executes state.
Devman orchestrates everything.
Git ignores the projection.
```

---

## Primary Responsibility

Copier answers:

> What should the canonical personal development configuration for this project contain?

Examples include generating:

- `devenv.local.nix`
- `devenv.local.yaml`
- project-specific Nix modules
- personal task definitions
- script modules
- agent configuration
- project-local development conventions
- metadata required by Devman
- Copier answer state

Copier should operate only inside:

```text
~/.config/devman/projects/<project>/
```

It should not directly manage the actual upstream project repository.

---

# Directory Model

## Copier Template

```text
~/.config/devman/
├── templates/
│   └── project/
│       ├── copier.yml
│       │
│       ├── devenv.local.nix.jinja
│       ├── devenv.local.yaml.jinja
│       │
│       └── modules/
│           ├── repo.nix.jinja
│           ├── scripts.nix.jinja
│           ├── agents.nix.jinja
│           └── ...
│
├── common/
├── projects/
└── devman/
```

---

## Generated Per-Project State

For a project named `scippy`:

```text
~/.config/devman/projects/scippy/
├── .copier-answers.yml
├── devenv.local.nix
├── devenv.local.yaml
│
└── modules/
    ├── repo.nix
    ├── scripts.nix
    ├── agents.nix
    └── ...
```

This directory is canonical and version-controlled by the central Devman Git repository.

---

## Project Projection

Dotbot exposes selected paths into:

```text
~/Documents/Projects/scippy/
├── devenv.local.nix
│   -> ~/.config/devman/projects/scippy/devenv.local.nix
│
├── devenv.local.yaml
│   -> ~/.config/devman/projects/scippy/devenv.local.yaml
│
└── .modules
    -> ~/.config/devman/projects/scippy/modules
```

These projected paths are excluded through:

```text
.git/info/exclude
```

For example:

```gitignore
/devenv.local.nix
/devenv.local.yaml
/.modules
```

The upstream repository therefore remains unaware of Devman.

---

# Responsibility Boundaries

## Devman

Devman owns the domain model and orchestration.

Responsibilities:

- detect the active repository;
- assign its Devman project identity;
- determine the central project directory;
- select templates/profiles/features;
- invoke Copier;
- invoke Dotbot;
- maintain Git-local exclusions;
- validate final state;
- expose the user-facing CLI.

Devman answers:

> What should happen for this repository?

---

## Copier

Copier owns templated file generation and evolution.

Responsibilities:

- ask or accept project configuration values;
- render Devman project files;
- retain template answers;
- regenerate/update projects when the template evolves;
- preserve project-specific generated configuration where possible.

Copier answers:

> What files should exist in the canonical Devman project configuration?

Copier does **not** own symlink reconciliation or repository detection.

---

## Dotbot

Dotbot owns filesystem projection.

Responsibilities:

- create symlinks;
- relink changed targets;
- create required directories;
- reconcile the desired projection;
- support dry runs;
- clean stale managed links where appropriate.

Dotbot answers:

> How do these canonical Devman files appear inside the actual repository?

Dotbot does not generate the canonical configuration itself.

---

## devenv

devenv consumes the projected configuration.

Responsibilities include:

- packages;
- environment variables;
- scripts;
- tasks;
- processes;
- services;
- shell configuration;
- Nix module composition.

devenv answers:

> What development environment should be activated?

---

## Git

The project Git repository owns only project-authorized content.

`.git/info/exclude` establishes the local isolation boundary for personal projections.

The central Devman Git repository versions:

- templates;
- shared modules;
- Devman source;
- per-project personal configuration;
- Copier answer state.

---

# Lifecycle

## `devman init`

For a new or existing project:

```bash
cd ~/Documents/Projects/scippy
devman init
```

Conceptual flow:

```text
detect project root
       │
       ▼
derive project identity
       │
       ▼
create ~/.config/devman/projects/scippy
       │
       ▼
run Copier template
       │
       ▼
generate canonical personal config
       │
       ▼
configure .git/info/exclude
       │
       ▼
run Dotbot
       │
       ▼
verify symlinks + devenv state
```

Copier is responsible only for the generation stage.

---

# Example Copier Inputs

A project template might capture information such as:

```yaml
project_name: scippy

language:
  type: str
  default: python

use_agents:
  type: bool
  default: true

use_scip:
  type: bool
  default: false

use_benchmarks:
  type: bool
  default: false
```

Devman may provide these answers itself rather than requiring interactive prompts.

For example:

```text
devman init --profile python --module agents --module scip
```

can be translated into Copier data programmatically.

This keeps the Devman CLI as the primary user interface.

---

# Copier as an Internal Library

Copier should preferably be invoked through its Python API from Devman.

Conceptually:

```python
from copier import run_copy

run_copy(
    src_path=template_path,
    dst_path=project_config_path,
    data=answers,
)
```

Benefits:

- no parsing of subprocess output;
- direct exception handling;
- structured integration with Devman's Pydantic models;
- easier testing;
- Devman remains the visible user-facing interface.

Copier's CLI remains useful for debugging templates manually, but should not be the main UX once Devman exists.

---

# Devman Configuration Model

Devman should own typed project configuration independently of Copier.

For example:

```python
from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    name: str
    profile: str = "base"
    modules: list[str] = Field(default_factory=list)
```

This model can be translated into Copier answers.

The architecture should therefore remain:

```text
Devman Pydantic model
        │
        ▼
Copier answer data
        │
        ▼
generated files
```

Copier's answer file should not become the primary application-domain model.

---

# Template Evolution

This is the strongest reason to include Copier.

Suppose Devman originally creates:

```text
modules/
├── repo.nix
└── scripts.nix
```

Later the standard evolves to:

```text
modules/
├── repo.nix
├── scripts.nix
├── exec.nix
└── agents.nix
```

Without Copier, Devman would need its own migration system.

With Copier:

```text
template v1
   │
   ├── project A
   ├── project B
   └── project C

template evolves

template v2
   │
   ├── update A
   ├── update B
   └── update C
```

Devman can expose this as:

```bash
devman update
```

or:

```bash
devman update --all
```

Internally, Copier handles template regeneration/update logic.

---

# `devman update`

Conceptual responsibilities:

```text
1. Locate central project configuration.
2. Determine the Copier template/version.
3. Run Copier update.
4. Validate generated configuration.
5. Run Dotbot sync.
6. Validate projected links.
```

This keeps migration of personal project environments separate from ordinary project Git history.

---

# `devman sync` vs `devman update`

These commands should remain distinct.

## `devman sync`

Reconcile projections only.

```text
canonical Devman config
        │
        ▼
      Dotbot
        │
        ▼
repository symlinks
```

Use when:

- a symlink was deleted;
- a repository moved;
- Devman configuration changed manually;
- local projection state is inconsistent.

It should not regenerate template-owned files.

---

## `devman update`

Evolve canonical project configuration from the Copier template.

```text
Copier template
      │
      ▼
central project configuration
      │
      ▼
Dotbot sync
```

Use when:

- the Devman template changed;
- new standard modules were introduced;
- generated structure should be migrated.

This distinction prevents surprising rewrites during ordinary synchronization.

---

# Editing Project-Specific Files

Generated project-specific files should remain normal editable files inside:

```text
~/.config/devman/projects/<project>/
```

For example:

```text
projects/scippy/modules/scripts.nix
```

may contain highly project-specific commands:

```nix
{ config, ... }:

{
  scripts.build-index.exec = ''
    python ${config.devenv.root}/tools/build_index.py
  '';

  tasks."dev:benchmark".exec = ''
    cd ${config.devenv.root}
    python benchmarks/run.py
  '';
}
```

These files are intentionally personal but repo-specific.

They should be committed to the Devman Git repository.

---

# Template Ownership Rules

Not every file needs to remain fully template-owned.

A useful distinction is:

## Strongly template-owned

Examples:

- structural entrypoints;
- standard generated headers;
- base imports;
- metadata files.

These are expected to evolve through Copier.

## User-owned after creation

Examples:

- `modules/scripts.nix`
- `modules/repo.nix`
- custom agent workflows
- project-specific task implementations

These may be initially scaffolded by Copier but subsequently edited freely.

The template should minimize unnecessary regeneration pressure on heavily customized files.

---

# Shared Modules vs Generated Modules

Shared reusable functionality belongs in:

```text
~/.config/devman/common/
```

and should generally be imported rather than copied.

Example:

```nix
{
  imports = [
    ../../common/python.nix
    ../../common/agents.nix

    ./modules/repo.nix
    ./modules/scripts.nix
  ];
}
```

Copier should generate the composition layer, not duplicate common module implementations into every project.

This keeps shared functionality centralized.

---

# Repository Path Access

Because project-specific configuration lives under Devman rather than physically inside the working repository, it should access project files through explicit devenv root information.

Example:

```nix
{ config, ... }:

{
  scripts.codegen.exec = ''
    python ${config.devenv.root}/tools/codegen.py
  '';
}
```

Avoid assumptions such as:

```nix
../../../actual-project/tools/codegen.py
```

The canonical Devman tree and project tree should remain location-independent.

---

# What Copier Must Not Do

Copier should **not**:

- generate personal files directly into the upstream repository;
- place `.copier-answers.yml` in the upstream repository;
- modify project `.gitignore`;
- manage Dotbot symlinks;
- decide which repository is active;
- replace Devman's project registry/domain model;
- manage devenv activation;
- become the user-facing command surface.

These boundaries preserve the clean Devman architecture.

---

# Failure Isolation

Each component should fail within its own responsibility.

Examples:

### Copier failure

```text
Template render/update failed.
```

No Dotbot projection should occur until canonical configuration is valid.

### Dotbot failure

```text
Canonical configuration exists,
but repository projection failed.
```

No need to regenerate with Copier.

### devenv failure

```text
Projection succeeded,
but generated/imported devenv configuration is invalid.
```

Devman reports configuration validation separately.

This separation makes diagnosis straightforward.

---

# Recommended CLI Surface

```bash
devman init
devman update
devman sync
devman status
devman doctor
```

Meaning:

```text
init
  Bootstrap central project config with Copier,
  then project it with Dotbot.

update
  Evolve central project config using Copier,
  then sync projections.

sync
  Reconcile Dotbot projections only.

status
  Show central config, template state,
  links, exclusions, and repository identity.

doctor
  Validate the entire chain.
```

---

# Final Boundary Model

```text
                    USER
                     │
                     ▼
                   Devman
            orchestration + models
                     │
           ┌─────────┴─────────┐
           │                   │
           ▼                   ▼
        Copier               Dotbot
   generate/evolve        project/reconcile
           │                   │
           ▼                   ▼
 ~/.config/devman/      actual repository
 projects/<repo>/         local symlinks
           │                   │
           └─────────┬─────────┘
                     ▼
                   devenv
                     │
                     ▼
            development workflow


Project Git:
    ignores Devman projections

Devman Git:
    versions personal configuration
```

---

## Core Principle

> **Copier owns how a Devman project configuration is created and evolved, but not where it is projected or how it is executed.**

That boundary keeps Copier useful without allowing it to become the architecture itself.

The resulting division is:

> **Devman orchestrates. Copier generates. Dotbot projects. devenv executes. Git isolates.**
