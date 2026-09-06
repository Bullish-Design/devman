# Portability-rule inventory and Templateer configuration note

Date: 2026-09-06

## Inventory

### Core contracts and user-facing documentation

- `AGENTS.md:65` — repository working agreement. Previously stated that the
  plane held no project facts or absolute workflow paths. It now says devman
  does not prescribe dependency portability.
- `README.md:43-44` — public architecture summary. States that the machine
  never learns project facts, project names, per-project options, or absolute
  paths.
- `AGENTS_GUIDE.md:268` — Nix module guide. Says the machine module must not
  learn project facts, project names, or per-project options.
- `USER.md:174-176` — command-line parameter contract. A parameter defaulting
  to a registered project name may be overridden only by another registered
  project name, not a path.
- `USER.md:294-296` — workflow authoring rule. Registered project names are
  resolved to paths so workflows do not hold absolute paths.
- `USER.md:551` — refusal catalog. Explains the error produced when a path is
  supplied where a registered project name is required.

### Runtime enforcement

- `src/devman/run.py:158-161` — classifies registered-project parameters as
  identity values and ordinary parameters as free values.
- `src/devman/run.py:197-204` — resolves registered names through the registry
  and describes absolute-path overrides as wrong-tree runs.
- `src/devman/run.py:206-212` — rejects a registered-project parameter whose
  override is not another registered project name.
- `src/devman/run.py:235-238` — generic missing-parameter refusal recommends
  registered project names as defaults.

These are behavior, not prose. Removing the portability rule from runtime
would require changing this resolver and its tests.

### Agent skills and authoring guidance

- `.agents/skills/devman/SKILL.md:52-55` — entry skill's central contract.
- `.agents/skills/devman-workflow/SKILL.md:168` — explains registered-project
  defaults as the path-resolution mechanism.
- `.agents/skills/devman-workflow/SKILL.md:241-242` — treats per-repository
  scheduling offsets as project facts.
- `.agents/skills/devman-workflow/SKILL.md:296-301` — cross-repository workflow
  example says target parameters hold project names, not paths.
- `.agents/skills/devman-workflow/SKILL.md:326` — group design table forbids
  project names, absolute paths, and per-repository offsets.
- `.agents/skills/devman-workflow/SKILL.md:516` — workflow checklist repeats the
  no-absolute-path/no-project-name/no-offset rule.

### Projection and module rationale

- `modules/devenv.nix:176-177` — rejects a Nix option for project-specific
  values because it would make the machine learn a project fact.
- `src/devman/show.py:73-74` — avoids saving projected workflow copies because
  they contain resolved absolute paths and would accumulate projection headers.

### Group-specific applications

- `groups/README.md:58` — group design comparison: project names are allowed
  as identities, absolute paths are not.
- `groups/format/triggers.toml:9-13` — explains why trigger project facts do
  not belong in workflow YAML, Nix options, or another runtime file.
- `groups/base/README.md:234-235` — avoids putting a machine-specific path in
  a shared workflow when discussing retention configuration.
- `groups/base/README.md:268-269` — treats per-repository timer offsets as
  project facts.
- `groups/base/workflows/maintain.yaml:47-49` — same shared-workflow rationale
  for machine paths.
- `groups/base/workflows/maintain.yaml:94-95` — same rationale for offsets.
- `groups/release/README.md:36-38` — documents relative paths and devman
  directory variables instead of absolute paths.
- `groups/changelog/workflows/changelog-entries.yaml:44-45` — says the
  repository, not the group, owns its gitman hook configuration.

These are local applications of the general rule. They may remain valid even
if the central portability policy changes.

### Templateer kickoff

- `.scratch/projects/022-templateer-changelog/KICKOFF.md:15-16` — forbids a
  sibling absolute path.
- `KICKOFF.md:51-55` — requires portable template/dependency delivery.
- `KICKOFF.md:70-73` — acceptance criterion requiring no sibling path.
- `KICKOFF.md:139-141` — stop condition if a sibling path is required.

This project note should be updated to permit the configured sibling path.

## Existing configuration surfaces

1. **Dagu workflow parameters** — the best fit for a workflow-specific path.
   A `params:` entry can carry a Templateer root or library path, and Dagu
   exposes it to the step environment. `devman run` already parses, fills, and
   validates declared parameters. This is the narrowest piggyback point.

2. **`devenv.nix` `env.*` values** — suitable for an adopter-wide default such
   as `TEMPLATEER_PATH`. It reaches interactive shells and can be inherited by
   Dagu, but the daemon environment boundary must be measured; the changelog
   work already found that Dagu does not automatically inherit adopter-shell
   variables.

3. **`DEVMAN_PROJECT_DIR` / `DEVMAN_SELF_DIR`** — existing directory plumbing,
   but not appropriate for Templateer. They identify the workflow project and
   cross-repository parent, and their precedence rules are deliberately special.

4. **The project registry** — stores project identity and paths, but is not a
   general configuration store. Using it for Templateer would conflate
   repository registration with dependency configuration.

5. **Nix module options in `modules/devenv.nix`** — existing options configure
   `devman.project`, `devman.groups`, and related projection inputs. A new
   Templateer option would be machine/repository configuration, but it would
   require a schema and projection change and is broader than a workflow
   parameter.

## Recommendation

Start with a declared workflow parameter, for example `TEMPLATEER_PATH`, whose
default is the configured sibling path in this repository. Keep the value
explicit in the workflow and pass it to a thin adapter. Only add a `devenv.nix`
option if multiple workflows or adopters need the same value and measurement
shows that a workflow parameter is insufficient.
