# 025 — the link plane

**This directory is the charter for how files reach a repository.**
`devman/AGENTS.md` names `CONCEPT.md` here as a governing document: a change that
contradicts it changes that document in the same commit, with the measurement that
forced it.

| File | What it is |
|---|---|
| [`CONCEPT.md`](CONCEPT.md) | **the charter.** The boundary test (§P0), the four planes, the link plane, the work plane, the agent surface, the layout, the migration |
| [`FINDINGS.md`](FINDINGS.md) | the twelve-repository audit the charter answers. Evidence, not design |
| [`GUIDE-01-agent-plane.md`](GUIDE-01-agent-plane.md) | move the agent surface into the config repository |
| [`GUIDE-02-link-plane.md`](GUIDE-02-link-plane.md) | the config repository, `devman.link`, the reconciler |
| [`GUIDE-03-notes-repair.md`](GUIDE-03-notes-repair.md) | repair `~/Notes`, then wire the notes plane |

## The one rule

> **Would this still be true for someone else who cloned the repository?**
>
> - **Yes → it is the project.** It stays in the repository, tracked.
> - **No — it is true for *me* or *this machine* → it goes central**, and reaches
>   the repository as a symlink.

Every placement decision is one application of this. **Never decide per file
type** — that is the failure mode this charter exists to stop, and it recurred
five times before the rule was written down.

## Provenance

Drafted in `~/Documents/Projects/.scratch/projects/026-family-first-principles/`,
which is untracked working scratch and does not survive. **This copy is
canonical.** Implementation artifacts for the first pass are in
`../028-link-plane/`.
