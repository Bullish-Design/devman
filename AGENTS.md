# AGENTS.md — devman

## What this repository is

devman is a friendly way to run Dagu workflows across the owner's
repositories. It compiles central workflow sources into files that Dagu runs.
It routes events to workflows, and it shows each repository what runs in it.
Dagu does everything else. If Dagu has a feature, devman uses it.

**The charter is `.scratch/projects/047-greenfield/CONCEPT.md`; the plan is
`PLAN.md` beside it.** This file is an interim version. Stage 9 of the plan
writes the full one. The old charters in `.scratch/` are history only.

## Rules that still hold

1. **A run that reports success while producing an incorrect result is the
   failure this design exists to prevent.** Prefer a loud refusal to a silent
   default, and prefer a check that can fail to one that cannot.
2. **Python for core logic; shell stays a thin wrapper.**
3. **Secrets are declared, never held.** A workflow names a secret through
   Dagu's `secrets:` field. Masking covers the exact value only, so a step must
   not print a fragment of a credential.
4. **Write in Simplified Technical English.** Short sentences, active voice,
   one word for one meaning, no filler. See `.agents/skills/writing/SKILL.md`.
5. **Read the stage log before you change a line that looks redundant.** Logs
   sit in `.scratch/projects/`. Keep a comment that cites one.
6. **The boundary test decides where a file lives.** Ask: *would this still be
   true for someone else who cloned the repository?* **Yes** — it is the
   project; it stays in the repository, tracked. **No, it is true for this user
   or this machine** — it goes central, under `~/.config/devman`, and reaches
   the repository as a link. Never decide this per file type. The library of
   shared workflows is central content (decision Q7).

## Verify before you save

```bash
devenv tasks run -v base:check   # ruff check and ruff format --check
devenv tasks run -v base:unit    # pytest
devenv tasks run -v base:test    # nix flake check
```

`devman doctor` is not part of verify until Stage 10. The new doctor arrives in
Stage 6, and the new plane runs only after the cutover.

## Choosing what to automate

**These are the questions worth asking, with what each costs when the answer
goes the wrong way.** Write the reasoning into the workflow file, so the next
reader can weigh it again.

**Two that rarely have a good answer:**

- **Is it irreversible outside this machine?** Publishing, tagging, deploying.
  `release` builds and does not publish, on purpose.
- **Could it succeed while doing nothing?** `devenv test` exited 0 having
  tested nothing in 30 of 58 repositories, and nothing noticed for a month.
  Give the run something that can fail.

**One that is usually a smell:** does it re-implement a task the repository
already has? Both copies keep passing while they drift.

**Trade-offs, measured:** an editor answers in tens of ms and the plane in
1.44 s. An unset variable makes a directory of that literal name. 54 identical
reports are one report nobody opens. A scheduled run did not pass through its
queue before Dagu 2.17.0. A fan-out chooses between `dag.run`, which bypasses
the queue, and `dag.enqueue`, which respects it but hides the child's failure.

**An unattended write to trunk is the one shape to keep out of a workflow.** It
appears in somebody's `git status` the next morning with nothing to explain it.
Write to a gitman lane instead. A lane carries a name and a diff.
