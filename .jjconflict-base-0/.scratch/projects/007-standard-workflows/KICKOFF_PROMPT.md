# Kickoff — designing the standard workflow set

**This session is a design session. Write no implementation code.** The output
is a written proposal that a later stage implements. If you find yourself
editing `groups/`, `modules/` or `src/`, you have left the session's scope.

Read these first, in this order:

1. `.scratch/projects/006-automation-plane/CONCEPT.md` — the charter. §7 (the
   contract), §8 (triggers), §9.2 (on disk), §11 (cross-repo), §14 (the
   seventeen criteria).
2. `.scratch/projects/006-automation-plane/STAGE_6_LOG.md` — the last stage.
   Its "What stage 6 did not do" table names the questions this session inherits.
3. Every file under `groups/*/workflows/`. There are nine. Read all nine.

---

## 0. Where the plane actually is

The plane is built, installed and running. This is not a greenfield design.

| | |
|---|---|
| Registered projects | 6 — `devman`, `siteman`, `observantic`, `pyjutsu`, `nix-paseo`, `pydantree` |
| Projected workflows | 36 |
| Groups that exist | `base`, `python`, `python-format`, `release` |
| Dagu | 2.15.0, `systemd --user` unit `dagu` |
| Nightly schedule | `base/maintain`, `5 0 * * *`, fired by Dagu's own scheduler, proved unattended |
| `devman doctor` | 12 checks, all ok |

**And this is the population it has to serve:**

| | Count |
|---|---|
| Git repositories under `~/Documents/Projects` | 67 |
| Of those, carrying a `devenv.nix` | 57 |
| Of those, registered with devman today | 6 |
| Carrying a `pyproject.toml` | 52 |
| Nix repositories with no Python | 11 |
| Other | one Rust+Python (`pyjutsu`), one Node (`paloma-story-generation`), several Neovim configurations, one repository with no language files at all (`siteman`) |

**The gap between 6 and 57 is the reason for this session.** Four groups grown
one stage at a time served six repositories. The question is what set serves
fifty-seven, and it is a different question.

---

## 1. What is fixed, and what is yours to change

**Fixed. Do not propose changing these.**

- A repository adopts the plane with three Nix keys: `enable`, `project`,
  `groups`. There is no per-workflow Nix option (§7.4).
- A workflow is portable Dagu YAML. devman never parses it (§7.2).
- Selection happens at group granularity. To be rid of a workflow, do not take
  its group.
- The global vocabulary is five queue names: `exclusive`, `gpu`, `heavy`,
  `light`, `normal`. Default `light`.
- Shadowing is whole-file (§12.4). A repository replaces a workflow by writing
  `.devman/workflows/<name>.yaml`.
- Triggers are four: a watcher, a git hook, Dagu's scheduler, and `devman run`
  (§8).

**Yours to change — everything about the content:**

- Which groups exist, and what each one is for.
- Which workflows each group ships, and what they are named.
- Which trigger fires each workflow.
- Which queue each workflow names.
- Which task names a group's workflows call, and therefore what a repository
  must define to take that group.

The last one is the hinge. Read §2.

---

## 2. The current set, stated honestly

```
base          check  full-test  maintain  review  validate
python        check  validate
python-format format
release       release
```

Bodies, compressed:

| Workflow | Queue | Calls | Writes files |
|---|---|---|---|
| `base/check` | light | `base:lint` | no |
| `base/validate` | normal | `base:lint`, `base:test` | no |
| `base/full-test` | heavy | `base:lint`, `base:test`, `devenv test` | no |
| `base/review` | normal | git inspection, then `base:lint`, `base:test`, each `continue_on: failure` | a report |
| `base/maintain` | light | prunes reports, runs `devman doctor` | a report |
| `python/check` | light | `python:lint`, `python:typecheck` | no |
| `python/validate` | normal | `python:lint`, `python:typecheck`, `python:test` | no |
| `python-format/format` | light | `python-format:fmt`, guarded by a content hash | **yes — source files** |
| `release/release` | heavy | gate on clean tree and a succeeded `validate`, then `release:build` | a report and artifacts |

**Four things about this set are worth attacking, and you should attack them.**

**2.1 `check`, `validate` and `full-test` are three points on one ladder.** They
differ by how much they run. Is a three-rung ladder right? Are those the names?
`check` and `validate` are near-synonyms in English, and a reader cannot tell
which is bigger without opening both.

**2.2 `base` is not language-neutral.** `base/check` calls `base:lint`. Every
repository taking `base` must define a task called `base:lint`, whatever its
language. That is either a good universal contract or a fiction that will break
on the eleventh Nix repository. Decide which, and say why.

**2.3 `python` and `python-format` are split for a mechanical reason.**
`format` writes source files, so it needs a content hash to satisfy criterion 13
and it is the only reactive workflow in the set. The split is real, but is
"a group per trigger class" the rule, or an accident of stage 3?

**2.4 `observantic` and `pydantree` take both `base` and `python`, so
`python/check` shadows `base/check`.** That works. But a repository taking two
groups that both ship `validate` is resolving a collision by group order. At
four groups this is invisible. At twelve it is a design property.

---

## 3. The questions to answer

Work these in order. Later ones depend on earlier ones.

### Q1 — What is the universal contract?

Name the task primitives every registered repository must define, regardless of
language. For each one, say what it means and what happens in a repository where
it makes no sense.

The current answer is `base:lint` and `base:test`. Test that answer against:
a Nix flake repository, a Neovim configuration, and `siteman` — which has no
language files and already shadows `full-test` because of it.

The alternatives are real, so state which you chose:

- **A universal contract**, as today. Every repository defines the same task
  names. Language groups add to them.
- **No universal contract.** `base` ships only workflows that call nothing —
  `maintain`, and whatever else is pure inspection. Every executing workflow
  comes from a language group.
- **A universal contract with a null implementation.** Every repository defines
  `base:lint`, and a repository with nothing to lint defines it as `true`.

### Q2 — What is the ladder, and what are the rungs called?

Decide how many tiers of "run the checks" exist and name them. For each rung,
state its trigger, its queue, its wall-clock budget, and what a developer learns
from it that the rung below did not tell them.

A rung that no trigger fires, and that no human would type, is not a rung.

### Q3 — What is the group set?

Propose the groups. For each: its name, its purpose in one sentence, the
workflows it ships, and the task names it requires of a repository.

Cover the population in §0. At minimum, a proposal must say what the eleven
Nix-only repositories take, and what a Neovim configuration takes.

Then answer the granularity question directly. Two failure modes:

- **Too few groups.** A repository takes `python` and inherits a `release`
  workflow it will never run. Criterion 4 says it must be able to be rid of it,
  and the only mechanism is not taking the group.
- **Too many groups.** `groups = [ "base" "python" "python-format"
  "python-typecheck" "python-test" "release" "docs" ]` is not three-key
  adoption in any meaningful sense.

State your rule for when a workflow deserves its own group. `python-format`
suggests one candidate rule — "a group per trigger class". Confirm it or replace
it.

### Q4 — The trigger matrix

Produce a table: every workflow against save, commit, push, schedule and manual.
Every workflow needs at least one trigger, or it is dead weight.

Two constraints bind here, and a proposal that ignores either is wrong:

- **Criterion 13.** Any workflow that writes files a watcher watches must break
  the loop with a content hash. `python-format/format` is the worked example.
  Copy its shape or justify a different one.
- **Criterion 14.** No workflow may re-state a dependency devenv already
  declares. If `python:test` already depends on `python:lint` in `devenv.nix`,
  a workflow listing both as steps has written the graph twice.

### Q5 — What else gets scheduled?

Today, one workflow carries a `schedule:`, and it is `maintain`. Stage 6 refused
to schedule anything else on purpose, for a stated reason:

> A scheduled workflow that rewrites source files is §8's reactivity argument in
> a new place.

Candidates that will come up: dependency updates (`nix flake update`, `uv
lock`), a security audit, a documentation build, a stale-branch report, a
repository-health digest across all projects.

Sort each into **reads only** or **writes source**. For anything in the second
column, answer the reactivity question before proposing it: the write lands in a
watched tree, at 03:00, with nobody present. Say what fires next.

Also decide the schedule shape. Fifty-seven repositories firing `maintain` at
`5 0 * * *` is fifty-seven simultaneous dispatches. Six was fine. Say whether
fifty-seven is, and if not, what carries the stagger — the queue, the
expression, or something that does not exist yet.

### Q6 — Do agent workflows become a group?

`devman` carries three local workflows: `agent-review`, `bench-entry`,
`stack-validate`. They live in `.devman/workflows/` because they are inventions,
not inheritances.

Decide whether any of them generalises into a group. If yes, say what it
requires of a repository, and how it handles secrets (§9.4 — a workflow reads
its own secret; the plane never holds one).

### Q7 — What must never become a workflow?

Write the list, with reasons. A plane that will run anything has no shape. This
answer is what a future stage points at when it wants to say no.

---

## 4. Rules for this session

1. **Test every proposal against §14's seventeen criteria.** Name the criteria
   your proposal touches. Criterion 4 is the sharp one: if a repository cannot
   rename or replace a default without something objecting, the proposal has
   grown an opinion the plane should not have.
2. **Cost every group in adoption lines.** A group that needs a repository to
   define five new tasks is not free, whatever its `groups` entry costs.
3. **Name the repositories.** "Python projects" is not a scope. `fsdantic`,
   `poddantic`, `webdantic` is a scope. Use the real inventory — the repositories
   are listed in §0 and readable on disk.
4. **Say what you would delete.** A proposal that only adds is not a design.
   `base` has five workflows; if the answer keeps all five, say why each earns
   its place.
5. **Disagree with the charter in writing.** If §7's group granularity is wrong
   for fifty-seven repositories, say so and say what replaces it. Do not work
   around it silently. A charter change is a legitimate output of this session.
6. **One idea per section.** Do not produce a document that has to be read twice
   to find the recommendation.

---

## 5. Deliverables

Write into this directory:

**`PROPOSAL.md`** — the design.

1. **The recommendation in ten lines**, at the top, before any reasoning.
2. **The universal contract** — the task names, and what a repository that
   cannot honour one does instead (Q1).
3. **The group table** — name, purpose, workflows, required tasks, and which of
   the 67 repositories takes it (Q3).
4. **The workflow table** — name, group, queue, trigger, writes-files, and the
   rung it occupies on the ladder (Q2, Q4).
5. **The scheduled set** (Q5), with the reactivity answer for anything that
   writes.
6. **What is deleted or renamed** from the current nine, with the migration each
   needs. `observantic` and `pydantree` already shadow `check`; a rename breaks a
   shadow, so say how.
7. **Against the seventeen criteria** — the ones the proposal touches, and the
   result for each.
8. **The rollout** — which repositories adopt in which order, and the first five
   by name. Say what proves each wave worked.
9. **Charter impact** — the sections of `CONCEPT.md` that change, and the new
   text for each.
10. **Rejected alternatives** — at least three, each with the reason it lost.

**`OPEN_QUESTIONS.md`** — what the session could not settle, and what
measurement would settle each one.

---

## 6. How to disagree with this prompt

This prompt assumes the four existing groups are a starting point rather than a
constraint. If the right answer is that `base` should not exist, say so in
`PROPOSAL.md` §1 and argue it. The prompt is not the charter.

The one thing not open: **the plane runs, nightly, unattended, in six
repositories.** Any proposal has to get from there to wherever it goes, without
a flag day.
