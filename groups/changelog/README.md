# changelog — a detail file per landed commit, summarised into CHANGELOG.md per lane

`devman.groups = [ "base" "changelog" ]`

Two workflows, chained, and the plane's first tier-B writer (015): one lands no
lane at all, the other lands one for a person to merge. Full design and the two
measurements that shaped it: `.scratch/projects/021-changelog/DESIGN.md`.

## Who should take this

**Consumed-by-others repositories, not every repository.** A changelog nobody
reads is output nobody reads. `shellij` (51 consumers), `gitman` and `devman`
itself each ship something another repository pins; a scratch or leaf repository
has no external reader and should not take this group — the same posture
`release` already takes for "most registered repositories have nothing to
release".

## What it is

| File | What it is |
|---|---|
| `workflows/changelog-entries.yaml` | tier free — writes one detailed diff file per landed commit under `.devman/changelog/entries/`. **Cannot run today** — see "The entries workflow is blocked" below |
| `workflows/changelog.yaml` | tier lane — summarises the un-summarised entries into `CHANGELOG.md`, via a local LLM, on a fixed-name gitman lane |
| `templates/changelog/` | the templateer template `changelog.yaml` renders the summary through |
| `writes.toml` | both workflows' declared tier and paths |

No `triggers.toml`. Neither workflow is reactive to a file save — `changelog-
entries` fires on a `gitman land`, which is a different event the watcher does
not see (§1 below).

## What taking it costs

No task name to define — both workflows are plain shell over console scripts,
with an inline `python3` step for the parts that shape JSON. No devenv task is
needed, unlike `release`'s `release:build`. It costs six things instead, each a
one-time setup:

**1. A line in this repository's own `gitman.toml`:**

```toml
[land.post_hook]
command = ["devman", "run", "changelog-entries"]
```

**2. A bootstrapped `CHANGELOG.md`, once, before the first run:**

```bash
trunk=$(python3 -c 'import pathlib,tomllib; print(tomllib.loads(pathlib.Path("gitman.toml").read_text())["trunk"])')
cid=$(gitman log --revset "$trunk" | tail -1 | cut -d" " -f1)
printf '<!-- devman-changelog: covers up to %s -->\n' "$cid" > CHANGELOG.md
git add CHANGELOG.md && git commit -m "chore: bootstrap the changelog"
```

`gitman log`, not an import: the marker is a jj change id, and `gitman log`
is the console script that hands one over without the caller importing
anything (see "Console scripts, never a library import" below).

`changelog.yaml`'s gate refuses loudly, naming the file, if this marker is
absent — no special-cased first run, no silent default.

**3. `.devman/changelog/entries/` excluded locally**, the same way this
repository already excludes `.devman/.runs/` and `.devman/gitman/` — a line in
`.git/info/exclude`, never a committed `.gitignore` (CONCEPT.md §9.2: run
output is per working tree). It is regenerable from jj's own history at any
time, so losing it costs nothing:

```
.devman/changelog/
```

Skipping this is harmless but noisy — every entry file shows up as untracked
in `git status` until it is excluded.

**4. `gitman` and `templateer` on the step's own PATH.** `changelog.yaml`
calls both by name and imports neither. The machine's shared toolchain venv
lends a console script through PATH, which is what makes this work in a
repository that never declared either as a dependency.

`changelog.yaml`'s gate probes for both before it reads a single commit, and
names the missing one. The probe runs inside the same `devenv shell --` every
later command uses, because that is the only interpreter and the only PATH
whose answer is relevant: a doctor asks its own, and reports green while a step
fails (023-toolchain P1).

**5. A template path, if this repository is not devman.**
`changelog.yaml`'s `TEMPLATEER_TEMPLATE_PATH` defaults to
`groups/changelog/templates`, relative to the repository — which resolves for
devman, the repository that owns these templates and adopts its own groups, and
for nobody else.

A group ships workflow **text** and no assets: `modules/devenv.nix` reads each
workflow with `builtins.readFile` and projects the text, and there is no asset
path beside it. Distributing a group's template files to an adopter is 022's
open question 2 and it is still open. Until it closes, another adopter copies
`templates/changelog/` into its own tree and passes the path:

```bash
devman run changelog TEMPLATEER_TEMPLATE_PATH=.devman/changelog/templates
```

The gate refuses loudly, naming the parameter, rather than letting `templateer`
fail later against an empty catalog.

**6. A reachable `$GPU_LLM_BASE_URL`** — start any OpenAI-compatible server
before running `changelog` (directly, or through the chain from
`changelog-entries`). devman does not start or own that server, only calls it,
and the step fails plainly if nothing answers.

`GPU_LLM_MODEL` is the endpoint's own model id, the same name `/v1/models`
lists and the same one `.devman/workflows/gitman-commit-message.yaml` sends.
`templateer` is a pydantic-ai caller and names a model `<provider>:<id>`, so
the workflow adds the provider itself. Measured: `--model gemma` returns
`failure_reason: config_error`, `Unknown model: gemma`, and no artifact.

## Why this needed two workflows, not one

**`.devman/**` writes need no review; a `CHANGELOG.md` edit does.** Splitting on
that line, rather than writing one workflow that does both, buys independent
re-runnability: `changelog-entries` can be re-run by hand to backfill history,
and `changelog` can be re-run alone after an LLM hiccup without repeating the
first stage's work.

**It also could not have been one workflow chained inside a synchronous hook
window, and that took a measurement to find out** (DESIGN.md §1). Gitman's own
`[land]` hooks are a change detector: any file a hook's command writes — even
one inside its configured `allowed_paths` — blocks the land or leaves it
flagged as an anomaly. So neither stage's own write may run as the hook's
command. What does work is `devman run`, because it never touches the working
tree itself — it resolves the project and runs one `dagu enqueue`, which
returns as soon as the run is admitted to its queue. The write happens later,
inside the enqueued run, outside the hook's own before/after snapshot. Once the
trigger only enqueues, there is no synchronous window left to chain the second
stage inside — so it is a second workflow, enqueued from the first's last step
via `action: dag.enqueue`.

## Why not the post-commit hook `groups/base/README.md` already documents

That group's documented pattern — `git-hooks.hooks.<name> = { stages =
["post-commit"]; }`, via devenv's `git-hooks` module — is proven for a plain
`git commit`. **It was measured, not assumed, not to reach a gitman
repository**: a colocated jj commit never invokes `.git/hooks/post-commit`,
because jj writes the object store and refs through its own backend and never
through the `git commit` command hooks are attached to. A scratch repo proved
it: `jj git init --colocate`, a hook that writes a marker, `jj describe` + `jj
new` — a real commit appears in `git log` and the marker is never written.

## Console scripts, never a library import — and never the `jj` CLI

**Neither the `jj` binary nor a library import is available to a step. Only a
console script is.**

The `jj` CLI was ruled out first. The first draft of both workflows shelled out
to `jj log`/`jj show`. Reading gitman's own `pyproject.toml` before shipping it
found the assumption wrong: *"pyjutsu >= 0.20 binds the complete in-process
surface ... there is no `jj` CLI dependency."* `gitman doctor` itself checks for
`pyjutsu` and `git` (for jj's "escape hatch"), never `jj`. A repository can run
gitman with no `jj` binary on PATH at all — measured in this repository's own
devenv, where `command -v jj` finds nothing.

The library import was ruled out second, and it cost more to find. Both
workflows then imported `pyjutsu` inside `devenv shell -- python3`. That fails
in every adopter's devenv: the shared toolchain venv lends a console script
through **PATH**, and PATH cannot lend a library through `sys.path`. The
expensive half was not the failure — it was that `repoman doctor` and
`gitman doctor` both reported `pyjutsu` green while the step failed, because
each asks its own interpreter and neither asks the step's (023-toolchain P1).

So `changelog.yaml` calls `gitman log --revset <a>..<b> --json`, a verb that
exists for exactly this consumer: one object per change, oldest first, with
`change_id` and `description`. It reads the range **once** and writes both the
pending list and a change-id-to-subject map, so the write step resolves nothing
a second time and cannot disagree with the gate about what the range held. The
`python3` that remains uses the standard library only — `json`, `pathlib`,
`tomllib`, `sys`. That is the line between what a step may assume and what it
may not.

The summary is rendered by `templateer`, also a console script, also called by
name. It previously reached a sibling checkout through an interpreter
search-path variable plus `uv run --project`, which made the step depend on a
directory layout that exists on one machine (023-toolchain P2).

## The entries workflow is blocked

**`changelog-entries.yaml` still imports `pyjutsu`, so it cannot run.** The
post-land hook fires it, it fails, and the chain never reaches
`changelog.yaml`. Run `changelog` by hand against entry files that already
exist; do not expect the chain.

It is not fixed the same way its sibling was, because the console script it
needs does not exist. `changelog.yaml` needed a commit range, and
`gitman log --json` supplies one. `changelog-entries.yaml` needs **diffs** —
`.diff` and `.diff_stat` per change — and gitman has no diff verb. Closing this
takes either a new `gitman diff --json`, or a decision to depend on the `jj`
binary that the first paragraph above rules out.

Its structured-diff rendering is worth keeping whichever way that goes: pyjutsu
emits hunks with no surrounding context by design, so the entry file's format is
this group's own rather than a copy of `git diff`'s — a deliberate trade, since
the file is read by a person or an LLM and never replayed as a patch.

## §12 rule 4, and where each workflow's vacuum is caught

Both gates fail; neither skips. `format.yaml`'s step-level `preconditions:`
records `Succeeded` with a step skipped, which is right for a self-stopping
reactive loop and wrong here — a refusal that looked like success is the
failure §12 rule 4 exists to prevent, and `release.yaml`'s gate already made
this call the same way.

- `changelog-entries` refuses when no commit has landed since its own receipt
  (`.devman/.runs/.changelog-entries.last`, a jj **change id** — not a git
  commit hash, and not a tree hash. Not a tree hash because 019 measured that
  one cannot tell "ran, changed nothing" from "ran, changed something". Not a
  git hash because `land`'s own rebase changes a commit's hash every time a
  lane folds in, while its change id never changes — the receipt would
  otherwise have to account for its own key rewriting under it).
- `changelog` refuses when no entry file exists for any commit newer than
  `CHANGELOG.md`'s own `covers up to` marker (also a change id). Filtering by
  "an entry file exists" rather than "the commit is new" is deliberate: it is
  also the check that catches `changelog-entries` having failed or been
  skipped upstream of the chain, rather than papering over the gap.

## The lane

Fixed name, `changelog`, checked before `gitman start` rather than left to fail
blind on it: gitman's `start` is not idempotent (`ensure_unique` refuses a name
collision — gitman `.scratch/projects/39-lane-lifecycle-facts/ISSUE.md`), so a
re-run before the prior lane lands gets an explained refusal — "land it before
running again" — instead of a raw collision error. `changelog.yaml` never runs
`gitman land` itself; a person reviews the lane's diff (the LLM's prose beside
a verbatim commit list) and lands it.

## Running it

```bash
devman run changelog-entries   # normally fired by gitman's post-land hook
devman run changelog           # normally chained from the run above
```

`changelog-entries` fails today, for the reason above. `changelog` runs against
whatever entry files `.devman/changelog/entries/` already holds.
