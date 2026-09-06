# 021 — A changelog workflow, and the plane's first tier-B writer

Design, revision 2. Read before writing YAML. Sources: `015/RESULT.md` (the
tier amendment), `019/KICKOFF.md` and `MEASUREMENT.md` (the receipt),
`020/KICKOFF.md` (why nothing here is scheduled, and Option E's "fire it from a
trigger, a hook, or by hand"), `AGENTS.md`, `.agents/skills/devman-workflow/
SKILL.md`, `groups/base/README.md` (the documented commit-hook shape, and its
own honest "0 of 54 repositories use it"), `groups/release/README.md` (the one
existing gate-that-fails), `.devman/workflows/gitman-commit-message.yaml` (the
one existing local-LLM workflow), and gitman's `src/gitman/hooks.py` /
`core.py:do_land` and `.scratch/projects/39-lane-lifecycle-facts/ISSUE.md`
(`start` is not idempotent).

**Revision 1 designed one workflow, one lane, no LLM, and asked two open
questions.** Both are answered now, and the second answer forced a real design
change, not a detail: **the two stages are two separate devman workflows, one
auto-triggered and one chained from it**, not one workflow with a step added.

**Baseline, unchanged from revision 1:** no repository in the fleet has a
`CHANGELOG.md` today; no group or workflow generates one; `writes.toml`'s
grammar (`TIERS = ("free", "lane", "insitu")`) already has everything both
stages need — no change to `src/devman/`.

---

## 1. What was measured before this revision was written

### 1.1 Gitman's own land hooks cannot inject a file into the land

Read `src/gitman/hooks.py` and `core.py:do_land`/`_do_land_locked` in full.
**Any file a pre- or post-land hook's command changes — even inside its
configured `allowed_paths` — blocks or flags the land.** `describe_changes`
takes a filesystem snapshot before and after the hook command runs; if
anything differs, `_land_hook_blocked` refuses the land (pre-land) or the
land succeeds but the CLI reports exit 1 with "post-land hook changed files:
…, land succeeded; no rollback was attempted" (post-land). **Gitman's hook is
a change detector, not an injection point.** A hook whose command writes a
file is treated as an anomaly a person must look at, on purpose — this is the
same "loud refusal over silent default" instinct §12 rule 4 already states,
just enforced one repository over. **Neither stage's file-writing step may run
as the hook's own command.**

### 1.2 A colocated jj commit does not fire git's hooks — measured, not assumed

`groups/base/README.md` documents a working commit-triggered pattern:
`git-hooks.hooks.<name> = { stages = ["post-commit"]; entry = "devman run
<workflow>"; }`, via devenv's `git-hooks` module, which installs into
`.git/hooks/`. That pattern is proven for a repository committing with plain
`git`. **It was not proven for a gitman repository, whose commits are made by
jj**, so before assuming it carries over, it was tested rather than guessed:

```
$ jj git init --colocate .
$ install .git/hooks/post-commit  (writes a marker file, chmod +x)
$ jj describe -m "first change"
$ jj bookmark create -r @ main
$ jj new
$ git log --oneline
e57a74f first change            ← a real git commit exists
$ cat hook-fired.log
No such file or directory       ← the hook never ran
```

**A real git commit lands in the colocated `.git`, and `.git/hooks/post-commit`
never fires.** jj writes the object store and refs through its own backend,
never through `git commit`, and git's hook scripts are invoked by that command
and no other path. **`groups/base`'s documented trigger does not reach a
gitman repository, and this is worth a note in that group's own README even
though this project does not own that file.** Neither stage's trigger may
depend on a `git-hooks` module post-commit/post-merge hook.

### 1.3 The mechanism that does work, and it is the one `run.py` already draws

`src/devman/run.py`'s own module docstring states the shape before this project
existed:

```
filesystem change → watchexec ─┐
commit / push     → hook      ─┼→ devman run → dagu enqueue → Dagu → devenv
a developer at a prompt       ─┘
```

**`devman run` never writes to the repository. It resolves the project, then
runs one `subprocess.run` of `dagu enqueue`** (`run.py:382`) — a network call to
the Dagu daemon that returns as soon as the run is admitted to its queue, not
when the run finishes. **A hook whose command is `devman run <workflow>`
therefore cannot trip §1.1's change detector**, because the snapshot taken
around the hook's synchronous execution window sees no filesystem change at
all — the write happens later, inside the enqueued run itself, on the daemon's
own time, entirely outside the hook's before/after snapshot.

**Gitman already has the config surface this needs, and it needs nothing new
from devman or from git:** `gitman.toml`'s `[land] post_hook`
(`config.py:LandHookConfig` — `command`, `timeout_seconds`, `allowed_paths`).
A repository that takes the `changelog` group configures:

```toml
# gitman.toml
[land.post_hook]
command = ["devman", "run", "changelog-entries"]
```

**If the Dagu daemon is down, this fails loudly rather than silently.**
`do_land` catches the hook's own failure and reports `post-land hook failed:
…` with exit 1, and the land itself is not rolled back — a person sees the
land succeeded and the changelog step did not, and can re-run
`devman run changelog-entries` by hand. This is a refusal a person acts on,
not a run that reports success while doing nothing (§12 rule 4).

## 2. Two workflows, not one — the race the combined design would have hit

**Because the trigger enqueues rather than runs, chaining both stages inside
one workflow file across `land`'s synchronous hook window is not available —
there is no synchronous window to chain inside.** The natural seam is
therefore the one the two stages already have on their own terms: one writes
free-tier files under `.devman/`, the other edits tracked source on a lane.
Splitting them the same way `writes.toml` already splits tiers costs nothing
extra and buys independent re-runnability — the entries writer can be re-run to
backfill history, and the summariser can be re-run alone if the local model
was down, without repeating the other stage's work.

```
groups/changelog/
├── README.md
├── writes.toml
└── workflows/
    ├── changelog-entries.yaml   # tier free — auto-triggered by gitman's post-land hook
    └── changelog.yaml           # tier lane  — chained from changelog-entries, gpu queue
```

### 2.1 `changelog-entries` — one detailed file per landed commit

**Tier free.** `.devman/**` is agent surface (`FREE_PREFIXES`), so this needs
no lane and no review — the same posture `maintain`'s report pruning already
has. Triggered automatically (§1.3); also runnable by hand for a backfill.

**The frontier is a file that already exists for exactly this reason in every
other receipt this plane keeps: a marker under `.devman/.runs/`.**
`.devman/.runs/.changelog-entries.last` holds the newest commit SHA already
given a detail file. (Not inside `CHANGELOG.md`, as revision 1 proposed — that
marker belongs to the *other* stage now; see §2.2.)

```bash
# gate — fails loudly on vacuum, exactly as release.yaml's gate does
last=$(cat .devman/.runs/.changelog-entries.last 2>/dev/null || git rev-list --max-parents=0 HEAD)
count=$(git rev-list --count "$last..HEAD")
if [ "$count" -eq 0 ]; then
  echo "no commits since $last — nothing to record" >&2
  exit 1
fi
echo "$count commits since $last"
```

```bash
# generate — one file per commit, oldest first
last=$(cat .devman/.runs/.changelog-entries.last 2>/dev/null || git rev-list --max-parents=0 HEAD)
mkdir -p .devman/changelog/entries
for sha in $(git rev-list --reverse "$last..HEAD"); do
  git show --stat --patch "$sha" > ".devman/changelog/entries/$sha.md"
done
git rev-parse HEAD > .devman/.runs/.changelog-entries.last
```

No cap on file size: this is a durable, agent-surface audit record, not an
LLM input (that bound belongs to the step that reads it, §2.2). No parsing of
"one land = one batch" is needed here — the marker already gives an exact
commit range regardless of how many commits one `land` produced or how many
times this ran since the last summary.

**`writes.toml`:**

```toml
[changelog-entries]
tier  = "free"
paths = [".devman/changelog/entries/**", ".devman/.runs/.changelog-entries.last"]
```

Both paths are under `.devman/`, inside `free_path`'s prefix set, so `doctor`'s
`check_writes` accepts the declaration without needing a lane at all.

### 2.2 `changelog` — the per-PR summary, chained and lane-written

**Tier lane**, and the one place an LLM appears. Chained from
`changelog-entries`'s last step via `action: dag.enqueue` — same project, so
the child DAG name is `${the same project}.changelog`, built the way
`release.yaml`'s gate already builds a same-project DAG name (`${me%.*}` from
`${context.dag.name}`, §"the gate names the DAG exactly" in that README).
**`dag.enqueue` hiding the child's failure (rule 9) is acceptable here**: the
parent (`changelog-entries`) already succeeded on its own terms before
enqueuing, and the child's own outcome is independently recorded in
`metadata.jsonl` and found by `doctor`, the same way a failed `release` is
found — nothing downstream needs the parent to know the child's verdict.

**Frontier: back to `CHANGELOG.md` itself**, as revision 1 designed, because
this is the artifact whose "already covered" state must never desync from what
the file actually contains:

```markdown
<!-- devman-changelog: covers up to 3f8e21a -->
```

**Gate — fails loudly on vacuum**, reading the entries directory rather than
`git log` directly, since an entry file is this stage's real unit of input:

```bash
last=$(git show HEAD:CHANGELOG.md 2>/dev/null | sed -n 's/.*covers up to \([0-9a-f]*\).*/\1/p' | head -1)
if [ -z "$last" ]; then
  echo "CHANGELOG.md has no 'covers up to' marker — bootstrap it by hand first" >&2
  exit 1
fi
new=$(git rev-list --reverse "$last..HEAD" | while read -r sha; do
  [ -f ".devman/changelog/entries/$sha.md" ] && echo "$sha"
done)
if [ -z "$new" ]; then
  echo "no un-summarised entries since $last — refusing rather than opening an empty lane" >&2
  exit 1
fi
echo "$new" > .devman/.runs/.changelog-pending
```

Filtering by "an entry file exists for this commit" rather than "this commit
is new" is deliberate: it is the check that would catch `changelog-entries`
having been skipped or having failed silently upstream of the chain — a commit
with no detail file behind it is not summarised, and the gap is visible in the
generated section (§2.2's write step lists it) rather than papered over.

**Lane collision, exactly as revision 1 designed** — a fixed lane name, checked
before `gitman start` rather than let `ensure_unique` fail blind (gitman #39:
`start` is not idempotent):

```bash
if gitman status --json 2>/dev/null | grep -q '"name":"changelog"'; then
  echo "a changelog lane already awaits review — land it before running again" >&2
  exit 1
fi
gitman start changelog
```

**The LLM step reuses `gitman-commit-message.yaml`'s shape exactly, and that is
the whole point of choosing it: no new queue name, no new secret.** That
workflow already proves the pattern — `gpu` queue (`max_concurrency: 1`,
because the constraint is one model in one GPU's VRAM, not "must not overlap"),
no `secrets:` block because the endpoint is a local, unauthenticated
OpenAI-compatible server named by `$GPU_LLM_BASE_URL`, and `scripts/
gpu_complete.py`'s bound input (`head -c`) against an unbounded bill. 020's two
open questions for a *scheduled, quota-metered, cloud* LLM workload — a sixth
queue name, and exercising `§9.4` secrets for the first time — do not apply,
because this is neither scheduled (§3) nor a metered external API; it is the
same local call `gitman-commit-message.yaml` already makes, triggered rather
than scheduled, respecting the `gpu` queue exactly as that workflow's own
`dagu enqueue` already does.

```bash
{
  printf '%s\n\n' "Summarise this batch of commits for a changelog entry read by \
someone who does not want diff detail. Group related commits into one or two \
sentences each. No preamble, no markdown fences, output only the summary body."
  while read -r sha; do
    printf '\n--- %s ---\n' "$sha"
    cat ".devman/changelog/entries/$sha.md"
  done < .devman/.runs/.changelog-pending
} | head -c 60000 | uv run --script scripts/gpu_complete.py > .devman/.runs/.changelog-summary.md
```

**Rule-4 exposure, stated rather than left implicit.** An LLM's fluent, empty
answer is the sharper failure 020 already named. It is bounded two ways here,
not zero: the step cannot fire on an empty batch (§2.2's gate already refused
that), and the write step below still lists every commit verbatim beside the
prose, so a hollow summary is caught by a person reading the section next to
the commit list it claims to describe, not trusted on its own.

**Write step — the section, the marker, and the list side by side:**

```bash
newest=$(tail -1 .devman/.runs/.changelog-pending)
{
  echo "<!-- devman-changelog: covers up to $newest -->"
  echo
  echo "## $(date +%Y-%m-%d)"
  echo
  cat .devman/.runs/.changelog-summary.md
  echo
  while read -r sha; do
    echo "- $(git log -1 --format='%s' "$sha") ($sha)"
  done < .devman/.runs/.changelog-pending
  echo
  tail -n +2 CHANGELOG.md
} > CHANGELOG.md.new
mv CHANGELOG.md.new CHANGELOG.md
gitman save -m "docs: update the changelog"
```

**`writes.toml`:**

```toml
[changelog]
tier  = "lane"
paths = ["CHANGELOG.md"]
```

**Queue: `gpu`**, for the whole workflow — the same call `groups/README.md`'s
queue table makes for `gitman-commit-message.yaml`: name the scarcest real
constraint, and the GPU is scarcer here than the lane operations around it.

## 3. Still not scheduled

Unchanged from revision 1, strengthened by §1: there is now an actual event —
`land` — driving this, through a queue-respecting `dagu enqueue`, exactly the
event-driven shape 020's Option E asked for and did not itself find a workload
for. Nothing here carries a `schedule:` key. A repository that never lands
never generates an entry or a summary, and that is correct, not a gap.

## 4. Group, scope, and bootstrap — unchanged from revision 1

Opt-in group `changelog`. §16's promotion rule: `shellij` (51 consumers),
`gitman`, `devman` all ship something another repository pins, satisfying "a
second repository wants the same file" three times over. A repository takes
the group, defines nothing (unlike `release`, no task name to honour — both
steps are plain shell over `git`/`gitman`, no devenv task needed), and adds two
things of its own:

```toml
# gitman.toml
[land.post_hook]
command = ["devman", "run", "changelog-entries"]
```

```bash
# once, before the first run
printf '<!-- devman-changelog: covers up to %s -->\n' "$(git rev-parse HEAD)" > CHANGELOG.md
git add CHANGELOG.md && git commit -m "chore: bootstrap the changelog"
```

...and a reachable `$GPU_LLM_BASE_URL`, exactly as `gitman-commit-message.yaml`
already requires — document this in the group's `README.md` as a real
dependency, not a hidden one, the same way `.devman/workflows/README.md` states
it for that workflow.

## 5. What ships

```
groups/changelog/README.md
groups/changelog/workflows/changelog-entries.yaml
groups/changelog/workflows/changelog.yaml
groups/changelog/writes.toml
groups/README.md                — add the row to the group index table
groups/base/README.md           — one note: its documented post-commit hook
                                   does not fire in a gitman/jj repository (§1.2)
```

No change to `src/devman/`. No sixth queue name. No new secret.

## 6. Verify before save

```bash
devenv tasks run -v base:check
devenv tasks run -v base:test
devman doctor      # from source — the installed build lags this tree
nix build .#checks.<system>.groups-validate
```

Confirm the chain end to end once implemented:

```bash
devman run changelog-entries          # writes .devman/changelog/entries/*.md
devman run changelog                  # or wait for the enqueued chain to reach it
cat .devman/.runs/reports/changelog-<run id>.md
```
