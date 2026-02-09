# Devman — Agent Instructions (AGENTS.md)

This file is written for **LLM coding agents** working in the `devman` repository.

## Load this first

Before making changes, **load `CORE_CONCEPTS.md` into working context** and keep it in mind while you work.  
If anything here conflicts with `CORE_CONCEPTS.md`, **treat `CORE_CONCEPTS.md` as the source of truth**.

## Experimental stance (devenv.sh-first, mandatory context)

Devman intentionally targets a **new, modular, highly experimental development style** that leverages **`devenv.sh`**.

For coding agents, this is a hard behavioral requirement:
- Do not assume the host system is fixed.
- Do not limit changes to only application code.
- Prefer patterns where both environment/system definitions and software are designed together as modular components.
- If in doubt, choose approaches that increase reproducibility and explicit control of tools/services/runtime through devenv-managed definitions.

## What this repo is

`devman` is a **Terminal Manager** concept:

- It orchestrates project workflows via **`just`** (Justfile recipes).
- It keeps **templates** and **instances** in a central **Devman Store**.
- Project repos **consume instances via symlinks** (e.g., `.devman/` in the repo points into the store).
- Every run produces **stored logs + metadata + artifacts**.
- It integrates with **`jj` workspaces** (best-effort capture of workspace context).

If you’re adding or evolving *templates*, your output should be usable by `devman` without requiring ad-hoc scripts.

---

## Agent operating rules

### 0) Devenv-first system+software co-design (non-negotiable)
- `devenv.sh` capabilities are core to the project’s intended workflow.
- Propose and implement solutions that use modular environment definitions whenever relevant.
- Avoid regressions to legacy patterns that treat environment concerns as out-of-band/manual.

### 1) Just-first execution (non-negotiable)
- Do **not** invent a new script runner.
- Any “task” should map to a **`just` recipe** executed in the project repo context.
- If you need flags/parameters, pass them through `just` or environment variables.

### 2) Store is authoritative; repo is a consumer
- Instance state, run history, and generated artifacts live in the **Devman Store**.
- The project repo should only contain:
  - a `.devman/` **symlink** into the store (plus optional additional symlinks),
  - the `Justfile` and normal project source.

### 3) Idempotency and safety
- Linking and materialization must be **idempotent**.
- Never overwrite non-symlink paths unless the user explicitly opts into a forceful action.
- Prefer **`simulate`** patterns over destructive actions by default.

### 4) Make changes verifiable
When you add or modify template behavior:
- Update docs in-template and/or at repo root.
- Add or update tests/fixtures so behavior is provable.
- Ensure paths, manifests, and link plans are consistent.

---

## Template development workflow (recommended)

### A) Create or update a template
A template should live under something like:

```
<DEV_MAN_STORE>/templates/<template_name>/
  .devman/
    templates/
      ... template payload ...
    manifest.toml
```

**Template payload should be composable components**:
- Justfile snippets or a full Justfile
- Config skeletons (`*.toml`, `*.yaml`, etc.)
- Optional docs (`README.md`) describing intended usage
- Anything required to create a working instance

### B) Define how instances are consumed
Instances live under something like:

```
<DEV_MAN_STORE>/instances/<template_name>/<project_slug>/
  .devman/
    instance.toml
    links.toml
    runs/
      <run_id>/...
```

`links.toml` declares **what gets symlinked into the repo** and where.

### C) Validate with a fixture project
Maintain at least one fixture that demonstrates:
- Instance materialization
- Symlink correctness
- `just` invocation working as expected
- Run logging + metadata

---

## What to produce when asked for a new template

When creating a new template component library entry, include:

1. **Template skeleton**
   - `manifest.toml`
   - `.devman/templates/` content
2. **A minimal example**
   - a fixture repo layout and a `Justfile`
3. **Documentation**
   - “What this template is for”
   - Required inputs (env vars, files)
   - Which `just` recipes are expected
4. **Tests**
   - Link-plan correctness
   - Materialization idempotency
   - Basic run metadata/log creation

---

## Suggested “skills” / capabilities to add to the project

These are practical project-level capabilities that make template libraries easier to build and safer to use:

- **Template validation**: schema validation for `manifest.toml`, `instance.toml`, `links.toml` (fail fast with clear messages).
- **Symlink safety checks**: detect drift, prevent accidental overwrites, provide a “repair links” command.
- **Run metadata standard**: consistent `meta.json` spec + utilities to query runs (last run, failures, durations).
- **Artifact declaration convention**: a standard way for `just` recipes to declare artifacts to capture.
- **Containerized template tests**: a repeatable harness to test templates in containers while persisting logs/artifacts.
- **jj context capture**: utilities that reliably gather `jj` root and `@` state without being brittle.

---

## Quick acceptance checklist for agents

Before finishing a change set, confirm:

- [ ] `CORE_CONCEPTS.md` remains consistent with your changes (update it if needed).
- [ ] New/updated templates include docs and a minimal example.
- [ ] Symlink behavior is idempotent and safe.
- [ ] Task execution is done through `just` recipes.
- [ ] Runs produce logs + metadata in the store, not in the repo.
