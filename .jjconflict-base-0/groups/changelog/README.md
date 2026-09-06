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
| `workflows/changelog-entries.yaml` | tier free — writes one detailed diff file per landed commit under `.devman/changelog/entries/` |
| `workflows/changelog.yaml` | tier lane — summarises the un-summarised entries into `CHANGELOG.md`, via a local LLM, on a fixed-name gitman lane |
| `writes.toml` | both workflows' declared tier and paths |

No `triggers.toml`. Neither workflow is reactive to a file save — `changelog-
entries` fires on a `gitman land`, which is a different event the watcher does
not see (§1 below).

## What taking it costs

No task name to define — both workflows are plain shell over `git` and
`gitman`, no devenv task needed, unlike `release`'s `release:build`. It costs
three things instead, each a one-time setup:

**1. A line in this repository's own `gitman.toml`:**

```toml
[land.post_hook]
command = ["devman", "run", "changelog-entries"]
```

**2. A bootstrapped `CHANGELOG.md`, once, before the first run:**

```bash
printf '<!-- devman-changelog: covers up to %s -->\n' "$(git rev-parse HEAD)" > CHANGELOG.md
git add CHANGELOG.md && git commit -m "chore: bootstrap the changelog"
```

`changelog.yaml`'s gate refuses loudly, naming the file, if this marker is
absent — no special-cased first run, no silent default.

**3. A reachable `$GPU_LLM_BASE_URL`**, exactly as `.devman/workflows/
gitman-commit-message.yaml` already requires — start any OpenAI-compatible
server before running `changelog` (directly, or through the chain from
`changelog-entries`). devman does not start or own that server, only calls it,
and the step fails plainly if nothing answers.

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

## §12 rule 4, and where each workflow's vacuum is caught

Both gates fail; neither skips. `format.yaml`'s step-level `preconditions:`
records `Succeeded` with a step skipped, which is right for a self-stopping
reactive loop and wrong here — a refusal that looked like success is the
failure §12 rule 4 exists to prevent, and `release.yaml`'s gate already made
this call the same way.

- `changelog-entries` refuses when no commit has landed since its own receipt
  (`.devman/.runs/.changelog-entries.last`, a commit SHA — not a tree hash,
  because 019 measured that a tree hash cannot tell "ran, changed nothing" from
  "ran, changed something").
- `changelog` refuses when no entry file exists for any commit newer than
  `CHANGELOG.md`'s own `covers up to` marker. Filtering by "an entry file
  exists" rather than "the commit is new" is deliberate: it is also the check
  that catches `changelog-entries` having failed or been skipped upstream of
  the chain, rather than papering over the gap.

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
