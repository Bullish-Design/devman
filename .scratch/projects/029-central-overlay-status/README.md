# 029 — central overlay status and remaining work

**Date:** 2026-09-10  
**Status:** implementation handoff and gap register  
**Scope:** devman, the machine-wide automation plane, and the central per-repository configuration system

## 1. Executive summary

The central configuration model is working in production on server. The
devman repository now ships the link plane, the typed devman.link declaration,
the reconciler, the central agent surface, and the central per-project workflow
source overlay. The repository is on main at d3f9932, after the tagged
v0.5.1 release at 8311f14. The corresponding nix-meta configuration is on
main at 76dd689 and pins devman to refs/tags/v0.5.1 / revision
8311f1434d6959ab0f50533cada8a451f5eab70e.

The system is therefore usable now, but it is not yet at the final layout in
the link-plane charter. Two architecture stages remain:

1. split authored configuration from generated registry state; and
2. stop rendering workflow copies and link Dagu directly to central workflow
   files.

The notes plane also has one external release prerequisite. Several design
questions remain measurements or cleanup work, not blockers for normal shell
entry.

The governing design is
[025-the-link-plane/CONCEPT.md](../025-the-link-plane/CONCEPT.md). Project
024 is superseded. Project 028 contains the first-pass implementation evidence
and return codes.

## 2. The intended system boundary

The design separates three owners:

| Location | Owner | Contents |
|---|---|---|
| ~/.config/devman | the user's central configuration repository | shared environment files, per-project devenv.local.nix, agent surfaces, and authored workflow overlays |
| ~/Notes | the notes service and its own repository | the single loci vault and all project notes |
| ~/.local/state/devman | devman at runtime | generated metadata, plans, triggers, run state, logs, and artifacts |

The current implementation has the first two owners in place, but the runtime
registry still lives at ~/.local/share/devman. That is the precise reason the
state split remains open; it is not a documentation-only difference.

The repository-side view follows the boundary test:

~~~text
project/
├── devenv.nix                 tracked project contract
├── devenv.local.nix           symlink to ~/.config/devman/projects/<name>/devenv.local.nix
├── .envrc                     symlink to ~/.config/devman/common/envrc
├── .agents                    symlink to the central project agent surface
├── .devman/workflows          symlink to the central project workflow overlay
└── .loci                      symlink to ~/Notes/1_Projects/<name>
~~~

The repository keeps shared, clone-visible project facts. Machine-specific
configuration reaches it through a link and an exclude entry; it does not become
part of the repository's history.

## 3. What was completed in the devman repository

### 3.1 Central per-project configuration

- overlayDir is a typed devenv option whose default is ~/.config/devman.
- A project-local devenv.local.nix is now consumed from
  overlayDir/projects/<project>/devenv.local.nix when the repository view is
  linked into the central store.
- The shell-entry path supports a central local configuration without adding
  per-project facts to the machine NixOS module.
- The central store contains 55 project directories and 55 per-project
  devenv.local.nix files in the current live checkout.
- The four backburnered repositories—foreman, forgelab,
  image-gen-pipeline, and lodestar—have their local Nix configuration in
  the central store while retaining their devman.enable = lib.mkForce false
  opt-out.

The four files were promoted as configuration, not silently discarded. This
preserves the backburner decision while making the machine-only choice visible
and versionable in one place.

### 3.2 The link plane

devman.link is declared as an attribute set of typed link declarations. Each
declaration names the view path and may use one of three canonical owners:

- central — canonical content under the central config repository;
- repo — canonical content in the project repository, exposed in the central
  store; or
- external — canonical content at an explicitly named path outside both.

One Python reconciler handles the five measured states:

| State | Action |
|---|---|
| correct symlink | leave it alone |
| wrong symlink | repoint it |
| real file or directory | promote content, then link it |
| absent view | create the link |
| absent view and absent canonical | create the canonical target, then link it |

The reconciler also:

- records the canonical content hash after linking;
- refuses a promote when both the view and canonical side changed;
- writes the corresponding .git/info/exclude entry;
- never removes a real view before its content has been promoted; and
- supports templates only for canonical content owned by the central store.

The same reconciliation function is called from shell entry and the watcher.
devman link status and devman doctor expose link state and drift.

Implementation is in src/devman/link.py, with the option and shell integration
in modules/devenv.nix and tests in tests/unit/test_link.py.

### 3.3 Central agent surface

The central configuration repository is the source of truth for the personal
agent surface. Project repositories receive a directory view rather than
copies of skills.

- Shared skills are pooled centrally.
- Per-project agent surfaces select the appropriate skills with tracked
  relative links inside the config repository.
- Repository .agents and .claude/skills paths are derived views.
- AGENTS.md remains repository-owned and tracked for cold readers.
- The router remains a generated file owned by repoman; the design requires it
  to describe what is actually present on disk.

This removed the previous mixture of template assets, copyroom assets,
gitman-created files, repoman output, and stale per-repository copies from the
central overlay model.

### 3.4 Central workflow source overlays

Workflow resolution is now explicitly layered:

1. selected group workflows;
2. later selected groups shadow earlier groups as whole files; and
3. the central per-project workflow overlay is the final project-specific layer.

For devman itself, the source files now live in:

~~~text
~/.config/devman/projects/devman/workflows/
~~~

The repository path .devman/workflows is a symlink view of that directory.
The current central store has five authored devman workflow files. This means a
workflow edit is made against central source content, while the repository keeps
the familiar path and no second tracked copy.

The registry still receives a generated projection. That is deliberate current
behavior and is separate from the source-overlay change.

### 3.5 Machine and CLI integration

- The NixOS module owns one Dagu service, the queues, Dagu configuration, the
  watcher, and the CLI on the system profile.
- The devman CLI has the link command in addition to run, show, doctor, watch,
  agent, and project.
- The shell hook remains idempotent and keeps the common path cheap.
- Registration still happens through shell entry; there is no separate
  register or unregister command.
- The registry remains derived from group sources and central overlay content.
- Project identity continues to come from explicit devman.project, not a
  guessed directory name.

The release packaging was corrected so the Nix package, Python package, and
published tag all report the same 0.5.1 version. nix-meta now imports the
tagged release rather than an untagged moving revision.

### 3.6 Documentation and verification

The devman repository documentation was aligned with the central-overlay model:

- README.md explains the planes, central configuration, and normal entry;
- USER.md documents the user-facing shell, link, workflow, and diagnosis
  behavior;
- AGENTS.md and AGENTS_GUIDE.md describe the boundary test, ownership, and
  operating rules;
- groups/README.md and group READMEs describe content locally;
- .scratch/projects/025-the-link-plane/CONCEPT.md records the governing
  charter and its implementation status; and
- .devman/workflows/README.md is represented by the central workflow overlay
  source rather than a second repository copy.

The first-pass evidence in
[028-link-plane](../028-link-plane/) records successful return codes for:

- devman doctor;
- devman link status;
- base:check; and
- base:test.

## 4. What was completed in the overall system

The live system now has the central config repository at ~/.config/devman,
including:

- common/envrc for the shared pinned direnv setup;
- common/claude.json for broad shared permissions;
- per-project devenv.local.nix files;
- the central agent pool and composed project surfaces; and
- the devman project workflow source overlay.

The devman repository's live views currently resolve as follows:

~~~text
devenv.local.nix  -> ~/.config/devman/projects/devman/devenv.local.nix
.envrc            -> ~/.config/devman/common/envrc
.loci             -> ~/Notes/1_Projects/devman
.devman/workflows -> ~/.config/devman/projects/devman/workflows
~~~

The four backburnered repositories also have their local Nix files in the
central store and retain their opt-out. Spot checks show the shared .envrc and
per-project .loci views in place for them.

The system rebuild path is aligned with the tagged devman release. The machine
profile imports devman's NixOS module and does not duplicate the plane's queue,
registry, or project rules.

## 5. Core work that remains

### 5.1 Stage 3 — split configuration from state

This is the most important remaining structural change.

Current live behavior:

~~~text
~/.config/devman/                 authored central content
~/.local/share/devman/            registry, generated workflows, and runtime data
~/.local/state/devman/            does not exist yet
~~~

The target behavior is:

~~~text
~/.config/devman/                 authored config plus central workflow sources
  dags/                            generated Dagu-facing links
  projects/<name>/                 authored overlays and derived views
~/.local/state/devman/             generated metadata and runtime state
  projects/<name>/metadata.json
  projects/<name>/plan.json
  projects/<name>/triggers.toml
  runs/
~~~

The implementation work is to:

1. change registryDir defaults in modules/devenv.nix and
   nix/nixos-module.nix to the authored config root;
2. add a stateDir option for generated metadata and runtime state;
3. point Dagu's paths.dags_dir at the new registry/DAG location;
4. move metadata, plans, triggers, logs, and artifacts to the state root;
5. preserve shell-entry re-registration and stale-entry pruning; and
6. rebuild, run devman doctor, and remove ~/.local/share/devman only after the
   new layout is clean.

The migration must not require edits to every repository. The charter's desired
end state is zero repository-local registryDir overrides.

### 5.2 Stage 4 — direct workflow links

Current behavior still renders a generated copy into the registry:

~~~text
~/.local/share/devman/projects/<project>/workflows/<workflow>.yaml
~~~

The target is a direct Dagu-facing link from the central authored source:

~~~text
~/.config/devman/dags/<project>.<workflow>.yaml
  -> ~/.config/devman/projects/<project>/workflows/<workflow>.yaml
~~~

This removes the second workflow copy and lets an edit to the central source
take effect on the next run without re-projection. It must preserve the
generated environment/header behavior currently needed by Dagu, including
DEVMAN_PROJECT_DIR, working_dir, log_dir, validation, collision detection, and
scheduled-run behavior.

This work is explicitly deferred until the central overlay has been used for
multiple repositories and the state split is stable. See section 6.2a of the
charter.

## 6. Remaining prerequisites and open questions

These are real follow-ups, but they are not reasons to undo the working link
plane.

### 6.1 loci-core release

The project-side .loci links are wired to the existing ~/Notes vault, but the
installed loci-core is 0.3.0 while the upward-vault-discovery implementation is
0.4.2 in source. Release 0.4.2 and rebuild the system before relying on:

~~~bash
cd <repo>/.loci
loci documents/list
~~~

Until then, use the explicit vault path or the configured shell alias:

~~~bash
loci --vault ~/Notes documents/list
~~~

~/Notes must remain its own repository and SilverBullet data directory. It must
not be moved into ~/.config/devman.

### 6.2 Claude settings save behavior

The .claude/settings.local.json case still needs one real end-to-end test:
link it, approve a permission, and confirm that the editor/Claude writer keeps
the symlink. If the writer uses rename-based replacement, keep this particular
file repo-local and move only genuinely shared settings to the global Claude
configuration.

### 6.3 Registry readers and lock noise

devman doctor still has checks that read devenv.lock across registry entries.
The new central tree may produce noise or stale-source findings. Run the full
doctor against the migrated layout and decide whether those readers should use
the state metadata or a narrower source path.

### 6.4 Promote conflicts

The reconciler correctly refuses when the central and view sides both changed.
No production data exists yet for how often that happens. After normal use,
measure conflict frequency before changing the safety rule.

### 6.5 Agentman adoption

The devman-side groups/agent contract and agent adapter exist, but no real
repository capsule has yet been used to settle whether agentman's zero-consumer
state is intentional or indicates a missing integration.

### 6.6 Unified toolchain

cliProvider = store remains a separate Stage 5 decision. It requires a vendomat
build and one repository running repoman doctor under the store provider. Do
not combine it with the registry migration or direct DAG-link work.

## 7. Broader cleanup still listed by the charter

The original front-door cleanup is adjacent to, but not required for, the
central overlay mechanism:

- render router routes from the filesystem;
- archive fleetman, foreman, and siteman if their zero-consumer status is still
  confirmed; and
- replace the remaining seed AGENTS.md files in repoman, fleetman, and siteman.

These should be tracked separately from the two core overlay stages so that
cleanup does not obscure the state/config or workflow-link migrations.

## 8. Current operational caveats

The central config checkout is currently detached at b4e15fa and has these
untracked paths:

~~~text
projects/devman/agents/
projects/paloma-text-pipeline/
projects/talkee/agents/
~~~

They were intentionally preserved while the overlay work was being performed.
Before treating the central repository as a durable shared source, put it on
the intended branch and either commit those paths or explicitly classify them
as local-only. Do not delete them as cleanup without inspecting their content.

The current generated registry is still expected at ~/.local/share/devman; its
presence is evidence that Stage 3 has not been performed, not evidence that the
current shell-entry implementation is broken.

## 9. Recommended next sequence

1. Clean up and commit the central config checkout, preserving the three
   untracked paths unless inspection proves they are disposable.
2. Release/rebuild loci-core 0.4.2, or keep the explicit --vault ~/Notes
   workaround documented and tested.
3. Implement Stage 3 with a reversible migration and no repository edits.
4. Rebuild nix-meta, re-enter representative repositories, and require
   devman doctor plus devman link status to exit 0.
5. Implement Stage 4 only after Stage 3 is stable and direct-link behavior is
   verified in at least two or three project overlays.
6. Revisit the remaining open questions and decide whether Stage 5 or the
   broader front-door cleanup deserves its own project.

## 10. Evidence index

- Governing charter: [025-the-link-plane/CONCEPT.md](../025-the-link-plane/CONCEPT.md)
- Agent-plane plan: [025-the-link-plane/GUIDE-01-agent-plane.md](../025-the-link-plane/GUIDE-01-agent-plane.md)
- Link-plane plan: [025-the-link-plane/GUIDE-02-link-plane.md](../025-the-link-plane/GUIDE-02-link-plane.md)
- Notes repair and loci prerequisite: [025-the-link-plane/GUIDE-03-notes-repair.md](../025-the-link-plane/GUIDE-03-notes-repair.md)
- First-pass verification artifacts: [028-link-plane/](../028-link-plane/)
- Link reconciler: [src/devman/link.py](../../../src/devman/link.py)
- Shell option and reconciliation hook: [modules/devenv.nix](../../../modules/devenv.nix)
- Machine service and Dagu paths: [nix/nixos-module.nix](../../../nix/nixos-module.nix)
- Workflow source resolution and projection: [src/devman/project.py](../../../src/devman/project.py)
- Link tests: [tests/unit/test_link.py](../../../tests/unit/test_link.py)
