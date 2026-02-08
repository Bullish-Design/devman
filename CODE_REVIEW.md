# Devman Code Review (post-watchdantic refactor)

**Review date:** 2026-02-08
**Scope:** Full library review of `src/devman/` and `tests/`
**Reviewed against:** `CONCEPT_OVERVIEW.md`, `README.md`, and the codebase as implemented

---

## Executive Summary

Devman is a well-conceived reactive template management system with a clean
three-tier architecture (templates, instances, projects). The post-watchdantic
refactor introduces a filesystem watcher built on `watchfiles` and Pydantic
config validation. The watcher subsystem is the strongest part of the codebase
in terms of both design and test coverage. However, the refactor left behind
several bugs, dead code artifacts, and inconsistencies between modules that
need attention before the library is production-ready.

**Critical bugs found:** 2
**Dead code / leftover artifacts:** 3
**Design issues:** 8
**Test coverage gaps:** 5

---

## Bugs

### BUG-1: Operator precedence error in seed template resolution (Critical)

**File:** `src/devman/bootstrap.py:43-49`

```python
configured_repo = (
    seed_templates_repo
    or Path(os.environ[SEED_TEMPLATES_ENV_VAR]).expanduser()
    if SEED_TEMPLATES_ENV_VAR in os.environ
    else DEFAULT_SEED_TEMPLATES_REPO
)
```

Python parses `a or b if c else d` as `(a or b) if c else d` because `or`
binds tighter than the ternary `if/else` expression. This means:

- When `SEED_TEMPLATES_ENV_VAR` **is not** in the environment: `configured_repo`
  is always `DEFAULT_SEED_TEMPLATES_REPO` regardless of whether
  `seed_templates_repo` was explicitly provided by the caller.
- A user calling `devman init --seed-templates-repo ~/my-templates` without the
  env var set will have their argument silently ignored.

**Expected logic:**

```python
if seed_templates_repo:
    configured_repo = seed_templates_repo
elif SEED_TEMPLATES_ENV_VAR in os.environ:
    configured_repo = Path(os.environ[SEED_TEMPLATES_ENV_VAR]).expanduser()
else:
    configured_repo = DEFAULT_SEED_TEMPLATES_REPO
```

### BUG-2: Keyword argument name mismatch in `get_template_for_pattern` (Critical)

**File:** `src/devman/watcher/config.py:121-128`

```python
def get_template_for_pattern(self, path: Path, change: str) -> str | None:
    from devman.watcher.engine import find_matching_pattern
    pattern = find_matching_pattern(path=path, change=change, patterns=self.patterns)
```

`find_matching_pattern` in `engine.py` has the signature:

```python
def find_matching_pattern(
    relative_path: str,
    change: Change | str,
    patterns: Sequence[PatternConfig],
) -> PatternConfig | None:
```

Two problems:
1. **Wrong keyword name:** `path=` does not match the parameter name
   `relative_path`. This raises `TypeError` at runtime.
2. **Wrong type:** A `Path` object is passed where `str` is expected.

This appears to be a stale call site left from the refactor where the parameter
was renamed from `path` to `relative_path`. The corresponding test in
`test_watcher_config.py:138-158` exercises this method, so the test suite
should fail if run.

---

## Dead Code and Refactor Artifacts

### DEAD-1: `_run_checked` function in `bootstrap_project.py`

**File:** `src/devman/bootstrap_project.py:28-46`

The `_run_checked` function is defined but never called anywhere in the
codebase. The module imports and uses `run_checked_subprocess` from
`subprocess_utils.py` instead. This also makes `import subprocess` (line 12)
dead.

Note: there is a test (`test_run_checked_wraps_stderr_context`) that imports
and exercises `_run_checked` directly, which keeps it "alive" in the test suite
but not in production code.

### DEAD-2: Standalone script metadata on a library module

**File:** `src/devman/bootstrap_project.py:1-7`

```python
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "copier>=9.0.0",
#   "tomli-w>=1.0.0",
# ]
# ///
```

This shebang and PEP 723 inline metadata block is appropriate for a standalone
script but out of place on a module within an installed package. The
dependencies are already declared in `pyproject.toml`. This is likely a leftover
from before the code was organized into the package structure.

### DEAD-3: `DevmanWatcher._dispatch_handlers` method

**File:** `src/devman/watcher/engine.py:69-86`

This method implements handler dispatch logic but is never called. The actual
dispatch happens inside the module-level `process_change_event` function
(lines 230-245), which duplicates the same try/except/log pattern. The method
appears to have been superseded during the refactor but not removed.

---

## Code Quality Issues

### CQ-1: Duplicated `_is_ignored_path` logic

**Files:** `src/devman/watcher/engine.py:88-100` and
`src/devman/watcher/handlers.py:202-216`

The same ignore-path logic exists in two places:
- `DevmanWatcher._is_ignored_path` (engine, instance method)
- `_is_ignored_path` (handlers, module-level function)

Both iterate over `settings.ignore_dirs` checking path parts, then iterate
over `settings.ignore_globs` running `fnmatch`. The handlers version is used
by `dispatch_change_event` for synthetic events. These should be consolidated
into one shared implementation.

### CQ-2: Duplicated update display logic in CLI

**File:** `src/devman/cli.py:156-223`

The `update` command has two nearly identical blocks for displaying project vs
file-type update results. The only differences are the variable name
(`metadata_file` vs deriving from `target.name`) and the initial print message.
The result-display logic (success/no-op, changes list with truncation) is
copy-pasted.

### CQ-3: Silent exception swallowing in `CopierConfig.from_yaml_file`

**File:** `src/devman/schemas/copier.py:62-66`

```python
try:
    questions_typed[name] = parse_question(name, spec)
except Exception:
    # Keep as raw dict if parsing fails
    questions_typed[name] = spec
```

A bare `except Exception` silently swallows all parsing errors with no logging.
If a question spec is malformed, the user gets no indication that the typed
parsing failed and the raw dict was kept instead. This makes debugging config
issues unnecessarily difficult. At minimum this should log a warning.

### CQ-4: Inconsistent copier invocation strategy

**Files:** `src/devman/bootstrap.py:166-176` vs
`src/devman/bootstrap_project.py:65-75`

- `bootstrap_file_type` calls copier directly: `["copier", "copy", ...]`
- `bootstrap_project` wraps copier through UV:
  `[sys.executable, "-m", "uv", "run", "--python", sys.executable, "copier", "copy", ...]`

This means the same tool (`copier`) is invoked via different mechanisms
depending on the code path. The UV wrapper adds indirection, requires UV to be
installed, and may resolve a different copier version than the one on PATH. The
two paths should be consistent.

### CQ-5: Inconsistent subprocess error handling in handlers

**File:** `src/devman/watcher/handlers.py:269-272`

`run_copier_instantiation` uses bare `subprocess.run` and manually checks
`returncode`:

```python
proc = subprocess.run(cmd, capture_output=True, text=True)
if proc.returncode != 0:
    raise WatchError(proc.stderr.strip() or "copier instantiation failed")
```

Meanwhile, other parts of the codebase use the shared
`run_checked_subprocess` utility from `subprocess_utils.py`, which provides
richer error messages, remediation hints, and handles `FileNotFoundError`
separately. The handler should use the shared utility for consistency.

### CQ-6: `_normalize_change` is a static method on `DevmanWatcher` but called from module-level functions

**File:** `src/devman/watcher/engine.py:108-112, 121, 174`

`_normalize_change` is a `@staticmethod` on the `DevmanWatcher` class, but
it's called from module-level functions (`find_matching_pattern`,
`process_change_event`) via `DevmanWatcher._normalize_change(change)`. This
creates unnecessary coupling between the free functions and the class. It
should be a module-level private function.

### CQ-7: Return type ambiguity in update functions

**File:** `src/devman/update.py`

Both `update_file_type` and `update_project` return `dict` with a `success`
key that is always `True`. Failure cases raise exceptions rather than returning
`success: False`. This makes the `success` key misleading -- callers might
write `if not result["success"]` expecting it to be a possible value, but it
never is. Either remove the `success` key, use a typed return (dataclass /
TypedDict), or actually return `success: False` for failure cases.

### CQ-8: Missing config file error not wrapped in update functions

**File:** `src/devman/update.py:27-28`

```python
config_path = type_path / CONFIG_SUBPATH
with open(config_path, "rb") as f:
    config = tomllib.load(f)
```

If `config_path` doesn't exist, this raises a bare `FileNotFoundError` with a
system-level message. The calling CLI code only catches `ValueError` and
`RuntimeError`, so this would produce an unformatted traceback. The file read
should be wrapped with a domain-appropriate error message.

---

## Design Observations

### D-1: No template name sanitization

Template names from TOML config are used directly in path construction
(`resolve_template_path`, `resolve_target_instance_path`) without any
sanitization. A malicious or accidental template name like `../../etc/passwd`
would resolve outside the intended template store. While the `template_path`
existence check in `resolve_template_path` provides some protection, it
doesn't guard against path traversal into directories that do exist.

Consider validating template names against a pattern like `^[a-zA-Z0-9_-]+$`.

### D-2: No file locking for concurrent instantiation

The watcher can trigger multiple instantiation attempts in rapid succession
(e.g., cascading events). The "instance already exists" check
(`instance_path.exists()`) is a TOCTOU race condition -- two events could both
see the directory as non-existent and attempt to create it simultaneously. For
a single-threaded watcher this is unlikely but not impossible with synthetic
events.

### D-3: `bootstrap_file_type` targets parent directory

**File:** `src/devman/bootstrap.py:174`

```python
copier_cmd.extend([str(template_path), str(target_path.parent)])
```

The copier command targets `target_path.parent` (e.g., `~/.devman-store/`)
rather than `target_path` itself, relying on the copier template's
`{{file_type}}` directory to create the expected directory name. This
implicitly couples the code to the template's directory structure. If the
template's output directory naming doesn't match `file_type`, the subsequent
`config_path = target_path / CONFIG_SUBPATH` check will silently skip metadata
writing.

### D-4: `_subdirectory` set to empty string in seed template

**File:** `src/devman/seed_templates/file-type/copier.yml:1`

```yaml
_subdirectory: ""
```

An empty `_subdirectory` is functionally equivalent to not setting it. If the
intent is "no subdirectory," omitting the key is cleaner and avoids potential
confusion about whether empty string has special semantics in Copier.

---

## Test Coverage Analysis

### Overall Assessment

The test suite has **55 tests** across **13 test files**. The watcher
subsystem (engine, handlers, config) has excellent coverage. The bootstrap and
update modules have notably weaker coverage.

### Strengths

- **Watcher handler tests** (`test_watcher_handlers.py`, 20 tests) are the
  standout -- comprehensive coverage of instantiation flow, symlink handling,
  safety defaults, cascade events, and loop protection.
- **Schema tests** (`test_schemas.py`, 19 tests) thoroughly cover question
  types, serialization round-trips, and backward compatibility.
- **Config validation tests** use `@pytest.mark.parametrize` effectively for
  invalid input coverage.
- **Error isolation** is tested (failed handlers don't block other handlers).
- **Timezone awareness** is consistently tested across bootstrap/update paths.

### Gaps

#### GAP-1: `get_template_for_pattern` test exercises buggy code (BUG-2)

The test at `test_watcher_config.py:138` calls the method that has a keyword
argument mismatch. If this test passes, it means the test suite is not
actually being run in CI, or there's something else at play. Either way, the
bug and the test need to be fixed together.

#### GAP-2: Bootstrap positive-path coverage is thin

`test_bootstrap.py` has only 3 tests, none of which test the successful
`bootstrap_file_type` flow end-to-end (mocked subprocess, successful copier
run, metadata written correctly). Only the fallback "unversioned" paths are
tested.

#### GAP-3: Update module has minimal coverage

`test_update.py` has only 3 tests. Missing coverage:
- Actual version change (non-no-op) flow
- Dry-run with changes
- Missing config file handling
- Invalid version strings
- Version downgrade behavior

#### GAP-4: No integration tests

All subprocess invocations (git, copier, jj) are mocked. There are no tests
that exercise real tool interactions, even as optional slow/integration tests.
This increases the risk that mocked behavior diverges from actual tool behavior.

#### GAP-5: CLI error formatting not fully tested

The CLI `_format_cli_error` function is trivial, but several error handling
paths (e.g., `FileNotFoundError` from update config reads) are not covered.
The `init`, `bootstrap`, and `project` commands have no CLI-level tests.

---

## Module-by-Module Notes

### `constants.py` -- Clean, no issues

Well-organized path constants. The helper functions (`get_store_root`,
`get_devman_meta_dir`, etc.) provide a clean abstraction over the path layout.

### `subprocess_utils.py` -- Good utility

`run_checked_subprocess` is well-designed with `FileNotFoundError` handling,
remediation hints, and structured error messages. The `_default_remediation_hints`
function is a nice touch for common tools. It should be used consistently
across the codebase (see CQ-5).

### `domain/errors.py` -- Clean, minimal

The error hierarchy is appropriate. `WatchError` inherits from `DomainError`
and is used consistently in the watcher layer.

### `domain/models.py` -- Clean

`ValidationResult` with its `add_error`/`add_warning` API is usable.
The `is_valid` property correctly checks only errors (not warnings).

### `schemas/questions.py` -- Well-structured

The discriminated union approach using Pydantic `Literal` types is clean.
The `parse_question` backward compatibility (auto-upgrading `str` +
`choices` to `choice` type) is a practical touch.

### `schemas/copier.py` -- Functional with caveats

The `from_yaml_file` / `to_yaml_file` round-trip works but silently
swallows parse errors (CQ-3). The `validate_questions` method only checks
a few cases -- questions that failed parsing and fell back to raw dicts
are flagged as missing `type`, which is a somewhat indirect error message.

### `schemas/tasks.py` -- Minimal, correct

`TaskList.to_yaml_format` correctly handles both simple (string-only) and
conditional (dict with `when`) tasks. No issues found.

### `watcher/config.py` -- Strong validation

Good use of Pydantic validators for events, log levels, and non-empty strings.
The `from_toml_file`/`to_toml_file` methods are clean. The TOML alias
(`pattern` vs `patterns`) handling is correct. One method is buggy (BUG-2).

### `watcher/engine.py` -- Core is solid, some dead code

The `run` loop, filter mechanism, and `process_change_event` function are
well-structured. The `_matches_glob` function handles the directory-pattern
edge case (trailing slash) thoughtfully. Contains dead code (DEAD-3) and the
static method coupling issue (CQ-6).

### `watcher/handlers.py` -- Most complex, mostly well-designed

The instantiation orchestration with injectable function parameters is a good
testing strategy. The synthetic event system with depth guards and loop
detection (`ContextVar`-based stack tracking) is carefully implemented. The
main issues are the duplicated ignore logic (CQ-1) and inconsistent subprocess
usage (CQ-5).

### `watcher/toml_gen.py` -- Simple, correct

Generates a deterministic starter config. The overwrite protection is
appropriate.

### `cli.py` -- Functional, some duplication

Lazy imports keep startup fast. Error handling is consistent (catch, format,
exit 1). The logging configuration helper `_configure_watch_logging` handles
idempotency correctly. The update command duplication (CQ-2) is the main issue.

### `bootstrap.py` -- Has the most significant bug

The seed template strategy logic (BUG-1) is the most impactful bug in the
codebase because it affects `devman init`, which is the entry point for new
users. The rest of the module is straightforward.

### `bootstrap_project.py` -- Works but needs cleanup

Contains dead code (DEAD-1, DEAD-2) and uses a different copier invocation
strategy than `bootstrap.py` (CQ-4). The `.devman-bootstrap.py` script
execution feature is not documented in the concept overview.

### `update.py` -- Functional, underspecified return type

Both functions work for the happy path but have fragile error handling (CQ-8)
and misleading return types (CQ-7). The dry-run implementation correctly
passes `--pretend` to copier.

---

## Recommendations (Priority Order)

1. **Fix BUG-1 and BUG-2** -- These are runtime failures waiting to happen.
   BUG-1 silently ignores user input; BUG-2 crashes on invocation.

2. **Remove dead code** (DEAD-1, DEAD-2, DEAD-3) -- Clean up refactor
   artifacts to avoid confusion about what's live.

3. **Consolidate `_is_ignored_path`** (CQ-1) -- Single source of truth for
   path filtering.

4. **Standardize copier invocation** (CQ-4, CQ-5) -- Pick one strategy
   (direct `copier` or UV-wrapped) and use it consistently. Use
   `run_checked_subprocess` everywhere.

5. **Add logging to silent exception handlers** (CQ-3) -- At minimum
   `logger.debug` when question parsing falls back to raw dicts.

6. **Expand update and bootstrap test coverage** (GAP-2, GAP-3) -- These
   are critical user-facing operations with thin test coverage.

7. **Add template name validation** (D-1) -- Reject names containing path
   separators or traversal patterns.

8. **Type the return values** of `update_file_type` and `update_project`
   (CQ-7) -- Use `TypedDict` or a dataclass.
