# Devman: Central Personal Development Environment Manager

## Purpose

`devman` is a centrally managed personal development-environment system that lets each repository gain customized local tooling, devenv configuration, scripts, and modules **without adding personal files to the repository's tracked Git state**.

The core idea is simple:

> Keep all personal development configuration in one VCS-managed `devman` repository, organize repo-specific configuration under `projects/<name>/`, and use Dotbot to project the required files into each working repository as symlinks.

This avoids nested Git repositories, duplicated configuration, manually managed symlinks, and personal files appearing in upstream project history.

---

## Goals

The system should provide:

- one central Git repository for all personal development configuration;
- reusable shared modules and profiles;
- repo-specific personal configuration;
- clean project repositories with no tracked personal files;
- automatic symlink creation and reconciliation;
- easy bootstrapping of new repositories;
- idempotent `sync` behavior;
- direct access from devenv to files in the real repository;
- minimal custom machinery.

---

## Core Architecture

```text
~/.config/devman/
├── common/
│   ├── python.nix
│   ├── agents.nix
│   ├── vcs.nix
│   └── ...
│
├── projects/
│   ├── scippy/
│   │   ├── devenv.local.nix
│   │   ├── devenv.local.yaml
│   │   └── modules/
│   │       ├── repo.nix
│   │       ├── scripts.nix
│   │       └── ...
│   │
│   ├── templateer/
│   │   ├── devenv.local.nix
│   │   └── modules/
│   │       └── scripts.nix
│   │
│   └── ...
│
├── dotbot/
│   └── generated-or-managed-config.yaml
│
└── devman/
    └── optional Python CLI
```

The actual project remains ordinary:

```text
~/Documents/Projects/scippy/
├── .git/
├── devenv.nix
├── devenv.yaml
├── src/
│
├── devenv.local.nix
│   -> ~/.config/devman/projects/scippy/devenv.local.nix
│
├── devenv.local.yaml
│   -> ~/.config/devman/projects/scippy/devenv.local.yaml
│
└── .modules
    -> ~/.config/devman/projects/scippy/modules
```

The project Git repository ignores these local projections through:

```text
.git/info/exclude
```

with entries such as:

```gitignore
/devenv.local.nix
/devenv.local.yaml
/.modules
```

No project `.gitignore` changes are required.

---

## Configuration Ownership

There are three distinct configuration layers.

### 1. Project-owned configuration

Tracked normally by the project:

```text
devenv.nix
devenv.yaml
src/
tests/
...
```

This is canonical repository configuration.

### 2. Shared personal configuration

Stored centrally:

```text
~/.config/devman/common/
```

Examples:

- standard Python tooling;
- agent tooling;
- Jujutsu helpers;
- shell utilities;
- common devenv tasks;
- common scripts;
- personal environment conventions.

These modules are reusable across many projects.

### 3. Repo-specific personal configuration

Stored centrally under:

```text
~/.config/devman/projects/<project>/
```

Examples:

```text
projects/scippy/
├── devenv.local.nix
├── devenv.local.yaml
└── modules/
    ├── repo.nix
    ├── scripts.nix
    ├── benchmarks.nix
    └── agents.nix
```

These files belong only to that project but remain part of the central personal Devman Git repository.

---

## Combining Shared and Repo-Specific Modules

A project-specific `devenv.local.nix` can import both shared and project-specific modules.

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

This gives each project a custom local environment while reusing common personal building blocks.

---

## Referencing the Real Repository

Repo-specific modules live physically under `~/.config/devman`, so they should not rely on relative paths to reach project files.

Use the devenv project root explicitly.

Example:

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

This keeps central configuration independent of where the Devman repository itself lives.

---

## Dotbot's Role

Dotbot is the filesystem projection and reconciliation engine.

It handles:

- symlink creation;
- relinking;
- directory creation;
- cleanup of stale managed links;
- idempotent repeated execution;
- dry-run support.

Dotbot should **not** own the conceptual project model.

Devman decides:

- which project is active;
- which central project directory belongs to it;
- what paths should be exposed;
- which shared modules are imported.

Dotbot simply applies that desired filesystem state.

Conceptually:

```text
Devman configuration
        │
        ▼
desired link map
        │
        ▼
      Dotbot
        │
        ▼
working repository
```

---

## Example Dotbot Mapping

Conceptually:

```yaml
- defaults:
    link:
      create: true
      relink: true

- link:
    ~/Documents/Projects/scippy/devenv.local.nix:
      path: projects/scippy/devenv.local.nix

    ~/Documents/Projects/scippy/devenv.local.yaml:
      path: projects/scippy/devenv.local.yaml

    ~/Documents/Projects/scippy/.modules:
      path: projects/scippy/modules
```

The actual config may be generated by `devman` rather than manually maintained.

---

## Bootstrap Workflow

The desired user experience:

```bash
cd ~/Documents/Projects/new-project
devman init
```

`devman init` should:

1. detect the repository root;
2. derive or ask for the project name;
3. create:

   ```text
   ~/.config/devman/projects/new-project/
   ```

4. create starter files such as:

   ```text
   devenv.local.nix
   devenv.local.yaml
   modules/
     repo.nix
     scripts.nix
   ```

5. add local exclusions to:

   ```text
   .git/info/exclude
   ```

6. generate or update the Dotbot mapping;
7. run Dotbot;
8. verify that the links resolve correctly.

The project remains clean from Git's perspective.

---

## Normal Workflow

Typical commands:

```bash
devman init
devman sync
devman sync --dry-run
devman status
devman doctor
```

Possible future commands:

```bash
devman module add agents
devman module remove agents

devman profile add python
devman profile remove python
```

The minimal MVP only needs:

```text
init
sync
status
```

---

## `devman sync`

`sync` should be safe and idempotent.

Its job:

1. locate the current project;
2. resolve its central configuration;
3. ensure `.git/info/exclude` contains the required entries;
4. generate the desired Dotbot link configuration;
5. run Dotbot;
6. report inconsistencies.

Repeated execution should converge on the same state.

---

## `devman status`

Example:

```text
Project
  scippy
  ~/Documents/Projects/scippy

Central config
  ~/.config/devman/projects/scippy

Managed links
  ✓ devenv.local.nix
  ✓ devenv.local.yaml
  ✓ .modules

Git isolation
  ✓ devenv.local.nix excluded
  ✓ devenv.local.yaml excluded
  ✓ .modules excluded

Devman repository
  2 modified files
```

This provides visibility without requiring the user to inspect symlinks manually.

---

## Version Control Model

Only two ordinary Git repositories are involved:

### Project repository

```text
~/Documents/Projects/scippy/.git
```

Contains project-owned files only.

### Devman repository

```text
~/.config/devman/.git
```

Contains:

- shared modules;
- profiles;
- Devman source;
- Dotbot configuration;
- all repo-specific personal development configuration.

Example:

```bash
cd ~/.config/devman
git add .
git commit -m "Update scippy development tasks"
```

This versions personal project configuration without touching the project's upstream history.

---

## Why This Model

This design avoids several unnecessary complexities:

- no nested Git repositories;
- no `--separate-git-dir`;
- no per-repo personal VCS;
- no custom symlink implementation;
- no manually maintained absolute symlinks;
- no project `.gitignore` changes;
- no need to duplicate common configuration;
- no requirement for upstream projects to know Devman exists.

The central Devman tree becomes the single source of truth for personal development configuration.

---

## Design Principle

The clean mental model is:

```text
Project repository
    owns the project

Devman repository
    owns your personal development experience

Dotbot
    projects selected Devman state into the working tree

.git/info/exclude
    prevents that projected state from affecting project Git history
```

Or, more compactly:

> **Devman stores it. Dotbot projects it. Git ignores it. Devenv uses it.**

---

## MVP

The initial implementation can remain very small.

### Central repository

```text
~/.config/devman/
├── common/
├── projects/
└── devman/
```

### Devman CLI

Python CLI with:

```text
devman init
devman sync
devman status
```

### Dependencies

- Python
- Pydantic for configuration models
- Dotbot for link reconciliation
- Git
- devenv

No database or daemon is required.

---

## Future Extensions

The architecture leaves room for:

- named reusable profiles;
- composable personal module sets;
- project discovery;
- templates for new project configurations;
- automatic project renaming/migration;
- Dotbot plugins;
- agent-specific configuration;
- Atuin integration;
- Codex/Claude-specific local configuration;
- generated development tasks;
- machine-specific overrides;
- validation and diagnostics.

These can be added without changing the fundamental layout.

---

## Final Architecture

```text
                      ~/.config/devman
                             │
              ┌──────────────┴──────────────┐
              │                             │
           common/                      projects/
       reusable modules             repo-specific config
              │                             │
              └──────────────┬──────────────┘
                             │
                           devman
                       resolves desired
                            state
                             │
                             ▼
                           Dotbot
                             │
                       creates symlinks
                             │
                             ▼
                 ~/Documents/Projects/foo
                             │
                ┌────────────┼─────────────┐
                │            │             │
       devenv.local.nix  devenv.local.yaml .modules
                │            │             │
                └────────────┴─────────────┘
                             │
                      ignored through
                     .git/info/exclude
                             │
                             ▼
                    project Git remains
                         completely clean
```

This is the recommended final concept.
