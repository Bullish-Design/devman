# Project 038 Wave 3 investigation prompt

Copy the text below into a fresh investigation session.

---

You are investigating Wave 3 of Project 038, the Devman machine-plane redesign.
Do not implement Wave 3 in this session. Produce a detailed, evidence-based
decision report that another session can use to design and implement the work.

## Investigation outcome

Answer all of these questions:

1. What are the actual Wave 3 requirements?
2. Which requirements are technical gates, which are operator decisions, and
   which may become explicit accepted limitations?
3. What options exist for each unresolved decision?
4. What are the benefits, costs, risks, implications, opportunities, migration
   effects, and rollback effects of each option?
5. What evidence is still missing, and what experiment or source inspection
   will provide it?
6. Which decisions are already resolved by current evidence, and which records
   must be corrected before anyone asks an operator to decide again?
7. What is the smallest safe implementation sequence after the investigation?

Do not copy a historical statement into the report without checking it against
the current checkout, current active generation, current central configuration,
and current consumer state. Record the command, result, and date for every
important claim. Call out conflicting records instead of silently choosing one.

## Scope

Investigate all four Wave 3 areas:

- **I — watcher strict maintenance gate:** decide how watcher-fired work behaves
  while a reload is pending, blocked, starting, or complete.
- **J — reload race:** decide how manual, watcher-fired, and scheduled runs are
  admitted or drained while a new Dagu generation activates.
- **K — compatibility mode:** decide how the remaining manifest, branch,
  compatibility-only, and legacy identity cases reach a supported end state.
- **L — `registryDir` move and direct render-to-link design:** decide whether
  generated workflow rendering can be removed or narrowed, and whether the
  registry can move without mixing authored and generated content.

Treat this as a design investigation, not as an implementation task. The report
must separate facts, measurements, inferences, recommendations, and operator
choices.

## Contract and system model

Use this model unless current primary evidence proves that it is stale:

- Dagu orchestrates.
- devenv executes repository tasks.
- Devman resolves projects, renders or links workflows, and triggers runs.
- Vendomat builds and activates the machine generation.
- RepoMan owns repository migrations and branch state.
- A repository manifest is authoritative when it exists.
- The active generation and its pointer are derived state.
- The plane must refuse unsafe ambiguity rather than silently use a default.
- A successful run must produce the correct result in the correct repository and
  directory.
- An unattended write to a tracked repository needs an explicit write tier and
  must not silently modify trunk.

Read the repository instructions before investigating. Follow their command
and writing rules. Use Simplified Technical English in the report.

## Read first

Read these files before forming a conclusion:

- `AGENTS.md`
- `AGENTS_GUIDE.md`
- `.scratch/projects/038-devman-plane-redesign/NEXT_SESSION_PROMPT.md`
- `.scratch/projects/038-devman-plane-redesign/REMOVAL_SEQUENCE_PROMPT.md`
- `.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_GUIDE.md`, with
  special attention to sections 4, 5, 6, and 11
- `.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md`, with
  special attention to Stages 10, 16, 17, 37, 38 repair, 39, 40, Wave 2G,
  and Wave 2H
- `.scratch/projects/038-devman-plane-redesign/CONSUMER_MIGRATION_GUIDE.md`,
  with special attention to sections 6, 9, 10, 11, 14, 15, and 16
- `.scratch/projects/038-devman-plane-redesign/LINK_PLANE_A_TO_C_GUIDE.md`,
  with special attention to sections 10, 11, and 13
- `.scratch/projects/025-the-link-plane/CONCEPT.md`, with special attention to
  sections 6.2a and 6.3 and the Stage 3 and Stage 4 records
- `nix/nixos-module.nix`
- `src/devman/run.py`
- `src/devman/watch.py`
- `src/devman/doctor.py`
- `src/devman/reconcile.py`
- `src/devman_link/identity.py`
- the relevant unit tests and VM tests
- the current Vendomat generation and recovery records

When Dagu behavior is a decision input, use the pinned Dagu version in this
repository. Prefer its pinned source, tests, and official documentation. Record
the exact version and, when possible, the source URL and commit used. Do not
assume that behavior from a newer Dagu release applies to the pinned version.

## Safety boundary

This is an investigation-only session.

Do not:

- edit implementation, workflow, Nix, test, or consumer files;
- edit generated state, the active pointer, the central configuration, or the
  compatibility registry;
- switch or activate a generation;
- remove an active generation or compatibility directory;
- change a consumer checkout, branch, detached HEAD, or manifest;
- commit or push changes;
- edit `src/devman/watch.py` or `tests/unit/test_watch.py`; record the need for
  changes if the evidence shows that they are required.

Read-only inspection and isolated, reversible experiments are allowed. Do not
run an experiment against the live plane if it can change active state. Use a
temporary copy, a disposable test directory, or an existing test harness.
Clean up only artifacts created by the investigation, and record the cleanup.

Use the repository's `devenv` tasks and project tools. Do not use bare
`python`, `pytest`, `ruff`, or `uv` when a repository task owns that operation.
Do not use raw `git` when the repository's version-control wrapper is available.

## Establish current ground truth

Start from `/tmp` for commands that need to prove that the installed command
does not depend on the current checkout. Clear Python path variables first.
Use explicit paths. Capture stdout, stderr, exit status, and the date.

At minimum, inspect:

```bash
cd /tmp
env -u PYTHONPATH -u PYTHONHOME devman doctor
env -u PYTHONPATH -u PYTHONHOME dagu ls
env -u PYTHONPATH -u PYTHONHOME devman link status --all
```

Then record:

- the active generation pointer and generation path;
- the active project count and active DAG count;
- the active generation digest;
- the Dagu version and service status;
- the reload marker directory and every marker state;
- the configured `registryDir`, `stateDir`, `overlayDir`, project root, and
  repository roots;
- the current central configuration status;
- the current Vendomat and RepoMan status, including dirty or unpinned state;
- any doctor findings, whether they are known, new, or stale.

Inspect the old share-side and state-side registry directories. Count and list
manifests without changing them. Search for old identity and compatibility
inputs, including:

```text
devman/modules
devman.project
devman.groups
devman =
```

For every candidate consumer, record a row with these fields:

| Field | Value to record |
|---|---|
| Repository | Absolute path and project name |
| Manifest | Path, present/absent, valid/invalid, and parsed identity |
| Identity source | Manifest, literal Nix fallback, compatibility data, or unknown |
| Compatibility declaration | Present/absent and exact source |
| Central declaration | Present/absent and exact source |
| Active state | In active generation, only in old registry, state-side only, or absent |
| Branch state | Branch name, detached HEAD, dirty state, and remote availability |
| Migration record | Commit, reachability, published status, and current applicability |
| Task surface | Required task names and whether each exists |
| Links and triggers | Workflow links, watcher mappings, schedules, and writers |
| Classification | Supported, migration candidate, compatibility-only, archive candidate, or unknown |

Distinguish the seven historically named migration repositories from the full
set of currently detached repositories. A detached HEAD is evidence to inspect,
not proof that a migration is blocked.

## Reconcile stale or conflicting records first

The current records may conflict. In particular, compare the statement in
`NEXT_SESSION_PROMPT.md` that three manifest placements and seven detached-HEAD
branch decisions remain blocked with the Stage 37 record that says root
manifests were approved for `copyroom`, `docman`, and `mypi-agent`, and mapped
destinations were approved for `gitman`, `image-gen-pipeline`, `llgym`,
`loci-core`, `nix-paseo`, `pydantree`, and `pyjutsu`.

For each historical decision, verify all of the following:

- the current checkout has the expected manifest or migration input;
- the expected branch or commit is present and reachable;
- the change is published where the record says it is published;
- the central configuration names the current identity;
- the active generation contains the expected project and workflow data;
- the current link and status commands see the expected result;
- no old compatibility path is still the only source of required data.

Classify each record as one of:

- resolved and published;
- resolved locally but not published;
- still blocked;
- no longer applicable;
- contradicted by current evidence and requiring operator review.

Do not ask the operator to decide a question that current evidence already
resolves. Do not call a detached file resolved merely because a migration commit
exists. Do not call a migration published merely because it exists in one local
checkout.

Include a reconciliation table with the historical record, current evidence,
classification, remaining action, and source links.

## Model the requirements

Build a traceability table with these columns:

| Requirement | Source | Current implementation | Evidence | Status | Decision or owner |
|---|---|---|---|---|---|

Use these status values only: `proven`, `unproven`, `accepted limitation`, or
`blocking gap`.

At minimum, test or reason about these requirements:

1. An active run is never killed by reload.
2. Reload cannot report success when the new generation did not start.
3. A blocked reload leaves the old generation available.
4. A failed reload leaves a structured marker and clear operator action.
5. Manual `devman run` has defined behavior during every reload state.
6. Watcher-fired runs have defined behavior during every reload state.
7. Scheduled Dagu runs have defined behavior during every reload state.
8. A crashed reload or stale marker has detectable and recoverable behavior.
9. Watcher events have an explicit loss, retry, coalescing, and duplicate policy.
10. Run history and run metadata survive generation changes.
11. Direct links preserve workflow identity, project directory, log directory,
    queue selection, and scheduled behavior.
12. Direct linking cannot overwrite authored central workflow files.
13. A `registryDir` move cannot merge authored and generated namespaces.
14. Compatibility removal leaves no supported repository without a workflow,
    identity, task surface, trigger, or rollback path.
15. Rollback restores the prior generation and preserves a useful recovery path.

Add requirements from the source documents when they are specific and testable.
For each requirement, state whether it is a hard gate, a design choice, an
operator choice, or an explicit accepted limitation.

## Decision Group A — reload and maintenance gate

### A1. Choose the gate owner

The current design uses stable markers and polling. The reload service writes a
`reload.pending` marker, waits for `dagu ps` to report no active runs, restarts
Dagu, and removes the marker after a successful restart. Manual `devman run`
checks the marker. The source records say that the watcher and scheduled paths
still have a race. Verify this current gap.

Compare at least these options:

1. Stable marker plus cooperative clients.
2. A shared lock or lease used by every producer and the reload service.
3. A systemd maintenance state that stops or gates producers together.
4. A Dagu-native pause or drain mechanism, if the pinned Dagu version proves
   that it provides the needed guarantees.
5. Accept a documented global race as a limitation.

For each option, evaluate atomicity, stale-state recovery, crash behavior,
multiple processes, visibility, implementation cost, testability, rollback, and
whether it covers manual, watcher, and scheduled producers.

### A2. Choose watcher behavior

Compare at least:

1. Wait and retry while the marker is present.
2. Refuse and drop the event.
3. Persist a coalesced event and replay it after reload.
4. Stop and restart the watcher around reload.

For each option, answer what happens to one event, many events, changes during
shutdown, a stale marker, duplicate events, content-hash loop breaks, and a
watcher process that crashes after accepting an event.

### A3. Choose scheduled-run behavior

Compare at least:

1. Pause or drain the Dagu scheduler through a supported maintenance mechanism.
2. Gate Dagu admission or queueing.
3. Put the scheduler behind a wrapper that checks the reload state.
4. Generate a per-project wrapper that carries the required project context.
5. Accept and document the remaining scheduled-run race.
6. Remove or prohibit schedules only if a current inventory proves that this is
   safe and an operator accepts the loss.

For every option, answer who blocks the run, who drains existing runs, how a
crash is recovered, how reload performs its final race check, how a run resumes,
and how project directory, log directory, queue, history, and identity remain
correct. Verify the actual pinned Dagu scheduler behavior.

### A4. Choose wait and failure policy

Measure real active-run durations and reload durations. Compare:

- indefinite drain;
- a measured deadline;
- a configured deadline;
- refusal to activate after the deadline while keeping the old generation.

Never choose a policy that kills an active run. A timeout must leave the old
generation available, leave enough marker state to diagnose the failure, and
give the operator a safe retry action.

### A5. Define observable states

Define visible states at minimum for:

- pending;
- waiting for admission;
- waiting for watcher drain;
- waiting for scheduler drain;
- started;
- complete;
- blocked;
- failed;
- stale marker or crashed reload.

Map each state to systemd status, doctor output, reload logs, exit status, marker
files, operator action, and recovery action. Ensure that a user can tell the
difference between “waiting”, “failed”, and “old generation still active”.

### A6. Build a proof matrix

State which checks belong in a unit test, integration harness, or VM test. Cover
manual, watcher, and scheduled runs before, during, and after reload; a long
active run; several active runs; simultaneous activation requests; timeout;
reload crash; stale marker; failed restart; rollback; history; retention; queue;
and correct working and log directories.

Do not call the gate ready until the matrix names a proof for every producer.

## Decision Group B — render-to-link and registry layout

The link-plane records identify a direct render-to-link opportunity. Manual
symlink behavior has been measured, but scheduled behavior after removing the
renderer is not proven. The current renderer injects per-project absolute
`working_dir`, `log_dir`, and `DEVMAN_PROJECT_DIR` values. A shared source cannot
carry a different absolute project path for every repository. The current
`registryDir` also mixes generated workflow data with central authored content.

### B1. Choose the project-directory mechanism

Compare at least:

1. Retain generated per-project wrappers and direct-link only content that does
   not need per-project values.
2. Link the shared workflow source and generate small per-project Dagu metadata
   or wrappers next to it.
3. Use a stable launcher that maps DAG identity to the project directory.
4. Change the workflow contract to use a Dagu-supported project parameter or
   context mechanism.
5. Run a separate Dagu instance or configuration per project.
6. Keep rendering until a later, fully proven design exists.

Evaluate manual runs, watcher runs, scheduled runs, edit visibility, discovery,
name safety, queue selection, history, authentication, authored-file safety,
reload and generation rollback, source-size reduction, operator complexity, and
migration scope.

### B2. Choose the registry and overlay layout

Compare at least:

1. Keep `registryDir` in its current location until direct-link behavior is
   proven.
2. Move `registryDir` after direct-link removes generated workflow ownership.
3. Split authored central files and generated runtime files into separate roots.
4. Use a two-root migration window with explicit read and write ownership.
5. Do not move `registryDir`; document why the current layout is the safe end
   state.

For each option, map the owner of every path, whether it is authored or derived,
every reader and writer, activation and rollback behavior, and the failure mode
when one root is missing. Prove that the option cannot overwrite, shadow, or
silently replace an authored central workflow.

### B3. Define the direct-link gate

Define the minimum evidence required before removing or narrowing the renderer.
At minimum include:

- an in-place source edit observed through a symlink;
- a scheduled run after that edit;
- correct working and log directories;
- correct queue and run history;
- multiple workflow documents;
- cross-repository names and duplicate-name refusal;
- activation and rollback;
- no authored-file overwrite;
- reload while a run is active;
- no dependence on an untracked shell entry point.

If the gate cannot be met, recommend retaining generated wrappers and state the
smallest safe prototype that would remove the uncertainty.

## Decision Group C — compatibility mode and fleet migration

Break “compatibility mode” into separate inputs and outputs. Trace each one:

- consumer input and module discovery;
- central configuration identity;
- literal `devman.project` fallback in Nix files;
- compatibility publisher and generated bundles;
- registry contents and old paths;
- rollback pins and recovery data.

Do not claim that a manifest sweep replaces compatibility writes unless every
reader and writer of the replaced data has been identified and tested.

### C1. Classify the supported set

Reconcile the historical compatibility-only list, which includes
`copyroom`, `docman`, `fleetman`, `flora-037-part-e`, and `mypi-agent`, against
the current filesystem, manifest, central, active-generation, and task data.

For every compatibility-only or questionable project, choose a disposition:

- migrate to the manifest and current plane;
- archive with an explicit reason and recovery record;
- retain under a narrow, named allowlist;
- move to another supported plane;
- remove only derived compatibility data after proving that no supported reader
  needs it.

For each disposition, record the owner, lost capability, rollback path, and
evidence required.

### C2. Resolve structural manifest placement

Compare these options for repositories with unusual layout:

1. A root `.devman/project.toml` manifest.
2. A manifest in the development directory, with an explicit documented
   exception.
3. Identity kept in Nix only.
4. Identity supplied only by central configuration.

State the current evidence for `copyroom`, `docman`, and `mypi-agent`. If Stage
37 is confirmed as resolved and published, record it as resolved rather than
asking the operator the same placement question again. If current evidence
contradicts the historical record, make that contradiction an explicit operator
review item.

### C3. Resolve branch decisions for the seven historical migrations

Investigate `gitman`, `image-gen-pipeline`, `llgym`, `loci-core`, `nix-paseo`,
`pydantree`, and `pyjutsu`. Distinguish these seven migration decisions from
the full set of currently detached checkouts.

Compare these options:

1. Merge the migration into the normal owner branch.
2. Continue on an existing owner feature branch.
3. Create an approved branch and publish it.
4. Keep the change local until the owner decides.
5. Abandon and recreate the migration from current trunk.

Do not force-push or move a branch. For each repository, record branch
reachability, remote state, dirty state, commit contents, manifest state, and
the exact owner decision still needed.

### C4. Choose the identity fallback policy

Compare:

1. Remove the literal Nix fallback after all supported consumers have manifests.
2. Keep an explicit, finite allowlist of fallback consumers.
3. Use a time-bounded deprecation period with refusal after the deadline.
4. Move compatibility identity to a separate package or command with its own
   support and removal policy.

For each option, list remaining consumers, tests, refusal behavior, support
burden, security and correctness risks, and the pin or rollback needed to
recover.

### C5. Define the compatibility write retirement gate

Produce a table for every compatibility read and write:

| Operation | Caller | Data | Current path | Replacement | Evidence | Retirement gate |
|---|---|---|---|---|---|---|

Include scheduled workflows, watcher mappings, project identity, central
declarations, rollback, and old registry paths. State which compatibility data
can be retired first and which data must remain until a later gate.

## Measurements and experiments

Turn uncertainty into a measurement plan. For each proposed experiment, state:

- hypothesis;
- isolated setup;
- exact command or test;
- expected output and exit status;
- actual output and exit status;
- cleanup;
- decision that the result informs;
- failure meaning and next step.

At minimum investigate or remeasure:

- active-run duration and reload wait duration;
- reload marker transitions and stale-marker recovery;
- watcher events during every marker state;
- scheduled starts during every marker state;
- simultaneous reload requests;
- reload crash before and after Dagu restart;
- pinned Dagu pause, drain, queue, scheduler, and reload behavior;
- direct symlink edit visibility;
- scheduled working directory and log directory;
- queue selection and run history;
- activation, rollback, and generation retention;
- no-op reconcile behavior;
- authored/generated path collisions;
- compatibility coverage and remaining fallback readers.

Use a table with columns `Hypothesis`, `Setup`, `Command`, `Observed result`,
`Evidence location`, `Conclusion`, and `Follow-up`. Do not invent a result for
an experiment that cannot be run safely.

## Required report structure

Write the final report with this structure:

1. **Executive brief** — no more than five sentences.
2. **Current state** — measured counts, versions, paths, generations, and
   known findings.
3. **Record reconciliation** — especially the NEXT_SESSION_PROMPT versus Stage
   37 conflict and all other stale or contradictory decisions.
4. **Requirement traceability** — the full requirement table and status.
5. **Option matrices** — one matrix for each decision group. Use these columns:
   `Option`, `Requirements met`, `Benefits`, `Costs`, `Risks`, `Implications`,
   `Opportunities`, `Migration impact`, `Rollback`, and `Evidence`.
6. **Recommended design** — state the recommendation, rejected options, and
   why the evidence supports the choice.
7. **Operator decision sheet** — list only unresolved decisions. For each,
   include the recommended option, alternatives, consequences, latest safe
   decision point, decision owner, and evidence still needed.
8. **Implementation sequence** — separate commits or work units for design,
   watcher behavior, scheduled behavior, VM proof, link prototype, registry
   move, compatibility retirement, and documentation. Do not implement them.
9. **Stop conditions** — state when the work must pause because evidence is
   missing, a safety property is false, records conflict, or an operator choice
   is required.
10. **Definition of done** — list the exact tests, VM proofs, status checks,
    migration checks, rollback checks, and documentation updates that will make
    Wave 3 complete.

End with exactly one of these status lines:

- `READY FOR OPERATOR DECISIONS`
- `READY FOR A CONTROLLED PROTOTYPE`
- `BLOCKED BY MISSING EVIDENCE`
- `BLOCKED BY CONFLICTING RECORDS`

Do not recommend implementation until the report names each requirement,
selects or rejects an option for each decision, identifies the evidence gate,
and names the owner for every remaining choice.

---

After writing the report, show the report path and run the repository's normal
read-only checks. Do not modify implementation files.

```bash
git diff --check
git status --short --branch
```

If this prompt is being committed from the main repository session, stage only
the prompt file, verify the staged diff, and use the repository's approved
version-control workflow. The expected commit subject is:

```text
docs: add Wave 3 investigation prompt
```
