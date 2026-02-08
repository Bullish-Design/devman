# Devman concept overview (post-watchdantic refactor)

Devman is a reactive, template-driven development manager. It watches a project
repository for new files/directories that match configured glob patterns,
instantiates the appropriate Copier template into an **instance store**, and
replaces the original path with a symlink to the instance output.

After the watchdantic refactor, Devman’s “daemon mode” is implemented with a
watchdantic-style engine built on **watchfiles** (Linux inotify) and **Pydantic**
configuration validation, and is exposed via the `devman watch` CLI.

---

## What Devman gives you

Devman is designed around three properties:

1. **Projects stay clean**  
   The working repo contains mostly “real” source and a few symlinks—generated
   infrastructure lives outside the project.

2. **Instances are autonomous**  
   Every instantiation produces an independent version-controlled repository
   (prefer `jj`, fall back to `git`) that can evolve separately from both the
   template and the consuming project.

3. **Templates compose via cascading**  
   A directory template can emit files that themselves match other patterns,
   causing follow-on instantiations (e.g., a project template emits `devenv.nix`,
   which triggers a `devenv-nix` file template).

---

## Foundation stack (revised)

- **Copier** — template engine used for instantiation
- **watchdantic / watchfiles** — filesystem watching, debouncing, glob matching
- **Pydantic v2** — config models and validation
- **Jujutsu (`jj`)** (preferred) / **git** (fallback) — instance version control
- **`devenv.nix`** — common use case for environment bootstrap templates

> Note: Devman embeds the watching engine programmatically; it does not rely on
> shell-command actions. Pattern matches are dispatched to Python handlers that
> run Copier, create repos, and rewrite paths as symlinks.

---

## Core model: templates, instances, projects

### Tier 1 — Base template repos

A **template** is a Copier template repo (often also version-controlled) stored
in a template store. Each template defines its own `copier.yml` and `template/`
tree.

Example:

```
~/.devman-store/devman/.devman/.templates/
├── python-project/
│   ├── copier.yml
│   └── template/...
├── devenv-nix/
│   ├── copier.yml
│   └── template/devenv.nix.jinja
└── pyproject-toml/
    ├── copier.yml
    └── template/pyproject.toml.jinja
```

### Seed template source strategy (init-time)

Devman initialization now uses an explicit seed-template strategy:

- **Option B (default):** `external_repo_path`
  - Resolves from `--seed-templates-repo`, then `$DEVMAN_SEED_TEMPLATES_REPO`, then `~/.devman-templates`.
  - Copies `file-type/` from that external path into `~/.devman-store/devman/.devman/.templates/file-type`.
- **Option A (optional):** `package_assets`
  - Copies bundled package assets via `importlib.resources`.

This keeps runtime template usage the same, while making bootstrap sourcing explicit and configurable.

### Tier 2 — Instance store

An **instance** is the result of instantiating a template. Devman creates a new
directory in the instance store and initializes it as its own repo.

Instances conventionally contain:

- `.devman/` — automation/workflow metadata (not required)
- `output/` — the rendered template output (preferred symlink target)
- repo metadata (`.jj/` or `.git/`)

Example:

```
~/.devman-store/instances/
└── my-app-src-modules-auth/      (jj or git repo)
    ├── .devman/
    ├── output/
    │   └── ...rendered files...
    └── .jj/  (or .git/)
```

### Tier 3 — Project repo

Your working repo stays minimal. When a match triggers, the original path is
replaced with a symlink to the instance output:

- Directory trigger → symlink to `<instance>/output/` (if present)
- File trigger → symlink to `<instance>/output/<file>` (if the template emits it)

---

## The reactive workflow

When running `devman watch`, Devman:

1. **Watches** a repository root for file events (debounced into batches)
2. **Filters** events using ignore rules (e.g., `.git`, `.venv`, `__pycache__`)
3. **Matches** each event against the configured pattern list
4. **Instantiates** the selected template into the instance store (non-interactive)
5. **Initializes** version control in the instance (`jj git init` preferred)
6. **Replaces** the original project path with a symlink to the instance output

A key guardrail: if the derived instance directory already exists, Devman treats
the instantiation as a no-op (prevents repeated triggers).

---

## Cascading instantiation (composition)

Cascading is a *result of watching the project tree*, not a special feature that
requires separate “watch the instance store” logic.

Typical cascade:

1. You create a directory `my-app/` in the project
2. A directory pattern matches and Devman instantiates `python-project`
3. Devman replaces `my-app/` with a symlink to the instance `output/`
4. The `python-project` output includes `devenv.nix` and `pyproject.toml`
5. Those newly created paths are visible in the project tree (through the symlink)
6. File patterns match and trigger additional instantiations for those files
7. Devman replaces those files with symlinks to their own dedicated instances

Conceptually, you end up with a symlink chain:

```
project path
  → project-template instance output
    → file-template instance output(s)
```

---

## Configuration (post-refactor)

Devman now uses a TOML configuration designed for its watcher subsystem.
It focuses on the one thing Devman needs: mapping **glob patterns → templates**.

### `devman-watch.toml`

- `[settings]` controls debounce, logging, ignore rules, and store locations
- `[[pattern]]` blocks declare mappings and event types

Example:

```toml
[settings]
debounce_ms = 500
log_level = "INFO"
ignore_dirs = [".git", ".venv", "__pycache__", "node_modules"]
ignore_globs = ["**/*.pyc", "**/.DS_Store"]

# Store locations (defaults shown)
instance_store = "~/.devman-store/instances"
template_store = "~/.devman-store/devman/.devman/.templates"

[[pattern]]
pattern = "devenv.nix"
template = "devenv-nix"
on = ["added"]

[[pattern]]
pattern = "pyproject.toml"
template = "pyproject-toml"
on = ["added"]

[[pattern]]
pattern = "src/modules/*/"
template = "python-module"
on = ["added"]
exclude = ["src/modules/**/__pycache__/**"]

[[pattern]]
pattern = "*/"
template = "python-project"
on = ["added"]
```

**Matching behavior (important):**

- Matching is **glob-based** on POSIX-style relative paths.
- Patterns are evaluated **in order**; the first match wins.
- `exclude` globs are checked before `pattern`.
- `on` typically uses `["added"]`, but `modified` and `deleted` are also valid.

---

## CLI surface area (revised)

The watch subsystem is additive; the existing CLI remains, and Devman adds:

- `devman watch` — run the reactive watcher (daemon mode, Ctrl+C to stop)
- `devman watch-init` — generate a starter `devman-watch.toml`
- `devman watch-check` — validate a `devman-watch.toml` and print a summary

---

## Instance naming and layout conventions

Devman derives an instance name from:

- the project directory name, and
- the triggering path, slugified (path separators replaced with `-`)

Example:

- project root: `my-app`
- trigger: `src/modules/auth/`
- instance: `my-app-src-modules-auth`

Symlink targets:

- Prefer `<instance>/output/` when it exists (directory templates)
- Otherwise symlink to the instance root (fallback)
- For file templates, the output convention is still `output/` and Devman links
  to the emitted file path under that directory.

---

## Why this architecture works

Migration note: existing template stores continue to work as-is; the strategy only affects new `devman init` runs.


- **Autonomy without duplication**: instances are full repos, not branches or
  workspaces of the template repo.
- **Fast iteration**: templates can evolve independently; instances can be
  updated or forked without rewriting project history.
- **Composable scaffolding**: directory templates can “pull in” specialized file
  templates via cascading.
- **Config safety**: TOML config is validated at startup; invalid event types or
  log levels fail early.
- **Operational sanity**: debouncing + ignore rules + “instance already exists”
  checks keep the watcher stable under noisy filesystem activity.

---

## Mental model recap

```
Template tier (Copier templates) ──instantiate──▶ Instance tier (independent repos)
          ▲                                              │
          │                                              └─symlink into project
          │
   evolve templates                                  Project tier (your work)
```

Devman’s job is to keep those tiers loosely coupled—connected by symlinks, but
versioned and evolvable independently.
