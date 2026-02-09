# Devman — Core Concepts (CORE_CONCEPTS.md)

This document defines the **shared mental model** for `devman`.

If you’re contributing code, templates, or docs: treat this file as the **conceptual source of truth**.

---

## What is Devman?

Devman is a **Terminal Manager**: a CLI-driven way to run project workflows consistently, record results, and manage reusable “template components” across many projects.

Devman does **not** replace your project’s tools. Instead, it:

1. **Runs tasks via `just`** (Justfile recipes) in a project context.
2. Stores **logs, metadata, and artifacts** for each run in a central location.
3. Manages **templates** (reusable scaffolds/components) and **instances** (project-specific realizations).
4. Makes project repos consume instance material via **symlinks**.
5. Captures **`jj` workspace context** when available.

---

## First principles

### 0) Experimental, modular, devenv.sh-first development
Devman is not a conservative wrapper around existing project scripts. It is an experimental control plane for modular development systems:
- Treat environment definition (`devenv.sh`) as a first-class part of the project architecture.
- Treat system/tooling/runtime modules and app/code modules as co-evolving components.
- Optimize for safe iteration speed and replaceability of modules over rigid one-off setup.
- Avoid agent behaviors that preserve legacy assumptions like “the system is fixed; only app code changes.”

### 1) Just-first execution
All task execution is performed by invoking **`just`**:
- Task == `just <recipe> [args…]`
- Parameters flow through `just` and/or environment variables.
- Devman avoids ad-hoc script execution mechanisms.

### 2) The store is authoritative
Devman has a central **Devman Store** that owns:
- Template source-of-truth
- Instance configuration and generated state
- Run history, logs, artifacts

Project repos are consumers that **link into** the store.

### 3) Projects consume instances via symlinks
A project repo typically contains a `.devman/` directory that is actually a **symlink**:

```
<PROJECT_REPO>/.devman  ->  <DEV_MAN_STORE>/instances/<template>/<project_slug>/.devman
```

This keeps run history and instance state out of the repo while still making it accessible.

### 4) Runs are recorded, not ephemeral
Every run produces:
- stdout/stderr logs
- exit status
- metadata (time, command, context)
- optional artifacts

The goal is reproducibility and debuggability.

### 5) `jj` integration is best-effort
Devman should work without `jj`, but when `jj` is present it should capture enough workspace context to relate runs to a working-copy state.

---

## Glossary

- **Devman Store**: central directory containing templates and instances.
- **Template**: reusable, parameterizable project “component library” (scaffolding + conventions).
- **Instance**: a materialized template for a specific project (project_slug) with its own `.devman` config and run history.
- **Project repo**: the code repository the user works in (often a `jj` workspace working copy).
- **Symlink plan**: rules for linking instance material into a repo (e.g., `.devman` plus optional extra links).
- **Run**: an execution of a `just` recipe (or “simulate”), captured with logs/metadata.
- **Artifact**: files produced/declared by a run that should be preserved.

---

## Canonical layout (conceptual)

### Devman Store
```
<DEV_MAN_STORE>/
  templates/
    <template_name>/
      .devman/
        templates/
          ... template payload ...
        manifest.toml

  instances/
    <template_name>/
      <project_slug>/
        .devman/
          instance.toml
          links.toml
          runs/
            <run_id>/
              meta.json
              stdout.log
              stderr.log
              artifacts/
                ...
```

### Project repo
```
<PROJECT_REPO>/
  .devman/     -> symlink into store instance
  Justfile     (required for task execution)
  ... normal project files ...
```

---

## Template design: “component libraries”

Templates are intended to be **composable building blocks** rather than monolithic project generators.

A good template component library entry:
- Encodes conventions (folders, configs) and repeatable tasks (`just` recipes)
- Is safe by default (supports simulate/dry-run behavior)
- Documents required inputs (env vars, config files)
- Provides a minimal “hello world” path from attach → run

### Template payload guidelines
- Prefer small, composable files rather than a huge one-off scaffold.
- Prefer declarative config over imperative scripts.
- If imperative logic is needed, expose it through `just` recipes (and keep them readable).

---

## Instance behavior

An instance binds:
- Template identity (`template_name`, version if applicable)
- Project identity (`project_slug`)
- Repo path / working copy context
- Link plan (symlinks into repo)
- Run history

Instances should be:
- **Idempotent** to create and re-link
- **Safe** to apply to a repo (no overwriting real directories without explicit force)
- **Portable** across machines if paths are designed carefully (use relative paths where possible; store absolute paths only when necessary)

---

## Symlink semantics

The essential behavior:
- `.devman` in the repo is a symlink into the instance `.devman` directory.
- Additional links are possible, declared by a link plan.

A link plan should support:
- Mapping a directory or file from instance → repo
- Detecting drift and broken links
- Refusing to overwrite non-link paths unless forced

---

## Run model

### What is a run?
A run is executing `just <recipe>` in the project repo context, with:
- Instance env injected
- Optional user overrides
- Optional `DEV_MAN_SIMULATE=1` for simulate mode
- Captured logs + metadata in the store

### Required run outputs
Each run should create a run directory containing at least:
- `stdout.log`
- `stderr.log`
- `meta.json` (structured metadata)
- `artifacts/` (optional)

### Artifact capture (recommended patterns)
One of:
1. **Declared output directory**: recipes write to `.devman/out/` (or similar) which devman copies into `artifacts/`
2. **Recipe-reported artifacts**: recipes print markers like `DEV_MAN_ARTIFACT: <path>` that devman collects

---

## `jj` workspace integration

When `jj` is present, capture (best-effort):
- `jj root`
- current working-copy state (e.g., rev `@`)
- any stable identifiers needed to relate a run to the workspace context

Devman must remain functional without `jj` (treat repo as a plain directory).

---

## Documentation expectations

Any change that affects how templates or instances behave should update:
- this document (if core concepts shift)
- template-level docs for behavior/inputs
- examples or fixtures that demonstrate the intended flow

---

## Design constraints (non-negotiable)

- **Just-first** task execution
- **Store-owned** state and run history
- **Symlink-based** consumption by repos
- **Idempotent** operations
- **Safe by default**, especially around destructive actions
- **Testable** with container-based runs where feasible
