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
| `.devman/workflows/` | [`.devman/workflows/README.md`](.devman/workflows/README.md) — this repository's central workflow overlay view |

Keep it that way. Never move a workflow's or a group's specifics up into a
library document, and never leave a new group or workflow without its own README
entry.

## The skills

| Task | Skill |
|---|---|
| anything devman — concept, CLI, diagnosis, routing | `.agents/skills/devman/SKILL.md` |
| write or change a workflow, a group, or a trigger | `.agents/skills/devman-workflow/SKILL.md` |
| bring a repository into the plane | `.agents/skills/devman-adopt/SKILL.md` |

## How this repository works

**Ten properties. Each has a measurement behind it, and knowing them is what
keeps a change from re-learning something the plane already paid for.**

1. **Read the stage log before you change a line that looks redundant.** Every
   non-obvious line here has a measurement behind it, recorded in
   `.scratch/projects/006-automation-plane/STAGE_*_LOG.md` and
   `.scratch/projects/007-standard-workflows/STAGE_7_LOG.md`. The log holds the
   answer, the versions, the exact command, the evidence, and what the charter
   had to change. Keep a comment that cites one.
2. **The charter governs.** `.scratch/projects/006-automation-plane/CONCEPT.md`
   is the design, amended by `007-standard-workflows/PROPOSAL.md`. **A second
   charter governs how files reach a repository:**
   `.scratch/projects/025-the-link-plane/CONCEPT.md`. A change that contradicts
   any of the three changes that document in the same commit, with the
   measurement that forced it.
3. **The shared contract is closed**: six queue names, `DEVMAN_PROJECT_DIR`,
   `DEVMAN_SELF_DIR`, and the `.devman/.runs/` path shape. Everything else is
   repository content or central per-repository overlay content. Adding another
   shared name changes the charter, because every repository inherits it — weigh
   it that way. **The queue list gained `llm` in 022**, and it is the only name
   whose limit bounds a quota held outside this machine rather than a local
   resource.
4. **A run that reports success while producing an incorrect result is the
   failure this design exists to prevent** — the wrong output, the wrong script,
   the right work in the wrong directory. Prefer a loud refusal to a silent
   default, and prefer a check that can fail to one that cannot. This is about
   correctness. Whether a correct result should have been reviewed first is a
   tier question, not this one.
5. **The plane holds no project fact.** No absolute path in a workflow file, no
   project name in the machine module, no per-project option in Nix. A workflow
   that needs another project's path takes a parameter whose default is a project
   *name*, and the trigger resolves it.
6. **The registry is derived.** Group sources and central overlay content are
   canonical. Read the registry freely; write to it through the projection, or
   through `doctor --prune`.

   **Current state:** the registry remains under `~/.local/share/devman/`.
   Link-plane Stage 3 plans to move generated registry and runtime state to
   `~/.local/state/devman/`; that directory does not exist yet.
7. **Python for core logic; shell stays a thin wrapper.** Shell that grows past a
   wrapper is shell nobody can test.
8. **Secrets are declared, never held.** A workflow names a secret through Dagu's
   `secrets:` field and the machine supplies the value. Dagu then masks it in
   logs, and a missing one fails the run before any step runs. Nothing in this
   repository holds a value. **Masking covers the exact value only** — measured
   in 022: the same step echoing five characters of a token logged them in clear.
   A step must not print a fragment of a credential.
9. **Write in Simplified Technical English.** Short sentences, active voice,
   one word for one meaning, no filler. See `.agents/skills/writing/SKILL.md`.
10. **The boundary test decides where a file lives.** Ask: *would this still be
    true for someone else who cloned the repository?* **Yes** — it is the project;
    it stays in the repository, tracked. **No, it is true for this user or this
    machine** — it goes central, under `devman.overlayDir`, and reaches the
    repository as a symlink with its own `.git/info/exclude` line. So `devenv.nix`
    stays and `devenv.local.nix` goes; `AGENTS.md` stays and `.agents/skills/`
    goes; a `base:check` task stays and the workflow that runs it at 3am goes.
    **Never decide this per file type** — every placement is one application of the
    one rule. The charter is `.scratch/projects/025-the-link-plane/CONCEPT.md` §P0,
    and it is written down because the question was re-litigated five times before
    anyone stated it.

## Verify before you save

```bash
devenv tasks run -v base:check     # ruff
devenv tasks run -v base:test      # nix flake check
devman doctor                      # the plane's own health
```

`devman doctor` must exit 0 before a change to `modules/`, `groups/`, `nix/` or
`src/devman/` is committed. It is the only thing that checks the whole plane.

## Choosing what to automate

**These are the questions worth asking, with what each costs when the answer goes
the wrong way.** Most have a workaround. Write the reasoning into the workflow
file, so the next reader can weigh it again. `PROPOSAL.md` §12 holds the long
form and the measurements.

**Two that rarely have a good answer:**

- **Is it irreversible outside this machine?** Publishing, tagging, deploying.
  `release` builds and does not publish, on purpose.
- **Could it succeed while doing nothing?** `devenv test` exited 0 having tested
  nothing in 30 of 58 repositories, and nothing noticed for a month. Give the run
  something that can fail.

**One that is usually a smell:** does it re-implement a task the repository
already has? Both copies keep passing while they drift.

**Five trade-offs — know the number, then decide:** an editor answers in tens of
ms and the plane in 1.44 s; an unset variable makes a directory of that literal
name; 54 identical reports is one report nobody opens; **a scheduled run does not
pass through its queue** (58 started at once, queue depth 0); and a fan-out picks
between `dag.run`, which bypasses the queue, and `dag.enqueue`, which respects it
but hides the child's failure.

**Every write falls into a tier** (015), and stating it in `writes.toml` is worth
doing even where nothing enforces it:

| Tier | What | Where it lands |
|---|---|---|
| `free` | a file that did not exist, and agent surface | the working tree |
| `lane` | an edit to existing tracked source | a **gitman lane**, for a person to merge |
| `insitu` | an idempotent normalisation of a watched file — `format` only | the working tree |

**An unattended write to trunk has no tier**, and it is the one shape to keep out
of a workflow: it appears in somebody's `git status` the next morning with
nothing to explain it. A lane carries a name and a diff instead.
