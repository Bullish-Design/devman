# Project 038 — link plane: A to C

Date: 2026-09-13
Status: implementation runbook
Scope: Devman, with the live Vendomat plane kept active

This runbook implements the agreed link-plane path:

1. **A now:** Vendomat owns the machine workflow plane. Devman remains the
   compatibility link adapter.
2. **C during the transition:** the repository manifest is the canonical
   project identity, and every machine-local link uses one central configuration
   location and one documented style.
3. **B later:** extract the link adapter into a small stable component without
   changing the central configuration interface.

This file supplements IMPLEMENTATION_GUIDE.md. It does not replace it, and it
does not retire compatibility mode.

## 1. The result to build

Keep these ownership boundaries:

| Concern | Canonical source | Current owner | Location |
|---|---|---|---|
| Project identity, groups, policy | Repository manifest | RepoMan and the repository | <repo>/.devman/project.toml |
| Machine-local links | Central overlay | Devman link adapter | $HOME/.config/devman/projects/<project>/devenv.local.nix |
| Workflow policy and sources | Devman policy plus central overlays | Vendomat and Devman renderer | Devman policy checkout and central config |
| Active workflow generation | Generated | Vendomat | $HOME/.local/state/vendomat/devman/active |
| Compatibility registry | Generated compatibility view | Devman, until item 4 of §11 is complete | $HOME/.local/share/devman |
| Runtime metadata | Generated state | Devman | $HOME/.local/state/devman |

Do not combine the central overlay, the compatibility registry, and the active
Vendomat generation. They have different owners and different lifetimes.

The central link file keeps the existing Nix module interface. Use this shape:

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

Rules for this file:

- Keep it under $HOME/.config/devman/projects/<project>/.
- Keep machine-local declarations out of tracked devenv.nix.
- Keep repository identity in .devman/project.toml.
- Keep one devman.link block per project.
- Use canonical, path, and optional template only.
- Do not put workflow definitions in this block.
- Do not put absolute repository paths in a central link declaration.
- Do not create a second human-authored link format during this transition.
- Treat the current devenv.local.nix as the stable user interface while the
  implementation moves behind it.

The ${config.devman.project} expression is a compatibility dependency in A.
During C, the link command and validation code must use .devman/project.toml as
the identity source and must refuse a mismatch. B removes the remaining Devman
Nix-module dependency.

## 2. Starting conditions

Start in the Devman checkout:

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
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/CONCEPT.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_GUIDE.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md
$DM_ROOT/.scratch/projects/025-the-link-plane/CONCEPT.md
$DM_ROOT/.scratch/projects/025-the-link-plane/GUIDE-02-link-plane.md
$VM_ROOT/AGENTS.md
$RM_ROOT/AGENTS.md
$NM_ROOT/AGENTS.md
~~~

Read the Devman, Devman adoption, Gitman, my-ai, and writing skills before
using their commands or editing their files.

Inspect every repository before work and before every commit:

~~~sh
for repo in "$DM_ROOT" "$VM_ROOT" "$RM_ROOT" "$NM_ROOT"; do
  printf '\n== %s ==\n' "$repo"
  git -C "$repo" status --short --branch
  git -C "$repo" log -1 --oneline --decorate
done
~~~

The expected Devman branch is the already-pushed Project 038 feature branch.
Continue from that branch. Do not start a new branch from stale main, and do
not commit directly to main.

Preserve these unrelated changes exactly:

~~~
Devman:
  src/devman/link.py
  src/devman/watch.py
  tests/unit/test_link.py
  tests/unit/test_watch.py

RepoMan:
  the pre-existing staged devenv.lock change
~~~

Do not run Gitman reconciliation in the Devman feature checkout. A prior run
removed the local feature branch because the checkout was off an old Gitman
lane. Use status, log, diff, and explicit branch operations only. If a Gitman
operation proposes to remove or move the feature branch, stop.

The central config directory is machine-local and is outside the four
repository worktrees:

~~~sh
git -C "$HOME/.config/devman" status --short --branch
~~~

Inspect it only at first. Do not reset it, clean it, change its detached HEAD,
or commit it as part of this runbook unless the user gives separate approval.

## 3. Record the live baseline

The live system must be checked outside every project devenv shell:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman doctor

env -u PYTHONPATH -u NIX_PYTHONPATH \
  dagu --dagu-home "$HOME/.local/share/dagu" ls
~~~

Record the following before implementation:

- the active Vendomat generation number and symlink target;
- the number of active projects;
- the number of active DAGs;
- the doctor mode;
- every doctor finding;
- the compatibility registry project count;
- the Dagu workflow count.

Do not treat the compatibility registry count as the active plane count.
Doctor's project summary still reads the old state-registration directory.

Save the baseline in a dated report if the implementation changes runtime
behavior. The current known findings are not proof that the plane is broken:

- flora-037-part-e has link drift;
- uncommitted Vendomat and RepoMan sources are consumed by unpinned inputs;
- one Dagu process has SHELL set, while default_shell controls execution.

## 4. Define A before changing it

A is complete only when all of these statements are true:

- Vendomat remains the source of the active workflow generation.
- Devman does not execute repository tasks during plane rendering.
- Devman still reconciles links at shell entry for repositories that use the
  Devman module.
- The link reconciler still owns the bootstrap devenv.local.nix link and the
  central .local.gitignore view.
- Plane mode is explicit in doctor output. It is never inferred from whichever
  binary happens to appear first on PATH.
- Compatibility mode remains available for consumers that need it.
- Compatibility registry writes are not removed in this slice unless the
  consumer inventory and comparison evidence explicitly allow item 4 of §11.
- The old registry and the active plane are never made to share a directory.

Inspect the existing mode implementation before adding a new option:

~~~sh
rg -n "check_mode|generation\.json|compatibility|plane" \
  src/devman/doctor.py src/devman/cli.py modules nix \
  .scratch/projects/038-devman-plane-redesign
~~~

If the existing generation-based mode already satisfies the contract, extend
its tests and documentation. Do not add a second mode flag with a different
source of truth. If a missing explicit mode is found, add one machine-level
source of truth and print it from both Devman doctor and Vendomat plane show.

The mode must have two named values:

~~~
plane
compatibility
~~~

Do not call the mode auto, legacy, or new. Those names hide the choice.

## 5. Build the C bridge

C makes the manifest the canonical identity at the Python boundary while
keeping the Devman module as a compatibility adapter.

### 5.1 Add one identity resolver

Use the existing manifest contract in src/devman/contract.py. Do not add a
second TOML parser or infer identity from a directory name.

The current worktree has protected changes in src/devman/link.py and
tests/unit/test_link.py. Do not modify either file. Put the new pure resolver
in a new src/devman/identity.py module and wire the public devman command from
the non-protected src/devman/cli.py boundary. The internal devman-link entry
point already receives an explicit project from the Nix module; leave that
protected implementation unchanged. If the required behavior cannot be wired
without editing a protected file, stop and ask the user.

The identity resolution order must be:

1. an explicit --project argument, when supplied;
2. .devman/project.toml in the supplied repository root;
3. the old literal devman.project extraction, only as a compatibility
   fallback for repositories that do not yet carry a manifest;
4. a refusal.

When both the manifest and old Nix option exist, compare them. Refuse with a
clear message if they differ. The refusal must name:

- the repository root;
- the manifest identity;
- the Nix compatibility identity;
- the command that fixes the mismatch.

The resolver must reject:

- an empty project name;
- a path-like identity;
- more than one identity;
- a missing or unreadable manifest;
- a manifest with an unsupported schema;
- a manifest with unknown fields;
- a project identity that fails the shared Dagu grammar.

Put new tests in a new test file if the existing protected link test file is
already modified. Do not edit or stage tests/unit/test_link.py in this
project slice.

Required resolver tests:

- manifest identity is used when no CLI identity is supplied;
- explicit CLI identity wins when it matches the manifest;
- explicit CLI identity refuses when it differs;
- matching manifest and Nix identities pass;
- mismatching manifest and Nix identities refuse;
- a manifest-free compatibility repository still uses the old fallback;
- a directory name is never used as identity;
- invalid manifest identity errors name the field and repair action.

### 5.2 Keep the central configuration interface stable

Do not replace the Nix link declaration with TOML, YAML, JSON, or an ad hoc
environment variable in this slice. That would create two sources of truth and
make B harder.

Add validation around the existing central file instead:

- verify that the central file exists before the bootstrap symlink is made;
- verify that the file evaluates through the Devman module;
- verify that every link view is relative to the repository;
- verify that central paths stay below overlayDir;
- verify that external paths remain outside both the repository and overlay;
- verify that ${config.devman.project} resolves to the manifest identity;
- report the central file path in link status and doctor findings.

The link declarations remain machine-local. The manifest remains portable. A
clone must not inherit another machine's .envrc, .agents, .loci, or local
settings.

### 5.3 Keep the reconciler's safety rules

Do not weaken these rules while changing identity resolution:

- a real view is promoted before it is replaced;
- a changed canonical side causes a refusal rather than a merge;
- a promotion creates a reviewable backup or lane as required by the existing
  link-plane contract;
- a dangling devenv.local.nix is never left behind;
- .git/info/exclude remains centrally owned;
- an absent canonical target is created only according to the declaration;
- a link outside its declared root is refused;
- the reconciler does not delete unrelated files.

Add regression coverage for the identity path without rewriting the existing
link-state tests. Run the complete link test set after the new tests pass.

### 5.4 Keep shell entry thin

The devenv hook must continue to do only these things:

1. establish the repository root and machine paths;
2. call the compatibility projection when the selected mode requires it;
3. call the link reconciler;
4. clean up its shell variables.

Do not move manifest parsing, link resolution, or promotion logic into shell.
Do not call the renderer twice. Do not make the hook discover repositories.

The link call must remain independent from the active Vendomat generation.
Changing or rolling back a workflow generation must not change link targets.

## 6. Prove the bridge with one real canary

Use a real migrated repository with ordinary central links. Vendomat is the
preferred canary because it is already in the plane, but its existing worktree
changes must remain untouched.

Before the canary, inspect:

~~~sh
sed -n '1,120p' /home/andrew/Documents/Projects/vendomat/.devman/project.toml
sed -n '1,160p' "$HOME/.config/devman/projects/vendomat/devenv.local.nix"
~~~

Run the link status command with the real installed binary, outside any
project shell:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman link status \
  --project vendomat \
  --root /home/andrew/Documents/Projects/vendomat \
  --overlay "$HOME/.config/devman"
~~~

Expected results:

- the project identity is vendomat from the manifest;
- every declared view reports ok, or a known pre-existing finding is named;
- no view points into the compatibility registry;
- no workflow DAG is rewritten by the link command.

Run one shell-entry reconciliation inside Vendomat only after the source and
lock state has been recorded:

~~~sh
cd /home/andrew/Documents/Projects/vendomat
env -u PYTHONPATH -u NIX_PYTHONPATH \
  devenv shell -- bash -c 'true'
~~~

Then verify the canary again:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman link status \
  --project vendomat \
  --root /home/andrew/Documents/Projects/vendomat \
  --overlay "$HOME/.config/devman"

env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman doctor
~~~

If the shell selects a stale local Devman package, stop and clear both
PYTHONPATH and NIX_PYTHONPATH before debugging. Do not interpret that false
result as a live-system failure.

## 7. Roll the bridge through the migrated set

Do not hand-edit generated registry files or the active plane generation.

For each migrated repository:

1. read .devman/project.toml;
2. locate $HOME/.config/devman/projects/<project>/devenv.local.nix;
3. compare the two identities;
4. verify that the central file uses the standard devman.link shape;
5. run link status with the explicit repository root;
6. record any drift without fixing unrelated findings;
7. reconcile only when the declaration is understood;
8. verify the repository worktree and central config status afterward.

The three structural repositories are now approved for root placement:

~~~
copyroom   -> <repo>/.devman/project.toml
docman     -> <repo>/.devman/project.toml
mypi-agent -> <repo>/.devman/project.toml
~~~

Do not place their manifests under dev/.

The seven detached-HEAD repositories still need an owner decision about which
branch should receive their local migration commit. Do not invent branch names
or force-push them. Leave those seven local-only until their branch mapping is
clear.

After the selected set is complete, update the live plane through Vendomat.
Pass one --project-root for every repository carrying a committed manifest.
Do not edit the generated generation by hand.

Validate all generated DAGs in one shell invocation:

~~~sh
cd /home/andrew/Documents/Projects/vendomat
devenv shell -- bash -c '
  set -eu
  for dag in "$HOME/.local/state/vendomat/devman/active"/dags/*.yaml; do
    dagu validate "$dag"
  done
'
~~~

Then verify the real live binaries:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman doctor

env -u PYTHONPATH -u NIX_PYTHONPATH \
  dagu --dagu-home "$HOME/.local/share/dagu" ls
~~~

## 8. Required tests and checks

Run the Devman checks after the implementation and after every later Devman
slice:

~~~sh
cd "$DM_ROOT"
devenv tasks run -v base:check
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
env -u PYTHONPATH -u NIX_PYTHONPATH \
  /run/current-system/sw/bin/devman doctor
~~~

The doctor command may return exit 1 for the documented findings. Report the
findings. Do not hide them and do not call them test failures without checking
their cause.

Run the dependent repository checks when their files change:

~~~sh
cd "$VM_ROOT"
devenv shell -- testee verify --mode quick

cd "$RM_ROOT"
devenv tasks run -v base:check
devenv tasks run -v base:test

cd "$NM_ROOT"
nixos-rebuild build --flake .#server
~~~

The RepoMan test failure caused by its two known unformatted files remains
pre-existing unless the task explicitly changes those files. Do not format
them as part of this link-plane work.

## 9. Commit and rollback discipline

Before every commit, inspect all four repositories again. In the repository
being committed, run:

~~~sh
git diff --check
git status --short
git diff --cached --check
git diff --cached --name-status
~~~

Stage explicit paths only. For the first documentation or implementation
slice, that means naming each intended file. Never use git add . or git add -A.

Before committing, verify that these paths are absent from the staged name list:

~~~
src/devman/link.py
src/devman/watch.py
tests/unit/test_link.py
tests/unit/test_watch.py
~~~

Use the repository's Gitman commit and push flow. Push completed commits to the
feature branch promptly. Devman lands through its normal pull-request path.

If a canary fails:

1. stop new plane updates;
2. preserve the failure output and the active generation pointer;
3. do not edit generated DAGs or registry files;
4. restore the previous source or central declaration through a reviewable
   change;
5. rerun the canary and the full repository checks;
6. record the failed attempt and the correction in the implementation log.

Do not remove compatibility mode as a rollback mechanism.

## 10. Stop conditions

Stop and ask the user when any of these occurs:

- a detached migration commit has no clear destination branch;
- a central link declaration and manifest identity disagree;
- a central overlay is missing, dangling, or has an unknown shape;
- a real view and its canonical side both changed;
- a proposed fix requires changing one of the protected files;
- a generated registry or plane file appears to need hand editing;
- a sudo nixos-rebuild switch fails because sudo is unavailable;
- the live system result differs depending on whether PYTHONPATH or
  NIX_PYTHONPATH is cleared;
- a compatibility-only repository would lose its supported path;
- a change would require deleting the old registry or active generation.

## 11. Definition of done for A to C

The slice is complete when:

- the active machine remains in explicit plane mode;
- Vendomat continues to own the live workflow generation;
- Devman continues to reconcile links through the central overlay;
- .devman/project.toml is the canonical identity at the Python boundary;
- a manifest/Nix identity mismatch refuses loudly;
- central link declarations follow one documented Nix style;
- link status and reconcile work without directory-name inference;
- the canary passes with environment variables cleared;
- every generated DAG validates;
- Devman, Vendomat, RepoMan, and nix-meta checks have the recorded results;
- the four protected Devman files and RepoMan's protected lock were not staged;
- no compatibility-only repository was broken;
- compatibility mode remains available;
- the implementation log records the exact commands, results, and known
  findings.

Do not mark Project 038 complete at this point. A to C is the bridge. B and the
remaining §11 removals still require separate evidence.
