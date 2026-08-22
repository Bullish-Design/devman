# .devman/context — reference material for agent sessions

This directory holds pointers to upstream sources that an agent session reads
while working on the automation plane. **The pointers are tracked. The sources
are not.**

`.vend/` is the payload directory. It is git-ignored (`.gitignore`, one rule for
`.devman/context/.vend/`), because it holds full upstream clones that are
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
rm -rf .devman/context/.vend/dagu
git clone --depth 1 --branch v2.15.0 \
  https://github.com/dagu-org/dagu.git .devman/context/.vend/dagu
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

## A note on this directory

`CONCEPT.md` §15.2 warns that `.devman/` has carried other meanings, and that
registration must detect a shape it does not recognise rather than adopt it.
`context/` is a third thing under `.devman/`, alongside §9.2's `workflows/` and
`.runs/`. Whoever writes the registration check should treat `context/` as
inert, the same way §7.2 treats everything in a group directory that is not
`workflows/*.yaml`.
