# format — the group that makes a repository react

`devman.groups = [ "base" "format" ]`

This is the only group that does something when nobody asked. Taking it means
that saving a `.py` file in this repository runs `format`, without a person
typing anything.

Renamed from `python-format` at stage 7. The group exists because of the trigger
and the write, not because of a language: naming it after the language says the
language is the reason, which is what the one-step rule argues against
(`PROPOSAL.md` §6). `groups/python-format/` is a tombstone — see its README.

## What it is

| File | What it is |
|---|---|
| `triggers.toml` | `"**/*.py" = "format"` — the mapping the watcher reads (§8) |
| `workflows/format.yaml` | one step, `format:fmt`, guarded by a content hash |

## The task name this group calls

| Task | What the repository puts in it |
|---|---|
| `format:fmt` | the formatter, writing in place |

```nix
tasks."format:fmt".exec = "ruff format .";
```

The group names a task and never a tool, so `black`, `ruff format`, `blue` or a
script all fit without the file changing (§7.1).

## Why reactivity is a group of its own

The rule for when a workflow deserves a group is:

> **A group exists when taking it costs the repository something it cannot
> decline any other way: a task name it must define, or a write to its own files
> it did not ask for.**

§7.4 says there is no per-workflow Nix option, because an inherited workflow you
never trigger costs nothing. **A triggered workflow costs plenty** — it rewrites
your files while you are editing them — so the argument does not carry over.

**What fires it is not the test; what it touches is.** `maintain` fires itself on
a schedule and still rides inside `base`, because everything it writes is under
`.devman/.runs/`, which the plane created and git and the watcher both ignore.
`format` rewrites the developer's source, which is a cost only a group can
decline.

So it is its own group, holding one workflow that exists to be triggered. Taking
it is the opt-in; not taking it is the opt-out. That is free here, because there
is nothing else in the group to lose.

## The loop, and what stops it

You save `foo.py`. The watcher fires `format`. `format` rewrites `foo.py`. The
watcher sees that write.

Two different layers stop that, and both are somebody else's mechanism:

1. **The watcher ignores `.devman/.runs/`**, so a run's own logs and this group's
   hash file are not events. Without that ignore, one save produced 107
   dispatches and 60 runs (`STAGE_3_LOG.md`, S8).
2. **The step's `preconditions:` compare a content hash** of every `.py` file
   against the hash stored after the last format. The formatter's own write
   therefore does no work the second time, and the sequence stops.

**A hash, not a timer.** Edit `foo.py` a second after the formatter wrote it and
the hash differs, so the work runs. A suppression window would swallow that edit
and would still pass a naive "one save, one run" test (§8, E1).

**Step-level, not DAG-level.** A DAG-level precondition that is not met records
the run as `Aborted`, which is the status a cancelled run also gets. A step-level
one gives `Succeeded` with the step marked skipped. A plane built on the
DAG-level form would fill its history with runs that look like failures (E1).

**`type: build` cannot be used here**, and that is measured. It skips a step whose
declared inputs and outputs are unchanged, but it cannot declare one path as both
input and output — and a formatter is exactly that. Dagu rejects it at run time
and `dagu validate` does not (E1).

**What "the sequence stops" costs, measured.** The skip is Dagu's, and Dagu skips
*after* enqueueing rather than before, so the loop terminates with one run that
formats and one run that skips. See `STAGE_3_LOG.md` S6.

## The widening rule, stated in advance

> **Adding a glob to `triggers.toml` requires widening the hash in
> `workflows/format.yaml` in the same edit.**

A glob whose files the hash does not cover fires a run whose precondition is
never true, so the new language's saves produce a run that skips and never
formats. That failure is silent: the run reports `Succeeded` with a skipped step,
which is exactly the status a correct loop-break produces. **Nothing in the plane
checks it.** It was reproduced on purpose at stage 7 (S-4).

**The glob stays `**/*.py` until a repository asks for more.** §16's promotion
rule applies to a glob as much as to a file. No Nix or Lua repository has asked
for format-on-save, and `devman` is the only taker of this group in the whole
inventory.

## The narrowing rule, and it is yours rather than this group's

> **A repository that excludes a path from its formatter excludes it from this
> trigger, in its own `.devman/triggers.toml`.**

```toml
# <your repo>/.devman/triggers.toml
ignore = [".scratch/**"]
```

**This group cannot know which files your formatter covers, and it must not
guess.** `**/*.py` is the honest glob for a group: it fires on every Python
file, and what happens next is your `format:fmt` task's business. But if your
Ruff configuration excludes a directory, a save there fires this workflow, the
precondition hash covers the file so the step does **not** skip, `devenv tasks
run format:fmt` runs in full, and nothing is formatted.

Measured in `devman` itself before the rule existed: `pyproject.toml` excludes
`.scratch`, and 16 of 252 `format` fires were saves under it — every one of them
a queue slot, a log directory and a `metadata.jsonl` line for work that could
not change a file (009 P3-3).

**The narrowing is a repository fact, so it lives in the repository.** Taking
this group still costs one task name and nothing else; §7.4 stays true. Before
project 009 stage 9 a repository could not state this at all, which is why the
mismatch was documented rather than fixed.

## What it does not do

It does not commit, and it does not tell you it ran. Read
`.devman/.runs/metadata.jsonl`, or run `devman doctor`, which reports what the
watcher last fired.
