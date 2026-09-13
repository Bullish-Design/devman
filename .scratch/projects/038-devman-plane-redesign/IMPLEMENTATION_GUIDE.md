# Project 038 implementation guide

Date: 2026-09-12

This guide finishes the Devman machine-plane redesign. Follow the phases in
order. Each phase has a stop condition. Do not switch the default until every
earlier stop condition passes.

The guide covers three repositories:

| Repository | Role | Local path |
|---|---|---|
| Devman | contract, resolver, renderer, doctor, machine module | /home/andrew/Documents/Projects/devman |
| Vendomat | package closure, generation, activation, rollback | /home/andrew/Documents/Projects/vendomat |
| RepoMan | repository migration and reviewable changes | /home/andrew/Documents/Projects/repoman |

The target daily operation is:

~~~sh
vendomat plane plan devman --to VERSION
vendomat plane update devman --to VERSION
devman doctor
~~~

The target rollback is:

~~~sh
vendomat plane rollback devman --to GENERATION
devman doctor
~~~

The current implementation supports the first vertical slice. The old shell
projection and consumer Devman pins still remain the default. This guide moves
the machine through dual projection, migration, canary, cutover, and removal.

## 1. Rules for every phase

Use each repository's devenv environment for every tool command. Use raw Git
for this refactor, as the project prompt requires. Keep repository mutation in
RepoMan. Keep machine-plane mutation in Vendomat. Keep workflow semantics in
Devman.

Before each change:

1. Read the target file and its nearby tests.
2. Read the relevant section of CONCEPT.md.
3. Read the relevant stage log.
4. Record the current branch and worktree state.
5. State the failure that the change prevents.

After each change:

1. Run the smallest relevant test.
2. Run the repository gate.
3. Run the cross-repository proof when a boundary changes.
4. Run git diff --check.
5. Stage explicit paths only.
6. Review the staged file list.
7. Commit and push the completed slice.
8. Update IMPLEMENTATION_LOG.md with the date, command, result, and decision.

Never stage a whole repository with git add . Never reset or discard a
worktree change that you did not create for this project.

## 2. Establish the baseline

Set task-specific shell variables. Do not replace HOME or another system
variable.

~~~sh
export DM_ROOT=/home/andrew/Documents/Projects/devman
export VM_ROOT=/home/andrew/Documents/Projects/vendomat
export RM_ROOT=/home/andrew/Documents/Projects/repoman
export DM_POLICY_ROOT=$DM_ROOT
~~~

Inspect all three repositories before the first new change:

~~~sh
for repo in "$DM_ROOT" "$VM_ROOT" "$RM_ROOT"; do
  printf '\n== %s ==\n' "$repo"
  git -C "$repo" status --short --branch
  git -C "$repo" log -1 --oneline --decorate
done
~~~

At the start of this guide, the known state is:

| Repository | Branch | Known local state |
|---|---|---|
| Devman | 037-follow-up-results | four pre-existing modified files: src/devman/link.py, src/devman/watch.py, tests/unit/test_link.py, tests/unit/test_watch.py |
| Vendomat | 038-devman-plane-redesign | clean |
| RepoMan | main | pre-existing staged devenv.lock |

Preserve those changes. Recheck the state before every commit. A change in the
four Devman files above is not part of this guide unless you explicitly adopt
it as a separate change.

Run the current health and repository gates:

~~~sh
cd "$DM_ROOT"
devenv tasks run -v base:check
devenv tasks run -v base:test
devenv shell -- devman doctor

cd "$VM_ROOT"
devenv shell -- testee verify --mode quick

cd "$RM_ROOT"
devenv tasks run -v base:check
devenv tasks run -v base:test
~~~

devman doctor returns exit code 1 when it finds a machine problem. Record each
finding. Do not hide it with || true. Fix only findings caused by the current
phase.

Record these baseline values in the implementation log:

- cold and warm plane update time;
- shell-entry time;
- active project count;
- projected workflow count;
- number of consumer Devman locks;
- number of repository shell entries needed for projection;
- current generation and registry roots;
- current Dagu and Devman versions.

The existing log records a shell-entry baseline of about 8.42–8.76 seconds and
an older 46-repository rollout of about 15.7 minutes. Re-measure both with the
same machine and the same project set.

## 3. Finish the immutable package closure

This phase closes the main remaining Vendomat gap. The current plane operation
accepts explicit renderer and Dagu paths. The final operation must use one
immutable Vendomat generation containing the Devman runtime, renderer, Dagu,
and shared toolchain.

### 3.1 Define package identities

In Devman, keep the public renderer boundary in:

- src/devman/contract.py;
- src/devman/reconcile.py;
- src/devman/project.py;
- nix/renderer.nix;
- the Devman package expression.

In Vendomat, keep lifecycle code in:

- src/vendomat/plane.py;
- src/vendomat/cli.py;
- the Vendomat Nix package expressions.

Use separate identities for:

- Devman runtime;
- renderer bundle;
- policy source;
- Dagu binary;
- toolchain closure;
- contract schema.

Use canonical bytes for every digest. Record the digest input in a test. Do
not use the current process PATH as the version signal.

### 3.2 Build one closure

Add a Vendomat package target that builds one closure for the plane. The target
must expose the Devman renderer and the Dagu binary from known store paths. The
renderer command must fail if the package is absent. Keep explicit binary flags
only as a development override.

Prove the closure:

~~~sh
cd "$VM_ROOT"
devenv shell -- nix build .#devman-plane --no-link
devenv shell -- nix path-info -r .#devman-plane
~~~

The closure must satisfy these checks:

- all projects call the same renderer store path;
- all projects use the same Dagu store path;
- the generation record names every identity;
- changing the renderer changes renderer_digest;
- changing Dagu changes dagu_digest;
- changing the toolchain changes toolchain_digest;
- a missing package fails before staging;
- no project shell entry runs during rendering.

Add unit tests for digest and package selection rules. Add one integration test
that counts renderer invocations and proves the renderer is shared.

### 3.3 Remove accidental PATH fallback

Keep a local override for development, but make the normal path explicit:

~~~text
normal update -> immutable renderer path from Vendomat
local experiment -> explicit --renderer override
~~~

Print the selected store paths in vendomat plane plan. Include the paths and
digests in the plan result. A plan that cannot identify its renderer must fail.

Stop if the plan can still select a different renderer because of PATH.

### 3.4 Gate

Do not continue until:

- the closure builds offline from the lock;
- the renderer and Dagu paths are explicit;
- all generation identities are present;
- a renderer change makes all affected projections stale;
- the package test and Vendomat quick verification pass.

Commit the Devman package-boundary changes in Devman. Commit the closure and
plane changes in Vendomat. Push both branches.

## 4. Harden generation lifecycle and project results

The current generation store already supports staging, validation, atomic
activation, rollback, recovery, and no-op reuse. This phase makes every failure
state visible and defines behavior for unreadable projects.

### 4.1 Define the state model

Use these locations:

| State | Location | Owner |
|---|---|---|
| immutable generations and active | $HOME/.local/state/vendomat/devman/ | Vendomat |
| project metadata and watcher state | $HOME/.local/state/devman/ | Devman |
| Dagu run history | $HOME/.local/share/dagu/ | Dagu |
| project run records | <project>/.devman/.runs/ | Dagu and the project |

Keep registryDir on the active generation. Keep stateDir and Dagu home stable.
Never write metadata into an immutable generation after activation.

Add assertions that reject:

- a normal directory at the active path;
- a generation without generation.json;
- a generation with mixed project identities;
- a projection record with a different generation;
- a post-activation file mutation;
- a staging path outside the plane state root.

### 4.2 Define unreadable-project behavior

Use fail-closed behavior as the default:

1. plan reports the project error and does not write state;
2. update reports a project-level failure;
3. update does not activate a partial generation;
4. the previous active generation stays usable;
5. the failure names the project, path, operation, and source identity;
6. an operator can retry after fixing the repository.

Do not silently drop an offline project. Do not silently reuse an old projection
unless the result states that the old projection was retained.

Add tests for:

- missing repository path;
- unreadable manifest;
- unreadable policy source;
- permission failure while staging;
- invalid manifest;
- invalid workflow;
- one failed project beside one healthy project.

### 4.3 Prove last-valid retention

Create generation 1. Inject a render failure for one project. Run update. Check:

~~~sh
vendomat plane show devman
vendomat plane recover devman
~~~

The active pointer must still target generation 1. Generation 1 must still
validate. The failed project must have a structured result. No consumer file
must change.

### 4.4 Prove interruption recovery

Inject failure at each boundary:

- before staging starts;
- during one project render;
- after the generation is complete;
- before the active pointer replacement;
- after the temporary pointer is created;
- during rollback.

Run vendomat plane recover devman after each failure. Recovery must move
abandoned staging data into retained recovery state. It must never remove or
replace a valid active generation.

### 4.5 Gate

Do not continue until every failure has:

- a non-zero exit code;
- a structured result;
- a preserved active generation;
- a recovery test;
- a documented operator action.

## 5. Complete the reload boundary

The current NixOS module watches the active pointer with a user-level systemd
path unit. The reload adapter waits for dagu ps to report no active runs, then
restarts Dagu. The stable Dagu home preserves run history.

### 5.1 Make the policy visible

Document these states in the service output:

- reload pending: active runs exist;
- reload waiting: no active runs yet;
- reload started;
- reload complete;
- reload failed.

Expose the pending state through systemctl --user status
devman-dagu-reload.service and the Devman doctor report.

Add a maximum wait policy. If the wait exceeds the configured limit, keep the
old Dagu process and report the blocked reload. Do not kill the active run.
Choose the limit from observed run durations and record the measurement.

### 5.2 Test active-run behavior

Keep the NixOS test in nix/tests/dagu-service.nix. It must:

1. start a long demo.hold run;
2. record Dagu's main process identifier;
3. atomically switch active to generation 2;
4. prove the process identifier did not change;
5. prove the active run completed;
6. prove Dagu restarted after completion;
7. prove generation 1 remains retained;
8. prove generation 2 is visible;
9. prove the run record and Dagu history remain present.

Run the check:

~~~sh
cd "$DM_ROOT"
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
~~~

### 5.3 Close the run-start race

The polling check protects runs that already appear in dagu ps. It does not
by itself prevent a new run from starting between the final check and the
restart. Decide this before calling the boundary complete.

For a strict guarantee, add a maintenance gate in stable Devman state:

1. the reload service creates reload.pending atomically;
2. devman run refuses or waits while the flag exists;
3. the watcher waits while the flag exists;
4. scheduled Dagu runs use a documented drain mechanism or remain covered by
   the accepted Dagu restart policy;
5. the reload service checks dagu ps again immediately before restart;
6. the service removes the flag after a successful restart;
7. failure leaves the flag and reports an operator action.

If Dagu cannot gate scheduled runs, state that limitation in the concept and
measure the risk. Do not claim an absolute guarantee from a polling loop.

### 5.4 Gate

Do not continue until the service test passes with an active run and the
operator can see a blocked reload. Preserve a clear rollback if reload fails.

## 6. Build the RepoMan migration wave

RepoMan owns repository changes. Vendomat must not edit repository manifests.
Devman must not infer a missing manifest during the final default path.

### 6.1 Inventory every consumer

Start from the registry and the project tree. Use both sources because a
repository can be configured but not registered.

~~~sh
cd "$DM_ROOT"
devenv shell -- devman doctor
devenv shell -- devman link status --all
~~~

For every candidate repository, run:

~~~sh
cd REPOSITORY
devenv shell -- repoman devman status
~~~

Write an inventory with these columns:

| Repository | Current Devman option | Manifest | Nested checkout | Local overlay | Migration result |
|---|---|---|---|---|---|

Do not assume that the three canary repositories are the full fleet. The current
machine reports four registered projects and the audit found more repositories
with Devman options.

### 6.2 Create one migration per repository

For each repository:

1. run repoman devman status;
2. run repoman devman migrate without --apply;
3. review project identity and ordered groups;
4. validate nested-checkout and identity rules;
5. run repoman devman migrate --apply;
6. inspect only .devman/project.toml;
7. run the repository's own checks;
8. create a reviewable repository lane;
9. commit and push that repository change;
10. record the commit in the migration inventory.

The migration must not edit devenv.nix, devenv.lock, workflow bodies, or
machine state. If a repository has a deliberate local choice, preserve it in
the review. If identity is ambiguous, stop and ask for a repository-specific
decision.

### 6.3 Add a controlled wave command

If manual repetition becomes error-prone, add a RepoMan command that invokes
the one-repository migration once per selected repository. The command must:

- accept an explicit repository list;
- show proposed changes before writing;
- keep one result per repository;
- preserve a successful lane when a later repository fails;
- never activate the machine plane;
- never commit without an explicit repository operation.

Test a wave with one valid repository, one ambiguous repository, and one
missing repository. The valid lane must remain reviewable after the other two
fail.

### 6.4 Gate

Do not switch the default until every selected consumer has:

- a committed manifest;
- a pushed migration commit;
- a passing repository check;
- a recorded migration result;
- no unresolved identity or nested-checkout finding.

## 7. Implement explicit dual projection

Keep the old projection during comparison. Add an explicit mode. Do not infer
the mode from which binary happens to be first on PATH.

Use names that fit the existing interfaces, such as:

~~~text
compatibility -> consumer shell-entry projection
plane         -> Vendomat generation projection
~~~

Keep compatibility mode available through a machine setting or an explicit
Vendomat option. Print the selected mode in devman doctor and vendomat plane
show.

For every selected repository, compare:

1. project identity;
2. workflow identity;
3. source identity;
4. policy identity;
5. parameters and defaults;
6. trigger mappings;
7. generated Dagu content;
8. working and log paths;
9. queue names and limits;
10. schedule fields;
11. run output and metadata behavior.

Normalize only generated source comments. Do not normalize path, parameter,
queue, or workflow differences. Write every mismatch to a dated comparison
report with the project and workflow name.

Run the comparison against:

- Devman;
- RepoMan;
- Vendomat;
- a project with a local overlay;
- a project with multiple groups;
- a cross-repository workflow;
- a scheduled workflow;
- a workflow with declared writes;
- a project with an unusual path.

The comparison gate passes only when every intentional difference has a
recorded decision and every unintentional difference is fixed.

## 8. Expand the end-to-end canary

Use a small canary set first. Start with Devman, RepoMan, and Vendomat. Add
the other categories only after the first set passes.

For each canary, run:

~~~sh
vendomat plane plan devman --to VERSION --project-root ...
vendomat plane update devman --to VERSION --project-root ...
vendomat plane show devman
devman doctor
~~~

Verify all of these:

- one generation contains every selected project;
- every DAG validates;
- Dagu discovers every expected DAG;
- queue names are valid;
- schedules remain present;
- a task runs in the target repository;
- logs land in the target repository;
- metadata.jsonl records the run;
- stale generation output is visible;
- a changed policy rerenders only affected projects;
- an unchanged project is copied without rerendering;
- rollback restores the previous generation;
- recovery handles interrupted staging;
- the compatibility projection remains available.

Run one update with a project directory temporarily unavailable. Confirm that
the old active generation stays usable. Restore the directory and retry.

Run one update with a deliberately invalid DAG. Confirm that no new active
pointer appears. Then run vendomat plane recover devman and confirm that the
old pointer remains active.

## 9. Measure the new path

Use the same project set and machine for before and after values. Record raw
commands and dates in IMPLEMENTATION_LOG.md.

Measure:

| Measure | Old path | New path | Required result |
|---|---:|---:|---|
| cold plane build | | | record |
| warm plane build | | | record |
| first projection | | | record |
| projection per project | | | record |
| full-fleet staging | | | record |
| no-op update | | | lower than a full update |
| activation | | | record |
| rollback | | | record |
| interrupted recovery | | | record |
| shell-entry time | | | lower after cutover |
| consumer lock changes | | | zero for routine plane updates |
| consumer shell entries | | | zero for routine plane updates |
| independent failure points | | | lower or better isolated |

Use a warm and a cold run. State cache conditions. Do not compare a cold old
run with a warm new run.

The new path passes the performance gate when it materially reduces repeated
consumer work and does not move that work into an unmeasured machine step.

## 10. Switch the machine default

Switch only after the package, lifecycle, migration, comparison, canary, and
performance gates pass.

### 10.1 Prepare the machine configuration

Point only registryDir at the active generation. Keep stateDir and Dagu home
stable:

~~~nix
services.devman-dagu.registryDir =
  "$HOME/.local/state/vendomat/devman/active";
services.devman-dagu.stateDir = "$HOME/.local/state/devman";
~~~

Confirm the active pointer exists before starting the service. Confirm the
reload path unit is enabled:

~~~sh
systemctl --user is-enabled devman-dagu-reload.path
systemctl --user status dagu devman-watch devman-dagu-reload.path
~~~

### 10.2 Make plane mode the default

Change the machine configuration so normal service discovery uses the active
generation. Keep compatibility mode behind an explicit switch. Do not let the
old shell hook write into the active generation.

Perform the cutover in this order:

1. stop new plane updates;
2. record the current active generation;
3. create and validate the target generation;
4. confirm every migrated project is included;
5. activate the target pointer;
6. wait for any active run to finish;
7. let the reload adapter restart Dagu;
8. run devman doctor;
9. run one task in every canary repository;
10. record the cutover generation;
11. monitor the service and run records.

Keep the old generation and compatibility projection during the observation
period. Do not delete either one.

### 10.3 Remove routine consumer pins

After the machine default works, remove direct Devman runtime pins from
consumer repositories in controlled RepoMan changes. Keep the repository
manifest and repository task definitions. Do not remove a pin until the
replacement machine generation is installed on the target machine.

For each repository:

1. create a RepoMan proposal;
2. review the exact files;
3. run the repository checks;
4. commit and push the repository lane;
5. update the migration inventory;
6. verify that a routine plane update no longer changes its lock.

## 11. Remove obsolete fan-out

Remove old code only after the observation period and after all supported
consumers use the new path.

Remove in this order:

1. duplicate shell-entry projection calls;
2. duplicate resolver or renderer code;
3. routine consumer Devman lock updates;
4. compatibility registry writes;
5. compatibility mode only after the last supported consumer leaves it;
6. obsolete documentation and flags.

Retain:

- .devman/project.toml;
- RepoMan migration and review tools;
- Vendomat plan, update, show, rollback, and recover;
- generation metadata;
- projection metadata;
- stale checks;
- devman doctor;
- repository task definitions;
- Dagu run history;
- a documented emergency rollback.

After each removal, rerun the complete proof. Do not remove a fallback because
the new path passed one canary.

## 12. Daily project operations after cutover

### Update the machine plane

Run a plan first:

~~~sh
vendomat plane plan devman --to vNEXT
~~~

Review:

- target runtime;
- renderer, policy, Dagu, and toolchain identities;
- projects in scope;
- changed projects;
- unsupported or failed projects;
- validation results.

Activate only after the plan is correct:

~~~sh
vendomat plane update devman --to vNEXT
vendomat plane show devman
devman doctor
~~~

An unchanged update must report a no-op. It must not create a new generation or
rerender an unchanged project.

### Roll back

If the active generation is wrong or unhealthy:

~~~sh
vendomat plane rollback devman --to PRIOR_GENERATION
devman doctor
systemctl --user status dagu devman-watch
~~~

Do not edit files inside a retained generation. Roll back the pointer.

### Recover

After an interrupted operation:

~~~sh
vendomat plane recover devman
vendomat plane show devman
devman doctor
~~~

Read the retained recovery path before starting another update.

### Migrate one repository

Use RepoMan for repository changes:

~~~sh
repoman devman status
repoman devman migrate
repoman devman migrate --apply
~~~

Review and commit .devman/project.toml through the repository's normal lane.
Do not use a plane update to create or edit a manifest.

### Run project workflows

Use Devman to enqueue a workflow:

~~~sh
devman run base:check
devman run base:test
devman run base:check --project PROJECT
~~~

Use the repository's own devenv task definitions. Read the project run record
and log path after the run:

~~~sh
tail -3 .devman/.runs/metadata.jsonl
ls -t .devman/.runs/reports/ | head
~~~

## 13. Troubleshooting

Start with the health report:

~~~sh
devman doctor
vendomat plane show devman
systemctl --user status dagu devman-watch devman-dagu-reload.path
~~~

Use these actions:

| Finding | Action |
|---|---|
| no active generation | run vendomat plane recover devman, then build a generation |
| invalid staged DAG | fix the source or policy; do not force activation |
| stale projection | inspect generation and source digests; rerun plane update |
| active run blocks reload | wait for the run; do not kill it to force reload |
| reload remains pending | inspect dagu ps and the reload service log |
| project is offline | restore the project or follow the documented failed-project policy |
| active pointer is not a symlink | stop and repair through Vendomat; do not replace it by hand |
| rollback target missing | run vendomat plane show and select a retained generation |
| watcher has no paths | inspect project triggers and the watcher state |
| Dagu shows no workflow | check the active dags/ tree and devman doctor |
| task fails | read the Dagu .err file and the repository devenv ledger |

Never fix a generated projection by editing the registry. Fix the manifest,
policy, or renderer input, then rebuild the generation.

## 14. Final acceptance checklist

Mark the redesign complete only when every item is true:

- [ ] one Vendomat command builds and updates the machine plane;
- [ ] one immutable generation contains all selected projects;
- [ ] Devman, renderer, policy, Dagu, toolchain, and schema identities are recorded;
- [ ] all projects use one packaged renderer;
- [ ] projections record generation and source digests;
- [ ] stale output is visible and actionable;
- [ ] unchanged projects are no-ops;
- [ ] failed projects preserve the last valid active generation;
- [ ] unreadable projects have explicit results;
- [ ] activation is atomic;
- [ ] rollback works;
- [ ] interrupted operations recover without touching the active pointer;
- [ ] Dagu reload waits for active runs;
- [ ] Dagu history survives reload;
- [ ] reload failure has an operator path;
- [ ] repository migration uses RepoMan;
- [ ] every migrated repository change is reviewable and pushed;
- [ ] dual projection comparison has no unexplained mismatch;
- [ ] canaries cover overlays, groups, cross-repo workflows, schedules, writes, and unusual paths;
- [ ] Devman executes no repository task during render;
- [ ] Dagu still owns orchestration and history;
- [ ] devenv still owns task execution;
- [ ] no workflow contains a machine path;
- [ ] path and identity safety checks pass;
- [ ] before/after measurements show a material reduction in repeated work;
- [ ] the machine plane is the default projection source;
- [ ] compatibility mode is explicit;
- [ ] routine consumer lock updates no longer occur;
- [ ] required documentation is current;
- [ ] all repository gates pass;
- [ ] all completed commits are pushed;
- [ ] no unrelated worktree change was staged or committed.

When the checklist passes, update the project 038 status from IMPLEMENTING to
COMPLETE in the concept and implementation log. Record the cutover generation,
observation period, final measurements, and rollback test.
