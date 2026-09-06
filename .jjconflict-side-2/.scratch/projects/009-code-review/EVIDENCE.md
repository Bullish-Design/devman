# Evidence log

## 2026-08-31 — baseline

Command:

```text
devenv shell -- devenv tasks run -v base:check base:unit
```

Result:

```text
All checks passed!
236 passed in 3.88s
```

The fast suite includes the pinned Dagu conformance layer.

The installed plane was also healthy at the start of the review:

```text
devman doctor
...
ok  validate       170 projected workflows load
ok  projection     164 of 170 DAG names each point at their own project's file
...
Nothing to report.
```

The six remaining links use the documented pre-codec migration path. They are
notes, not findings.

## 2026-08-31 — focused Python reproductions

Command:

```text
devenv shell -- env PYTHONPATH=src python \
  .scratch/projects/009-code-review/reproductions.py
```

Result, with temporary directory names shortened:

```text
nested watcher hits: ['inner', 'outer']
nested_watch_reproduction: CONFIRMED

resolved parameters: {
  'DEVMAN_PROJECT_DIR': '/tmp/.../override-project',
  'TYPO': 'value'
}
undeclared_override_reproduction: CONFIRMED

resolved target after directory override: /tmp/.../different-project
directory_override_reproduction: CONFIRMED

malformed_registry_reproduction: CONFIRMED — AttributeError:
  'list' object has no attribute 'get'

codec result for a Dagu-invalid name: bad@project.check
invalid_dag_name_reproduction: CONFIRMED

schema-invalid workflow resolved for enqueue: schema.check
schema_invalid_workflow_reproduction: CONFIRMED
```

The script creates a disposable registry and project trees. It does not touch
the installed registry.

## 2026-08-31 — generated projection semantics

The actual `plan` store script from a current registry entry was run against two
disposable workflow sources.

An ordinary workflow with an unrelated top-level `env:` block produced:

```yaml
working_dir: /tmp/project
log_dir: /tmp/project/.devman/.runs/logs
env:
  - REVIEW_FLAG: enabled
steps:
  - run: printf '%s\n' "$DEVMAN_PROJECT_DIR"
```

The generated file has no `DEVMAN_PROJECT_DIR`. The source `env:` block made
the header skip it.

An ordinary workflow whose comment merely mentioned `DEVMAN_SELF_DIR` produced:

```yaml
env:
  - DEVMAN_SELF_DIR: /tmp/project
working_dir: /tmp/project
log_dir: /tmp/project/.devman/.runs/logs
# This ordinary workflow mentions DEVMAN_SELF_DIR only in documentation.
steps:
  - run: printf '%s\n' "$DEVMAN_PROJECT_DIR"
```

The source comment changed the generated runtime variable. This is not only a
fixture. `.devman/workflows/plane-report.yaml` says in a comment that an
ordinary project variable is correct, but that same comment contains
`DEVMAN_SELF_DIR`. Its installed projection therefore receives
`DEVMAN_SELF_DIR`.

## 2026-08-31 — path serialization

The current projection plan was run for a valid Unix directory whose name held
colon-space:

```text
/tmp/devman-review: bad.<suffix>
```

The generated file contained unquoted scalars:

```yaml
env:
  - DEVMAN_PROJECT_DIR: /tmp/devman-review: bad.<suffix>
working_dir: /tmp/devman-review: bad.<suffix>
```

The pinned Dagu validator refused it:

```text
mapping value is not allowed in this context
```

The metadata template performs the same class of raw substitution inside a JSON
string. A project path that holds a quote or backslash can make the registry
entry invalid JSON.

## 2026-08-31 — scheduled shell environment

The live user manager and the Dagu service process both held:

```text
SHELL=/run/current-system/sw/bin/zsh
```

Dagu uses `$SHELL` before `default_shell`. `src/devman/run.py` clears it for
CLI, watcher, and hook enqueues. Dagu schedules `base/maintain` and
`devman/plane-report` from the daemon process, so those runs bypass that clear
and use zsh. The NixOS module currently says the daemon schedules no workflow;
that statement predates projects 006 stage 6 and 007 stage 7.

## 2026-08-31 — reactive scope mismatch observed during this review

Saving `reproductions.py` under `.scratch/` fired the installed `format`
workflow. Its trigger is `**/*.py` and its hash includes `.scratch/`, but this
repository configures Ruff to exclude `.scratch/`. The workflow therefore ran
successfully without formatting the file that fired it.

The final doctor output recorded three such dispatches at 11:33, 11:38, and
11:43 local time.

## 2026-08-31 — final verification

Commands:

```text
devenv shell -- devenv tasks run -v base:check base:test
devenv shell -- devman doctor
```

Results:

```text
All checks passed!
all checks passed!
base:test completed in 37.0s

devman doctor — 54 projects, 170 workflows
...
Nothing to report.
```

The full flake check evaluated the packages and ran the group validation,
Python/Dagu suite, and NixOS Dagu service VM check. The doctor command exited 0.
