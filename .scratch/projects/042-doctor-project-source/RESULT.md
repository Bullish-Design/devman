# 042 — Name the project source in `devman doctor`

**Date:** 2026-10-02.

## Defect and decision

`Registry.load()` reads project metadata from the state root in compatibility
mode. It reads from the active generation in plane mode. `doctor` named the
registry root in its header but did not name the project source. A reader could
take the four compatibility projects for a check of the active fleet.

The header now prints the exact `projects/` directory used for the count. This
adds one line to a report a person reads on demand. The line names a distinct
source, so its cost is justified. `check_mode` stays informational: the mode is
a label, not a finding. The load path and mode choice did not change.

No other command prints the registry root as the source of its project count.
`watch` passes the registry root to its child process; it does not report it as
a project source. This change leaves other commands alone.

## Live headers before

Default:

```text
devman doctor — 4 projects, 19 workflows
    registry   /home/andrew/.local/share/devman
    state      /home/andrew/.local/state/devman
    dagu home  /home/andrew/.local/share/dagu
```

Active generation:

```text
devman doctor — 48 projects, 152 workflows
    registry   /home/andrew/.local/state/vendomat/devman/active
    state      /home/andrew/.local/state/devman
    dagu home  /home/andrew/.local/share/dagu
```

## Live headers after

Default:

```text
devman doctor — 4 projects, 19 workflows
    registry   /home/andrew/.local/share/devman
    state      /home/andrew/.local/state/devman
    projects   /home/andrew/.local/state/devman/projects
    dagu home  /home/andrew/.local/share/dagu
```

Active generation:

```text
devman doctor — 48 projects, 152 workflows
    registry   /home/andrew/.local/state/vendomat/devman/active
    state      /home/andrew/.local/state/devman
    projects   /home/andrew/.local/state/vendomat/devman/active/projects
    dagu home  /home/andrew/.local/share/dagu
```

## Verification

The separate workspace starts at trunk. Another draft lane contains the later
check-efficacy tests, so its baseline is not this lane's baseline.

```text
Before: base:unit  652 passed, 1 skipped
After:  base:unit  654 passed, 1 skipped
base:check         All checks passed!
PATH stripped:     64 passed, 3 skipped in 4.03s
```

The two new cases build separate temporary state and registry roots. Each
asserts that the printed `projects` path supplied the loaded project. The
PATH-stripped run found three existing git-dependent tests without skip markers
on trunk. The tests now skip when `git` is absent; the negative run has zero
errors.

The live doctor still reports two findings with the default registry and eight
with the active generation. Those findings predate this header change. The
repository requires doctor to exit zero before a change to `src/devman/` is
committed. The operator approved describing this lane with those existing
findings. The lane stays unlanded and unpushed.
