# Project 038 consumer migration guide

Date: 2026-09-13

Use this guide in a clean session to remove the old Devman consumer integration
from the remaining repositories. Work on one repository at a time. Keep the
compatibility path until every supported repository has passed its migration
gate.

This guide covers the remaining consumer work after the machine-owned link
boundary became live. It does not restart the machine-plane redesign.

## 1. The target

Each migrated consumer has these properties:

- The repository tracks .devman/project.toml.
- The repository keeps its own task definitions.
- The central declaration imports the machine-owned link module.
- The central declaration reads the manifest identity or accepts the adapter's
  explicit project argument.
- The consumer has no Devman flake input.
- The consumer does not import devman/modules.
- The consumer has no devman option block for the old shell integration.
- A tracked lock removes only the unused Devman input and its root edge.
- Shell entry succeeds without a Devman input.
- Both public link status commands report the same five ok states.
- The active plane and Dagu inventory do not change.

The migration removes a consumer dependency. It does not remove the project
manifest, groups, task names, workflows, triggers, or machine-local links.

The target transition has two matched parts:

~~~
central devenv.local.nix -> imports link-module.nix and receives project identity
consumer devenv.yaml/nix  -> removes the old Devman input, import, and option
~~~

Apply both parts before testing shell entry. Importing the central module while
the consumer still imports the old module creates a duplicate devman.link
option declaration.

## 2. Current state

The machine boundary is live:

~~~
/run/current-system/sw/bin/devman-link
/run/current-system/sw/share/devman/link-module.nix
~~~

The active plane baseline is:

~~~
active pointer: generations/2
project directories: 46
DAG files: 146
DAG digest: 5acf4cc3be671f7118643e33eb01f37d708ed780ee228027956dce0dcee6022b
dagu ls output: 147 lines
~~~

Re-measure these values at the start of the session. Do not assume that the
machine state stayed unchanged.

Completed consumer removals:

| Repository | Consumer commit | Central declaration commit |
|---|---|---|
| vendomat | 5517878 | b089c4ba |
| atuout | 26e05f9 | 605daba8 |
| knappy | 62698bf | bcd4bc62 |

argentic has the consumer edits in its worktree. Its full gate is blocked by
11 live SilverBullet failures. Do not discard those edits. The details are in
ARGENTIC_GATE_RESEARCH_REPORT.md.

allium-env is leaving the project lineup. Exclude it from this migration.
Do not alter its checkout, manifest, central declaration, or active generated
state. The current design has no unregister command for an existing checkout.
Handle project removal as a separate operation.

## 3. Required reading

Start in the Devman repository:

~~~
$DM_ROOT/AGENTS.md
$DM_ROOT/AGENTS_GUIDE.md
$DM_ROOT/.scratch/projects/025-the-link-plane/CONCEPT.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/CONCEPT.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_GUIDE.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/REMOVAL_SEQUENCE_PROMPT.md
~~~

Read Stages 16 through 22 of IMPLEMENTATION_LOG.md. Stage 18 defines the
machine boundary. Stages 19 through 21 prove the consumer transition. Stage 22
records the Argentic gate.

Read the target repository's AGENTS.md before changing it. Read the target
repository's devenv.yaml, devenv.nix, .devman/project.toml, and central
devenv.local.nix before editing any of them.

Read the devman, devman-adopt, gitman, my-ai, and writing skills before using
their commands or editing their files.

## 4. Session setup

Use task-specific variables. Do not replace common system variables.

~~~
export DM_ROOT=/home/andrew/Documents/Projects/devman
export VM_ROOT=/home/andrew/Documents/Projects/vendomat
export RM_ROOT=/home/andrew/Documents/Projects/repoman
export NM_ROOT=/home/andrew/Documents/Projects/nix-meta
export DM_POLICY_ROOT=$DM_ROOT
cd "$DM_ROOT"
~~~

Run tools inside the repository's devenv shell. Batch commands when possible:

~~~
devenv shell -- true
devenv tasks run -v base:check
devenv tasks run -v base:test
~~~

Use the repository's own task names. Do not replace them with a direct tool
call. A direct test command is valid only for isolating a recorded failure.

Route version control through gitman. If a repository reports an off-canonical
state, preserve the state and stop. Do not run gitman reconcile during this
project unless the operator gives a separate instruction. Do not force-push.

## 5. Safety boundaries

Preserve these pre-existing changes:

~~~
Devman: src/devman/watch.py
        tests/unit/test_watch.py
RepoMan: devenv.lock and its other protected worktree changes
~~~

Do not modify, stage, discard, or commit these files as part of a consumer
migration. The Devman watcher files block only the final removal of the thin
src/devman/link.py re-export. Do not edit the watcher to unblock that cleanup.

Treat the central configuration checkout as a separate repository. Change only
the selected project's declaration. Preserve unrelated changes and generated
.local.gitignore files. Record the central commit separately. The central
checkout has no remote, so do not claim that its commit was pushed.

Do not hand-edit generated state:

~~~
$HOME/.local/share/devman
$HOME/.local/state/devman
$HOME/.local/state/vendomat/devman
$HOME/.local/share/dagu
~~~

Never stage a whole repository. Stage explicit paths only. Never reset or
discard a change that the session did not create.

## 6. Consumer inventory

Use the list below as the starting queue. Confirm every entry with a fresh
worktree check before editing it.

### 6.1 Migrations to complete

These repositories have a manifest but still need the old consumer integration
removed:

~~~
argentic       browsee              boomtube             cairn
embeddy        eventic              flora                flora-core
flora-qc       fornix               gitman               grail
image-gen-pipeline               interplay             llgym
loci-core      loci.nvim            nix-desktop          nix-nvim
nix-paseo      nix-secrets          nixbuild             nixvim
observantic    paloma-text-pipeline parsedantic         poddantic
pydantree      pyjutsu              pyllij               pytuin
shellij        structured-agents-v2 talkee               templateer_v2
terminal-state testee              tyo3                  webdantic
zelligate
~~~

The line breaks are for reading. Treat each name as one repository. The list
contains the current Argentic worktree and the 39 remaining manifest-backed
consumers after the completed migrations and the allium-env exclusion.

Start with a clean, manifest-backed repository whose branch has a clear owner.
flora-qc, loci.nvim, nix-nvim, pyllij, browsee, tyo3, and zelligate are useful
early candidates because their prior manifest migration reached a clean or
known gate. Rerun all gates. Do not treat an old result as a current pass.

### 6.2 Decisions required before migration

These repositories do not have a root manifest. Their old Devman option block
is in dev/devenv.nix:

~~~
copyroom
docman
mypi-agent
~~~

Choose the manifest location with the operator before changing any of them.
Do not move the option, add a second manifest, or infer the location from a
nearby repository.

Seven repositories have local manifest commits from an earlier detached HEAD:

~~~
gitman
image-gen-pipeline
llgym
loci-core
nix-paseo
pydantree
pyjutsu
~~~

Choose the destination branch before adding a new consumer-removal commit.
Do not create a branch or push a detached commit without that decision.

### 6.3 Compatibility-only state

The compatibility registry also contains five old-only projects:

~~~
copyroom
docman
fleetman
flora-037-part-e
mypi-agent
~~~

It also contains three broken my-ai links. These are separate cleanup work.
Do not delete them because the active plane has no matching project.

## 7. Establish the baseline

Inspect the four working repositories and the central checkout:

~~~
for repo in "$DM_ROOT" "$VM_ROOT" "$RM_ROOT" "$NM_ROOT"; do
  printf '\n== %s ==\n' "$repo"
  gitman --repo "$repo" status
  gitman --repo "$repo" log --revset '@'
done

printf '\n== central configuration ==\n'
cd "$HOME/.config/devman"
gitman status
gitman log --revset '@'
cd "$DM_ROOT"
~~~

If a repository does not provide gitman, follow its own AGENTS.md and the
active project prompt. Keep the same rules: explicit paths, no force-push, and
no mutation of unrelated work.

Record the installed boundary before testing a consumer:

~~~
test -x /run/current-system/sw/bin/devman-link
test -f /run/current-system/sw/share/devman/link-module.nix
readlink -f /run/current-system/sw/bin/devman-link
~~~

Record the plane baseline outside every project shell. Clear both Python path
variables so a checkout cannot shadow the installed command:

~~~
env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman doctor

env -u PYTHONPATH -u NIX_PYTHONPATH \
  dagu --dagu-home "$HOME/.local/share/dagu" ls

PLANE="$HOME/.local/state/vendomat/devman/active"
readlink "$PLANE"
find -L "$PLANE/projects" -mindepth 1 -maxdepth 1 -type d | wc -l
find -L "$PLANE/dags" -mindepth 1 -maxdepth 1 -type f -name '*.yaml' | wc -l
find -L "$PLANE/dags" -type f -name '*.yaml' -exec sha256sum {} + | sort | sha256sum
~~~

The known doctor result is exit 1 with four existing findings. Record the
findings. Do not hide the exit code with || true. A new finding blocks the
commit until it has a cause and an approved decision.

Save the baseline values in the session record:

~~~
doctor exit and findings:
active pointer:
project count:
DAG count:
DAG digest:
dagu ls line count:
~~~

## 8. Select and preflight one repository

Set the target variables after selecting a repository:

~~~
export PROJECT_NAME=flora-qc
export PROJECT_ROOT=/home/andrew/Documents/Projects/flora-qc
export CENTRAL_FILE="$HOME/.config/devman/projects/$PROJECT_NAME/devenv.local.nix"
~~~

Check the repository before creating a lane:

~~~
cd "$PROJECT_ROOT"
gitman status
gitman log --revset '@'
test -f .devman/project.toml
sed -n '1,120p' .devman/project.toml
sed -n '1,240p' devenv.yaml
sed -n '1,280p' devenv.nix

printf '\n== central declaration ==\n'
sed -n '1,260p' "$CENTRAL_FILE"
~~~

Confirm the identity before editing:

~~~
env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman-link status \
  --project "$PROJECT_NAME" \
  --root "$PROJECT_ROOT" \
  --overlay "$HOME/.config/devman"
~~~

The command must return exit 0 with five ok states. If it reports drift,
record the drift and decide whether it belongs to this migration. Do not repair
unrelated real files such as a repository-owned .agents directory.

Search for all old consumer references in the target:

~~~
rg -n \
  'devman/modules|devman\.project|devman\.groups|devman[[:space:]]*=' \
  devenv.yaml devenv.nix dev 2>/dev/null
~~~

Read the matching context. Do not remove a field that belongs to a repository
task or another integration.

## 9. Create the migration lane

Create one named lane for the selected repository. Use the branch name required
by the target repository's policy. A normal name is:

~~~
cd "$PROJECT_ROOT"
gitman start 038-devman-consumer-"$PROJECT_NAME"
~~~

If a lane already exists, resume it. If the checkout is detached, stop and
resolve branch ownership first. If the worktree is dirty, identify each change
before editing. Preserve changes that predate this session.

Do not process two consumers in one lane or one commit. One consumer gives one
reviewable rollback point and one proof record.

## 10. Make the matched transition

### 10.1 Change the central declaration

Edit only the selected project's central declaration. Keep its existing link
map. Change the function boundary and identity expression to this shape:

~~~nix
{ config, project ? null, ... }:

let
  projectName =
    if project != null then project
    else
      (builtins.fromTOML
        (builtins.readFile "\${config.devenv.root}/.devman/project.toml")).project;
in

{
  imports = [ /run/current-system/sw/share/devman/link-module.nix ];

  devman.link = {
    # Keep the selected project's existing declarations here.
    # Replace only old config.devman.project expressions with projectName.
  };
}
~~~

Do not copy another project's link map. Preserve canonical paths and link
ownership. Keep one devman.link attribute set. Do not add a second file
format for links.

The adapter supplies project when it calls the central function. The manifest
fallback keeps normal devenv evaluation clear and testable. The central file
must not depend on the old config.devman.project option.

Check the result:

~~~
rg -n 'config\.devman\.project|imports|devman\.link|projectName' \
  "$CENTRAL_FILE"
~~~

### 10.2 Change devenv.yaml

Remove only the old Devman input and the devman/modules import. Preserve:

- RepoMan, Vendomat, Shellij, and other inputs;
- input follows and lock structure;
- secretspec settings;
- repository-specific modules;
- comments that still describe a live integration.

Use the exact names and formatting already present in the file. Do not remove
an input because its name resembles Devman.

### 10.3 Change devenv.nix

Remove only the old Devman option block. It commonly looks like:

~~~nix
devman = {
  enable = true;
  project = "project-name";
  groups = [ "base" ];
};
~~~

The manifest now supplies the project identity and groups. Preserve all task
definitions. Preserve devenv.local.nix imports and other machine settings.

If the block is not in root devenv.nix, stop. This is the known structural case
for copyroom, docman, and mypi-agent.

### 10.4 Update the lock only as needed

If devenv.lock is tracked, remove the unused Devman node and its root edge.
Keep every unrelated input, revision, and pin unchanged.

If devenv.lock is ignored, update it locally only when shell evaluation needs
the change. Do not stage it.

After any lock operation, inspect the diff. devenv shell can normalize
unrelated lock entries. Do not accept those changes as part of this migration.
Restore only changes created by the current session, with an explicit patch.
Do not discard pre-existing lock changes.

## 11. Verify the consumer

Run the checks in layers. Stop at the first new failure.

### 11.1 Structural check

~~~
cd "$PROJECT_ROOT"
devenv shell -- true

rg -n \
  'devman/modules|devman\.project|devman\.groups|devman[[:space:]]*=' \
  devenv.yaml devenv.nix dev 2>/dev/null
~~~

The search may find repository comments or unrelated compatibility test data.
Review every result. The old consumer input, import, and option must be gone.

### 11.2 Repository gate

Run the target's declared checks:

~~~
devenv tasks run -v base:check
devenv tasks run -v base:test
~~~

If the repository has no base:check or base:test, run the task names that its
AGENTS.md defines. Record a missing task as a repository property. Do not
invent a new gate in the migration.

For Argentic, run the full gate exactly:

~~~
devenv tasks run -v base:test
~~~

If its live suites fail, isolate only for diagnosis:

~~~
devenv shell -- pytest \
  --ignore=tests/test_loop_live.py \
  --ignore=tests/test_overlay_live.py
~~~

Do not fix application behavior as part of a Devman boundary migration. Record
the failure, preserve the consumer edits, and wait for the live gate or an
explicit documented waiver.

### 11.3 Link canaries

Run both public boundaries from outside every project shell:

~~~
cd /tmp
env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman-link status \
  --project "$PROJECT_NAME" \
  --root "$PROJECT_ROOT" \
  --overlay "$HOME/.config/devman"

env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman link status \
  --project "$PROJECT_NAME" \
  --root "$PROJECT_ROOT" \
  --overlay "$HOME/.config/devman"
~~~

Both commands must return exit 0. Both must report five ok states and the same
central configuration path. A canary failure blocks the commit.

### 11.4 Plane invariants

Repeat the baseline measurements:

~~~
PLANE="$HOME/.local/state/vendomat/devman/active"
readlink "$PLANE"
find -L "$PLANE/projects" -mindepth 1 -maxdepth 1 -type d | wc -l
find -L "$PLANE/dags" -mindepth 1 -maxdepth 1 -type f -name '*.yaml' | wc -l
find -L "$PLANE/dags" -type f -name '*.yaml' -exec sha256sum {} + | sort | sha256sum
env -u PYTHONPATH -u NIX_PYTHONPATH \
  dagu --dagu-home "$HOME/.local/share/dagu" ls
env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman doctor
~~~

The active pointer, project count, DAG count, DAG digest, and Dagu line count
must match the baseline. Doctor may keep the known findings. It must not gain a
new finding.

Run the Devman gates when the migration changes a Devman file or the project
log:

~~~
cd "$DM_ROOT"
devenv tasks run -v base:check
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
devenv shell -- nix build .#packages.x86_64-linux.devman-link --no-link
~~~

Gitman has no diff command. In this project, the removal prompt permits the
read-only Git fallback for diff review. Use it only after gitman status:

~~~
git -C "$PROJECT_ROOT" diff --check
git -C "$PROJECT_ROOT" diff
~~~

Review the complete diff before saving it.

## 12. Save one migration

Review the target file list. It should contain only the intended consumer files
and, for a tracked lock, the narrow Devman removal.

~~~
cd "$PROJECT_ROOT"
gitman status
git -C "$PROJECT_ROOT" diff --check
git -C "$PROJECT_ROOT" diff
~~~

Save the consumer lane with a focused message:

~~~
gitman save -m "refactor: remove Devman consumer integration"
gitman publish
~~~

Do not publish a detached commit. Do not publish a change with a failed gate.
If the consumer repository requires a pull request, publish the lane and record
the branch and commit for review.

Save the central declaration separately, using its repository's version-control
rules. Record its local commit hash. The central checkout has no remote.

After both commits exist, rerun the two canaries and the plane invariants. A
successful pre-commit canary is not enough. The proof must describe the final
committed state.

Append one dated entry to IMPLEMENTATION_LOG.md. Include:

~~~
repository and project identity
consumer commit and central commit
changed files
old input/module/option removed
lock result
repository gate commands and results
both link canary results
doctor result and findings
active pointer, project count, DAG count, digest, and Dagu count
unrelated findings preserved
next repository or blocker
~~~

Commit and publish the Devman log update as its own Devman documentation
change. Do not include protected watcher files or unrelated worktree changes.

## 13. Failure handling

| Failure | Meaning | Action |
|---|---|---|
| attribute 'devman' missing | The central declaration still reads the old option. | Convert the central declaration first. Do not remove more consumer code. |
| Duplicate devman.link option | The central module and old consumer module both declare the option. | Remove the old consumer import and centralize the declaration in the same transition. |
| no manifest | The repository has no portable identity. | Stop and choose the manifest placement with the operator. |
| Detached HEAD | The migration has no safe publish destination. | Stop and resolve branch ownership. |
| Lock diff changes unrelated pins | The evaluator normalized more than Devman. | Preserve pre-existing changes and narrow the session diff. |
| Link status is not five ok states | The central declaration or machine boundary is wrong. | Do not commit. Inspect the exact reported path and identity. |
| New doctor finding | The migration changed machine-visible state or exposed existing drift. | Classify it. Fix only a finding caused by this migration. |
| Repository test failure | The consumer gate is not green. | Isolate, classify, and record it. Do not hide it with a waiver. |
| Generated plane count or digest changed | The consumer migration touched the active plane. | Stop. Consumer migration must not activate or rewrite plane state. |
| gitman reports off-canonical | Version-control state needs operator recovery. | Preserve the worktree. Do not reconcile during this project. |

## 14. Migration order

Use this order:

1. Resume or resolve the Argentic gate.
2. Migrate one clean manifest-backed repository.
3. Run the full consumer and plane proof.
4. Record and publish the consumer and Devman log commits.
5. Repeat for the next repository.
6. Resolve the three manifest-placement decisions.
7. Resolve the seven detached-HEAD branch decisions.
8. Recheck the compatibility-only projects and broken links.
9. Confirm that every supported consumer has left the old integration.
10. Begin the section 11 compatibility removals, one item per reviewed change.

Do not batch the fleet into one unreviewed mutation. A wave command is valid
only if it shows a proposal, keeps one result per repository, preserves earlier
successful lanes, and never activates the machine plane. Manual one-repository
migrations are preferred until the remaining exceptions are understood.

## 15. Complete the section 11 removal sequence

The first two items are complete:

1. Duplicate shell-entry projection calls: complete.
2. Duplicate resolver or renderer code: complete.

The remaining items depend on the consumer fleet:

3. Remove routine consumer Devman lock updates after every supported consumer
   has the machine-owned link boundary.
4. Remove compatibility registry writes after a supported replacement exists for
   every remaining consumer.
5. Remove compatibility mode only after the last supported consumer leaves it.
6. Remove obsolete documentation and flags after the previous removals.

Give each removal its own design note, focused diff, test result, canary, plane
invariant result, doctor result, and commit. Do not remove a fallback because
one canary passed.

Retain these supported interfaces and data:

~~~
.devman/project.toml
RepoMan migration and review tools
Vendomat plan, update, show, rollback, and recover
generation and projection metadata
stale checks
devman doctor
repository task definitions
Dagu run history
documented emergency rollback
~~~

The thin src/devman/link.py re-export remains until the protected watcher change
is released. Then fold the import into the final owner and delete the shim in a
separate Devman change.

## 16. Completion checklist

Project 038 consumer work is ready for final cleanup only when all answers are
true:

- [ ] Every supported manifest-backed consumer has a pushed migration commit.
- [ ] Every central declaration uses the machine-owned link module.
- [ ] No supported consumer imports devman/modules.
- [ ] No supported consumer carries the old devman option block.
- [ ] Every tracked lock has only the intended Devman removal.
- [ ] Argentic has a passing live gate or a documented operator waiver.
- [ ] The three structural repositories have approved manifest placements.
- [ ] The seven detached repositories have approved branch destinations.
- [ ] Allium-env remains unchanged and explicitly excluded.
- [ ] The five old-only compatibility projects have an explicit disposition.
- [ ] The three broken compatibility links have an explicit disposition.
- [ ] The compatibility registry has a supported replacement before writes stop.
- [ ] The active pointer and all plane invariants remain stable.
- [ ] Devman doctor has no new finding.
- [ ] Protected worktree changes remain untouched.
- [ ] The final removal sequence has separate commits and evidence.
