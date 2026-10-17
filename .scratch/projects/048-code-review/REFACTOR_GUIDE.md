# 048 — constrained configuration refactor guide

Use this guide in a new session. It implements findings F1 to F4 in
[`REVIEW.md`](REVIEW.md). It also removes the unused `defaultQueue` option (F8).
Keep F5 to F7 as separate work. This guide uses the measurements in
[`../047-greenfield/MEASUREMENTS.md`](../047-greenfield/MEASUREMENTS.md).

The goal is one owner for each setting that can change a run's result:

| Setting | Sole owner after the refactor | Source behavior |
|---|---|---|
| Project work directory | `projects.toml` `path` | Refuse `working_dir` in workflow YAML |
| Queue | Each workflow YAML file | Require a configured `queue` in every file |
| Exit handler and `devman.task` | Packaged devman base template | Refuse source overrides of reserved names |
| Compile health | `compile.json` version 2 plus current input check | Show every refusal or stale input |

Dagu inherits `base.yaml` settings, and a DAG can override many of them.
This makes an editable global base a weak place for required behavior. See
[Dagu base configuration](https://docs.dagu.sh/server-admin/base-config).
Dagu supports an explicit queue in a DAG file. See
[Dagu queue configuration](https://docs.dagu.sh/server-admin/queues).
The project 047 measurements, which used pinned Dagu 2.20.1, decide runtime
behavior when current Dagu documentation differs.

## 1. Set the contract before editing code

The integrator owns these decisions. Record them in the agent task messages.
Agents must not silently change them.

1. Keep one central manifest and overlay workflow files.
2. Keep Dagu 2.20.1, repository tasks, event routing, and the repository view.
3. Reject top-level workflow `working_dir`. Always render the manifest path.
   Do not infer a path from the workflow file's location.
4. Require an explicit queue string in every workflow source. Refuse a
   missing, null, empty, non-string, or unknown queue. Remove the queue from
   `base.yaml`.
5. Remove Home Manager `defaultQueue`. All four current project workflow
   files and all four seed library workflows already name a queue.
6. Move mandatory `handler_on.exit` and `devman.task` definitions into a
   packaged template, such as `src/devman/base.yaml`. Keep the generated
   `<state>/base.yaml` path that Dagu already reads.
7. Keep `hist_retention_days: 7` in the packaged base. There is no measured
   need for a retention option. Add a typed positive Home Manager option in a
   later change only if a real use requires a different value.
8. Keep project-specific workflows in the overlay. A project can still use
   Dagu built-in actions and its own commands. Reserve the name `devman.task`.
9. Keep the last good DAG files after a refusal. Make status and doctor red
   until a successful full compile covers the current inputs.

Rules 6 and 7 narrow charter ruling R13. The shared workflow library stays
in the overlay. The required handler and action become mechanism. Their
behavior is true for a new clone, while retention stays fixed at seven days.
The 048 probes supply the measurement that requires this amendment.

This contract prevents the four reviewed configuration failures. It does
not prove that an arbitrary user command does useful work. A step-level
`shell:` and some Dagu built-in actions bypass `guard.sh`. Keep this limit
explicit in the charter and tests. Do not expand this refactor into a new
policy system.

## 2. Start a clean parallel session

Start the new session with this request:

> Implement `.scratch/projects/048-code-review/REFACTOR_GUIDE.md` in order.
> Spawn the three background agents in §2. Keep their work in separate gitman
> workspaces. Integrate, verify, land, and push each lane in the stated order.
> Keep all new notes and experiments under project 048. Follow `AGENTS.md`.

Read `AGENTS.md` and the devman, writing, and gitman skills. Run these from
the main checkout before opening a workspace:

```bash
jj workspace list
jj log -r '(::working_copies() ~ ::trunk()) ~ empty()'
jj status
```

Report any work that `main` lacks. Account for it before opening new workspaces.
Use three background agents plus one integrator. Give each agent its own
gitman workspace. The agents may work in parallel, but they must not land or
push until the integrator completes the charter and verification in each lane.
This is an explicit review gate for the parallel session. The integrator
lands each ready lane in the order below.
Each agent lists workspaces and reports pending work before opening its lane.

| Lane | Agent owns | Avoid |
|---|---|---|
| `048-contract` | `render.py`, render tests, required queue and work directory fixture changes | `compile.py`, Nix, status, doctor |
| `048-base` | packaged base, `paths.py`, base fill in `compile.py`, Nix module, base tests | `render.py`, status, doctor |
| `048-health-tests` | new black-box regression tests for F1 to F4 | production code and existing test files |
| Integrator | charter, mechanism docs, health implementation, lane rebases and landing | concurrent edits in an agent's active workspace |

Each agent must use a unique directory under
`.scratch/projects/048-code-review/implementation/` for notes and logs.
Do not write a shared log file. Keep all new review experiments there.
Before running Nix, stage new files with `git add -A`. Nix ignores untracked
files. Do not run `systemctl`, `home-manager`, or a rebuild from a stage.

### Agent A prompt: work directory and queue contract

> Open `gitman work 048-contract`. Read `AGENTS.md`, the 047 charter, and the
> 048 review. Edit `src/devman/render.py`. Refuse source `working_dir`. Always
> render the manifest path. Require a nonempty `queue` that exists in Dagu's
> configured queues. Keep `group` and `labels` source overrides. Refuse a
> source action named `devman.task` if it can replace the packaged action.
> Update `tests/test_render.py` and the shared `STEP` fixture in
> `tests/conftest.py`. Add focused compile and real Dagu regression cases in
> new test files, to avoid edits to other agents' tests. Verify the lane.
> Report its workspace path, changed files, tests, and any conflict. Do not
> move `main` or push. Leave the lane for integration.

Agent A's acceptance cases:

- A source with `working_dir` is refused. Compile leaves its old DAG file.
- A rendered valid file always has the manifest `working_dir`.
- A source without `queue`, or with an undefined queue, is refused.
- A file with a configured queue validates with real Dagu.
- The current seed library and current four project workflow files remain
  valid. Do not edit the live overlay from this lane.

### Agent B prompt: mechanism-owned base

> Open `gitman work 048-base`. Read `AGENTS.md`, the 047 charter, and the 048
> review. Move the required base template into the Python package. Keep the
> generated state file as Dagu's `paths.base_config`. Make `Paths.base_src`
> refer to the packaged template, not overlay `library/base.yaml`. Keep the
> three existing path tokens. Keep seven days of run history.
> Remove the base queue. Require `handler_on.exit` and `devman.task` in the
> template before publication. Stage a candidate base, validate it with real
> Dagu and the compiled files, then publish it atomically. Update the Nix
> wrapper, package data, base fixtures, and base tests. Do not edit status,
> doctor, or `render.py`. Verify the lane. Report its workspace path, changed
> files, tests, and any conflict. Do not move `main` or push.

Agent B must handle these concrete paths:

- `src/devman/paths.py`: keep `base_src` as a `Path`, but point it to packaged
  data. Keep `DEVMAN_LIBRARY` for workflow test overrides only.
- `src/devman/compile.py`: change `fill_base` and its call order. Read the
  configured queues before publishing the candidate base. Write a temporary
  Dagu config whose `paths.base_config` points to the candidate. Validate
  compiled DAG files with that config. Check the required handler and action
  fields directly because Dagu validation does not enforce devman's contract.
- `src/devman/base.yaml`: own the handler and action definitions. No queue.
- `nix/hm-module.nix`: remove `defaultQueue` and its assertion. Search
  nix-meta and other module users for `defaultQueue` before removal. Update
  callers in their proper lane.
- `nix/package.nix` and `pyproject.toml`: prove the template enters the wheel
  and Nix package. Preserve one dependency source in `uv.lock`.
- `flake.nix` and `tests/fixtures/library/`: update the library validation
  fixture so it tests the packaged base. Remove the obsolete seed base after
  its consumers change.

Agent B's acceptance cases:

- Removing or replacing overlay `library/base.yaml` cannot remove the handler
  or change the generated base queue. Overlay workflows still compile.
- A bad packaged template refuses before the active base changes.
- Real Dagu emits `done` and `failed` after the move.
- The generated base keeps `hist_retention_days: 7`.
- No installed package needs the live overlay base file at run time.

The current `tests/conftest.py` copies the seed base into the overlay. Agent
B may need to edit that file. Agent A owns its `STEP` fixture lines. Let one
agent finish first, then rebase Agent B's lane and resolve this small overlap.

The existing 048 `experiments.py` and `experiment-results.jsonl` contain the
F1 to F4 failing inputs. Use them as behavior references. Keep new tests in
`tests/`; do not make the scratch probe a release gate.

### Agent C prompt: independent regression tests

> Open `gitman work 048-health-tests`. Read the 048 review and the target
> contract above. Add new test files only. Test all four failures from outside
> their implementation functions. Use an isolated temporary plane. Include
> real Dagu tests for the work directory and handler. Include compile, status,
> and doctor assertions for a broken manifest, a bad base, and changed input
> after a good compile. Keep an initial failing result as evidence. Do not
> change production code or existing tests. Report the expected failure list
> and workspace path. Do not land or push. The integrator will make this lane
> green after Agents A and B land.

Agent C must not make tests mirror the implementation. Each test must assert
the visible result: a refusal, unchanged published files, the run's directory,
an emitted event, or a red health report. Avoid exact JSON key assertions
until the integrator fixes the version 2 schema below.

## 3. Land the contract lane first

Wait for Agent A to stop editing. The integrator then owns that workspace.
Add a charter amendment in the same change as the code. Amend §5 so the
manifest always owns `working_dir` and every source must name a configured
queue. Cite 048 findings F1 and F3. Update `README.md`, `USER.md`, and
`AGENTS_GUIDE.md` only where the mechanism or daily instructions change.
Keep library content detail in the library README.
Update `PLAN.md` interface A.2 and decision rows B5 and B6. Mark older stage
notes that promise a source work directory or a base queue as superseded.

Run the required gates in the lane:

```bash
git add -A
devenv tasks run -v base:check
devenv tasks run -v base:unit
devenv tasks run -v base:e2e
devenv tasks run -v base:test
nix build .#devman
/etc/profiles/per-user/andrew/bin/devman doctor
```

The installed doctor checks the live plane. It does not prove staged code.
Inspect the focused tests and the real Dagu result as well. If a gate fails,
fix it before landing. Use `jj describe` with one short imperative message.
Fetch and rebase the lane onto `trunk()`. Verify again if the tree changes.
Move `main`, push it, update the empty main checkout with `jj new main`, and
close the lane with `gitman done 048-contract`.

## 4. Rebase and land the base lane

Wait for Agent B to stop editing. Fetch and rebase `048-base` onto the new
`trunk()`. Resolve the `tests/conftest.py` fixture overlap if it appears.
Check that the package template, not the overlay file, supplies the handler.

In the same change, amend charter R13 and §§3, 5, 7, and 8. State that only
workflow content remains in the overlay library. The mandatory base is
mechanism. Cite 048 findings F2 and F3 and the real Dagu result. Update the
mechanism documents. Remove `defaultQueue` from the option table and its
module test. Update `tests/fixtures/library/README.md` when its base file
goes. Do not edit the live overlay in a stage.
Update `PLAN.md` interface A.1, the base interface, and decision row B11.
Mark the old overlay base steps as superseded. Preserve their measurements.

Run all six gates from §3 after the rebase and after these edits. Test the
Nix wheel contents directly through `nix build .#devman`. If the package
version changes, update its hard-coded install check at the same time. Land,
push, update main, and close `048-base` only on green.

## 5. Implement and land compile health in the test lane

Wait for Agent C to stop editing. Fetch and rebase `048-health-tests` onto
the new `trunk()`. The integrator now writes the production code in this
workspace. No other agent edits it.

Use this version 2 state contract. Keep the current per-project records.

```json
{
  "version": 2,
  "compiled_at": "UTC time of the last state change",
  "global": {
    "status": "ok or refused",
    "at": "UTC time of the last recorded result",
    "reasons": [],
    "successful_input_sha256": "digest from the last full green compile"
  },
  "projects": {}
}
```

Implement a deterministic input digest in one helper. Include the manifest,
packaged base template, `DEVMAN_BASH`, `DEVMAN_GUARD`, `DEVMAN_BIN`,
guard file bytes, state path, Dagu config, every workflow YAML path and its
bytes, and the names of project workflow directories. Sort paths before
hashing. A missing or unreadable required input makes health red. Encode
absence of optional workflow directories as a stable marker. Ignore generated
DAGs, run logs, examples, and README files. The digest must notice a new
`workflows/<project>/` directory even when the watcher misses it.

Implement these transitions in `src/devman/compile.py`:

1. Keep the prior successful digest until a **full** compile succeeds for
   every project and finds no orphan.
2. On a full green compile, write the new digest and `global.status = ok`.
   Preserve the file's bytes on a second no-change compile.
3. On malformed TOML, base failure, missing guard, unreadable Dagu config,
   or an unexpected global exception, write `global.status = refused` with
   the reason. Preserve the last good DAG files and digest. If state storage
   itself fails, return an error; the reader must also report unreadable state.
4. On a project refusal or orphan, keep its per-project refusal and make the
   global result red. Put project names or orphan names in `global.reasons`.
   Keep details in the project records. Do not advance the successful digest.
5. On a partial compile, never advance the global successful digest. Keep a
   prior green global result only when the current input digest still equals
   the prior full green digest. Otherwise report stale.
6. Publish `compile.json` by atomic rename under the existing compile lock.
   Do not let an error in one project erase another project's record.

Update `status.py` and `doctor.py` to read `global` and compare the live input
digest with `successful_input_sha256`. A mismatch is stale even when the last
compile attempt reported `ok`. Treat version 1 or a missing global record as
needing a full compile. Show the global reason in `status` text and JSON.
Make status and doctor return 1 on a global refusal, a mismatch, or an
unreadable input. Preserve status exit 2 for usage and unreadable state errors.
Return `{"global": ..., "projects": [...]}` for all-project JSON status.
Return `{"global": ..., "project": {...}}` for one-project JSON status.
The global object must include a derived `stale` value and its reasons.
Keep router behavior: it can still use the last good `compile.json` routes
and DAG files. Make the stale state visible to a person.
Update `tests/test_compile.py`, `tests/test_status.py`, and
`tests/test_doctor.py` for the version 2 record and status exit codes.

Amend charter §§5, 6, and 11 in this same change. Cite 048 finding F4.
Update `PLAN.md` interfaces A.3 and A.7, plus the status JSON example. Mark
the old compile health rule as superseded. Update README, USER, and
AGENTS_GUIDE for the new diagnosis result. Run all six gates from
§3 and Agent C's black-box tests. Land, push, update main, and close the lane
only when every gate passes.

## 6. Review the live boundary after code lands

The code refactor and the live deployment are separate checks. Never run a
Home Manager switch or `systemctl` from a stage. After `main` holds all three
lanes, inspect the central overlay repository and its own version-control
rules. Its `library/README.md` must describe every library file.

1. Confirm every live workflow has a configured queue. The current four
   project files do. Read them again because they may have changed.
2. Update the overlay library README. Remove the obsolete overlay
   `library/base.yaml` only when the installed devman reads its packaged base.
3. Build and pin the new devman version through the normal nix-meta release
   path. Treat release configuration as a risky file under `AGENTS.md`.
4. Run the switch from the main checkout under that repository's rules.
5. Run a full `devman compile`, then `devman doctor` with the installed binary.
6. Run one real `check` and confirm a `done` event. Run a safe failing fixture
   and confirm a `failed` event. Confirm that status names the expected queue.
7. Leave no gitman workspace open. Report each landed commit and the live
   health result.

If the live switch is outside the session's authorization, finish every
reviewable build and manifest change first. Ask only before the switch or a
risky release-config push, as the local version-control rules require.

## 7. Final acceptance checklist

- A workflow source cannot change `working_dir` or omit `queue`.
- No editable overlay base can remove `handler_on.exit` or change queue policy.
- Every queue name in compiled files exists in Dagu config.
- A malformed manifest or bad base cannot leave status or doctor green.
- A changed input cannot appear current before a successful full compile.
- Existing Dagu-native agent workflows still validate and run.
- Unit, end-to-end, Nix, package, and live doctor gates pass.
- The 047 charter, mechanism docs, overlay library README, and live plane
  agree with the code.
- Every lane is on `main`, pushed, shown by the main checkout, and closed.
