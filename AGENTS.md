# AGENTS.md — devman

## What this repository is

devman is the **development automation plane**. One Dagu control plane runs per
machine. Every devenv-managed repository joins it through this Nix flake and
inherits a small, shared set of workflows.

**Dagu orchestrates. devenv executes. devman is the contract between them.**
devman itself executes nothing, and never parses a workflow to understand it.

## Scope

This file applies to the entire repository. Read
[`AGENTS_GUIDE.md`](AGENTS_GUIDE.md) next for the map and the operations.

**Mechanism and content are documented separately, and the split is deliberate.**
`README.md`, `USER.md` and `AGENTS_GUIDE.md` describe the library — the
interfaces, the contract, resolution, projection, the CLI, the refusals. **What
this flake actually ships documents itself, in the directory that holds it:**

| Directory | Its README |
|---|---|
| `groups/` | [`groups/README.md`](groups/README.md) — the group mechanism, and an index of the groups here |
| `groups/<group>/` | what that group ships, and what taking it costs a repository |
| `.devman/workflows/` | [`.devman/workflows/README.md`](.devman/workflows/README.md) — this repository's own workflows |

Keep it that way. Never move a workflow's or a group's specifics up into a
library document, and never leave a new group or workflow without its own README
entry.

## The skills

| Task | Skill |
|---|---|
| anything devman — concept, CLI, diagnosis, routing | `.agents/skills/devman/SKILL.md` |
| write or change a workflow, a group, or a trigger | `.agents/skills/devman-workflow/SKILL.md` |
| bring a repository into the plane | `.agents/skills/devman-adopt/SKILL.md` |

## The law

1. **Read the stage log before you change a line that looks redundant.** Every
   non-obvious line here has a measurement behind it, recorded in
   `.scratch/projects/006-automation-plane/STAGE_*_LOG.md` and
   `.scratch/projects/007-standard-workflows/STAGE_7_LOG.md`. The log holds the
   answer, the versions, the exact command, the evidence, and what the charter
   had to change. Never delete a comment that cites one.
2. **The charter governs.** `.scratch/projects/006-automation-plane/CONCEPT.md`
   is the design, amended by `007-standard-workflows/PROPOSAL.md`. A change that
   contradicts either changes that document in the same commit, with the
   measurement that forced it.
3. **The four global names are a closed list**: the five queue names,
   `DEVMAN_PROJECT_DIR`, `DEVMAN_SELF_DIR`, and the `.devman/.runs/` path shape.
   Adding a fifth is a charter change, not an implementation detail.
4. **One workflow, one step, one `devenv tasks run`.** Order belongs to the
   repository's devenv task graph, never to a Dagu file.
5. **A successful run that did the wrong thing is the failure this design
   exists to prevent.** Prefer a loud refusal to a silent default. Never make a
   check pass by making it check nothing.
6. **The plane never learns a project fact.** No absolute path in a workflow
   file, no project name in the machine module, no per-project option in Nix.
7. **The registry is derived; the repository is canonical.** Read it freely.
   Write to it only through the projection, or through `doctor --prune`.
8. **Keep scripts minimal and auditable.** Python for core logic; shell stays a
   thin wrapper.
9. **Never commit secrets or tokens.** §9.4 — the secrets path — has never
   fired, and nothing in this repository needs it to.
10. **Write in Simplified Technical English.** Short sentences, active voice,
    one word for one meaning, no filler. See `.agents/skills/my-ai/SKILL.md`.

## Verify before you save

```bash
devenv tasks run -v base:check     # ruff
devenv tasks run -v base:test      # nix flake check
devman doctor                      # the plane's own health
```

`devman doctor` must exit 0 before a change to `modules/`, `groups/`, `nix/` or
`src/devman/` is committed. It is the only thing that checks the whole plane.

## What must never become a workflow

Eight rules, in `PROPOSAL.md` §12. The short form:

- anything an editor already does synchronously
- anything irreversible outside this machine
- anything that writes tracked source with nobody present
- anything whose success is indistinguishable from doing nothing
- anything needing a fact the repository did not state
- a second implementation of a task the repository already has
- anything whose output nobody reads
- anything expensive, on a schedule — **a scheduled run bypasses its queue**
