# .scratch/context — reference material for agent sessions

This directory holds pointers to upstream sources that an agent session reads
while working on the automation plane. **The pointers are tracked. The sources
are not.**

`.vend/` is the payload directory. It is git-ignored (`.gitignore`, one rule for
`.scratch/context/.vend/`), because it holds full upstream clones that are
refetched on demand rather than committed.

## What is vendored

| Path | Source | Pin |
|---|---|---|
| `.vend/dagu` | `https://github.com/dagu-org/dagu` | tag `v2.15.0` |

The Dagu pin **must match the version the plane installs**, which `nix/dagu.nix`
sets. Bump both together, or an investigation measures one version and reads
another.

## Refetch

```bash
rm -rf .scratch/context/.vend/dagu
git clone --depth 1 --branch v2.15.0 \
  https://github.com/dagu-org/dagu.git .scratch/context/.vend/dagu
```

## Where to read first, in the order it helps

| Path under `.vend/dagu/` | Holds |
|---|---|
| `internal/cmn/schema/dag.schema.json` | every legal DAG field, with descriptions (270k) |
| `internal/cmn/schema/config.schema.json` | every instance config field (49k) |
| `skills/dagu/SKILL.md`, `skills/dagu/references/*.md` | the agent skill upstream ships |
| `llms.txt` | the documentation in one file (86k) |
| `README_SCHEMA.md`, `SCHEMA_MIGRATION.md` | current syntax, and what it replaced |
| `internal/cmd/*.go` | command behaviour when the schema is ambiguous |

**Read the schema, then prove it by running a DAG.** A schema field is a claim;
a run is evidence. Investigation A found three places where the documentation
and the behaviour disagree — see `.scratch/projects/006-automation-plane/FINDINGS.md`.

## Why this is not under `.devman/`

It used to be, and stage 1 moved it.

`CONCEPT.md` §15.2 is a **whitelist**: `.devman/` may hold only `workflows/`
and `.runs/`, and any other top-level entry means registration refuses and
reports. D6's survey of 77 checkouts found four shapes of `.devman/`, and
`context/` — this directory — was one of the two real specimens it found. A
blacklist would have silently adopted it.

So the choice at stage 1 was to widen the whitelist or to move the directory.
Moving it is right: the whitelist is what stops the plane adopting a
`.devman/` that means something else, and this repository was the first to
prove the rule bites. Criterion 16 says devman adopts itself, and a repository
that has to weaken the rule to adopt the plane has not adopted it.
