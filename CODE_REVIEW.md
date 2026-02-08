# Devman Library — Code Review

**Date:** 2026-02-08
**Scope:** Full library review post-watchdantic refactor
**Reference documents:** `WATCHDANTIC_REFACTOR_GUIDE.md`, `CONCEPT_OVERVIEW.md`, `WATCHDANTIC_USER_GUIDE.md`

---

## Executive Summary

The watchdantic refactor has been successfully completed. The new `watcher/` package implements all eight phases from the refactor guide: config models, a reactive engine, action handlers, three new CLI commands (`watch`, `watch-init`, `watch-check`), starter config generation, and comprehensive tests. The refactor is additive — existing modules (`bootstrap.py`, `bootstrap_project.py`, `update.py`, `domain/`, `schemas/`) are untouched and the original CLI commands remain intact.

The code is well-structured, idiomatic, and demonstrates strong Pydantic v2 usage throughout. The review below calls out specific issues organized by severity.

---

## Table of Contents

- [Refactor Guide Compliance](#refactor-guide-compliance)
- [Critical Issues](#critical-issues)
- [High-Severity Issues](#high-severity-issues)
- [Medium-Severity Issues](#medium-severity-issues)
- [Low-Severity / Nits](#low-severity--nits)
- [File-by-File Review](#file-by-file-review)
- [Test Coverage Assessment](#test-coverage-assessment)
- [Architecture & Design Notes](#architecture--design-notes)
- [Summary Scorecard](#summary-scorecard)

---

## Refactor Guide Compliance

| Phase | Requirement | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Add `watchfiles` dependency to `pyproject.toml` | Done | Line 17 |
| 1 | Create `watcher/__init__.py` | Done | Exports public API |
| 1 | Add `WATCH_CONFIG_NAME` constant | Done | `constants.py:11` |
| 2 | `PatternMapping` / `PatternConfig` model | Done | Named `PatternConfig`; adds `name` field beyond guide spec |
| 2 | `WatchSettings` / `SettingsConfig` model | Done | Named `SettingsConfig`; adds `CRITICAL` log level beyond guide |
| 2 | `DevmanWatchConfig` with `from_toml_file()` | Done | Uses `model_validate()` instead of manual `cls(**data)` — better |
| 2 | `to_toml_file()` serialization method | **Missing** | Guide specifies a `to_toml_file()` on `DevmanWatchConfig`; not implemented |
| 2 | `get_template_for_pattern()` lookup method | **Missing** | Guide specifies this helper; not implemented |
| 3 | `DevmanWatcher` class with `run()` / `run_once()` | Done | Clean implementation |
| 3 | `find_matching_pattern()` pure function | Done | Well-tested |
| 3 | Signal handlers (SIGHUP/SIGINT/SIGTERM) | **Missing** | Guide specifies signal handling for reload/shutdown |
| 4 | `handle_instantiation()` orchestrator | Done | Improved over guide with DI for testability |
| 4 | `_run_copier()` / `run_copier_instantiation()` | Done | |
| 4 | `_init_repo()` / `initialize_instance_repository()` | Done | jj-preferred, git-fallback |
| 4 | `_create_symlink()` / `replace_source_with_symlink()` | Done | Adds safety check for unrelated symlinks |
| 5 | `devman watch` CLI command | Done | |
| 5 | `devman watch-init` CLI command | Done | |
| 5 | `devman watch-check` CLI command | Done | |
| 5 | `devman instantiate` CLI command | Done | **Bonus** — not in guide, useful for debugging |
| 6 | `toml_gen.py` starter config generation | Done | Uses raw string instead of `tomli_w` (see notes) |
| 7 | `test_watcher_config.py` | Done | |
| 7 | `test_watcher_engine.py` | Done | |
| 7 | `test_watcher_handlers.py` | Done | |
| 7 | `test_watcher_toml_gen.py` | Done | |
| 8 | All existing tests still pass | **Untestable** | See Python version issue below |

---

## Critical Issues

### C1. `pyproject.toml` requires Python >= 3.13, but code uses 3.11 compatibility shims

**File:** `pyproject.toml:9`, `watcher/config.py:7-10`, `watcher/engine.py:10-21`

The project declares `requires-python = ">=3.13"`, yet the config and engine modules include `try: import tomllib / except: import tomli` and a full `Change` enum fallback for missing `watchfiles`. These compatibility shims are appropriate for a `>=3.11` project but contradictory with the `>=3.13` floor.

**Impact:** Either the floor is too high (users on 3.11/3.12 are excluded but the code would work for them) or the shims are dead code that can never execute. This should be reconciled — pick one stance.

**Recommendation:** If 3.13+ is the real target, remove the `tomli` fallback and the `Change` enum stub. If broader compatibility is desired, lower the floor to `>=3.11` and add `tomli` as a dependency for `<3.11` (or just `>=3.11` since `tomllib` ships with 3.11+, making the `tomli` fallback unreachable anyway).

### C2. `WatchError` dataclass inherits `message` but has no body

**File:** `domain/errors.py:38-41`

```python
@dataclass(frozen=True)
class WatchError(DomainError):
    """Generic error for watcher domain operations."""
```

`DomainError` defines `message: str` as a required field. Since `WatchError` is also a frozen dataclass inheriting from `DomainError`, it inherits the `message` field and works correctly at runtime. However, the class body is completely empty — no `pass`, no additional fields. While syntactically valid (the docstring serves as the body), this is misleading to readers who may wonder whether it's an unfinished stub.

More importantly, `WatchError` is raised in `handlers.py` as `WatchError("some message")`, which works because it inherits the `message` positional arg from `DomainError`. But this relies on implicit inheritance of dataclass fields, which is fragile if anyone later adds a field to the subclass. Adding an explicit `pass` or a comment clarifying the inheritance intent would be helpful.

---

## High-Severity Issues

### H1. `handle_instantiation()` signature uses mutable `None` defaults for callable parameters

**File:** `watcher/handlers.py:59-62`

```python
def handle_instantiation(
    ...
    resolve_instance_path_fn: Callable[..., Path] = None,
    run_copier_fn: Callable[..., None] = None,
    init_repo_fn: Callable[..., None] = None,
    replace_path_fn: Callable[..., None] = None,
) -> Path:
```

The type annotations say `Callable[..., Path]` but the default is `None`. This is a type error — `None` is not a `Callable`. The correct annotation is `Callable[..., Path] | None = None`. This will fail under `mypy --strict`.

**Lines 65-68** then reassign: `resolve_instance_path_fn = resolve_instance_path_fn or resolve_target_instance_path`. This pattern is fine functionally but the type signature is misleading.

### H2. `_matches_glob()` uses `fnmatch` which has different semantics than `pathlib.PurePosixPath.match()`

**File:** `watcher/engine.py:173-182`

The refactor guide specifies using `pathlib.PurePosixPath.match()` for glob matching. The implementation uses `fnmatch.fnmatch()` instead. These have different semantics:

- `fnmatch("src/modules/core/README.md", "*.md")` returns `False` (fnmatch treats `/` as ordinary characters in the pattern `*`)
- `PurePosixPath("src/modules/core/README.md").match("*.md")` returns `True` (match checks the final component)

The `fnmatch` approach is actually more predictable for path-based matching and aligns with how watchdantic itself works. However, this is a deliberate deviation from the guide that should be documented. It also means `**` patterns may not work as users expect — `fnmatch` does not support `**` as "zero or more directories". For example:

- `fnmatch("src/foo.py", "**/*.py")` returns `True` only by accident (the `**` matches `src` and `*` matches `foo`).
- `fnmatch("foo.py", "**/*.py")` returns `False` — because `**` expects at least one character before `/`.

This could cause surprising behavior for patterns like `**/*.py` not matching root-level files.

### H3. `replace_source_with_symlink()` always uses `target_is_directory=True`

**File:** `watcher/handlers.py:174`

```python
source_path.symlink_to(instance_path, target_is_directory=True)
```

This hardcodes `target_is_directory=True` regardless of whether the trigger was a file or directory. Per `CONCEPT_OVERVIEW.md`, file triggers should symlink to the instance root or to a file within `output/`. The guide's `_create_symlink()` checks for an `output/` subdirectory and adjusts the symlink target accordingly. The current implementation does not implement this output-directory preference logic at all.

### H4. No `--force` flag on `watch-init` command

**File:** `cli.py:217-238`

The refactor guide specifies a `--force` flag on `watch-init` to allow overwriting an existing config file. The implementation relies on `generate_starter_config()` raising `FileExistsError` but provides no way for the user to bypass this. This is a missing feature from the guide spec.

### H5. `toml_gen.py` uses a raw string instead of `tomli_w`

**File:** `watcher/toml_gen.py:7-21`

The refactor guide specifies using `tomli_w.dump()` to generate the starter config (Phase 6). The implementation uses a hardcoded `_STARTER_CONFIG` string literal instead. While this produces deterministic output (which the tests verify), it means the starter config format is not validated by the same TOML serialization path that `DevmanWatchConfig` uses. If the TOML syntax in the string is wrong, it would only be caught when someone tries to load it.

The tests do verify that the generated file is loadable (`DevmanWatchConfig.from_toml_file(output_path)` in `test_watcher_toml_gen.py:34`), which mitigates this concern. But the approach diverges from the guide.

---

## Medium-Severity Issues

### M1. `instance_store` default path inconsistency

**File:** `watcher/config.py:76` vs `CONCEPT_OVERVIEW.md`

`SettingsConfig` defaults `instance_store` to `"~/.devman-store/instances"`, but the `CONCEPT_OVERVIEW.md` example shows instances at `"~/.devman-store/instances/"` with a trailing slug. The existing `bootstrap.py` places file types directly under `~/.devman-store/` (e.g., `~/.devman-store/pyproject.toml/`). The watcher's instance naming scheme (`{repo}-{template}-{slug}`) creates a parallel hierarchy under `instances/`.

This is architecturally reasonable (separating manual bootstraps from automatic instantiations) but the two naming schemes are never reconciled. A user running `devman bootstrap` and `devman watch` will have instances scattered across two different locations with incompatible naming conventions.

### M2. `DevmanWatcher.run()` does not write a PID file

**File:** `watcher/engine.py:44-60`

The watchdantic user guide mentions that `watchdantic run` writes a PID to `.watchdantic.pid`. The devman watcher does not write a PID file, which means there's no way to send `SIGHUP` for config reload (which is also not implemented — see compliance table). This is fine for MVP but worth noting for daemon-mode robustness.

### M3. No validation that `pattern` and `template` are non-empty after stripping in `PatternConfig`

**File:** `watcher/config.py:35-43`

The `validate_non_empty_strings` validator strips whitespace and rejects empty strings, which is good. However, the `model_validator` on `DevmanWatchConfig` (lines 97-104) then checks `if not pattern.pattern` — but by this point the field validator has already ensured it's non-empty (or rejected it). The model validator is redundant and can never trigger for the pattern/template case. This is dead code.

### M4. `run_once()` normalizes changes but `_process_changes()` normalizes again

**File:** `watcher/engine.py:62-65` and `watcher/engine.py:70`

```python
def run_once(self, changes):
    normalized = {(self._normalize_change(change), str(path)) for change, path in changes}
    return self._process_changes(normalized)

def _process_changes(self, changes):
    for change, changed_path in changes:
        change_name = self._normalize_change(change)  # Double normalization
```

`run_once()` normalizes `Change` enums to strings, then `_process_changes()` normalizes them again. The second call is harmless (normalizing an already-lowercase string returns the same string) but it's unnecessary work and obscures the data flow. `run()` calls `_process_changes()` with raw `Change` enums from `watchfiles`, so the normalization in `_process_changes()` is needed for that path. The fix would be to not normalize in `run_once()` and let `_process_changes()` handle it, or to have `_process_changes()` skip normalization when the input is already a string.

### M5. Bare `except Exception` in handler dispatch swallows all errors

**File:** `watcher/engine.py:114`

```python
except Exception:
    logger.exception("watcher handler failed", ...)
```

This catches all exceptions including programming errors like `TypeError`, `AttributeError`, etc. While `logger.exception` does log the traceback, the watcher silently continues. For a daemon this is defensible (you don't want one bad event to crash the watcher), but it could mask bugs during development. Consider catching a narrower exception type or at least re-raising in a debug mode.

### M6. `bootstrap.py` hardcodes paths instead of using `constants.py`

**File:** `bootstrap.py:12-13`, `bootstrap.py:85-87`

```python
store_root = Path.home() / ".devman-store"
devman_path = store_root / "devman"
```

The `constants.py` module defines `STORE_ROOT`, `DEVMAN_META_DIR`, and `TEMPLATES_DIR` for exactly this purpose, but `bootstrap.py` reconstructs these paths from scratch. Same issue in `bootstrap_project.py:19-20` and `update.py:18-19`. This creates a maintenance risk if the store path ever changes.

### M7. `bootstrap_project.py` executes arbitrary Python from `.devman-bootstrap.py`

**File:** `bootstrap_project.py:46-55`

```python
bootstrap_script = target_dir / ".devman-bootstrap.py"
if bootstrap_script.exists():
    result = subprocess.run(
        ["python", str(bootstrap_script)],
        cwd=target_dir, ...
    )
```

This executes an arbitrary Python script that was just generated by a copier template. While this is by design (templates can include bootstrap scripts), it's worth noting that this executes with the full permissions of the devman process. There's no sandboxing or user confirmation. The script path is also hardcoded rather than being configurable.

### M8. `cli.py` update command has significant code duplication

**File:** `cli.py:96-177`

The `update` command has two nearly identical branches (file-type vs project), each ~40 lines, differing only in which update function is called and minor message wording. This could be extracted into a shared helper.

---

## Low-Severity / Nits

### L1. `from __future__ import annotations` is unnecessary for Python >= 3.13

**Files:** All source files

If the `requires-python >= 3.13` constraint is kept, the `from __future__ import annotations` imports are unnecessary since PEP 563 behavior can be relied upon natively. Not harmful, just redundant.

### L2. Unused `TYPE_CHECKING` import opportunity

**File:** `watcher/engine.py:6`

The `Callable`, `Iterable`, `Iterator`, `Sequence` imports from `collections.abc` are used in type annotations. With `from __future__ import annotations`, these could be placed under `if TYPE_CHECKING:` to avoid runtime import cost. Minor optimization.

### L3. `typing.Optional` used alongside `X | None` syntax

**Files:** `bootstrap.py:6`, `bootstrap_project.py:5`, `update.py:5`

Pre-refactor modules use `Optional[Path]` while post-refactor modules use `Path | None`. This inconsistency is cosmetic but could be standardized.

### L4. `schemas/copier.py` silently swallows parsing errors

**File:** `schemas/copier.py:56-61`

```python
try:
    questions_typed[name] = parse_question(name, spec)
except Exception:
    questions_typed[name] = spec
```

Bare `except Exception` silently falls back to the raw dict on any parsing failure. This makes debugging difficult when a question spec is almost-valid. Consider logging a warning.

### L5. `test_project_structure.py` uses relative paths

**File:** `tests/test_project_structure.py:6-30`

Tests use relative `Path("src/devman/...")` which only works if `pytest` is run from the repo root. This is fragile — if someone runs `pytest` from a different directory, these tests will fail. Consider using `Path(__file__).parent.parent / "src/..."` or a fixture.

### L6. `_STARTER_CONFIG` in `toml_gen.py` includes `"modified"` in `on` events

**File:** `watcher/toml_gen.py:11`

The starter config sets `on = ["added", "modified"]` for the example pattern. Per `CONCEPT_OVERVIEW.md`, the typical use case is `on = ["added"]` only (you want to instantiate when a new file appears, not every time it's modified). This could cause unexpected re-triggering for users who use the starter as-is.

### L7. Dev dependency versions are pinned to old releases

**File:** `pyproject.toml:21-26`

```toml
dev = [
    "pytest==7.4.2",
    "pytest-cov==4.1.0",
    "ruff==0.1.6",
    "mypy==1.6.1",
]
```

These are from late 2023. Current versions (as of early 2026) are significantly newer. Pinning exact versions in dev deps is fine for reproducibility, but these should be updated periodically. `ruff==0.1.6` in particular is very old and missing many rules and fixes.

### L8. `_normalize_change` is a `@staticmethod` on `DevmanWatcher` but called from module-level `find_matching_pattern`

**File:** `watcher/engine.py:154`

```python
change_name = DevmanWatcher._normalize_change(change)
```

A module-level function reaching into a class for a static method is an odd coupling. `_normalize_change` should either be a standalone module-level function or `find_matching_pattern` should be a method on `DevmanWatcher`.

---

## File-by-File Review

### `src/devman/__init__.py`
Clean. Version string only. No issues.

### `src/devman/constants.py`
Clean. All path constants properly defined. `WATCH_CONFIG_NAME` added per guide. Minor: `WORKFLOWS_DIR` is defined but never imported elsewhere — verify it's needed.

### `src/devman/cli.py`
**Strengths:** Good error handling with `ValidationError` details printed per-field. Lazy imports keep startup fast. The `instantiate` command is a useful addition beyond the guide spec.

**Issues:** Missing `--force` on `watch-init` (H4). `--root`/`-r` option from guide spec missing on `watch` command (it always uses `Path.cwd()`). Significant duplication in `update` command (M8).

### `src/devman/bootstrap.py`
**Strengths:** Straightforward copier invocation. Version metadata capture is clean.

**Issues:** Hardcoded paths instead of constants (M6). No `shutil.which("git")` or `shutil.which("copier")` check before subprocess calls — will produce confusing `FileNotFoundError` if either binary is missing. `subprocess.run(..., check=True)` in `init_devman_store` means a git failure produces a raw `CalledProcessError` rather than a user-friendly message.

### `src/devman/bootstrap_project.py`
**Strengths:** Clean metadata handling with `tomllib`/`tomli_w`. Bootstrap script execution is a sensible extension point.

**Issues:** Arbitrary code execution (M7). Hardcoded paths (M6). Uses `"python"` rather than `sys.executable` for the bootstrap script — could invoke the wrong Python.

### `src/devman/update.py`
**Strengths:** Dry-run support is well implemented. Return dicts provide structured feedback.

**Issues:** Hardcoded paths (M6). `update_file_type()` returns a dict with different keys on success vs failure (`"message"` vs `"error"`) — the caller in `cli.py` has to handle both shapes. Consider a unified result model.

### `src/devman/domain/errors.py`
**Strengths:** Frozen dataclasses for exceptions are immutable and well-structured. Hierarchy is clear.

**Issues:** `WatchError` empty body (C2). `PathNotFoundError` and `PathNotDirectoryError` override `__str__` but also inherit `message` as a required field — creating them requires passing both `message=""` and `path=...`, which is awkward (visible in `test_domain_errors.py:8` where `message=""` is explicitly passed). Consider making `message` optional or computed from `path`.

### `src/devman/domain/models.py`
Clean. `ValidationResult` is well-designed with `is_valid` property and builder methods. No issues.

### `src/devman/schemas/questions.py`
**Strengths:** Excellent Pydantic v2 discriminated union usage. `parse_question()` factory with backward compatibility (`str` + `choices` -> `choice`) is thoughtful.

No issues.

### `src/devman/schemas/copier.py`
**Strengths:** Round-trip YAML serialization. Structured validation with `ValidationResult`.

**Issues:** Silent exception swallowing (L4). `to_yaml_file()` only outputs fields that are truthy — an empty `skip_if_exists: []` won't be written back, which could be surprising for round-trip fidelity.

### `src/devman/schemas/tasks.py`
Clean. Minimal and correct. No issues.

### `src/devman/watcher/__init__.py`
Clean. Exports the public API surface. No issues.

### `src/devman/watcher/config.py`
**Strengths:** Strong validation — normalizes whitespace and case, rejects empty strings, validates event types and log levels. `CRITICAL` log level is supported beyond the guide spec. `model_validate()` is used correctly for TOML loading.

**Issues:** Missing `to_toml_file()` and `get_template_for_pattern()` from guide spec. Redundant model validator (M3). The `tomli` fallback is unreachable if Python >= 3.13 is enforced (C1).

### `src/devman/watcher/engine.py`
**Strengths:** Clean separation — `find_matching_pattern()` is a pure function, easily testable. `DevmanWatcher` accepts a `watch_factory` for testing the run loop without real filesystem watching. Handler dispatch is pluggable via constructor injection. Structured logging with `extra` dicts throughout.

**Issues:** `fnmatch` vs `pathlib` glob semantics (H2). Double normalization (M4). Static method coupling (L8). `Change` enum fallback is unreachable under Python >= 3.13 (C1). No signal handling (compliance table).

### `src/devman/watcher/handlers.py`
**Strengths:** Best file in the watcher package. Clean orchestration in `handle_instantiation()`. Dependency injection for all side-effects makes testing excellent. `replace_source_with_symlink()` has a safety check against replacing unrelated symlinks. `_path_to_slug()` is simple and correct. `DEFAULT_HANDLERS` tuple at module level is a nice pattern for extensibility.

**Issues:** Type annotations on callable params (H1). No `output/` directory preference for symlink targets (H3). `handle_pattern_match` catches `WatchError` and logs as warning — this means template-not-found, instance-already-exists, etc. are all silently swallowed at the handler dispatch level. Appropriate for daemon mode but could use a counter/metric for observability.

### `src/devman/watcher/toml_gen.py`
**Strengths:** Deterministic output. `open("x")` mode for atomic refuse-to-overwrite. Creates parent dirs.

**Issues:** Uses raw string instead of `tomli_w` (H5). Starter config has `on = ["added", "modified"]` which may surprise users (L6).

---

## Test Coverage Assessment

### Watcher Tests (new, post-refactor)

| Test File | Tests | Coverage | Quality |
|-----------|-------|----------|---------|
| `test_watcher_config.py` | 3 tests (1 parametrized with 4 cases) | Config loading, normalization, validation errors, defaults | Good |
| `test_watcher_engine.py` | 5 tests | Pattern matching, excludes, directory patterns, ignore filters, handler dispatch + error resilience | Excellent |
| `test_watcher_handlers.py` | 6 tests | Instance path resolution, full instantiation workflow with DI, symlink safety, copier subprocess, jj detection | Excellent |
| `test_watcher_toml_gen.py` | 2 tests | Deterministic output, overwrite protection | Good |
| `test_cli.py` | 2 tests | `instantiate` command path resolution, missing config handling | Adequate |

### Pre-existing Tests

| Test File | Tests | Coverage | Quality |
|-----------|-------|----------|---------|
| `test_schemas.py` | 15 tests | All question types, tasks, copier config round-trip, validation, backward compat | Excellent |
| `test_domain_errors.py` | 2 tests | Error message formatting | Minimal |
| `test_domain_models.py` | 2 tests | ValidationResult tracking | Adequate |
| `test_project_structure.py` | 4 tests | File existence checks, copier importable | Basic smoke tests |

### Coverage Gaps

1. **No tests for `bootstrap.py`** — `init_devman_store()`, `bootstrap_file_type()`, `get_current_devman_version()` are all untested. These involve subprocess calls that would need mocking.
2. **No tests for `bootstrap_project.py`** — `bootstrap_project()` is untested.
3. **No tests for `update.py`** — `update_file_type()` and `update_project()` are untested.
4. **No tests for CLI commands** `init`, `bootstrap`, `project`, `update` — only `instantiate` has CLI tests.
5. **No test for `DevmanWatcher.run()`** — the blocking loop is untested (only `run_once()` is tested). The `watch_factory` injection makes this testable; a test could inject a factory that yields one batch then stops.
6. **No edge case tests for `_matches_glob()`** — root-level files with `**/*.py` patterns, deeply nested paths, patterns with `?` or `[abc]` character classes.
7. **`replace_source_with_symlink` not tested for the file-trigger case** — only the unrelated-symlink-rejection case is tested. The happy path (file removed, symlink created) is not directly tested (only indirectly via `test_handle_instantiation_executes_steps_with_injected_functions` which uses a fake replacement function).

---

## Architecture & Design Notes

### What works well

1. **Additive refactor** — The watcher subsystem is cleanly isolated in its own package. No existing code was modified beyond adding the constant and CLI commands. This minimizes risk.

2. **Dependency injection in handlers** — `handle_instantiation()` accepts optional function parameters for every side-effect (copier, repo init, symlink). This makes the orchestration logic testable without touching the filesystem or invoking subprocesses. This is better than what the guide specified.

3. **Handler chain pattern** — `DEFAULT_HANDLERS` as a tuple of callables, injected via `DevmanWatcher.__init__`, is a clean extensibility point. Adding logging handlers, metrics handlers, or notification handlers is trivial.

4. **Structured logging** — Consistent use of `extra={}` dicts with `event`, `path`, `pattern`, `template` keys enables structured log aggregation. This is production-quality.

5. **Pydantic validation** — Input normalization (whitespace stripping, case normalization) happens at the model layer, so all consumers get clean data. Validation errors are surfaced with field-level detail in the CLI.

### What could be improved

1. **No shared result type** — `bootstrap.py`, `update.py`, and `handlers.py` all return raw `dict` objects with ad-hoc keys. A shared `OperationResult` Pydantic model would provide type safety and consistency.

2. **No unified path resolution** — Constants are defined in `constants.py` but not used by the pre-refactor modules. The watcher uses `config.settings.instance_store` / `config.settings.template_store` (strings expanded at call sites). A centralized `PathResolver` or at least consistent use of constants would reduce duplication.

3. **Cascading instantiation is implicit** — `CONCEPT_OVERVIEW.md` describes cascading (a project template emits files that trigger further instantiations). This works because the watcher monitors the repo root and symlinks make template output visible in the project tree. However, there's no explicit handling of cascade depth limits or cycle detection. If template A emits a file that matches template B, which emits a file matching template A, the watcher could loop. The "instance already exists" check provides a partial guard, but only if the instance names collide.

4. **`watch` command has no `--root` flag** — The guide specifies `--root`/`-r` to set the repo root. The implementation hardcodes `Path.cwd()`. This prevents watching a directory other than the current one.

---

## Summary Scorecard

| Category | Rating | Notes |
|----------|--------|-------|
| **Refactor completeness** | 8/10 | All phases implemented; missing `to_toml_file`, `get_template_for_pattern`, signal handling, `--force` flag |
| **Code quality** | 8/10 | Clean, idiomatic Python; good Pydantic usage; minor type annotation issues |
| **Architecture** | 9/10 | Excellent separation of concerns; DI for testability; pluggable handler chain |
| **Test quality** | 7/10 | Strong watcher tests; pre-refactor modules untested; some edge cases missing |
| **Documentation** | 7/10 | Good docstrings; `CONCEPT_OVERVIEW.md` and guides are thorough; inline comments sparse |
| **Production readiness** | 6/10 | Needs signal handling, PID file, cycle detection, and integration testing for daemon mode |

**Overall: Solid implementation that faithfully delivers the refactor guide vision with some improvements. The identified gaps are mostly in edge cases and operational robustness rather than core functionality.**
