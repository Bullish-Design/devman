# Watchdantic Refactor Guide

Step-by-step guide for refactoring devman to use watchdantic for all
file/system watching. After completing this guide, devman will have a reactive
daemon mode that automatically instantiates templates when files or directories
matching configured patterns appear on the filesystem.

---

## Table of Contents

- [Background](#background)
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Phase 1: Add Watchdantic Dependency and Module Structure](#phase-1-add-watchdantic-dependency-and-module-structure)
- [Phase 2: Define Devman Watch Config Models](#phase-2-define-devman-watch-config-models)
- [Phase 3: Build the Reactive Engine](#phase-3-build-the-reactive-engine)
- [Phase 4: Implement Action Handlers](#phase-4-implement-action-handlers)
- [Phase 5: Add the `devman watch` CLI Command](#phase-5-add-the-devman-watch-cli-command)
- [Phase 6: Create Default watch.toml Generation](#phase-6-create-default-watchtoml-generation)
- [Phase 7: Write Tests](#phase-7-write-tests)
- [Phase 8: Integration Testing and Final Verification](#phase-8-integration-testing-and-final-verification)
- [File Change Summary](#file-change-summary)
- [Reference: Watchdantic Concepts Cheat Sheet](#reference-watchdantic-concepts-cheat-sheet)

---

## Background

### What devman does today

Devman is a self-bootstrapping file-oriented system that uses
[copier](https://copier.readthedocs.io/) templates to generate and manage file
type configurations. Its current workflow is entirely **manual and CLI-driven**:

1. `devman init` — creates the template store at `~/.devman-store/`
2. `devman bootstrap <file_type>` — instantiates a file type from a copier template
3. `devman project <template> <target>` — scaffolds a project from a meta-template
4. `devman update <target>` — updates a file type or project to a new template version

There is **no filesystem watching** in the current codebase.

### What devman should do after this refactor

The CONCEPT_OVERVIEW.md describes a **reactive daemon** that:

1. Monitors project directories for new files/folders matching glob patterns
2. Automatically identifies the correct template for the match
3. Runs copier to instantiate the template into the instance store
4. Initialises a jj/git repo for the new instance
5. Replaces the original file/folder with a symlink to the instance output

### Why watchdantic

Watchdantic is a config-driven file watcher built on
[watchfiles](https://watchfiles.helpmanual.io/) (Linux inotify) and
[Pydantic](https://docs.pydantic.dev/). It provides exactly the primitives
devman needs:

| Watchdantic feature | How devman uses it |
|---|---|
| `[[watch]]` blocks | Monitor project directories for new files |
| `[[rule]]` blocks with glob matching | Match `src/modules/*/`, `*.service.py`, etc. |
| `FileEvent` objects | Know which path was created and what changed |
| Debouncing | Avoid duplicate triggers during rapid file creation |
| Ignore filters | Skip `.git`, `__pycache__`, `.venv`, etc. |
| `Engine` programmatic API | Embed the watcher inside devman's own process |
| Pydantic config validation | Catch misconfiguration at startup |

### Key architectural decision

We will use watchdantic's **programmatic API** (not its CLI). This means:

- Devman imports `Engine`, `load_config`, `FileEvent`, and `event_matches_rule`
  from `watchdantic.engine.*`
- Devman provides its **own action dispatch logic** (copier instantiation, repo
  creation, symlink replacement) instead of using watchdantic's shell command
  actions
- The `watch.toml` file still defines watches and rules, but actions are
  handled by devman's Python code

This avoids the indirection of shell commands and environment variable parsing,
and lets devman's action handlers directly access Python objects.

---

## Architecture Overview

### Current source layout

```
src/devman/
├── __init__.py              # Package version
├── cli.py                   # Typer CLI (init, bootstrap, project, update)
├── constants.py             # Path constants
├── bootstrap.py             # File type bootstrapping via copier
├── bootstrap_project.py     # Project creation from meta-templates
├── update.py                # Version update mechanism
├── domain/
│   ├── __init__.py
│   ├── errors.py            # DomainError, PathNotFoundError, etc.
│   └── models.py            # ValidationResult, ValidationIssue
├── schemas/
│   ├── __init__.py
│   ├── copier.py            # CopierConfig pydantic model
│   ├── questions.py         # Question type models
│   └── tasks.py             # Task/TaskList models
└── seed_templates/
    └── file-type/           # Copier template for bootstrapping new file types
```

### Target source layout (new files marked with `+`)

```
src/devman/
├── __init__.py
├── cli.py                   # + Add `watch` command
├── constants.py             # + Add WATCH_CONFIG constant
├── bootstrap.py
├── bootstrap_project.py
├── update.py
├── domain/
│   ├── __init__.py
│   ├── errors.py            # + Add WatchError
│   └── models.py
├── schemas/
│   ├── __init__.py
│   ├── copier.py
│   ├── questions.py
│   └── tasks.py
├── watcher/                 # + NEW PACKAGE — all watchdantic integration
│   ├── __init__.py
│   ├── config.py            # + Devman-specific watch config models
│   ├── engine.py            # + Wraps watchdantic Engine with devman dispatch
│   ├── handlers.py          # + Action handlers (instantiate, symlink, etc.)
│   └── toml_gen.py          # + Generates watch.toml from devman config
└── seed_templates/
    └── file-type/
```

---

## Prerequisites

Before starting, make sure you understand:

1. **The watchdantic user guide** (`WATCHDANTIC_USER_GUIDE.md` at repo root) —
   read the entire document, especially the *Programmatic Usage* and
   *Configuration* sections
2. **Pydantic v2 models** — devman already uses these extensively in
   `schemas/` and `domain/models.py`
3. **How copier works** — the `bootstrap.py` and `bootstrap_project.py` files
   show the subprocess-based copier invocation pattern
4. **The CONCEPT_OVERVIEW.md** — this is the target vision for the reactive
   workflow

---

## Phase 1: Add Watchdantic Dependency and Module Structure

### Step 1.1: Add watchdantic to pyproject.toml

Open `pyproject.toml` and add `watchdantic` and `watchfiles` to the
dependencies list:

```toml
# pyproject.toml
[project]
dependencies = [
    "typer>=0.9.0",
    "pydantic>=2.0.0",
    "copier>=9.0.0",
    "pyyaml>=6.0.0",
    "tomli-w>=1.0.0",
    "rich>=13.0.0",
    "watchfiles>=1.0.0",      # <-- ADD
]
```

**Note:** Watchdantic is not yet a published PyPI package. For now, the
watchdantic engine modules will be created directly within devman under
`src/devman/watcher/`. Once watchdantic is published separately, this can be
changed to a standard dependency import. The `watchfiles` library *is* on PyPI
and must be installed.

### Step 1.2: Create the watcher package directory

```bash
mkdir -p src/devman/watcher
```

### Step 1.3: Create `src/devman/watcher/__init__.py`

```python
# src/devman/watcher/__init__.py
"""Watchdantic-based filesystem watching for devman."""
```

### Step 1.4: Add the WATCH_CONFIG constant

Edit `src/devman/constants.py` and add:

```python
# Add at the end of the file:
WATCH_CONFIG_NAME = "watch.toml"
```

This is the filename watchdantic expects.

### Verify

At this point the project should still pass all existing tests:

```bash
pytest tests/ -v
```

Nothing functional has changed yet.

---

## Phase 2: Define Devman Watch Config Models

This phase creates Pydantic models that represent devman's watch configuration.
These models bridge devman's concept (pattern → template mapping) with
watchdantic's config structure (watch/rule/action).

### Step 2.1: Create `src/devman/watcher/config.py`

This file defines the Pydantic models for devman's watch configuration. The
config file will be a TOML file that lives alongside (or is embedded within)
the project's `watch.toml`.

```python
# src/devman/watcher/config.py
"""Pydantic models for devman watch configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomllib
import tomli_w
from pydantic import BaseModel, Field, field_validator


class PatternMapping(BaseModel):
    """Maps a glob pattern to a template for automatic instantiation.

    This is the core devman concept: when a file/directory matching
    ``pattern`` is created, devman instantiates ``template`` from
    the template store.
    """

    pattern: str = Field(description="Glob pattern to match (e.g., 'src/modules/*/')")
    template: str = Field(description="Template name in the devman store")
    on: list[str] = Field(
        default=["added"],
        description="Event types to react to. Usually just 'added'.",
    )
    exclude: list[str] = Field(
        default_factory=list,
        description="Glob patterns to exclude from matching",
    )

    @field_validator("on")
    @classmethod
    def validate_event_types(cls, v: list[str]) -> list[str]:
        allowed = {"added", "modified", "deleted"}
        for event_type in v:
            if event_type not in allowed:
                raise ValueError(
                    f"Invalid event type '{event_type}'. "
                    f"Must be one of: {', '.join(sorted(allowed))}"
                )
        return v


class WatchSettings(BaseModel):
    """Global settings for devman's watch daemon."""

    debounce_ms: int = Field(default=500, ge=50, le=5000)
    log_level: str = Field(default="INFO")
    ignore_dirs: list[str] = Field(
        default_factory=lambda: [".git", ".venv", "__pycache__", "node_modules"]
    )
    ignore_globs: list[str] = Field(
        default_factory=lambda: ["**/*.pyc", "**/.DS_Store"]
    )
    instance_store: str = Field(
        default="~/.devman-store",
        description="Root directory for instance repos",
    )
    template_store: str = Field(
        default="~/.devman-store/devman/.devman/.templates",
        description="Root directory for templates",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if v.upper() not in allowed:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: {', '.join(sorted(allowed))}"
            )
        return v.upper()


class DevmanWatchConfig(BaseModel):
    """Root configuration for devman's filesystem watcher.

    Example devman-watch.toml:

        [settings]
        debounce_ms = 500
        log_level = "INFO"
        instance_store = "~/.devman-store"

        [[pattern]]
        pattern = "src/modules/*/"
        template = "python-module"

        [[pattern]]
        pattern = "*.service.py"
        template = "service-layer"
    """

    settings: WatchSettings = Field(default_factory=WatchSettings)
    patterns: list[PatternMapping] = Field(
        default_factory=list,
        alias="pattern",
    )

    model_config = {"populate_by_name": True}

    @classmethod
    def from_toml_file(cls, path: Path) -> DevmanWatchConfig:
        """Load config from a TOML file."""
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(**data)

    def to_toml_file(self, path: Path) -> None:
        """Write config to a TOML file."""
        data: dict[str, Any] = {
            "settings": self.settings.model_dump(),
            "pattern": [p.model_dump() for p in self.patterns],
        }
        with open(path, "wb") as f:
            tomli_w.dump(data, f)

    def get_template_for_pattern(self, pattern_str: str) -> str | None:
        """Look up which template a pattern string maps to."""
        for mapping in self.patterns:
            if mapping.pattern == pattern_str:
                return mapping.template
        return None
```

### What this gives you

- `DevmanWatchConfig` is the **single source of truth** for devman's reactive
  watching configuration
- It is separate from watchdantic's own config models — devman converts between
  the two (see Phase 3)
- The `PatternMapping` class represents the concept from CONCEPT_OVERVIEW.md:
  `pattern → template`

---

## Phase 3: Build the Reactive Engine

This is the core integration phase. We create a wrapper around watchdantic's
`Engine` that intercepts file events and dispatches them to devman's action
handlers instead of watchdantic's shell command runner.

### Step 3.1: Create `src/devman/watcher/engine.py`

This module:
1. Converts `DevmanWatchConfig` into a watchdantic-compatible config
2. Starts the watchdantic engine's watch loops
3. When events arrive, matches them against devman's pattern mappings
4. Dispatches matched events to devman's action handlers

```python
# src/devman/watcher/engine.py
"""Devman reactive engine built on watchdantic's file watching."""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from watchfiles import watch, Change

from devman.watcher.config import DevmanWatchConfig, PatternMapping
from devman.watcher.handlers import handle_instantiation

if TYPE_CHECKING:
    pass

logger = logging.getLogger("devman.watcher")


def _match_glob(pattern: str, rel_path: str) -> bool:
    """Check if a relative path matches a glob pattern.

    Uses pathlib's PurePosixPath.match() which supports ** globs.
    Tries both with and without trailing slash for directory patterns.
    """
    from pathlib import PurePosixPath

    p = PurePosixPath(rel_path)

    # If pattern ends with /, it's a directory pattern
    clean_pattern = pattern.rstrip("/")
    if p.match(clean_pattern):
        return True

    # Also try matching just the parts
    return PurePosixPath(rel_path).match(pattern)


def _should_ignore(rel_path: str, ignore_dirs: list[str], ignore_globs: list[str]) -> bool:
    """Check if a path should be ignored."""
    from pathlib import PurePosixPath

    parts = PurePosixPath(rel_path).parts
    for d in ignore_dirs:
        if d in parts:
            return True

    for glob in ignore_globs:
        if PurePosixPath(rel_path).match(glob):
            return True

    return False


def _change_to_event_type(change: Change) -> str:
    """Convert a watchfiles Change enum to a watchdantic event type string."""
    mapping = {
        Change.added: "added",
        Change.modified: "modified",
        Change.deleted: "deleted",
    }
    return mapping.get(change, "modified")


def find_matching_pattern(
    rel_path: str,
    event_type: str,
    patterns: list[PatternMapping],
) -> PatternMapping | None:
    """Find the first PatternMapping that matches a file event.

    Args:
        rel_path: Path relative to the watched root.
        event_type: One of "added", "modified", "deleted".
        patterns: List of PatternMapping from the devman watch config.

    Returns:
        The first matching PatternMapping, or None.
    """
    for pm in patterns:
        if event_type not in pm.on:
            continue

        # Check excludes first
        excluded = False
        for exc in pm.exclude:
            if _match_glob(exc, rel_path):
                excluded = True
                break
        if excluded:
            continue

        if _match_glob(pm.pattern, rel_path):
            return pm

    return None


class DevmanWatcher:
    """Reactive file watcher that triggers template instantiation.

    Usage:
        config = DevmanWatchConfig.from_toml_file(Path("devman-watch.toml"))
        watcher = DevmanWatcher(config, repo_root=Path("."))
        watcher.run()  # Blocks until Ctrl+C
    """

    def __init__(self, config: DevmanWatchConfig, repo_root: Path) -> None:
        self.config = config
        self.repo_root = repo_root.resolve()
        self._running = False

        # Set up logging
        log_level = getattr(logging, config.settings.log_level, logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )

    def run(self) -> None:
        """Start watching and block until interrupted.

        Sets up SIGHUP for config reload and SIGINT/SIGTERM for shutdown.
        """
        self._running = True
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGHUP, self._handle_reload)

        logger.info(
            "Devman watcher starting — monitoring %s with %d pattern(s)",
            self.repo_root,
            len(self.config.patterns),
        )
        for pm in self.config.patterns:
            logger.info("  %s → template '%s'", pm.pattern, pm.template)

        # Build the watchfiles filter function
        ignore_dirs = set(self.config.settings.ignore_dirs)
        ignore_globs = self.config.settings.ignore_globs

        try:
            for changes in watch(
                self.repo_root,
                debounce=self.config.settings.debounce_ms,
                step=50,
                watch_filter=None,
                stop_event=None,
            ):
                if not self._running:
                    break
                self._process_changes(changes, ignore_dirs, ignore_globs)
        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Devman watcher stopped.")

    def run_once(self, changes: set[tuple[Change, str]]) -> list[dict]:
        """Process a single batch of changes. Useful for testing.

        Args:
            changes: Set of (Change, path_str) tuples from watchfiles.

        Returns:
            List of result dicts from action handlers.
        """
        ignore_dirs = set(self.config.settings.ignore_dirs)
        ignore_globs = self.config.settings.ignore_globs
        return self._process_changes(changes, ignore_dirs, ignore_globs)

    def _process_changes(
        self,
        changes: set[tuple[Change, str]],
        ignore_dirs: set[str],
        ignore_globs: list[str],
    ) -> list[dict]:
        """Process a batch of file change events.

        For each change:
        1. Compute relative path from repo_root
        2. Check against ignore filters
        3. Match against pattern mappings
        4. If matched, dispatch to the appropriate handler
        """
        results = []

        for change, path_str in changes:
            abs_path = Path(path_str)

            try:
                rel_path = abs_path.relative_to(self.repo_root)
            except ValueError:
                logger.debug("Ignoring path outside repo root: %s", path_str)
                continue

            rel_str = str(rel_path)
            event_type = _change_to_event_type(change)

            if _should_ignore(rel_str, list(ignore_dirs), ignore_globs):
                logger.debug("Ignored: %s", rel_str)
                continue

            logger.debug("Event: %s %s", event_type, rel_str)

            matched = find_matching_pattern(
                rel_str, event_type, self.config.patterns
            )
            if matched is None:
                continue

            logger.info(
                "Match: %s → pattern '%s' → template '%s'",
                rel_str,
                matched.pattern,
                matched.template,
            )

            result = handle_instantiation(
                template_name=matched.template,
                trigger_path=abs_path,
                rel_path=rel_path,
                repo_root=self.repo_root,
                instance_store=Path(
                    self.config.settings.instance_store
                ).expanduser(),
                template_store=Path(
                    self.config.settings.template_store
                ).expanduser(),
            )
            results.append(result)

        return results

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle SIGINT/SIGTERM for clean shutdown."""
        logger.info("Shutdown signal received, stopping...")
        self._running = False

    def _handle_reload(self, signum: int, frame: Any) -> None:
        """Handle SIGHUP for config reload."""
        logger.info("Reload signal received, re-reading config...")
        # The config path must be stored to support reload.
        # For now, log that reload is not yet implemented with path tracking.
        logger.warning("Config reload not yet implemented for in-memory config.")
```

### Key design notes

- **`DevmanWatcher.run()`** blocks the main thread, just like
  `watchdantic run`. It is the daemon mode entry point.
- **`DevmanWatcher.run_once()`** processes a single batch of changes and
  returns results. This is the testing entry point.
- **`find_matching_pattern()`** is a pure function — easy to unit test.
- **`_match_glob()`** uses `pathlib.PurePosixPath.match()` for glob matching,
  consistent with watchdantic's approach.
- Signal handling follows the same pattern as watchdantic (SIGHUP reload,
  SIGINT/SIGTERM shutdown).

---

## Phase 4: Implement Action Handlers

Action handlers are the devman-specific logic that runs when a pattern matches.
This is where copier instantiation, repo creation, and symlink replacement
happen.

### Step 4.1: Create `src/devman/watcher/handlers.py`

```python
# src/devman/watcher/handlers.py
"""Action handlers for devman watch events.

When a file event matches a pattern, these handlers perform the
template instantiation workflow described in CONCEPT_OVERVIEW.md:

1. Run copier to instantiate the template into the instance store
2. Initialize a git/jj repo for the new instance
3. Replace the original path with a symlink to the instance output
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("devman.watcher.handlers")


def handle_instantiation(
    template_name: str,
    trigger_path: Path,
    rel_path: Path,
    repo_root: Path,
    instance_store: Path,
    template_store: Path,
) -> dict:
    """Handle a matched file event by instantiating a template.

    Args:
        template_name: Name of the template to instantiate (e.g., "python-module").
        trigger_path: Absolute path of the file/dir that triggered the event.
        rel_path: Path relative to repo_root.
        repo_root: Absolute path to the project root being watched.
        instance_store: Absolute path to the instance store root (e.g., ~/.devman-store).
        template_store: Absolute path to the template directory.

    Returns:
        Dict with keys: success (bool), instance_path (Path or None),
        template (str), trigger (str), error (str or None).
    """
    # Derive instance name from project name + relative path
    project_name = repo_root.name
    instance_name = f"{project_name}-{_path_to_slug(rel_path)}"
    instance_path = instance_store / instance_name
    template_path = template_store / template_name

    result = {
        "success": False,
        "instance_path": None,
        "template": template_name,
        "trigger": str(rel_path),
        "error": None,
    }

    # 1. Verify template exists
    if not template_path.exists():
        msg = f"Template not found: {template_path}"
        logger.error(msg)
        result["error"] = msg
        return result

    # 2. Check if instance already exists
    if instance_path.exists():
        msg = f"Instance already exists: {instance_path}"
        logger.warning(msg)
        result["error"] = msg
        return result

    # 3. Run copier to instantiate
    try:
        _run_copier(template_path, instance_path)
    except RuntimeError as e:
        result["error"] = str(e)
        return result

    # 4. Initialize version control repo
    try:
        _init_repo(instance_path)
    except RuntimeError as e:
        result["error"] = str(e)
        return result

    # 5. Replace trigger path with symlink to instance output
    try:
        _create_symlink(trigger_path, instance_path)
    except RuntimeError as e:
        result["error"] = str(e)
        return result

    result["success"] = True
    result["instance_path"] = instance_path
    logger.info(
        "Instantiated: %s → %s (template: %s)",
        rel_path,
        instance_path,
        template_name,
    )
    return result


def _path_to_slug(rel_path: Path) -> str:
    """Convert a relative path to a URL-safe slug.

    Example: Path("src/modules/auth") → "src-modules-auth"
    """
    return str(rel_path).replace("/", "-").replace("\\", "-").strip("-")


def _run_copier(template_path: Path, target_path: Path) -> None:
    """Run copier to instantiate a template.

    This follows the same subprocess pattern used in
    devman.bootstrap.bootstrap_file_type().
    """
    copier_cmd = [
        "copier",
        "copy",
        "--defaults",   # Use default answers (non-interactive)
        str(template_path),
        str(target_path),
    ]

    logger.debug("Running: %s", " ".join(copier_cmd))
    proc = subprocess.run(copier_cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        raise RuntimeError(f"Copier failed: {proc.stderr}")


def _init_repo(instance_path: Path) -> None:
    """Initialize a git repository in the instance directory.

    If jj (jujutsu) is available, use it instead. Falls back to git.
    This follows the same pattern as devman.bootstrap.init_devman_store().
    """
    import shutil

    if shutil.which("jj"):
        cmd = ["jj", "git", "init"]
    else:
        cmd = ["git", "init"]

    logger.debug("Initializing repo: %s in %s", " ".join(cmd), instance_path)
    proc = subprocess.run(cmd, cwd=instance_path, capture_output=True, text=True)

    if proc.returncode != 0:
        raise RuntimeError(f"Repo init failed: {proc.stderr}")


def _create_symlink(trigger_path: Path, instance_path: Path) -> None:
    """Replace the trigger path with a symlink to the instance.

    If the trigger path is a directory, the symlink target is
    instance_path/output/ (the conventional output directory).
    If it's a file, the symlink points to the instance root.

    The original trigger path is removed before creating the symlink.
    """
    import shutil

    # Determine symlink target
    output_dir = instance_path / "output"
    if output_dir.exists():
        symlink_target = output_dir
    else:
        symlink_target = instance_path

    # Remove the original trigger path
    if trigger_path.is_dir():
        shutil.rmtree(trigger_path)
    elif trigger_path.exists():
        trigger_path.unlink()

    # Create the symlink
    trigger_path.symlink_to(symlink_target)
    logger.info("Symlink: %s → %s", trigger_path, symlink_target)
```

### What each handler function does

| Function | Responsibility |
|---|---|
| `handle_instantiation()` | Orchestrates the full workflow: copier → repo → symlink |
| `_path_to_slug()` | Converts `src/modules/auth` → `src-modules-auth` for instance naming |
| `_run_copier()` | Subprocess wrapper matching existing `bootstrap.py` pattern |
| `_init_repo()` | Initializes jj or git repo, matching `bootstrap.py` pattern |
| `_create_symlink()` | Replaces trigger path with symlink to instance output |

### Important notes

- `_run_copier()` uses `--defaults` for non-interactive mode since the daemon
  cannot prompt for input. If templates require answers, they should be
  provided via a data file (future enhancement).
- `_init_repo()` prefers `jj` if available, falling back to `git`. This aligns
  with the CONCEPT_OVERVIEW.md vision.
- `_create_symlink()` looks for an `output/` subdirectory in the instance
  (the conventional output location from CONCEPT_OVERVIEW.md). If it doesn't
  exist, it symlinks to the instance root.

---

## Phase 5: Add the `devman watch` CLI Command

### Step 5.1: Edit `src/devman/cli.py`

Add a new `watch` command to the existing Typer app. Insert this after the
existing `update` command and before the `if __name__` block:

```python
@app.command()
def watch(
    config: Path = typer.Option(
        None, "--config", "-c",
        help="Path to devman-watch.toml config file",
    ),
    repo_root: Path = typer.Option(
        ".", "--root", "-r",
        help="Repository root to watch",
    ),
):
    """Start the reactive file watcher daemon."""
    from devman.watcher.config import DevmanWatchConfig
    from devman.watcher.engine import DevmanWatcher

    # Find config file
    if config is None:
        config = Path("devman-watch.toml")

    if not config.exists():
        console.print(
            f"[red]Error[/red] Config file not found: {config}\n"
            f"  Run 'devman watch-init' to generate a starter config."
        )
        raise typer.Exit(1)

    # Load and validate config
    try:
        watch_config = DevmanWatchConfig.from_toml_file(config)
    except Exception as e:
        console.print(f"[red]Error[/red] Invalid config: {e}")
        raise typer.Exit(1)

    if not watch_config.patterns:
        console.print("[yellow]Warning[/yellow] No patterns configured. Nothing to watch.")
        raise typer.Exit(0)

    console.print(f"[green]Starting[/green] devman watcher on {repo_root.resolve()}")
    console.print(f"  Config: {config}")
    console.print(f"  Patterns: {len(watch_config.patterns)}")
    for pm in watch_config.patterns:
        console.print(f"    {pm.pattern} → {pm.template}")
    console.print("\n  Press Ctrl+C to stop.\n")

    watcher = DevmanWatcher(watch_config, repo_root=Path(repo_root).resolve())
    watcher.run()
```

### Step 5.2: Add a `watch-init` command

Also add a command to generate a starter `devman-watch.toml`:

```python
@app.command("watch-init")
def watch_init(
    output: Path = typer.Option(
        "devman-watch.toml", "--output", "-o",
        help="Output file path",
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing file",
    ),
):
    """Generate a starter devman-watch.toml configuration."""
    from devman.watcher.toml_gen import generate_starter_config

    if output.exists() and not force:
        console.print(
            f"[red]Error[/red] File already exists: {output}\n"
            f"  Use --force to overwrite."
        )
        raise typer.Exit(1)

    generate_starter_config(output)
    console.print(f"[green]OK[/green] Created: {output}")
    console.print("  Edit the file to add your pattern → template mappings.")
```

### Step 5.3: Add a `watch-check` command

```python
@app.command("watch-check")
def watch_check(
    config: Path = typer.Option(
        "devman-watch.toml", "--config", "-c",
        help="Path to devman-watch.toml config file",
    ),
):
    """Validate a devman-watch.toml config file."""
    from devman.watcher.config import DevmanWatchConfig

    if not config.exists():
        console.print(f"[red]Error[/red] Config file not found: {config}")
        raise typer.Exit(1)

    try:
        watch_config = DevmanWatchConfig.from_toml_file(config)
    except Exception as e:
        console.print(f"[red]Error[/red] Invalid config: {e}")
        raise typer.Exit(1)

    console.print(f"[green]OK[/green] Config is valid: {config}")
    console.print(f"\n  Settings:")
    console.print(f"    Debounce:    {watch_config.settings.debounce_ms}ms")
    console.print(f"    Log level:   {watch_config.settings.log_level}")
    console.print(f"    Ignore dirs: {watch_config.settings.ignore_dirs}")
    console.print(f"\n  Patterns ({len(watch_config.patterns)}):")
    for pm in watch_config.patterns:
        console.print(f"    {pm.pattern} → {pm.template} (on: {', '.join(pm.on)})")
```

---

## Phase 6: Create Default watch.toml Generation

### Step 6.1: Create `src/devman/watcher/toml_gen.py`

```python
# src/devman/watcher/toml_gen.py
"""Generate starter devman-watch.toml configuration files."""

from __future__ import annotations

from pathlib import Path

import tomli_w


def generate_starter_config(output_path: Path) -> None:
    """Write a minimal devman-watch.toml with example patterns.

    This is the equivalent of ``watchdantic init`` but for devman's
    own config format.
    """
    config = {
        "settings": {
            "debounce_ms": 500,
            "log_level": "INFO",
            "ignore_dirs": [".git", ".venv", "__pycache__", "node_modules"],
            "ignore_globs": ["**/*.pyc", "**/.DS_Store"],
            "instance_store": "~/.devman-store",
            "template_store": "~/.devman-store/devman/.devman/.templates",
        },
        "pattern": [
            {
                "pattern": "src/modules/*/",
                "template": "python-module",
                "on": ["added"],
                "exclude": [],
            },
        ],
    }

    with open(output_path, "wb") as f:
        tomli_w.dump(config, f)
```

---

## Phase 7: Write Tests

### Step 7.1: Create test file `tests/test_watcher_config.py`

Tests for the Pydantic config models:

```python
# tests/test_watcher_config.py
"""Tests for devman.watcher.config models."""

import pytest
from pathlib import Path
from devman.watcher.config import (
    DevmanWatchConfig,
    PatternMapping,
    WatchSettings,
)


def test_pattern_mapping_defaults():
    pm = PatternMapping(pattern="src/modules/*/", template="python-module")
    assert pm.on == ["added"]
    assert pm.exclude == []


def test_pattern_mapping_rejects_invalid_event_type():
    with pytest.raises(ValueError, match="Invalid event type"):
        PatternMapping(pattern="**/*.py", template="x", on=["created"])


def test_watch_settings_defaults():
    ws = WatchSettings()
    assert ws.debounce_ms == 500
    assert ws.log_level == "INFO"
    assert ".git" in ws.ignore_dirs


def test_watch_settings_rejects_invalid_log_level():
    with pytest.raises(ValueError, match="Invalid log level"):
        WatchSettings(log_level="TRACE")


def test_devman_watch_config_round_trip(tmp_path: Path):
    config = DevmanWatchConfig(
        settings=WatchSettings(debounce_ms=200),
        patterns=[
            PatternMapping(pattern="src/**/*.py", template="py-module"),
            PatternMapping(
                pattern="docs/**/*.md",
                template="doc-page",
                on=["added", "modified"],
            ),
        ],
    )

    toml_file = tmp_path / "devman-watch.toml"
    config.to_toml_file(toml_file)

    loaded = DevmanWatchConfig.from_toml_file(toml_file)
    assert len(loaded.patterns) == 2
    assert loaded.settings.debounce_ms == 200
    assert loaded.patterns[0].template == "py-module"
    assert loaded.patterns[1].on == ["added", "modified"]


def test_devman_watch_config_empty_patterns():
    config = DevmanWatchConfig()
    assert config.patterns == []
    assert config.settings.debounce_ms == 500


def test_get_template_for_pattern():
    config = DevmanWatchConfig(
        patterns=[
            PatternMapping(pattern="src/modules/*/", template="python-module"),
            PatternMapping(pattern="*.service.py", template="service-layer"),
        ],
    )
    assert config.get_template_for_pattern("src/modules/*/") == "python-module"
    assert config.get_template_for_pattern("*.service.py") == "service-layer"
    assert config.get_template_for_pattern("nope") is None
```

### Step 7.2: Create test file `tests/test_watcher_engine.py`

Tests for the engine's pattern matching logic (no filesystem required):

```python
# tests/test_watcher_engine.py
"""Tests for devman.watcher.engine pattern matching."""

from devman.watcher.config import PatternMapping
from devman.watcher.engine import find_matching_pattern, _match_glob, _should_ignore


# --- Glob matching ---

def test_match_glob_star():
    assert _match_glob("*.py", "foo.py")
    assert not _match_glob("*.py", "src/foo.py")


def test_match_glob_double_star():
    assert _match_glob("**/*.py", "foo.py")
    assert _match_glob("**/*.py", "src/foo.py")
    assert _match_glob("**/*.py", "a/b/c/foo.py")
    assert not _match_glob("**/*.py", "foo.txt")


def test_match_glob_directory_pattern():
    assert _match_glob("src/modules/*/", "src/modules/auth")
    assert _match_glob("src/modules/*", "src/modules/auth")


def test_match_glob_prefix():
    assert _match_glob("src/**/*.py", "src/foo.py")
    assert _match_glob("src/**/*.py", "src/a/b/foo.py")
    assert not _match_glob("src/**/*.py", "lib/foo.py")


# --- Ignore filtering ---

def test_should_ignore_dir():
    assert _should_ignore("src/.git/config", [".git"], [])
    assert _should_ignore(".venv/lib/python", [".venv"], [])
    assert not _should_ignore("src/app.py", [".git"], [])


def test_should_ignore_glob():
    assert _should_ignore("src/__pycache__/foo.pyc", [], ["**/*.pyc"])
    assert not _should_ignore("src/app.py", [], ["**/*.pyc"])


# --- Pattern matching ---

def test_find_matching_pattern_simple():
    patterns = [
        PatternMapping(pattern="**/*.py", template="py-module"),
    ]
    result = find_matching_pattern("src/app.py", "added", patterns)
    assert result is not None
    assert result.template == "py-module"


def test_find_matching_pattern_no_match():
    patterns = [
        PatternMapping(pattern="**/*.py", template="py-module"),
    ]
    result = find_matching_pattern("src/app.js", "added", patterns)
    assert result is None


def test_find_matching_pattern_wrong_event_type():
    patterns = [
        PatternMapping(pattern="**/*.py", template="py-module", on=["added"]),
    ]
    result = find_matching_pattern("src/app.py", "modified", patterns)
    assert result is None


def test_find_matching_pattern_respects_exclude():
    patterns = [
        PatternMapping(
            pattern="**/*.py",
            template="py-module",
            exclude=["tests/**"],
        ),
    ]
    assert find_matching_pattern("src/app.py", "added", patterns) is not None
    assert find_matching_pattern("tests/test_app.py", "added", patterns) is None


def test_find_matching_pattern_first_match_wins():
    patterns = [
        PatternMapping(pattern="src/modules/*", template="specific-module"),
        PatternMapping(pattern="src/**/*", template="generic-src"),
    ]
    result = find_matching_pattern("src/modules/auth", "added", patterns)
    assert result is not None
    assert result.template == "specific-module"
```

### Step 7.3: Create test file `tests/test_watcher_handlers.py`

Tests for the action handlers using a temporary filesystem:

```python
# tests/test_watcher_handlers.py
"""Tests for devman.watcher.handlers."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from devman.watcher.handlers import (
    handle_instantiation,
    _path_to_slug,
    _create_symlink,
)


def test_path_to_slug():
    assert _path_to_slug(Path("src/modules/auth")) == "src-modules-auth"
    assert _path_to_slug(Path("app.py")) == "app.py"
    assert _path_to_slug(Path("a/b/c")) == "a-b-c"


def test_handle_instantiation_template_not_found(tmp_path: Path):
    result = handle_instantiation(
        template_name="nonexistent",
        trigger_path=tmp_path / "trigger",
        rel_path=Path("trigger"),
        repo_root=tmp_path,
        instance_store=tmp_path / "instances",
        template_store=tmp_path / "templates",
    )
    assert not result["success"]
    assert "not found" in result["error"]


def test_handle_instantiation_instance_already_exists(tmp_path: Path):
    # Create template dir
    (tmp_path / "templates" / "my-template").mkdir(parents=True)
    # Create instance dir (pre-existing)
    instance_dir = tmp_path / "instances" / "proj-trigger"
    instance_dir.mkdir(parents=True)

    result = handle_instantiation(
        template_name="my-template",
        trigger_path=tmp_path / "proj" / "trigger",
        rel_path=Path("trigger"),
        repo_root=tmp_path / "proj",
        instance_store=tmp_path / "instances",
        template_store=tmp_path / "templates",
    )
    assert not result["success"]
    assert "already exists" in result["error"]


def test_create_symlink_directory(tmp_path: Path):
    """Test symlink creation for a directory trigger."""
    trigger = tmp_path / "modules" / "auth"
    trigger.mkdir(parents=True)
    (trigger / "placeholder.txt").write_text("temp")

    instance = tmp_path / "instance"
    instance.mkdir()
    output = instance / "output"
    output.mkdir()
    (output / "real_file.py").write_text("content")

    _create_symlink(trigger, instance)

    assert trigger.is_symlink()
    assert trigger.resolve() == output.resolve()


def test_create_symlink_file(tmp_path: Path):
    """Test symlink creation for a file trigger."""
    trigger = tmp_path / "app.service.py"
    trigger.write_text("placeholder")

    instance = tmp_path / "instance"
    instance.mkdir()

    _create_symlink(trigger, instance)

    assert trigger.is_symlink()
    assert trigger.resolve() == instance.resolve()
```

### Step 7.4: Create test file `tests/test_watcher_toml_gen.py`

```python
# tests/test_watcher_toml_gen.py
"""Tests for devman.watcher.toml_gen."""

from pathlib import Path

from devman.watcher.toml_gen import generate_starter_config
from devman.watcher.config import DevmanWatchConfig


def test_generate_starter_config_creates_valid_toml(tmp_path: Path):
    output = tmp_path / "devman-watch.toml"
    generate_starter_config(output)

    assert output.exists()

    # Must be loadable by our config model
    config = DevmanWatchConfig.from_toml_file(output)
    assert len(config.patterns) == 1
    assert config.patterns[0].template == "python-module"
    assert config.settings.debounce_ms == 500
```

---

## Phase 8: Integration Testing and Final Verification

### Step 8.1: Run all tests

```bash
pytest tests/ -v
```

All existing tests (test_schemas, test_domain_errors, test_domain_models,
test_project_structure) must still pass. All new tests (test_watcher_*) must
also pass.

### Step 8.2: Manual integration test

Create a temporary project to test the full end-to-end flow:

```bash
# 1. Create a test project directory
mkdir -p /tmp/test-devman-watch/src/modules

# 2. Initialize devman (if not already done)
devman init

# 3. Generate a watch config
cd /tmp/test-devman-watch
devman watch-init

# 4. Edit devman-watch.toml to point to a real template
#    (use "file-type" since it's the built-in seed template)

# 5. Validate the config
devman watch-check

# 6. Start the watcher
devman watch

# 7. In another terminal, create a file matching the pattern
mkdir /tmp/test-devman-watch/src/modules/auth

# 8. Observe the watcher logs — you should see:
#    - "Match: src/modules/auth → pattern '...' → template '...'"
#    - "Instantiated: ..."
```

### Step 8.3: Verify existing commands still work

```bash
devman --help        # Should show init, bootstrap, project, update, watch, watch-init, watch-check
devman init          # Should still work (idempotent check)
devman bootstrap X   # Should still work
devman update ...    # Should still work
```

---

## File Change Summary

### New files to create

| File | Purpose |
|---|---|
| `src/devman/watcher/__init__.py` | Package marker |
| `src/devman/watcher/config.py` | Pydantic models for devman-watch.toml |
| `src/devman/watcher/engine.py` | DevmanWatcher class wrapping watchfiles |
| `src/devman/watcher/handlers.py` | Action handlers (copier, repo, symlink) |
| `src/devman/watcher/toml_gen.py` | Starter config generation |
| `tests/test_watcher_config.py` | Config model tests |
| `tests/test_watcher_engine.py` | Engine pattern matching tests |
| `tests/test_watcher_handlers.py` | Handler tests |
| `tests/test_watcher_toml_gen.py` | Config generation tests |

### Existing files to modify

| File | Change |
|---|---|
| `pyproject.toml` | Add `watchfiles>=1.0.0` to dependencies |
| `src/devman/constants.py` | Add `WATCH_CONFIG_NAME` constant |
| `src/devman/cli.py` | Add `watch`, `watch-init`, `watch-check` commands |

### Files NOT changed

All existing modules (`bootstrap.py`, `bootstrap_project.py`, `update.py`,
`domain/`, `schemas/`, `seed_templates/`) remain untouched. The refactor is
**additive** — it adds the watcher subsystem alongside the existing CLI
commands.

---

## Reference: Watchdantic Concepts Cheat Sheet

Quick reference for watchdantic concepts as they map to this refactor:

| Watchdantic concept | Devman equivalent | Notes |
|---|---|---|
| `watch.toml` | `devman-watch.toml` | Devman uses its own config format, not raw watchdantic config |
| `[engine]` | `[settings]` in devman config | Debounce, logging, ignore patterns |
| `[[watch]]` | Implicit — devman watches the `repo_root` | Single watch target (the project dir) |
| `[[action]]` | `handlers.py` functions | Python code, not shell commands |
| `[[rule]]` | `[[pattern]]` in devman config | Pattern → template mapping |
| `Engine.run_forever()` | `DevmanWatcher.run()` | Blocks main thread |
| `Engine.run_once()` | `DevmanWatcher.run_once()` | For testing |
| `FileEvent` | `(Change, path_str)` tuples from watchfiles | We use watchfiles directly |
| `event_matches_rule()` | `find_matching_pattern()` | Pure function, easy to test |
| `watchdantic run` | `devman watch` | CLI entry point |
| `watchdantic init` | `devman watch-init` | Generates starter config |
| `watchdantic check` | `devman watch-check` | Validates config |
| `SIGHUP` reload | Signal handler in DevmanWatcher | Config hot-reload |
| `debounce_ms` | `settings.debounce_ms` | Passed directly to `watchfiles.watch()` |
| `ignore_dirs` | `settings.ignore_dirs` | Checked in `_should_ignore()` |
| `ignore_globs` | `settings.ignore_globs` | Checked in `_should_ignore()` |
| `rule.on` | `pattern.on` | Event types: added, modified, deleted |
| `rule.match` | `pattern.pattern` | Glob patterns |
| `rule.exclude` | `pattern.exclude` | Exclusion globs |
| `rule.do` | `handle_instantiation()` | Always the same handler for devman |
| `max_workers` | Not needed initially | Sequential is fine for MVP |
| `continue_on_error` | Error handling in `handle_instantiation()` | Per-handler logic |

### Programmatic usage pattern (from watchdantic user guide)

```python
# What watchdantic's guide shows:
from watchdantic.engine.config_loader import load_config
from watchdantic.engine.engine import Engine

config = load_config(Path("watch.toml"))
engine = Engine(config, repo_root)
engine.run_forever()

# What devman does instead:
from devman.watcher.config import DevmanWatchConfig
from devman.watcher.engine import DevmanWatcher

config = DevmanWatchConfig.from_toml_file(Path("devman-watch.toml"))
watcher = DevmanWatcher(config, repo_root=Path("."))
watcher.run()
```

The key difference: devman skips watchdantic's action/rule/dispatch layer and
uses `watchfiles.watch()` directly, with its own pattern matching and Python
action handlers. This gives devman full control over what happens when a file
event matches, while still using the same underlying inotify-based detection
that watchdantic uses.
