# TEMPLATE_REPO_SETUP Skill

## Goal
Use this skill when you need to either:
1. Create a new **Devman template module library** (especially for `devenv.nix`-oriented workflows), or
2. Retrofit an existing project repo so it matches the Devman architecture.

This skill is based on how Devman currently structures seed templates and project layout for `devenv.nix`.

---

## Core mental model (must keep)
- **Devenv-first:** environment and software definitions evolve together.
- **Just-first:** execution surface is `just` recipes, not ad-hoc scripts.
- **Store-owned state:** template + instance state and run history live in the Devman Store.
- **Repo consumes via symlink:** project repos consume `.devman/` by symlink into the store instance.

---

## What Devman expects for `devenv.nix`

### A) Seed template shape (in template source)
For a dedicated `devenv.nix` file-type template, mirror Devman’s pattern:

```text
<template_root>/
  copier.yml
  devenv.nix/
    devenv.nix.jinja
    .devman/
      config.toml.jinja
      boomtube.yaml.jinja
      workflows/
        validate.py.jinja
```

Recommended baseline content:
- `devenv.nix.jinja`: minimal working env with `pkgs.just` and `pkgs.uv`.
- `.devman/config.toml.jinja`: `[file_type]` and `[validation]` metadata.
- `.devman/workflows/validate.py.jinja`: validates that `devenv.nix` exists.
- `.devman/boomtube.yaml.jinja`: link declarations (empty list is acceptable initially).

### B) Store materialization target (after bootstrap)

```text
<DEV_MAN_STORE>/devenv.nix/
  .devman/
    config.toml
    workflows/validate.py
    boomtube.yaml
  devenv.nix
```

### C) Project repo consumption target

```text
<PROJECT_REPO>/
  .devman/   -> symlink into store instance
  Justfile
  devenv.nix
  ...project code...
```

---

## Mode 1: Create a new template for a new Devman module library

### Step 1: Scaffold template payload
Create template files under the Devman template source tree and include:
- `copier.yml`
- Jinja payload files
- In-template docs (`README.md` preferred) describing:
  - purpose
  - required inputs
  - expected `just` recipes

### Step 2: Keep environment composition modular
In `devenv.nix` templates:
- Start minimal and composable.
- Add only essential language/tool blocks.
- Prefer explicit package declarations over implicit host assumptions.

### Step 3: Define validation workflow
Add `.devman/workflows/validate.py` logic that fails fast with actionable output.
At minimum:
- check required file presence
- print clear pass/fail messages

### Step 4: Ensure idempotent link behavior
- Do not assume destructive overwrite.
- Link plans should be safe by default.
- If adding link entries, design for repeatable re-apply.

### Step 5: Add fixture coverage
Create/update tests for:
- template file presence
- expected directory layout
- materialization assumptions

---

## Mode 2: Retrofit an existing project to Devman structure

### Step 1: Normalize repo entry points
Ensure project root has:
- `Justfile` as task surface
- `devenv.nix` for environment definition

### Step 2: Move operational state to instance/store
- Ensure `.devman/` in repo is a **symlink** to store instance.
- Keep run logs/metadata/artifacts in store instance, not in repo.

### Step 3: Keep execution through `just`
When converting existing scripts:
- expose commands through `just <recipe>`
- pass parameters via `just` args and environment variables

### Step 4: Add/align validation hooks
Include a validation recipe or workflow that checks required files and expected links.

### Step 5: Verify non-destructive behavior
Re-run setup and confirm:
- links are stable
- no non-symlink paths were overwritten implicitly

---

## Fast verification checklist
- [ ] `devenv.nix` template has `copier.yml` + Jinja payload + `.devman` workflow files.
- [ ] `devenv.nix` file type materializes with `.devman/config.toml`, workflow, and `boomtube.yaml`.
- [ ] Project repo uses `.devman` symlink into store instance.
- [ ] Project execution remains `just`-first.
- [ ] Run outputs (logs/meta/artifacts) are store-owned.
- [ ] Changes are covered by tests/fixtures.

---

## Useful commands while applying this skill

```bash
# Run test suite (or targeted tests)
pytest -q
pytest -q tests/test_project_structure.py

# Inspect seeded template layout quickly
find src/devman/seed_templates/devenv.nix -type f | sort

# Check for devenv and just references
rg -n "devenv.nix|just" README.md src/devman tests
```

---

## Anti-patterns to avoid
- Adding alternate task runners outside `just`.
- Writing run history/artifacts into the project repo.
- Treating `devenv.nix` as optional in devenv-focused template flows.
- Implicitly replacing real directories/files where symlinks are expected.
