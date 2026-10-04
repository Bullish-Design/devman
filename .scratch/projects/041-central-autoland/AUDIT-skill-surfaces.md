# Audit: shared-skill surfaces at the 2026-10-03 snapshot

**Date:** 2026-10-03
**Scope:** the central Devman skill pool and its 65 project surfaces. This is a
historical research record. The machine-wide retirement scan is the current
inventory.

## Result

The pool target for the former personal-layer skill had already been removed
from trunk. The separate writing skill existed, but the fleet had not received
it everywhere. At the snapshot, 35 repository instruction files still cited
the removed skill path. All 35 repositories had crossed to the link plane, so
these were text defects rather than broken directory links.

The central trunk used for the audit was
 ef1b3847f028dce07c70bc64b0dad7319982da01. It held 15 pool skills:

- copyroom, copyroom-adopt, copyroom-template-edit
- eight devenv skills: authoring, inputs, lock, module-edits, processes,
  python-venv, run-commands, troubleshoot
- docman, gitman, testee, and writing

The former personal-layer skill was absent. The writing skill was present and
held only the Simplified Technical English rules. It did not define devenv
discipline, exit codes, manager routing, or the agent-files convention.

## Surface measurements

The central repository had 65 project directories, of which 64 held an agent
skill surface. Those 64 surfaces contained 714 entries: 542 relative symlinks
into the pool, 161 real directories, and 10 real files. No tracked absolute
symlinks appeared among 559 checked links.

The writing skill appeared on 18 of 65 surfaces. Of the 35 repositories whose
AGENTS.md cited the removed skill path at that time, 7 also had writing and 28
did not. The seven were forgelab, inferference, lodestar, PyGentic,
pytuin-desktop, silverbullet-server, and template-py. The other 28 had no
writing link; history showed it had never been added to those surfaces.

The 35 repositories in the citation survey were:

allium-env, atuout, boomtube, cairn, clinch, copyroom, embeddy, flora,
flora-core, flora-qc, forgelab, fornix, grail, image-gen-pipeline, inferference,
interplay, knappy, loci-core, lodestar, observantic, parsedantic, poddantic,
pydantree, PyGentic, pyjutsu, pyllij, pytuin, pytuin-desktop, repoman,
silverbullet-server, siteman, structured-agents-v2, templateer_v2,
template-py, terminal-state, vendomat, webdantic, and zelligate.

The writing skill was not a replacement for the four-topic boilerplate. A path
swap would have made a false claim. The recommended fix was to keep project
instructions in each repository, state stable rules there, and name the repoman
skill for generated manager routing.

## Historical timeline

- 2026-09-11: commits bf06e351 and 5d43caa2 moved the writing rules into the
  writing pool skill.
- 2026-09-16: commit e93ea4e9 distributed the gitman skill across the fleet.
- 2026-09-19: commit 71344a42 linked testee, docman, and writing into one
  project surface.
- 2026-10-01: commits beginning ff7be524 archived two central projects. The
  personal-layer skill had already been removed from the pool.

The audit found that deletion of the pool target had pruned many per-project
links as generated state. It did not add writing to surfaces that lacked it.
The report's central-workspace lane list was only a snapshot and must not guide
current Gitman actions.

## Current interpretation

The 2026-10-03 retirement request supersedes the audit's earlier recommendation
to add writing to 28 surfaces. The writing skill remains the home for the
writing rules. Remove active references to the retired layer by reviewing each
instruction, test, and example in context. Do not use the old 35-repository
count as a current inventory.
