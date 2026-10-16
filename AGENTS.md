# AGENTS.md — devman

## What this repository is

devman runs Dagu workflows across the owner's repositories. It compiles central
workflow sources into files that Dagu runs. It routes events to workflows. It
shows each repository what runs in it. Dagu does everything else. If Dagu has a
feature, devman uses it and does not rebuild it.

**The charter is `.scratch/projects/047-greenfield/CONCEPT.md`.** It is the only
charter. `PLAN.md` beside it holds the interfaces (section A), the decisions
(section E) and the as-built notes. A change that contradicts the charter changes
it in the same commit, with the measurement that forced the change. Older
documents in `.scratch/` are history.

## Scope

Mechanism and content are documented separately.

| Where | Holds |
|---|---|
| `README.md` | the mechanism: files, manifest, commands, refusals, install |
| `USER.md` | daily use |
| `AGENTS_GUIDE.md` | the code map, the tests, diagnosis |
| `~/.config/devman/library/README.md` | the content: what each library file does |
| `~/.config/devman/workflows/<project>/` | the workflows of one project |

Never copy library detail into a mechanism document. Never leave a library file
without an entry in its README.

## The skills

| Task | Skill |
|---|---|
| anything devman: concept, commands, diagnosis | `.agents/skills/devman/SKILL.md` |
| write or change a workflow or an `on` entry | `.agents/skills/devman-workflow/SKILL.md` |
| add a project | `.agents/skills/devman-adopt/SKILL.md` |
| write any text | `.agents/skills/writing/SKILL.md` |
| open and close a workspace | `.agents/skills/gitman/SKILL.md` |

## Rules

1. **A run that reports success while producing a wrong result is the failure
   this design prevents.** Prefer a loud refusal to a silent default. Prefer a
   check that can fail to one that cannot.
2. **The boundary test decides where a file lives.** Ask: would this still be
   true for someone else who cloned the repository? Yes: it stays in the
   repository, tracked. No: it goes central, under `~/.config/devman`. Never decide
   this per file type.
3. **The plane holds no project fact.** No absolute path in a workflow file. No
   project name in the module. The manifest holds them.
4. **Python for core logic. Shell stays a thin wrapper.**
5. **Secrets are declared, never held.** A workflow names a secret in Dagu's
   `secrets:` field. Masking covers the exact value only. A step must not print a
   fragment of a credential.
6. **Write in Simplified Technical English.** Short sentences, active voice, one
   word for one meaning, no filler. This covers docs, comments, error text and
   commit messages.
7. **Read the evidence before you change a line that looks redundant.**
   `SPIKES.md` and `MEASUREMENTS.md` in the charter directory record why. Keep a
   comment that cites one.
8. **Add no shared name lightly.** The queue names, the environment variables
   and the `devman.task` action reach every repository.

## Verify before you save

```bash
devenv tasks run -v base:check   # ruff check, ruff format --check, uv lock --check
devenv tasks run -v base:unit    # pytest
devenv tasks run -v base:e2e     # pytest against a real Dagu on loopback ports
devenv tasks run -v base:test    # nix flake check
nix build .#devman
devman doctor                    # the plane's own health; must exit 0
```

All must pass. In a gitman workspace, run `git add -A` first: Nix ignores
untracked files. Never run `systemctl`, `home-manager` or a rebuild from a
stage. The cutover (Stage 10) is done. `devman doctor` checks the live plane,
so run it by its absolute path when a stale venv `devman` is first on PATH.

**Machine evidence, 2026-10-16:** 33 projects, 72 compiled DAG files, Dagu
2.20.1, devman 0.9.0. Read the counts as evidence, not as architecture.

## Version control

- Work in a gitman workspace: `gitman work NAME`. Read the gitman skill.
- The goal of every workspace is `main`. Verify, rebase onto `trunk()`, verify
  again if the tree changed, move `main`, push, then `gitman done NAME`.
- Land by default once verify passes. Stop and ask when verify fails, a conflict
  appears, or the change touches secrets or release configuration.
- Commit messages follow the writing rules. Add no attribution trailer.
- Before you open a workspace, list the existing ones and report any work that
  `main` lacks.

## Choosing what to automate

Ask these before you write a workflow. Write the answers into the file.

- **Is it irreversible outside this machine?** Publishing, tagging, deploying.
  `release` builds and does not publish, on purpose.
- **Could it succeed while doing nothing?** `devenv test` exited 0 having tested
  nothing in 30 of 58 repositories, and nobody noticed for a month. Give the run
  something that can fail.
- **Does it rebuild a task the repository already has?** Call the task. Two
  copies drift while both pass.
- **Does it write to trunk without a person?** Keep it out. A write that nobody
  sees appears in `git status` the next morning with nothing to explain it. Write
  to a branch, as the agent example does.

Measured trade-offs:

- An editor answers in tens of milliseconds. The plane takes about 1.4 seconds.
- An unset variable makes a directory with that literal name.
- 54 identical reports are one report that nobody opens.
- A fan-out chooses between `dag.run`, which bypasses the queue, and
  `dag.enqueue`, which respects it but hides the child's failure.
- Dagu does not report the cost of an agent step. The cap comes from the
  harness flag, such as `max-budget-usd`.
