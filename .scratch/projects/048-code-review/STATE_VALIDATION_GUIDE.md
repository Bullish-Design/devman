# 048 — compile state validation guide

Use this guide in a new session. It follows the 048 refactor review. Fix state
validation, then carry the fix into the pending 0.9.1 release. This work does
not change workflow policy, Dagu, or the live services.

Start the new session with this request:

> Implement `.scratch/projects/048-code-review/STATE_VALIDATION_GUIDE.md` in
> order. Fix state validation, integrate devman candidate `553403e`, and update
> nix-meta candidate `06b7ae1` to the final release commit. Use the existing
> candidate workspaces. Run the required gates. Follow each repository's
> release approval rule before landing or pushing release changes. Do not run
> a Home Manager switch, a live compile, or an event test without separate
> approval.

## 1. Read and check the starting point

Read `AGENTS.md`, the devman, writing, and gitman skills, this guide, the 047
charter, and `PLAN.md` interfaces A.3 and A.7. Read the 048 review and its
refactor guide. Read `src/devman/{paths,health,compile,status,doctor,router,watch}.py`.

Run these commands in the main checkout before opening a workspace:

```bash
jj workspace list
jj log -r '(::working_copies() ~ ::trunk()) ~ empty()'
jj status
git log --oneline --decorate -8
```

Report work that `main` lacks. As of 2026-10-17, devman `main` ends at
`921cb87`. The `release-048-v0-9-1` workspace holds candidate `553403e`.
The nix-meta `devman-0-9-1-pin` workspace holds candidate `06b7ae1`. Recheck
these facts in the new session. Treat both candidates as unlanded. Open a new
lane from `main` for the state fix. Keep the release version bump in its lane.

The devman remote currently has a branch named `v0.9.1`, not a tag with that
name. The nix-meta candidate names `refs/tags/v0.9.1` in `flake.nix` and
`flake.lock`. A locked flake check can pass using its stored revision while the
named tag is missing. The release work must create the final tag only after
the final devman commit lands. Then refresh the nix-meta lock against that tag.

Keep F5 to F7 from `REVIEW.md` outside this change. Keep `defaultQueue` removed.
Do not change the workflow directory, queue, base, or retention rules.

## 2. Reproduce the state failure before the fix

Use an isolated `Plane` fixture. Do not alter the live `compile.json`. Save the
initial failing test output under
`.scratch/projects/048-code-review/implementation/048-state-validation/`.
Put release tests under `tests/`.

The current code has three distinct failures:

1. `global_health` drops a string `global.reasons`. A matching digest can then
   give `status: ok` and `stale: false` for malformed state.
2. A truthy non-mapping JSON value, such as `[1]`, raises `AttributeError` in
   the landed doctor's `check_compile` path.
3. A null project record raises `AttributeError` in `status` project discovery.
   `show`, `emit`, and the watcher also read project records without a shared
   shape check.

Candidate `553403e` adds a top-level mapping check in `compile.py` and
`paths.py`. Its doctor test writes `[]`. The landed doctor already reports
that empty list as unreadable. Thus the test cannot prove the new guard.
Keep the candidate's intent, but test a truthy non-mapping value.

## 3. Fix the read contract

Use one state reader for every command path. Put the JSON read and shape checks
in one module. A dedicated `StateError(ValueError)` can carry a path-specific
reason. Keep the distinction between a missing file and a malformed file.

| Input | Reader result | Compile | Status | Doctor |
|---|---|---|---|---|
| Missing file | `None` | Start the first full compile | Exit 2 | Exit 1 with a finding |
| Valid version 1 | Valid legacy state | Full compile can upgrade it | Exit 1: full compile required | Exit 1: full compile required |
| Valid version 2 | Valid state | Use prior records | Report derived health | Report derived health |
| Malformed JSON or shape | `StateError` with field path | Exit 1 before publication | Exit 2 | Exit 1 with a finding |

Do not use truthiness to test JSON shape. `[]` and `[1]` have the same wrong
type. A missing state file is an initial condition. An existing malformed file
is an error. Do not replace malformed state with `{}`. Do not overwrite it to
record a global refusal, because its last good routes cannot be recovered.

Validate every field a consumer indexes. Keep the checks narrow and explicit:

- Top level: a mapping with `version`, `compiled_at`, and `projects`.
- Version 2: `version` is integer 2, not boolean `true`. `global` is a mapping.
- Global record: `status` is `ok` or `refused`; `at` is a nonempty UTC time;
  `reasons` is a list of strings; the successful digest is a 64-character
  lowercase SHA-256 string or `null`.
- A green global record has a digest and no reasons. A refused record may have
  a null digest when no full compile has succeeded.
- `projects` is a mapping. Each project record is a mapping with valid
  `status`, boolean `stale`, time `at`, `reasons` as a list of strings,
  `on` as a list, and `workflows` as a mapping.
- A refused project may have `path: null` before its first good compile. An
  `ok` project has a nonempty path string.
- Each `on` entry has string `event` and `run`, plus lists of strings named
  `match` and `exclude`.
- Each workflow record has string `dag`, `file`, `origin`, `source`, and a
  64-character lowercase SHA-256 string named `sha256`.

Use the version 1 project shape in `PLAN.md` when reading old state. Validate
its fields before reuse. Preserve its records during a full upgrade. Version
1 remains unhealthy until that full compile succeeds. Reject unknown version
numbers. Extra keys may remain for forward-compatible additions, but do not
use them to fill a missing required field.

Give each error a JSON path and an expected type. Example:
`compile.json: global.reasons must be a list of strings`. Do not include the
bad value in the error. That value can contain private event data.

## 4. Connect every reader

Find every read before editing:

```bash
rg -n 'compile_doc\(|records\(|compile_json|global_health\(' src/devman tests
```

Route `compile`, `status`, `show`, `doctor`, `emit`, and watcher project selection
through the shared reader. Remove duplicate `json.loads` calls for state.
`global_health` should receive validated state. It must not turn a malformed
field into an empty default.

Keep command behavior explicit:

- `compile` reads and validates prior state before it publishes a base or DAG.
  On malformed state, it exits 1 and leaves the state and published files
  byte-for-byte unchanged.
- `status` returns exit 2 and a useful state error. It does not emit a partial
  JSON result for malformed state.
- `doctor` returns exit 1 and reports `FAIL compile clean` with the state
  error. Its other checks must not crash on the same file.
- `show` returns exit 2 with a state error.
- `emit` and `run` refuse before enqueue. They record a refusal and do not
  send a run to Dagu.
- The watcher remains alive. It keeps watching the overlay, so a repaired
  input can trigger another compile. A malformed state must not crash
  `targets()`.

Keep the existing rule for valid state: a global input failure records a
refusal, keeps the successful digest, and keeps the last good DAG files.
Do not change the partial-compile rule or the router's use of valid last-good
records.

## 5. Add tests that can detect the wrong behavior

Write command-level tests in `tests/test_state_validation.py` with the isolated
`Plane`. Start each corruption case from a successful full compile when prior
files matter. Call the public commands through `CliRunner`. Assert
`result.exception is None` as well as the exit code. A caught Python exception
can otherwise look like the expected nonzero exit.

Use this minimum matrix:

| State change | Required observation |
|---|---|
| Remove `compile.json` | Initial full compile works; status exits 2; doctor names missing state |
| Write broken JSON | Compile exits 1; status exits 2; doctor exits 1; DAG and state bytes stay unchanged |
| Write `[]`, `[1]`, `42`, and `"x"` | Every command refuses cleanly; the `[1]` case proves the candidate guard |
| Set `global.reasons` to a string with a matching digest | Status and doctor cannot report green |
| Remove `global.at`, or set a wrong digest type | Status and doctor name the malformed field |
| Set `projects.alpha` to `null` | Status, show, emit, doctor, and watcher paths do not raise |
| Set `projects.alpha.workflows.check` to `null` | Status, show, doctor, and emit do not raise |
| Keep a valid version 1 record | Status and doctor require a full compile; that compile writes valid version 2 |

For `emit`, assert that the fake Dagu received no enqueue and that the event
record names the refusal. For `doctor`, assert the `compile clean` line and its
field path. A failure in the API or watcher check is not proof of state
validation. For the watcher, test project selection without starting a live
service. Assert that it still watches the overlay.

Test recovery with valid state in a separate case. Compile once, break an
input, and run a full compile that records a global refusal. Restore the
input and run another full compile. Assert that the refusal clears, the digest
advances, and both status and doctor report clean compile health. Run a
second no-change full compile and compare `compile.json` bytes. Keep the
existing partial-compile stale test.

Do not add a real Dagu test for JSON parsing. The public command and fake
enqueue paths prove this change. Run the existing real Dagu suite as a gate.

## 6. Align the documents

Clarify malformed-state behavior in `PLAN.md` A.3 and A.7. Update the
mechanism documents only where command behavior changes. Add `health.py` or
the new state module to the code map in `AGENTS_GUIDE.md`. Keep library content
out of mechanism documents. Update the 047 charter only if an implementation
decision changes its contract. Record the evidence in the same change.

Correct two stale PLAN statements from the review:

- In A.8, the selected guard is the compiled header's `shell`, not a shell in
  `base.yaml`.
- In decision B16, name the compiled header as the guard owner.

Keep the old measurement as history. Extend the existing rendered-file test to
assert that the compiled DAG has the guard shell and the packaged base has no
top-level shell.

## 7. Verify and land the state fix

Stage new files before Nix runs. Run all repository gates in the state lane:

```bash
git add -A
devenv tasks run -v base:check
devenv tasks run -v base:unit
devenv tasks run -v base:e2e
devenv tasks run -v base:test
nix build .#devman --no-link
/etc/profiles/per-user/andrew/bin/devman doctor
```

The installed doctor checks the live 0.9.0 plane. It does not prove the
staged state reader. Use the isolated command tests for that proof. Do not
run a Home Manager switch, `systemctl`, a full live compile, or an event test
in this lane.

Follow `AGENTS.md` and the gitman skill to land the verified lane on `main`.
Fetch, rebase onto `trunk()`, and rerun verification if the tree changes.
Push `main`, update the empty main checkout, and close the workspace. Stop
before landing if a gate fails, a conflict appears, or release configuration
enters the lane.

## 8. Integrate the devman 0.9.1 candidate

Use the existing `release-048-v0-9-1` workspace. Rebase its candidate onto
the new devman `main`. Review `git diff` against the landed state fix. Preserve
the 0.9.1 changes in `pyproject.toml`, `src/devman/__init__.py`, `uv.lock`, and
the Nix install check. Keep only state guards that the shared reader still
needs. Remove duplicate checks. Replace the candidate doctor test that uses
only `[]` with a case that would fail on the old code, such as `[1]`.

Run the six checks from §7 in the release workspace. Also run the candidate
package command and check its reported version:

```bash
nix build .#devman --no-link --print-out-paths
<candidate-package>/bin/devman --version
```

The package must report `devman 0.9.1` and include the packaged base template.
Do not use the installed 0.9.0 doctor as evidence for the candidate. Inspect
the final diff and status. Follow `AGENTS.md`: release configuration needs
owner approval before landing or pushing. Complete the build and review first.
After approval, land and push the release lane, update the main checkout, and
close its workspace. Create and push `v0.9.1` only at the final landed commit.
Verify that the remote tag points to that commit. Do not point it at the old
`553403e` candidate. If that tag already names another commit, stop and resolve
the mismatch with the owner.

## 9. Update the nix-meta candidate

Use the existing `devman-0-9-1-pin` workspace in nix-meta. Read its `AGENTS.md`
and version-control rules. Rebase candidate `06b7ae1` onto nix-meta `main`.
Refresh only the devman input in `flake.lock` after the final devman tag exists.
Confirm that `flake.nix` names `refs/tags/v0.9.1` and that `flake.lock` records
the final devman commit. Do not accept a check that only uses the old locked
revision. Run `nix flake check` against the revised nix-meta candidate. Record
the evaluated configuration and any omitted systems.

Inspect the final nix-meta diff and status. Follow its approval rule for
release configuration before landing or pushing. After approval, land and
push the pin, update its main checkout, and close its workspace. Do not run a
Home Manager switch or change a live service in this step.

## 10. Acceptance

The work is ready for release review when all of these statements hold:

1. No malformed state can produce green status or a green compile check.
2. A malformed state file cannot make a command or watcher path raise an
   uncaught exception.
3. Compile does not publish files or replace malformed prior state.
4. A valid full compile can clear a recorded input failure and advance its
   successful digest. A partial compile cannot do so.
5. The new tests fail on the landed `921cb87` baseline for the intended
   reason and pass on the fix.
6. The 047 interfaces, charter, mechanism documents, and guard test agree.
7. All required gates pass. The state lane is on `main` and closed.
8. The 0.9.1 devman commit contains the fix, builds, and has the final tag.
9. The landed nix-meta pin names that tag and its final commit.

The live 0.9.1 switch and post-switch checks need separate approval. Keep the
installed binary's version visible in the final report.
