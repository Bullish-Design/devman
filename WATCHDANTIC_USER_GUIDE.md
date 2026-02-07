# Watchdantic User Guide

Config-driven file watcher with shell command actions, powered by
[watchfiles](https://watchfiles.helpmanual.io/) +
[Pydantic](https://docs.pydantic.dev/).

Watchdantic monitors files and directories for changes, matches them against
glob patterns, and runs shell commands in response. All behaviour is defined in
a single TOML config file validated at startup by Pydantic.

**Platform:** Linux only | **Python:** 3.11+

---

## Table of Contents

- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
  - [Config File Structure](#config-file-structure)
  - [Engine Settings](#engine-settings)
  - [Watches](#watches)
  - [Actions](#actions)
  - [Rules](#rules)
- [Glob Pattern Matching](#glob-pattern-matching)
- [Action Environment Variables](#action-environment-variables)
- [CLI Reference](#cli-reference)
- [Hot Reloading](#hot-reloading)
- [Concurrency](#concurrency)
- [Error Handling](#error-handling)
- [Recipes](#recipes)
- [Programmatic Usage](#programmatic-usage)
- [Development](#development)

---

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Generate a starter config

```bash
watchdantic init
```

This creates a `watch.toml` in the current directory with a minimal working
configuration that echoes a message on any file change.

### 3. Validate the config

```bash
watchdantic check
```

Output confirms the config parsed correctly and summarises watches, actions, and
rules.

### 4. Start watching

```bash
watchdantic run
```

Watchdantic starts monitoring, logs matched events to the console, and runs the
configured actions. Press `Ctrl+C` to stop.

### 5. Customise

Open `watch.toml` and replace the starter echo action with something useful:

```toml
version = 1

[engine]
repo_root = "."
debounce_ms = 300
ignore_dirs = [".git", ".venv", "__pycache__"]
ignore_globs = ["**/*.pyc"]
log_level = "INFO"

[[watch]]
name = "repo"
paths = ["."]

[[action]]
name = "run_tests"
type = "command"
cmd = ["pytest", "-x", "-q"]
timeout_s = 300

[[rule]]
name = "test_on_py_change"
watch = "repo"
on = ["added", "modified"]
match = ["src/**/*.py", "tests/**/*.py"]
do = ["run_tests"]
```

Now every time a `.py` file under `src/` or `tests/` is created or modified,
pytest runs automatically.

---

## How It Works

Watchdantic processes file changes in a pipeline:

```
watch.toml
    |
    v
Load & validate config (Pydantic)
    |
    v
Start watch loops (one per [[watch]] block)
    |
    v
Detect file changes (watchfiles / inotify)
    |
    v
Normalize to FileEvent objects
    |
    v
Apply ignore_globs filter
    |
    v
Match events against [[rule]] blocks
  - event type in rule.on?
  - watch name matches rule.watch?
  - path matches rule.match globs?
  - path NOT in rule.exclude globs?
    |
    v
Dispatch matched rules to action runner
    |
    v
Execute [[action]] commands (sequential or concurrent)
```

Events are debounced (grouped within a time window) before processing. This
prevents rapid successive saves from triggering the same action dozens of times.

---

## Configuration

### Config File Structure

Watchdantic reads a `watch.toml` file with four sections:

| Section | Cardinality | Purpose |
|---------|-------------|---------|
| `[engine]` | Exactly one | Global settings (debounce, logging, concurrency) |
| `[[watch]]` | One or more | Directories/files to monitor |
| `[[action]]` | One or more | Shell commands to run |
| `[[rule]]` | One or more | Glue: when *watch* sees *event* matching *pattern*, run *action* |

Cross-references are validated at load time. A rule that references a
nonexistent watch or action causes a startup error, not a silent runtime
failure.

Names within each section must be unique. Duplicate watch, action, or rule names
are rejected during validation.

### Engine Settings

The `[engine]` block controls global behaviour.

```toml
[engine]
repo_root = "."
debounce_ms = 300
step_ms = 50
use_default_filter = true
ignore_dirs = [".git", ".venv", "__pycache__"]
ignore_globs = ["**/*.pyc", "**/.DS_Store"]
log_level = "INFO"
max_workers = 1
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `repo_root` | `str` | `"."` | Repository root, relative to the config file location. All watch paths and action `cwd` values are resolved relative to this. |
| `debounce_ms` | `int` | `300` | Debounce window in milliseconds. Events within this window are batched together. |
| `step_ms` | `int` | *(none)* | Polling step interval in milliseconds. Optional; omit to use the watchfiles default. |
| `use_default_filter` | `bool` | `true` | Use the watchfiles `DefaultFilter`, which ignores common non-source files. |
| `ignore_dirs` | `list[str]` | `[".git", ".venv", "__pycache__"]` | Directory names to ignore entirely. Applied by the watchfiles filter. |
| `ignore_globs` | `list[str]` | `[]` | Glob patterns to ignore. Applied *after* events are received, so they work on relative paths. |
| `log_level` | `str` | `"INFO"` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `max_workers` | `int` | `1` | Number of concurrent action workers. `1` means actions run sequentially. |

### Watches

Each `[[watch]]` block defines a set of paths to monitor.

```toml
[[watch]]
name = "backend"
paths = ["src", "lib"]
debounce_ms = 500
ignore_dirs = [".git", "__pycache__", "node_modules"]
ignore_globs = ["**/*.log"]
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | yes | Unique identifier. Referenced by rules via `watch = "backend"`. |
| `paths` | `list[str]` | yes | Paths to watch, relative to `repo_root`. Must not contain `..`. |
| `debounce_ms` | `int` | no | Override the engine-level debounce for this watch. |
| `use_default_filter` | `bool` | no | Override `engine.use_default_filter` for this watch. |
| `ignore_dirs` | `list[str]` | no | Override `engine.ignore_dirs` for this watch. |
| `ignore_globs` | `list[str]` | no | Override `engine.ignore_globs` for this watch. |

When override fields are omitted (`null`), the engine-level value is used.

Multiple watches run in separate threads, each with independent debounce
settings. A single watch runs in the main thread.

### Actions

Each `[[action]]` block defines a shell command.

```toml
[[action]]
name = "run_tests"
type = "command"
cmd = ["pytest", "-x", "-q"]
cwd = "."
timeout_s = 300
env = { "PYTHONUNBUFFERED" = "1" }
shell = false
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | yes | Unique identifier. Referenced by rules via `do = ["run_tests"]`. |
| `type` | `str` | yes | Action type. Currently only `"command"` is supported. |
| `cmd` | `list[str]` | yes | Command and arguments as an argv list. |
| `cwd` | `str` | no | Working directory, relative to `repo_root`. Defaults to `repo_root`. Must not contain `..`. |
| `env` | `dict[str, str]` | no | Extra environment variables merged into the process environment. |
| `timeout_s` | `int` | no | Kill the command after this many seconds. Minimum value is 1. |
| `shell` | `bool` | no | If `true`, the `cmd` list is joined into a single string and executed via the shell. Required for pipes, redirects, and shell variable expansion. Defaults to `false`. |

**When to use `shell = true`:**

```toml
# This needs shell features (pipe + redirect)
[[action]]
name = "build_and_log"
type = "command"
cmd = ["make build 2>&1 | tee build.log"]
shell = true
```

When `shell = false` (the default), commands are executed directly without a
shell, which is safer and avoids shell injection risks.

### Rules

Each `[[rule]]` block connects a watch to one or more actions via pattern
matching.

```toml
[[rule]]
name = "test_on_py_change"
watch = "repo"
on = ["added", "modified"]
match = ["src/**/*.py", "tests/**/*.py"]
exclude = ["tests/fixtures/**"]
do = ["run_tests"]
continue_on_error = false
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | yes | Unique identifier for this rule. |
| `watch` | `str` | yes | Name of a `[[watch]]` block. Only events from this watch are considered. |
| `on` | `list[str]` | yes | Event types to match: `"added"`, `"modified"`, `"deleted"`. |
| `match` | `list[str]` | yes | Glob patterns to match against the file's relative path. Uses OR logic: any match qualifies. |
| `exclude` | `list[str]` | no | Glob patterns to exclude. Uses OR logic: any exclude match disqualifies, even if `match` matched. Excludes are checked first. |
| `do` | `list[str]` | yes | Ordered list of action names to execute when the rule fires. |
| `continue_on_error` | `bool` | no | If `true`, continue executing remaining actions in `do` even if one fails. Defaults to `false` (stop on first failure). |

**Evaluation order for a single event:**

1. Is `event.change` in `rule.on`? If not, skip.
2. Is `event.watch_name` equal to `rule.watch`? If not, skip.
3. Does the relative path match any `rule.exclude` pattern? If yes, skip.
4. Does the relative path match any `rule.match` pattern? If yes, fire the rule.

---

## Glob Pattern Matching

Watchdantic uses segment-based glob matching on POSIX-style relative paths.

| Pattern | Meaning |
|---------|---------|
| `*` | Matches any characters within a single path segment (does not cross `/`) |
| `**` | Matches zero or more directory segments |
| `?` | Matches any single character |
| `[abc]` | Matches one of the listed characters |

### Examples

| Pattern | Matches | Does NOT Match |
|---------|---------|----------------|
| `*.py` | `foo.py` | `src/foo.py` |
| `**/*.py` | `foo.py`, `src/foo.py`, `a/b/c/foo.py` | `foo.txt` |
| `src/**/*.py` | `src/foo.py`, `src/a/b/foo.py` | `lib/foo.py` |
| `src/*.py` | `src/foo.py` | `src/a/foo.py` |
| `docs/**` | `docs/index.md`, `docs/a/b.txt` | `src/docs/x.md` |
| `**/*.test.js` | `foo.test.js`, `src/foo.test.js` | `foo.test.ts` |

Multiple patterns in `match` or `exclude` use OR logic. A file matches the rule
if it matches *any* of the `match` patterns and *none* of the `exclude`
patterns.

---

## Action Environment Variables

Every action receives these environment variables in addition to the inherited
process environment:

| Variable | Description |
|----------|-------------|
| `WATCHDANTIC_REPO_ROOT` | Absolute path to the repository root |
| `WATCHDANTIC_RULE_NAME` | Name of the rule that fired |
| `WATCHDANTIC_WATCH_NAME` | Name of the watch that detected changes |
| `WATCHDANTIC_EVENT_COUNT` | Number of file events in this batch (string) |
| `WATCHDANTIC_EVENTS_JSON` | JSON array of event objects |

### Events JSON structure

Each element in `WATCHDANTIC_EVENTS_JSON` has this shape:

```json
{
  "change": "modified",
  "path_abs": "/home/user/myproject/src/app.py",
  "path_rel": "src/app.py",
  "is_dir": false,
  "watch_name": "repo"
}
```

You can use these in scripts to implement conditional logic based on which files
changed:

```bash
#!/bin/bash
# deploy.sh — only deploy if config files changed
echo "$WATCHDANTIC_EVENTS_JSON" | python3 -c "
import json, sys
events = json.load(sys.stdin)
config_changed = any(e['path_rel'].startswith('config/') for e in events)
if config_changed:
    print('Config changed, reloading...')
"
```

Variables defined in the action's `env` field are merged on top and can
override the watchdantic variables if needed.

---

## CLI Reference

```
watchdantic [--version] <command> [options]
```

### `watchdantic run`

Start the file watching engine.

```bash
watchdantic run                  # Use auto-discovered watch.toml
watchdantic run -c path/to.toml  # Use a specific config file
```

- Writes PID to `.watchdantic.pid` in the repo root
- Handles `SIGHUP` for hot reloading
- Stop with `Ctrl+C`

### `watchdantic check`

Validate config and exit without starting the watcher.

```bash
watchdantic check
watchdantic check -c path/to.toml
```

Prints a summary of watches, actions, and rules on success. Prints errors to
stderr and exits with code 1 on failure. Use this in CI to catch config errors.

### `watchdantic reload`

Send `SIGHUP` to a running instance to reload its config.

```bash
watchdantic reload
watchdantic reload --pid-file /path/to/.watchdantic.pid
```

Reads the PID from `.watchdantic.pid` (or the specified file) and sends
`SIGHUP`. The running instance re-reads `watch.toml` and restarts its watch
loops with the new config.

### `watchdantic init`

Generate a starter `watch.toml`.

```bash
watchdantic init                  # Creates watch.toml
watchdantic init -o custom.toml   # Custom output path
watchdantic init --force          # Overwrite existing file
```

### Config discovery

When no `-c` flag is given, watchdantic searches for `watch.toml` starting from
the current directory and walking up toward the filesystem root. This lets you
run `watchdantic run` from any subdirectory within your project.

---

## Hot Reloading

You can update the config of a running instance without restarting:

```bash
# Edit watch.toml, then either:
watchdantic reload

# Or send the signal directly:
kill -HUP $(cat .watchdantic.pid)
```

On reload, the engine:

1. Re-reads and validates `watch.toml`
2. Stops all current watch loops
3. Creates a new dispatcher with the updated rules and actions
4. Restarts watch loops with the new configuration

If the new config is invalid, the reload fails with a logged error and the
running instance continues with the previous config.

---

## Concurrency

The `max_workers` setting in `[engine]` controls how actions are executed:

- **`max_workers = 1`** (default): Actions run sequentially. If a rule triggers
  two actions, the second waits for the first to complete. This is the safest
  option and avoids race conditions between actions.

- **`max_workers > 1`**: Actions from different rules can run concurrently using
  a thread pool. Actions within the same rule's `do` list still run in order.

Multiple `[[watch]]` blocks always run in separate threads regardless of
`max_workers`. A single watch block runs in the main thread.

---

## Error Handling

### Config errors

Invalid config is caught at load time with clear error messages:

- Missing required fields
- Type mismatches
- Duplicate names
- Dangling references (rule references nonexistent watch or action)
- Path traversal attempts (`..` in paths)

Use `watchdantic check` to validate before running.

### Action failures

When an action exits with a non-zero code:

- The exit code, stdout, and stderr are logged
- If `continue_on_error = false` (default), remaining actions in the rule's `do`
  list are skipped
- If `continue_on_error = true`, execution continues with the next action

When an action times out:

- The process is killed
- The result is logged with `timed_out = true`
- The same `continue_on_error` logic applies

### Watch loop crashes

If a watch loop encounters an unexpected error, it logs the exception and stops.
Other watch loops continue running.

### Exception hierarchy

```
WatchdanticError (base)
├── ConfigurationError   — config parsing / validation
└── ActionError          — command execution failures (e.g., binary not found)
```

---

## Recipes

### Run tests on Python changes

```toml
[[action]]
name = "pytest"
type = "command"
cmd = ["pytest", "-x", "-q"]
timeout_s = 300

[[rule]]
name = "test_on_change"
watch = "repo"
on = ["added", "modified"]
match = ["src/**/*.py", "tests/**/*.py"]
do = ["pytest"]
```

### Rebuild docs on Markdown changes

```toml
[[action]]
name = "build_docs"
type = "command"
cmd = ["bash", "-lc", "make -C docs html"]
cwd = "."
timeout_s = 120
env = { "PYTHONUNBUFFERED" = "1" }

[[rule]]
name = "docs_on_md"
watch = "repo"
on = ["added", "modified"]
match = ["docs/**/*.md", "content/**/*.md"]
exclude = ["docs/_build/**"]
do = ["build_docs"]
```

### Lint on save

```toml
[[action]]
name = "lint"
type = "command"
cmd = ["ruff", "check", "--fix", "."]
timeout_s = 60

[[rule]]
name = "lint_python"
watch = "repo"
on = ["added", "modified"]
match = ["**/*.py"]
exclude = ["**/__pycache__/**"]
do = ["lint"]
```

### Chain multiple actions

Actions in `do` run in order. Use `continue_on_error` to control whether the
chain stops on failure:

```toml
[[action]]
name = "typecheck"
type = "command"
cmd = ["mypy", "src"]
timeout_s = 120

[[action]]
name = "test"
type = "command"
cmd = ["pytest", "-x", "-q"]
timeout_s = 300

[[rule]]
name = "check_and_test"
watch = "repo"
on = ["modified"]
match = ["src/**/*.py"]
do = ["typecheck", "test"]
continue_on_error = false
```

Here, `test` only runs if `typecheck` succeeds.

### Watch separate directories independently

```toml
[[watch]]
name = "frontend"
paths = ["frontend/src"]
debounce_ms = 200

[[watch]]
name = "backend"
paths = ["backend/src"]
debounce_ms = 500

[[action]]
name = "build_frontend"
type = "command"
cmd = ["npm", "run", "build"]
cwd = "frontend"
timeout_s = 60

[[action]]
name = "run_backend_tests"
type = "command"
cmd = ["pytest", "-x"]
cwd = "backend"
timeout_s = 300

[[rule]]
name = "build_on_frontend_change"
watch = "frontend"
on = ["added", "modified"]
match = ["**/*.tsx", "**/*.ts"]
do = ["build_frontend"]

[[rule]]
name = "test_on_backend_change"
watch = "backend"
on = ["added", "modified"]
match = ["**/*.py"]
do = ["run_backend_tests"]
```

### Notify on file deletions

```toml
[[action]]
name = "notify_delete"
type = "command"
cmd = ["echo", "File deleted!"]

[[rule]]
name = "on_delete"
watch = "repo"
on = ["deleted"]
match = ["**/*"]
do = ["notify_delete"]
continue_on_error = true
```

### Use shell features

```toml
[[action]]
name = "count_changes"
type = "command"
cmd = ["echo \"$WATCHDANTIC_EVENT_COUNT files changed\" >> /tmp/change.log"]
shell = true
```

---

## Programmatic Usage

You can use watchdantic's engine directly from Python:

```python
from pathlib import Path
from watchdantic.engine.config_loader import load_config
from watchdantic.engine.engine import Engine

config_path = Path("watch.toml")
config = load_config(config_path)
repo_root = config.resolve_paths(config_path.parent)

engine = Engine(config, repo_root)

# Run until interrupted
engine.run_forever()

# Or process one batch (useful in tests)
events = engine.run_once(timeout_s=5.0)
```

### Loading and inspecting config

```python
from pathlib import Path
from watchdantic.engine.config_loader import load_config, find_config

# Auto-discover watch.toml
config_path = find_config()

# Or load a specific file
config = load_config(Path("watch.toml"))

print(f"Watches: {[w.name for w in config.watch]}")
print(f"Actions: {[a.name for a in config.action]}")
print(f"Rules:   {[r.name for r in config.rule]}")
```

### Matching events manually

```python
from pathlib import Path
from watchdantic.engine.events import FileEvent
from watchdantic.engine.matcher import event_matches_rule
from watchdantic.engine.config_models import RuleConfig

event = FileEvent(
    change="modified",
    path_abs=Path("/repo/src/app.py"),
    path_rel=Path("src/app.py"),
    is_dir=False,
    watch_name="repo",
)

rule = RuleConfig(
    name="test",
    watch="repo",
    on=["modified"],
    match=["src/**/*.py"],
    do=["run_tests"],
)

assert event_matches_rule(event, rule)
```

---

## Development

### Setup

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
pytest tests/ -v
```

### Lint

```bash
ruff check src/ tests/
```

### Project layout

```
src/watchdantic/
├── __init__.py              # Package version
├── cli.py                   # CLI entry point and subcommands
├── exceptions.py            # WatchdanticError, ConfigurationError, ActionError
└── engine/
    ├── config_models.py     # Pydantic models for watch.toml
    ├── config_loader.py     # TOML parsing, config discovery
    ├── engine.py            # Core Engine class (watch loops, lifecycle)
    ├── events.py            # FileEvent dataclass, normalization
    ├── matcher.py           # Glob matching, rule evaluation
    ├── dispatcher.py        # Rule-to-action dispatch (sequential/concurrent)
    └── actions/
        ├── runner.py        # Action execution dispatcher
        └── command.py       # Shell command executor, ActionResult
```
