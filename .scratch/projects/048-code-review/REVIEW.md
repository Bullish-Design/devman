# 048 — devman code review

Date: 2026-10-17. Baseline: `main` at `a5af0f93`. Review target: the
charter in `../047-greenfield/CONCEPT.md`.

## Result

The main workflow works in the current machine check. All existing test gates
pass. The review found eight defects. Four affect the charter's rule that a
successful run must produce the intended result. One can expose values passed
as event fields. The findings below rank the fixes by impact.

The review changed no mechanism file. The scripts and results in this directory
reproduce the findings in isolated trees. The scripts use Dagu 2.20.1 and
watchexec 2.5.1 from the development environment.

## Findings

### F1 — P1: a workflow can succeed in a newly created wrong directory

`render.py:103` lets a source replace `working_dir`. `compile.py:114` checks
only the manifest path. `dagu/guard.sh:5` checks `DEVMAN_PROJECT_DIR`, which
also names the manifest path. It does not check the effective work directory.

The `source-working-dir` probe set `working_dir` to a directory that did not
exist. Compile returned 0. Real Dagu created the directory. The step wrote its
current directory there and the run returned 0. This reproduces the green run
with a wrong result described in charter §5 and measurement M2.

Check the effective `working_dir` before publication. Add a run check for a
directory that disappears after compile. Keep the charter's source override,
but make a missing target fail. Add an end-to-end test for a source override.

### F2 — P1: base config can remove the exit handler and still compile green

`compile.py:68-75` checks that `base.yaml` is a YAML mapping. It then publishes
the mapping. No check requires `handler_on.exit`. `doctor.py:121-144` checks
action names, but it does not check the handler.

The `base-removes-handler` probe replaced the base with `{}`. Compile returned
0. A real Dagu run returned 0 without an exit handler. Doctor's compile check
returned no finding. Thus `done` and `failed` events stop while runs stay green.
This violates charter §7, which defines the exit handler as their event source.

Validate the required base fields before publication. Preserve the last good
base if validation fails. Check the active base in doctor. Test a missing exit
handler with a real run.

### F3 — P1: an undefined base queue bypasses the queue limit

`render.py:62-66` checks a queue only when a workflow source names it.
`compile.py:256-264` publishes the base before it reads the configured queues.
It does not compare the base `queue` with those queues.

The `base-queue` probe changed `queue: light` to `queue: ghost`. Compile returned
0 and doctor reported no compile problem. Measurement M1 in project 047 proves
that Dagu runs an undefined queue without its configured limit. A project
workflow with no queue inherits this unsafe value.

Check the base queue against Dagu's configured queues before publication. Test
a base queue typo with a workflow that has no source queue.

### F4 — P1: global compile failures leave status and doctor green

`compile.py:256-264` returns before it writes `compile.json` for a base error.
`compile.py:292-325` prints a manifest file error, but the output record has no
place for it. `doctor.py:81-87` reads only project refusals and orphan names.

The `invalid-manifest` and `invalid-base` probes each made compile return 1.
The prior project record stayed `ok`. `devman status` printed `compile: ok`.
Doctor's compile check returned no finding. The manifest case had no project
source directory, so an orphan warning could not hide this result.

Record global failures with their reason and time. Make status and doctor read
that record. Keep the last good project files, but mark their status stale.
Add tests for both failure paths after a successful compile.

### F5 — P2: the watcher misses the first project workflow directory

`watch.py:82-90` excludes a missing `workflows/` directory from its recursive
watch set. The overlay has only a shallow watch. `watch.py:113-124` discards
directory events. `watch.py:226-228` refreshes the watch set only after it sees
an overlay file event.

The real `watch_probe.py` test started with a library workflow and no
`workflows/` directory. The watcher became ready. The probe created
`workflows/probe/check.yaml`. The compiled workflow still came from the
library after two seconds. An edit to `projects.toml` then caused a compile,
selected the project source, and added the new watch path.

Treat creation of a relevant overlay directory as a reason to compile and
refresh the watch set. Test fresh overlay setup. Also check restoration of a
missing project checkout: `targets()` excludes it, and the watcher has no
parent watch that can detect its return.

The probe removed the `.gitman` ignore pattern only in its test process. Its
temporary tree sits inside a gitman workspace. Production must keep that
ignore pattern.

### F6 — P2: an event field can enter a readable log in full

`router.py:43-53` accepts any field name outside the reserved prefix.
`router.py:118` copies every field value into the event record.
`router.py:93-99` creates `events.jsonl` with mode `0644`, subject to umask.

The `event-fields` probe sent a harmless sentinel in `TOKEN`. Its value
appeared in the log. The file mode was `0644`. A caller who sends a credential
as a field leaves its exact value in the log. The live parent state directory
has mode `0700`, so it blocks other users on this machine today. The project
rule still says secrets are declared and never held by devman.

Treat event fields as public data in the command help. Reject a known secret
field when possible. Keep field values out of `events.jsonl`, and create the
file with mode `0600`. Use Dagu `secrets:` for credentials.

### F7 — P2: one checkout can register twice through a symlink

`manifest.py:199-207` compares the written path strings. It does not compare
resolved paths. `router.py:62-72` resolves paths while it selects the project.

The `duplicate-symlink` probe registered one real path and one symlink to it.
The manifest accepted both, and compile returned 0. A command run in the real
checkout selected the alias project. This violates charter §4's refusal for
two projects with one path. It can route an event to the wrong workflows.

Compare resolved project paths when the paths exist. Refuse every project that
shares one resolved path. Add a symlink case to the manifest tests.

### F8 — P3: `defaultQueue` has no effect

`nix/hm-module.nix:112-116` says `defaultQueue` names the queue in the library
base. The module uses the option only in the assertion at lines 170-173.
`library/base.yaml` lives in the overlay and names `light` directly. A user can
set `defaultQueue = "normal"` without changing the actual default queue.

Remove the option, or connect it to a checked base template value. State the
single source of truth in the module help and README.

## What the review checked

I read the charter, the interface plan, measurements M1 to M7, all core Python
modules, the Dagu guard, the Nix package and module, the seed library, and the
tests. I compared the live overlay library with the seed. They match.

The implementation has useful checks. It validates changed DAG files with real
Dagu. It keeps a project's published files when that project's validation
fails. It locks compile, writes files by rename, and records per-project
refusals. The guard catches a vanished manifest checkout for ordinary run
steps. End-to-end tests cover event routing, library tasks, handler events,
and that guard. These checks do not cover the cases above.

The tests use a fake Dagu for 154 unit cases. Seven end-to-end cases use real
Dagu. The new probes cover the gaps with real Dagu and watchexec where needed.
They run in temporary trees under this review directory. They do not change
the live overlay, live Dagu state, or service units.

## Verification

| Gate | Result | Evidence |
|---|---|---|
| `base:check` | pass | `base-check.txt` |
| `base:unit` | 154 pass, 7 deselected | `base-unit.txt` |
| `base:e2e` | 7 pass, 154 deselected | `base-e2e.txt` |
| `base:test` | Nix flake checks pass | `base-test.txt` |
| `nix build .#devman --no-link` | pass | `nix-build.txt` |
| installed `devman doctor` | 8 checks pass | `doctor.txt` |
| isolated probes | findings reproduced | `experiment-results.jsonl`, `watch-results.jsonl` |

`live-permissions.txt` records the live directory and event log modes. It
does not contain log contents.

The Nix flake check ran for the current Linux system. It reported that it
omitted the other three declared systems. This review did not test those
platforms. The installed doctor checked the live plane, not the isolated
faults; the probes called its compile check on their own state.

## Repair order

1. Fix F1, then add the real Dagu regression test.
2. Fix F2 and F3 together at the base publication boundary.
3. Fix F4 so later refusals stay visible in status and doctor.
4. Fix F5 and F7 to make new workflows and project selection deterministic.
5. Fix F6 before using event fields for sensitive data.
6. Resolve F8 in the module interface.
