# Project 038 — B: independent link adapter

Date: 2026-09-13
Status: implementation guide
Scope: the Devman link adapter only

This guide is for a clean implementation session after the A-to-C bridge.
It does not repeat the migration, comparison, or canary work that A to C
completed.

The guide implements B:

> Extract the machine-local link adapter into a stable, independently
> packageable component without changing the central link configuration.

The guide does not remove compatibility mode. It does not remove compatibility
registry writes. It does not move registryDir. It does not remove consumer
Devman pins. Those changes need separate evidence under Project 038 §11.

## 1. Target result

Keep these interfaces unchanged:

~~~
<repository>/.devman/project.toml
$HOME/.config/devman/projects/<project>/devenv.local.nix
~~~

Keep this central Nix shape:

~~~nix
{ config, ... }:

{
  devman.link = {
    ".envrc" = {
      canonical = "central";
      path = "common/envrc";
    };

    ".agents" = {
      canonical = "central";
      path = "projects/${config.devman.project}/agents";
    };

    ".claude/skills" = {
      canonical = "central";
      path = "projects/${config.devman.project}/agents/skills";
    };

    ".loci" = {
      canonical = "external";
      path = "~/Notes/1_Projects/${config.devman.project}";
    };
  };
}
~~~

The final B layout has these ownership boundaries:

| Concern | Owner after B | B rule |
|---|---|---|
| Repository identity | .devman/project.toml and the existing contract | Do not add a second identity parser |
| Central declarations | $HOME/.config/devman/projects/<project>/devenv.local.nix | Do not add TOML, YAML, or JSON link declarations |
| Link declaration evaluation | devman-link | Evaluate the existing Nix expression |
| Path resolution and safety | devman-link | Keep all current root checks |
| Link inspection and reconciliation | devman-link | Keep the current result states and promotion rules |
| Workflow rendering | Devman renderer and Vendomat | Do not move it into the link adapter |
| Active workflow generation | Vendomat | Do not read or write it from link reconciliation |
| Compatibility projection | Devman | Keep it until its own removal gate passes |
| Repository-specific changes | RepoMan | Do not make B a migration wave |

The recommended first B target is a separate importable and packageable
devman_link component. It may remain source-owned by the Devman repository in
the first B slice. A separate source repository needs an approved owner and
remote. Do not invent that repository during implementation.

Use the executable name devman-link. Keep devman link as the user-facing
Devman command. The public command may resolve identity and then call the
component. The shell hook may call the component directly.

The component must not depend on:

- the compatibility registry for normal status or reconciliation;
- the active Vendomat generation;
- the workflow renderer;
- the watcher;
- Dagu run execution;
- repository task execution;
- directory-name identity inference.

The component may call the existing Nix evaluator for the central file and the
existing template tool for a declared central template. It must not parse a
workflow to understand a link.

## 2. Current baseline

The A-to-C bridge left these facts in place:

- Vendomat owns the active workflow plane.
- The active plane is explicit plane mode.
- Compatibility mode remains available.
- The active generation has 46 projects and 146 generated DAG files.
- The live generation pointer is retained by Vendomat.
- Devman state registration still reports the old compatibility set.
- 43 repositories are migrated in the current inventory.
- copyroom, docman, and mypi-agent remain blocked.
- The central overlay remains machine-local and outside the project worktrees.

Re-measure every count in the new session. Do not copy a count from this
section into the implementation log without running the command.

The current Devman feature branch is 038-fixup-and-fanout. The A-to-C bridge
was pushed at or after commit f615a79. Continue from the current feature
branch. Do not create a new branch from stale main.

The following Devman paths are protected while the existing unrelated worktree
changes remain:

~~~
src/devman/link.py
src/devman/watch.py
tests/unit/test_link.py
tests/unit/test_watch.py
~~~

Do not modify, stage, discard, or commit these paths. If B cannot be completed
without changing one of them, stop and ask the user. Do not copy their code
into a second implementation to bypass this rule.

RepoMan has a protected pre-existing devenv.lock change. Do not modify,
unstage, discard, or commit it.

## 3. Start the clean session

Start in Devman:

~~~sh
cd /home/andrew/Documents/Projects/devman

export DM_ROOT=/home/andrew/Documents/Projects/devman
export VM_ROOT=/home/andrew/Documents/Projects/vendomat
export RM_ROOT=/home/andrew/Documents/Projects/repoman
export NM_ROOT=/home/andrew/Documents/Projects/nix-meta
export DM_POLICY_ROOT=$DM_ROOT
~~~

Read these files completely before changing code:

~~~
$DM_ROOT/AGENTS.md
$DM_ROOT/AGENTS_GUIDE.md
$DM_ROOT/.scratch/projects/025-the-link-plane/CONCEPT.md
$DM_ROOT/.scratch/projects/025-the-link-plane/GUIDE-02-link-plane.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/CONCEPT.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_GUIDE.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/LINK_PLANE_A_TO_C_GUIDE.md
$VM_ROOT/AGENTS.md
$RM_ROOT/AGENTS.md
$NM_ROOT/AGENTS.md
~~~

Read these skills before using their commands or editing their files:

~~~
Devman
Devman adoption
Gitman
my-ai
writing
~~~

Do not use FULL_REFACTOR_PROMPT.md as authority. The implementation log and
the A-to-C guide control this work.

Inspect all repositories before work:

~~~sh
for repo in "$DM_ROOT" "$VM_ROOT" "$RM_ROOT" "$NM_ROOT"; do
  printf '\n== %s ==\n' "$repo"
  git -C "$repo" status --short --branch
  git -C "$repo" log -1 --oneline --decorate
done
~~~

Inspect the central checkout only. Do not modify or commit it:

~~~sh
git -C "$HOME/.config/devman" status --short --branch
~~~

Use read-only Gitman status and log commands. Do not run gitman reconcile.
If Gitman cannot save or publish because the checkout is off-canonical, use
the explicit raw Git fallback described in section 15.

## 4. Record the live baseline

Run the live commands outside every project devenv shell. Clear both Python
path variables:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman doctor

env -u PYTHONPATH -u NIX_PYTHONPATH dagu --dagu-home "$HOME/.local/share/dagu" ls
~~~

Record these values:

1. The devman doctor exit code.
2. The doctor mode.
3. Every doctor finding.
4. The active Vendomat generation number.
5. The active generation symlink target.
6. The active project directory count.
7. The active DAG file count.
8. The compatibility registry project count.
9. The Dagu workflow count.

Use read-only commands for the active generation:

~~~sh
PLANE_ROOT="$HOME/.local/state/vendomat/devman/active"
readlink "$PLANE_ROOT"
find -L "$PLANE_ROOT/projects" -mindepth 1 -maxdepth 1 -type d | wc -l
find -L "$PLANE_ROOT/dags" -mindepth 1 -maxdepth 1 -type f -name '*.yaml' | wc -l
sed -n '1,160p' "$PLANE_ROOT/generation.json"
~~~

Do not confuse the doctor summary with the active plane count. The doctor
summary still reads the old Devman state-registration directory.

Known findings must remain visible if they still exist:

- flora-037-part-e link drift;
- dirty, unpinned Vendomat source;
- dirty, unpinned RepoMan source;
- any other finding reported by the live command.

A doctor exit code of 1 is a finding result. It is not proof of a crash. A
passing test does not erase a doctor finding.

## 5. Confirm that B is ready

Confirm A before extracting anything:

~~~sh
rg -n "check_mode|generation\.json|compatibility|plane" src/devman/doctor.py src/devman/cli.py modules nix .scratch/projects/038-devman-plane-redesign
~~~

The implementation must still expose exactly these two mode values:

~~~
plane
compatibility
~~~

Do not add a mode source as part of B. Do not move registryDir. Do not remove
compatibility registry writes. Do not change Vendomat generation ownership.

Confirm C before extracting anything:

~~~sh
rg -n "ProjectManifest|project\.toml|resolve_project_identity|devman\.link|central config" src/devman modules tests
~~~

The manifest resolver in src/devman/identity.py remains the one identity
resolver. The central file remains the one human-authored link declaration.

Inventory all adapter call sites:

~~~sh
rg -n "devman-link|devman link|linkScript|devman\.link|from (devman|\.) import link|--registry|--state" src modules nix tests flake.nix pyproject.toml "$VM_ROOT" "$RM_ROOT" "$NM_ROOT"
~~~

Read these implementation files before choosing an extraction seam:

~~~
src/devman/contract.py
src/devman/identity.py
src/devman/cli.py
src/devman/link.py
tests/unit/test_link.py
modules/devenv.nix
nix/renderer.nix
nix/devman-cli.nix
nix/nixos-module.nix
nix/tests/dagu-service.nix
~~~

Read link.py and test_link.py only. Do not edit them while they are protected.

The current devman-link entry point is devman.link:cli. The current shell hook
obtains the link binary from the renderer derivation. The current public
devman link command already resolves the manifest before it enters the
protected adapter. Use these facts as the extraction baseline.

## 6. Define the stable component contract

Write the B decision into the implementation log before code changes. Keep it
short and concrete. The decision must answer these questions.

### 6.1 Component inputs

The adapter receives:

- a repository root;
- an optional explicit project identity;
- an overlay root;
- the central project configuration path, derived below the overlay root;
- a link operation: status or reconcile.

The adapter must resolve the root and overlay to absolute paths. It must refuse
an absent repository root, an absent central file, and a central file outside
the overlay.

The adapter must use the existing manifest contract. Do not copy the TOML
parser into the new component.

Use one of these two ownership choices:

1. Depend on a separately packageable contract library that exports the
   existing manifest and identity rules.
2. Move the pure contract code into a small contract package and leave
   compatibility imports in devman.contract.

Choose one. Do not make the adapter depend on the full workflow renderer or
the compatibility registry merely to reuse identity_fault.

### 6.2 Component operations

Keep these operations:

~~~
status       inspect links without changing files
reconcile    apply declarations and return one result per view
~~~

Keep the current link result states:

~~~
ok
repoint
promote
link
create
~~~

Keep the command exit contract:

~~~
0  operation succeeded; status found no drift
1  status found drift, or reconciliation refused a requested change
2  usage or infrastructure error
~~~

Keep structured data available for the public Python caller. Keep the existing
plain-text status output for operators. Status must report the central
configuration path.

### 6.3 Component dependencies

The new component may depend on the Python standard library, the shared
contract, and the operating-system tools needed to evaluate Nix. It must not
import these modules:

~~~
devman.registry
devman.project
devman.watch
devman.doctor
devman.run
vendomat
~~~

It must not read metadata.json, a compatibility project record, or
generation.json to perform a normal link operation.

### 6.4 Compatibility command behavior

Inventory callers before removing --registry and --state from any command.
Do not silently accept and ignore those flags.

If a caller still needs the old registry-driven command, keep an explicit
compatibility wrapper for the observation period. Give it a name that states
its role, or keep it behind the existing compatibility mode. Make the new
devman-link path refuse a legacy-only invocation with a repair action.

Do not make --all part of the independent adapter. The compatibility registry
is the only owner that can enumerate the old registered projects.

## 7. Characterize the current adapter

Build a behavior matrix before moving code. Use a temporary directory and
central declarations. Do not use a generated registry or the active plane as
the fixture.

Cover these cases:

1. A missing view with an existing central target.
2. A missing view and missing central target.
3. A correct link as a no-op.
4. A wrong link to an existing target.
5. A real file that must be promoted.
6. A real directory that must be promoted.
7. A changed canonical side that must refuse promotion.
8. A central path that escapes the overlay.
9. A central path that escapes through a symlinked parent.
10. A repository view that escapes through a symlinked parent.
11. An external path inside the repository.
12. An external path inside the overlay.
13. A dangling bootstrap link.
14. A normal Git exclude file.
15. A linked-worktree Git exclude file.
16. A two-sided .git/info/exclude edit.
17. A central template on a central declaration.
18. A template on a repository or external declaration.
19. A declaration with an unknown or invalid shape.
20. A repository with no compatibility registry entry.
21. A repository with a manifest identity and matching explicit identity.
22. A repository with a manifest identity and mismatching explicit identity.
23. A manifest-free compatibility repository.
24. A directory whose name differs from the stated project identity.

Use the protected tests/unit/test_link.py as a read-only behavior reference.
Add new tests in a new file. Do not edit or stage the protected test file.

Record the old result and the new result for each case. The result may differ
only when the old result depended on the compatibility registry. All safety
refusals must remain refusals.

## 8. Implement the new component

Use a new package boundary. The recommended initial layout is:

~~~
src/devman_link/
  __init__.py
  api.py
  declarations.py
  paths.py
  reconcile.py
  cli.py
~~~

The exact file split may differ. Keep the public API small. Do not expose
internal state-file helpers as the component contract.

### 8.1 Move the pure declaration and path logic

Implement one declaration type with these fields:

~~~
view
canonical
path
template
~~~

Validate the declaration before resolving a path. Refuse unknown canonical
values, non-string paths, invalid templates, absolute central paths, relative
external paths after expansion, empty views, and traversal components.

Resolve the three canonical classes as follows:

~~~
central    under overlay/projects or the declared overlay path
repo       under overlay/projects/<project>/repo, pointing to the repository
external   absolute path outside both the repository and overlay
~~~

Keep ${project} expansion. Validate the expanded value before joining it to a
root. Resolve symlinked parents and check the resolved path against the root.
Reject the root itself and every path outside the declared root.

### 8.2 Move reconciliation behavior

Preserve these rules exactly:

- inspect before changing a view;
- promote real views before replacement;
- refuse when the canonical side changed since the recorded baseline;
- make promotion reviewable with the existing backup behavior;
- create a canonical target only when the declaration permits it;
- create the bootstrap central devenv.local.nix with the standard link block;
- maintain the central .local.gitignore file;
- keep .git/info/exclude centrally owned;
- support linked Git worktrees;
- write state atomically;
- do not delete unrelated files.

Keep the state file location and record shape stable unless the decision record
proves that the new component needs a versioned change. A change to the state
schema needs a compatibility reader and a migration test.

### 8.3 Evaluate the central file

The adapter must evaluate the central file before it reconciles links. Supply
the selected project identity as the config.devman.project value. Read only
the resulting devman.link attribute set.

Refuse these cases with the file path and a repair action:

- central file does not exist;
- Nix evaluation fails;
- evaluation does not return a link attribute set;
- the expression has unknown link fields;
- the expression resolves to an identity different from the manifest;
- a declared central target escapes the overlay;
- an external target enters the repository or overlay.

Do not replace Nix with a second human-authored format. Do not evaluate the
whole repository environment to reconcile a link.

### 8.4 Preserve identity precedence

Keep this precedence at the public adapter boundary:

1. explicit --project;
2. .devman/project.toml in the supplied root;
3. old literal devman.project only when no manifest exists;
4. loud refusal.

When both manifest and old Nix identity exist, compare them. Refuse a mismatch
and name:

- repository root;
- manifest identity;
- compatibility identity;
- repair action.

Never use the directory name. Never accept an empty, path-like, unsupported, or
invalid Dagu identity.

If the independent component cannot use the existing resolver without copying
the parser, make the contract package decision in section 6.1 first. Do not
write a second parser.

## 9. Wire the public and shell boundaries

Wire the new component in this order.

### 9.1 Public devman link

Keep src/devman/cli.py as the public identity boundary. It must:

1. resolve the identity;
2. validate the central file and declarations;
3. call the independent adapter API;
4. print the central configuration path for status;
5. return the adapter result code.

Keep the protected src/devman/link.py out of the normal path. Keep the old
--all compatibility path only if the compatibility registry still owns
enumeration.

Do not make devman link read the active generation. Do not call the renderer.

### 9.2 devman-link executable

Point the devman-link entry point at the new component. The canonical command
must work without a compatibility registry entry:

~~~sh
devman-link status --project vendomat --root /home/andrew/Documents/Projects/vendomat --overlay "$HOME/.config/devman"
~~~

If old positional arguments or old flags have consumers, keep a separate
compatibility wrapper. Do not hide a registry dependency inside the new
command.

### 9.3 The shell hook

Keep the hook thin. It may:

1. establish the repository root and machine paths;
2. call compatibility projection when the selected mode requires it;
3. call devman-link reconcile;
4. clean up its variables.

The hook must not parse TOML, evaluate link declarations, promote files, or
discover repositories. Do not call the workflow renderer twice.

The preferred B shape calls the machine-installed devman-link component.
Keep the old renderer-provided adapter as an explicit rollback path until the
new machine package passes the observation gate. Do not silently fall back to
whichever binary appears first on PATH.

The hook must remain independent from the active Vendomat generation. A plane
generation update must not change link targets.

## 10. Package the component independently

Start with a separate Nix derivation. The recommended file is:

~~~
nix/link-adapter.nix
~~~

The derivation must:

- build only the adapter and its contract dependency;
- expose devman-link;
- avoid dagu, watchexec, and the workflow renderer;
- run an install check for devman-link --help;
- run a no-registry status fixture;
- expose a stable package output such as packages.<system>.devman-link.

Do not remove devman-link from nix/renderer.nix in the same first change
that creates the package. First prove that the machine package works. Then use
separate commits for:

1. the new package;
2. the machine installation;
3. the shell-hook switch;
4. removal of the renderer copy after the observation period.

The machine package may initially come from the Devman flake. That is an
independent package boundary. A later source-repository split must keep the
same executable and central configuration interface.

Install the component on the machine through the existing NixOS module or the
Vendomat plane package. Do not put a new per-project path or link format in
devenv.local.nix.

If the module needs a new option, keep it machine-level and document its
default. Do not add a new DEVMAN_* environment variable. The shared
environment contract is closed.

## 11. Add tests without touching protected tests

Create a new test file. Use a name such as:

~~~
tests/unit/test_link_adapter.py
~~~

Test the public adapter API and at least one real subprocess invocation. The
new test file must cover:

- no registry access for normal status;
- no active-generation access;
- manifest identity without --project;
- matching explicit identity;
- mismatching explicit identity;
- matching manifest and Nix identities;
- mismatching identities;
- manifest-free compatibility fallback;
- directory-name refusal;
- field-specific repair messages;
- central-file evaluation;
- central-path and external-path safety;
- bootstrap target validation;
- all five link states;
- promotion and conflict refusal;
- .git/info/exclude ownership;
- linked-worktree excludes;
- atomic state writes;
- status has no writes;
- reconcile does not touch a DAG or generation file.

Keep existing protected link and watcher tests unchanged. Add a conformance
fixture only when the new component introduces a new boundary that a unit test
cannot reach.

Update the Nix fileset whenever a new source or test file must enter the
hermetic flake check. A local test passing while base:test omits the new file
is not a valid result.

## 12. Verify the extraction in layers

Run commands inside devenv unless the command explicitly checks the live
installed system.

### 12.1 Fast Devman loop

~~~sh
cd "$DM_ROOT"
devenv tasks run -v base:check
devenv tasks run -v base:unit
~~~

Use the repository task entry point. Do not call bare pytest, python, or ruff.

### 12.2 Hermetic and Nix checks

~~~sh
cd "$DM_ROOT"
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
~~~

Confirm that the new component package builds and its install check runs. Use
the exact output name selected in section 10.

### 12.3 Live identity and mode check

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman doctor
~~~

The command may return 1 for known findings. Confirm the mode is still plane,
and confirm compatibility mode remains available in code and tests.

### 12.4 Machine package check

If nix-meta changes, run:

~~~sh
cd "$NM_ROOT"
nixos-rebuild build --flake .#server
~~~

If activation is required and sudo cannot obtain a password, do not change
the machine by another method. Commit and push the nix-meta change, then give
the operator this command:

~~~sh
sudo nixos-rebuild switch --flake .#server
~~~

### 12.5 Dependent repositories

Run these only when their files change:

~~~sh
cd "$VM_ROOT"
devenv shell -- testee verify --mode quick

cd "$RM_ROOT"
devenv tasks run -v base:check
devenv tasks run -v base:test
~~~

RepoMan's known base-test failure from its two pre-existing unformatted files
is not part of B. Do not format those files.

## 13. Run the real canary

Use Vendomat. Preserve its existing worktree changes.

Inspect the canary inputs:

~~~sh
sed -n '1,120p' "$VM_ROOT/.devman/project.toml"
sed -n '1,160p' "$HOME/.config/devman/projects/vendomat/devenv.local.nix"
~~~

Record the active generation pointer and a digest of its DAG tree before the
canary. Do not edit generated files.

Run the new installed adapter with both Python path variables cleared:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman link status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
~~~

Expected results:

- identity comes from the manifest or a matching explicit argument;
- status reports the central configuration path;
- declared links are correct or report a known pre-existing drift;
- no view points into the compatibility registry;
- no compatibility registry entry is needed for normal status;
- no active generation file changes.

Enter the canary shell once:

~~~sh
cd "$VM_ROOT"
env -u PYTHONPATH -u NIX_PYTHONPATH devenv shell -- bash -c 'true'
~~~

Run status again and inspect the links:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman link status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"

for view in .envrc .agents .claude/skills .loci devenv.local.nix; do
  printf '%s -> ' "$view"
  readlink -f "$VM_ROOT/$view"
done
~~~

Confirm that each target is the declared central or external target. Confirm
that no target is below the compatibility registry.

Confirm that the active generation did not change. Confirm that its project
count and DAG count did not change. Confirm that dagu ls still reports the
same active workflow count:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH dagu --dagu-home "$HOME/.local/share/dagu" ls
~~~

Then run the live doctor again and record every finding. A changed result after
clearing Python path variables is an environment-shadowing problem. Stop and
diagnose it before changing code.

## 14. Roll out and retain rollback

Do not roll B through all repositories in the first canary commit.

Use this order:

1. install the new adapter package;
2. run unit, hermetic, and package checks;
3. run the Vendomat canary;
4. switch one shell hook to the new package;
5. run the canary again;
6. observe one normal shell entry and one link edit;
7. compare active-generation and Dagu counts;
8. add a second ordinary repository only after the first result is stable;
9. expand to the migrated set;
10. record each repository result without repairing unrelated drift.

Keep the old adapter path during the observation period. A rollback must be a
reviewable source or machine-package change. It must not edit a generated
registry, a generated DAG, or a retained generation.

If the new adapter fails:

1. stop new adapter rollout;
2. preserve the output, active pointer, and worktree status;
3. restore the old adapter path through a reviewable change;
4. run the canary again;
5. run the Devman checks again;
6. record the failure and correction in the implementation log.

Do not remove compatibility mode as a rollback mechanism.

## 15. Commit discipline

Keep commits small and separate by repository. A recommended Devman sequence
is:

1. add the component contract and characterization tests;
2. add the independent adapter implementation;
3. wire the public CLI and executable;
4. add the Nix package and checks;
5. switch the machine package and shell hook;
6. document the canary and observation result.

Do not stage the protected files. Before every commit, run:

~~~sh
git diff --check
git status --short
git diff --cached --check
git diff --cached --name-status
~~~

Stage explicit paths only. Never run git add ., git add -A, git reset --hard,
or git checkout --.

Verify the staged name list does not contain:

~~~
src/devman/link.py
src/devman/watch.py
tests/unit/test_link.py
tests/unit/test_watch.py
~~~

Verify the RepoMan staged name list does not contain devenv.lock.

Use Gitman for normal save and publish. The current Devman checkout may report
OFF-CANONICAL because of the old 021-changelog lane. Do not run gitman
reconcile. If Gitman refuses to save or publish for that reason, use raw Git
only as this explicit fallback:

~~~sh
git add -- <each-intended-path>
git diff --cached --check
git diff --cached --name-status
git commit -m "<message>"
git push origin 038-fixup-and-fanout
~~~

Replace <each-intended-path> with explicit paths. Never include the four
protected files. Verify the branch and remote after the push:

~~~sh
git status --short --branch
git log -1 --oneline --decorate
~~~

Push each completed commit promptly. Never force-push.

## 16. Implementation log entry

After B has a passing canary, add a dated Stage 16 entry to:

~~~
.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md
~~~

The entry must record:

- the coupling or failure that the extraction prevents;
- the chosen component owner and package boundary;
- the unchanged central configuration interface;
- exact commands run;
- exact exit codes and result counts;
- the active generation and DAG count before and after;
- every known doctor finding;
- files changed per repository;
- the protected-file and protected-lock checks;
- compatibility-mode status;
- rollback behavior;
- the migrated count and blocked repositories;
- the next incomplete phase.

Do not mark Project 038 complete. B is a bridge. The remaining §11 removals
need their own evidence.

## 17. Definition of done for B

B is complete only when every item is true:

- [ ] devman-link is a separately importable and packageable component.
- [ ] Normal link status does not require a compatibility registry entry.
- [ ] The active Vendomat generation is not read or written by link reconcile.
- [ ] The workflow renderer remains a separate component.
- [ ] The central Nix file path is unchanged.
- [ ] The devman.link declaration shape is unchanged.
- [ ] .devman/project.toml remains the repository identity source.
- [ ] No identity parser was duplicated.
- [ ] The public devman link boundary uses the manifest resolver.
- [ ] The shell hook remains thin.
- [ ] The shell hook does not call the renderer twice.
- [ ] Central, repository, and external path rules still refuse unsafe paths.
- [ ] Promotion and conflict rules still refuse unsafe replacement.
- [ ] Bootstrap and .git/info/exclude behavior remains intact.
- [ ] Status remains read-only.
- [ ] The new component has unit and subprocess coverage.
- [ ] The hermetic flake test includes all new files.
- [ ] The Vendomat canary passes with both Python path variables cleared.
- [ ] The active generation and DAG count are unchanged by link reconciliation.
- [ ] Known doctor findings remain visible and understood.
- [ ] Compatibility mode remains available.
- [ ] Compatibility registry writes remain available.
- [ ] Consumer Devman pins remain unless a separate approved change removes one.
- [ ] The four protected Devman files were not staged.
- [ ] RepoMan's protected devenv.lock was not staged.
- [ ] Completed commits are pushed.
- [ ] Stage 16 records the exact evidence.

The next incomplete work is the separately gated §11 removal sequence. Do not
start it from this B guide.
