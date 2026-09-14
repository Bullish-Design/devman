# Project 038 — clean-session prompt for B

Copy the text below into a clean implementation session.

---

You are continuing Project 038: the Devman machine-plane redesign.

Do not restart Project 038. Do not repeat the completed migration, comparison,
A-to-C bridge, or Vendomat canary work.

Your immediate goal is B:

> Extract the machine-local link adapter into a stable, independently
> importable and packageable component without changing the central link
> configuration interface.

Use this prompt together with:

~~~text
/home/andrew/Documents/Projects/devman/.scratch/projects/038-devman-plane-redesign/LINK_ADAPTER_B_GUIDE.md
~~~

Read that guide completely before changing code. It is the detailed runbook for
this prompt.

## Repositories

Use these repository roots:

~~~sh
export DM_ROOT=/home/andrew/Documents/Projects/devman
export VM_ROOT=/home/andrew/Documents/Projects/vendomat
export RM_ROOT=/home/andrew/Documents/Projects/repoman
export NM_ROOT=/home/andrew/Documents/Projects/nix-meta
export DM_POLICY_ROOT=$DM_ROOT
~~~

Start in:

~~~sh
cd "$DM_ROOT"
~~~

The current Devman branch is:

~~~text
038-fixup-and-fanout
~~~

The latest pushed documentation commit is:

~~~text
65b3abc docs: add link adapter B guide
~~~

The A-to-C implementation is already present on this branch. Continue from
the current branch. Do not create a new branch from stale main.

## Read before action

Read these files completely:

~~~text
$DM_ROOT/AGENTS.md
$DM_ROOT/AGENTS_GUIDE.md
$DM_ROOT/.scratch/projects/025-the-link-plane/CONCEPT.md
$DM_ROOT/.scratch/projects/025-the-link-plane/GUIDE-02-link-plane.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/CONCEPT.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_GUIDE.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/LINK_PLANE_A_TO_C_GUIDE.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/LINK_ADAPTER_B_GUIDE.md
$VM_ROOT/AGENTS.md
$RM_ROOT/AGENTS.md
$NM_ROOT/AGENTS.md
~~~

Read Project 038 implementation-log Stages 11, 12, 13, 14, and 15 in full.
Do not treat FULL_REFACTOR_PROMPT.md as authoritative. The implementation log
and the A-to-C and B guides supersede it.

Read these skills before using their commands or editing their files:

~~~text
Devman
Devman adoption
Gitman
my-ai
writing
~~~

Run verification and tools inside devenv. Do not call bare uv, python, pytest,
ruff, or copier.

## Non-negotiable safety rules

The following Devman files have protected, unrelated worktree changes:

~~~text
src/devman/link.py
src/devman/watch.py
tests/unit/test_link.py
tests/unit/test_watch.py
~~~

Do not modify, stage, discard, or commit these files.

Read them as behavior references only. Add new implementation and tests at a
non-protected boundary. If B cannot be completed without changing one of these
files, stop and ask the user. Do not copy their code into a second
implementation to bypass the protection.

RepoMan has a protected pre-existing devenv.lock change. Do not modify,
unstage, discard, or commit it.

Do not modify the central configuration checkout:

~~~text
$HOME/.config/devman
~~~

Read its status only. Do not reset it, clean it, change its detached HEAD, or
commit it.

Do not hand-edit generated files:

~~~text
$HOME/.local/share/devman
$HOME/.local/state/devman
$HOME/.local/state/vendomat/devman
$HOME/.local/share/dagu
~~~

Do not run gitman reconcile. The Devman checkout may report OFF-CANONICAL
because lane 021-changelog has a divergent change-id. Use read-only Gitman
status and log commands. Use the explicit raw Git fallback only if Gitman
cannot save or publish because of that state.

Do not force-push.

## Preserve A and C

A remains complete and unchanged:

- Vendomat owns the active workflow generation.
- Devman remains the compatibility link adapter and compatibility projection.
- Devman does not execute repository tasks during Vendomat rendering.
- Explicit modes remain plane and compatibility.
- Compatibility registry writes remain.
- registryDir remains where the current design places it.
- Consumer Devman pins remain.
- Vendomat remains the owner of generation build, activation, rollback, and
  recovery.

C remains complete and unchanged:

- .devman/project.toml is the repository identity source.
- The existing contract in src/devman/contract.py remains authoritative.
- The public Devman link boundary uses the manifest-first resolver in
  src/devman/identity.py.
- The central link file remains:
  $HOME/.config/devman/projects/<project>/devenv.local.nix
- The central file contains one devman.link attribute set.
- Do not add TOML, YAML, JSON, or a second human-authored link format.
- Do not infer identity from a directory name.
- Do not move identity into a workflow, generation, registry, or machine path.

Keep this central Nix interface exactly:

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

B must preserve the file path, block name, fields, canonical values, path
expansion, and repair behavior.

## Inspect state first

Run this exact repository check before changing anything:

~~~sh
for repo in "$DM_ROOT" "$VM_ROOT" "$RM_ROOT" "$NM_ROOT"; do
  printf '\n== %s ==\n' "$repo"
  git -C "$repo" status --short --branch
  git -C "$repo" log -1 --oneline --decorate
done
~~~

Inspect the central checkout:

~~~sh
git -C "$HOME/.config/devman" status --short --branch
~~~

Run read-only Gitman status in the Devman shell:

~~~sh
devenv shell -- gitman status
~~~

If it reports OFF-CANONICAL, record the reason. Do not reconcile.

Record the live baseline outside every project shell. Clear both Python path
variables:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman doctor

env -u PYTHONPATH -u NIX_PYTHONPATH dagu --dagu-home "$HOME/.local/share/dagu" ls
~~~

Record:

- both command exit codes;
- doctor mode;
- every doctor finding;
- active generation symlink target;
- active generation number;
- active project count;
- active DAG count;
- compatibility registry project count;
- Dagu workflow count.

Use these read-only active-plane checks:

~~~sh
PLANE_ROOT="$HOME/.local/state/vendomat/devman/active"
readlink "$PLANE_ROOT"
find -L "$PLANE_ROOT/projects" -mindepth 1 -maxdepth 1 -type d | wc -l
find -L "$PLANE_ROOT/dags" -mindepth 1 -maxdepth 1 -type f -name '*.yaml' | wc -l
sed -n '1,160p' "$PLANE_ROOT/generation.json"
~~~

The expected active baseline is 46 projects, 146 DAG files, and generation 2.
Re-measure it. Do not assume it.

Doctor may still report:

- flora-037-part-e link drift;
- dirty, unpinned Vendomat source;
- dirty, unpinned RepoMan source;
- the old state-registration summary;
- any other finding from the live command.

Treat doctor exit code 1 as a finding result. Do not hide or erase findings
because tests pass.

## Confirm the existing boundaries

Inspect the existing mode implementation:

~~~sh
rg -n "check_mode|generation\.json|compatibility|plane" src/devman/doctor.py src/devman/cli.py modules nix .scratch/projects/038-devman-plane-redesign
~~~

Confirm that only plane and compatibility exist. Do not add another mode source.

Inspect the existing identity and link boundary:

~~~sh
rg -n "ProjectManifest|project\.toml|resolve_project_identity|validate_link_configuration|devman\.link|central config" src/devman modules tests
~~~

Inspect every adapter call site:

~~~sh
rg -n "devman-link|devman link|linkScript|devman\.link|from (devman|\.) import link|--registry|--state" src modules nix tests flake.nix pyproject.toml "$VM_ROOT" "$RM_ROOT" "$NM_ROOT"
~~~

Read these files before selecting the seam:

~~~text
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

The current facts are:

- pyproject.toml exposes devman-link as devman.link:cli;
- the shell hook currently obtains devman-link from the renderer derivation;
- the public devman link command resolves identity before entering the
  protected adapter;
- the protected adapter currently contains the link safety and promotion
  behavior;
- the renderer owns workflow projection and must stay separate.

## Define B before implementation

Write a short B decision in the implementation log before code changes. Do
not start code until the decision answers these points.

### Component ownership

The recommended first target is a new package boundary:

~~~text
src/devman_link/
~~~

Use a separately importable and separately packageable component. The source
may remain in the Devman repository for this first B slice. Do not create a new
source repository without an approved owner and remote.

The component may later move to its own repository without changing its public
command or central configuration interface.

### Stable operations

Keep these operations:

~~~text
status       inspect links without changing files
reconcile    apply declarations and return one result per view
~~~

Keep these result states:

~~~text
ok
repoint
promote
link
create
~~~

Keep these exit meanings:

~~~text
0  success; status found no drift
1  status found drift, or reconciliation refused a requested change
2  usage or infrastructure error
~~~

Keep structured results for Python callers and the existing plain-text output
for operators. Status must report the central configuration path.

### Stable inputs

The adapter receives:

- repository root;
- optional explicit project identity;
- overlay root;
- the central project configuration under the overlay;
- status or reconcile operation.

Resolve root and overlay to absolute paths. Refuse an absent repository,
absent central file, or central file outside the overlay.

Do not make normal operation depend on the compatibility registry, active
generation, workflow renderer, watcher, Dagu run execution, or repository task
execution.

### Identity

Keep the one existing manifest resolver and contract. Do not copy the TOML
parser.

Keep this order:

1. explicit --project;
2. .devman/project.toml in the supplied root;
3. old literal devman.project only without a manifest;
4. loud refusal.

When manifest and old Nix identity both exist, compare them. A mismatch must
name the repository root, manifest identity, compatibility identity, and repair
action.

Reject empty, path-like, unsupported, unknown, unreadable, multiple, and
invalid Dagu identities. Never use a directory name.

If the component cannot reuse the contract without a second parser, stop and
choose a contract-package seam before writing code.

### Safety

Preserve every existing link safety rule:

- validate declarations before resolving paths;
- keep central paths below the overlay;
- keep repository views inside the repository;
- keep external paths outside the repository and overlay;
- resolve symlinked parents before root checks;
- promote real views before replacement;
- refuse conflicting canonical and view edits;
- keep promotion backups;
- never leave a dangling bootstrap link;
- keep .git/info/exclude centrally owned;
- support linked worktrees;
- write link state atomically;
- do not delete unrelated files.

## Characterize before moving code

Create a behavior matrix with temporary roots. Do not use the live registry or
active generation as a test fixture.

Cover:

1. missing view with existing canonical;
2. missing view and canonical;
3. correct link no-op;
4. wrong link repoint;
5. real file promotion;
6. real directory promotion;
7. canonical-change conflict refusal;
8. central traversal refusal;
9. central symlink escape refusal;
10. repository-view symlink escape refusal;
11. external path inside repository refusal;
12. external path inside overlay refusal;
13. dangling bootstrap creation;
14. normal Git exclude ownership;
15. linked-worktree exclude ownership;
16. two-sided exclude conflict refusal;
17. central template;
18. invalid non-central template;
19. invalid declaration shape;
20. operation without a compatibility registry entry;
21. matching explicit and manifest identities;
22. mismatching explicit and manifest identities;
23. manifest-free compatibility fallback;
24. directory-name identity refusal.

Use tests/unit/test_link.py as a read-only behavior reference. Add new tests in a
new test file. Do not edit the protected test file.

Record old and new results. Safety behavior must not weaken.

## Implement the component

Create the new package boundary. Keep the public API small. A recommended
layout is:

~~~text
src/devman_link/
  __init__.py
  api.py
  declarations.py
  paths.py
  reconcile.py
  cli.py
~~~

The names may differ if the boundary stays clear.

Do not expose internal state-file helpers as the public contract.

Implement one declaration type with:

~~~text
view
canonical
path
template
~~~

Use the existing central, repo, and external resolution model:

~~~text
central    under the overlay
repo       a repository canonical path exposed through the overlay
external   an absolute path outside the repository and overlay
~~~

Keep project expansion. Validate the expanded path before joining it to a
root. Reject the root itself and every path outside the declared root.

Keep link state behavior stable. If the state record must change, add a
compatibility reader and a migration test before changing it.

Evaluate the central Nix file before reconciliation. Supply the selected project
as config.devman.project. Read only devman.link. Refuse failed evaluation,
wrong return shape, unknown fields, identity mismatch, missing bootstrap target,
and unsafe paths. Include the file path and repair action in every refusal.

Do not evaluate the whole repository environment. Do not parse workflow files.
Do not call Dagu or a repository task.

## Wire the boundaries

### Public Devman command

Keep src/devman/cli.py as the public identity boundary. It must:

1. resolve identity;
2. validate the central file and declarations;
3. call the independent adapter API;
4. print the central configuration path for status;
5. return the adapter exit code.

Keep normal link status and reconcile independent from the active generation.
Keep the old --all path only if compatibility registry enumeration still owns
that operation.

Do not route normal operations through the protected link implementation.

### devman-link executable

Point the devman-link entry point at the new component.

The following command must work without a compatibility registry entry:

~~~sh
devman-link status --project vendomat --root /home/andrew/Documents/Projects/vendomat --overlay "$HOME/.config/devman"
~~~

Inventory old positional arguments and old --registry or --state flags first.
Do not accept and ignore obsolete flags silently. Keep an explicit
compatibility wrapper when a real caller still needs the old path.

### Shell hook

Keep the shell hook limited to:

1. establish repository root and machine paths;
2. call compatibility projection when the selected mode requires it;
3. call link reconciliation;
4. clean up variables.

Do not move identity, Nix evaluation, path resolution, promotion, or
repository discovery into shell. Do not call the workflow renderer twice.

The preferred B shape calls the machine-installed devman-link component. Keep
the old renderer-provided adapter as an explicit rollback path until the new
package passes the observation gate. Do not silently select an arbitrary
binary from PATH.

A workflow-generation update must not change link targets.

## Package the component

Create a separate Nix derivation, preferably:

~~~text
nix/link-adapter.nix
~~~

Expose a stable flake output such as:

~~~text
packages.<system>.devman-link
~~~

The package must:

- contain only the adapter and its contract dependency;
- expose devman-link;
- avoid Dagu, watchexec, and the workflow renderer;
- run devman-link --help in its install check;
- run a no-registry fixture;
- be usable by the machine package.

Do not remove devman-link from nix/renderer.nix in the first package commit.
Use separate commits for:

1. new component and package;
2. machine installation;
3. shell-hook switch;
4. removal of the renderer copy after observation.

Keep the workflow renderer derivation and its plan guard intact.

Install the new component through the existing NixOS or Vendomat machine
boundary. Keep any new option machine-level. Do not add a DEVMAN_* variable.
The shared environment contract is closed.

## Add tests

Create a new test file, for example:

~~~text
tests/unit/test_link_adapter.py
~~~

Cover:

- no registry access during normal status;
- no active-generation access;
- manifest identity without --project;
- matching explicit identity;
- mismatching explicit identity;
- matching manifest and Nix identities;
- mismatching identities;
- manifest-free compatibility fallback;
- directory-name refusal;
- field-specific repair action;
- central Nix evaluation;
- central and external root safety;
- bootstrap validation;
- all five link states;
- promotion and conflict refusal;
- .git/info/exclude ownership;
- linked-worktree excludes;
- atomic state writes;
- read-only status;
- no DAG or generation mutation during reconcile.

Include at least one subprocess test. Update the Nix fileset so base:test
actually includes every new source and test file.

Do not modify tests/unit/test_link.py or tests/unit/test_watch.py.

## Verify in layers

Run the Devman checks inside its devenv:

~~~sh
cd "$DM_ROOT"
devenv tasks run -v base:check
devenv tasks run -v base:unit
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
~~~

Run the installed doctor outside every project shell:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman doctor
~~~

Report its exit code and every finding. Exit code 1 is allowed for known
findings. Confirm that the mode is plane and compatibility mode still exists.

If nix-meta changes, run:

~~~sh
cd "$NM_ROOT"
nixos-rebuild build --flake .#server
~~~

Do not assume sudo works. If switching is required and sudo fails, commit and
push the nix-meta change and give the user this exact command:

~~~sh
sudo nixos-rebuild switch --flake .#server
~~~

If Vendomat files change, run:

~~~sh
cd "$VM_ROOT"
devenv shell -- testee verify --mode quick
~~~

If RepoMan files change, run:

~~~sh
cd "$RM_ROOT"
devenv tasks run -v base:check
devenv tasks run -v base:test
~~~

Do not format RepoMan's two pre-existing unformatted files.

## Run the Vendomat canary

Preserve all existing Vendomat worktree changes.

Inspect:

~~~sh
sed -n '1,120p' "$VM_ROOT/.devman/project.toml"
sed -n '1,160p' "$HOME/.config/devman/projects/vendomat/devenv.local.nix"
~~~

Record the active generation pointer and DAG-tree digest before link changes.

Run the installed canary with both Python path variables cleared:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman link status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
~~~

Confirm:

- manifest identity or matching explicit identity is used;
- central configuration path is printed;
- declared links are correct;
- no target points into the compatibility registry;
- no compatibility registry entry is required;
- no active generation or DAG file changes.

Enter the shell once:

~~~sh
cd "$VM_ROOT"
env -u PYTHONPATH -u NIX_PYTHONPATH devenv shell -- bash -c 'true'
~~~

Run status again and inspect these targets:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman link status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"

for view in .envrc .agents .claude/skills .loci devenv.local.nix; do
  printf '%s -> ' "$view"
  readlink -f "$VM_ROOT/$view"
done
~~~

Confirm that link reconciliation did not rewrite the active generation. Confirm
that active project and DAG counts are unchanged. Run Dagu listing again:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH dagu --dagu-home "$HOME/.local/share/dagu" ls
~~~

Run doctor again. If results differ when Python path variables are cleared,
stop and diagnose environment shadowing before changing code.

## Rollout and rollback

Do not update the full fleet in the first implementation commit.

Use this order:

1. package the new adapter;
2. pass unit, hermetic, and package checks;
3. run the canary;
4. install the machine package;
5. switch one shell hook to the new package;
6. run the canary again;
7. observe one normal shell entry and one link edit;
8. compare active generation and Dagu counts;
9. test a second ordinary repository;
10. expand to the migrated set;
11. record results without repairing unrelated drift.

Keep the old adapter path for the observation period.

If the new adapter fails:

1. stop rollout;
2. preserve output, active pointer, and worktree status;
3. restore the old adapter path through a reviewable change;
4. rerun the canary;
5. rerun the Devman checks;
6. record the failure and correction.

Do not edit generated registry files, generated DAG files, or retained
generations during rollback.

## Commit and push

Keep commits small and separate by repository. Use Gitman for normal save and
publish. The current Devman off-canonical state may require the documented raw
Git fallback.

Before every commit, run:

~~~sh
git diff --check
git status --short
git diff --cached --check
git diff --cached --name-status
~~~

Stage explicit paths only. Never run:

~~~text
git add .
git add -A
git reset --hard
git checkout --
~~~

Verify that the staged name list excludes:

~~~text
src/devman/link.py
src/devman/watch.py
tests/unit/test_link.py
tests/unit/test_watch.py
~~~

Verify that RepoMan's staged name list excludes:

~~~text
devenv.lock
~~~

If Gitman cannot save or publish because it reports OFF-CANONICAL, use only
this explicit raw Git fallback:

~~~sh
git add -- <each-intended-path>
git diff --cached --check
git diff --cached --name-status
git commit -m "<message>"
git push origin 038-fixup-and-fanout
~~~

Replace the placeholder with explicit paths. Never force-push.

## Implementation log

After the canary passes, add a dated Stage 16 entry to:

~~~text
.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md
~~~

Record:

- the coupling or failure B prevents;
- chosen component owner and package boundary;
- unchanged central configuration interface;
- exact commands;
- exact exit codes;
- exact active project and DAG counts;
- every doctor finding;
- files changed per repository;
- protected-file and protected-lock checks;
- compatibility-mode status;
- rollback behavior;
- migrated count and blocked repositories;
- next incomplete phase.

Do not mark Project 038 complete. B is a bridge. The remaining §11 removals
need separate evidence.

## Stop and ask the user

Stop before making changes and ask the user if:

- B requires editing a protected Devman file;
- a new component repository needs an owner or remote decision;
- the central Nix declaration and manifest identity disagree;
- a caller still depends on an undocumented old CLI shape;
- a real view and canonical side both changed;
- a generated registry or DAG appears to need hand editing;
- the live result changes when Python path variables are cleared;
- the machine package requires a switch that sudo cannot perform;
- a detached migration branch has no clear destination;
- the implementation would remove compatibility mode, compatibility writes,
  registryDir, or consumer pins;
- the requested change would delete old registry state or an active generation.

## Final report

At the end, report:

- files changed per repository;
- tests and exact results;
- live active generation and DAG count;
- all known doctor findings;
- commits and pushed branches;
- confirmation that protected Devman files were not staged;
- confirmation that RepoMan's protected lock was not staged;
- confirmation that compatibility mode remains;
- current migrated count and blocked repositories;
- next incomplete phase;
- any blocker that needs user input.

Do not claim B is complete until its definition-of-done checklist in the B guide
passes.
