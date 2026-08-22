# python-format — the group that makes a repository react

`devman.groups = [ "python" "python-format" ]`

This is the first group that does something when nobody asked. Taking it means
that saving a `.py` file in this repository runs `format`, without a person
typing anything.

## What it is

| File | What it is |
|---|---|
| `triggers.toml` | `"**/*.py" = "format"` — the mapping the watcher reads (§8) |
| `workflows/format.yaml` | one step, `python-format:fmt`, guarded by a content hash |

## The task name this group calls

| Task | What the repository puts in it |
|---|---|
| `python-format:fmt` | the formatter, writing in place |

```nix
tasks."python-format:fmt".exec = "uv run ruff format .";
```

The group names a task and never a tool, so `black`, `ruff format`, `blue` or a
script all fit without the file changing (§7.1).

## Why reactivity is a group of its own

§7.4 says there is no per-workflow Nix option, because an inherited workflow you
never trigger costs nothing. **A triggered workflow costs plenty** — it rewrites
your files while you are editing them — so the argument does not carry over, and
reactivity cannot ride along inside `python`.

So it is its own group, holding one workflow that exists to be triggered. Taking
it is the opt-in and not taking it is the opt-out, which is §7.4's own answer:
"to be rid of one, do not take its group". That is free here, because there is
nothing else in the group to lose.

## The loop, and what stops it

You save `foo.py`. The watcher fires `format`. `format` rewrites `foo.py`. The
watcher sees that write.

Two different layers stop that, and both are somebody else's mechanism:

1. **The watcher ignores `.devman/.runs/`**, so a run's own logs and this
   group's hash file are not events. Without that, every run in a repository
   re-fires every watcher in it, whatever the workflow declares.
2. **The step's `preconditions:` compare a content hash** of every `.py` file
   against the hash stored after the last format. The formatter's own write
   therefore does no work the second time, and the sequence stops.

**A hash, not a timer.** Edit `foo.py` a second after the formatter wrote it and
the hash differs, so the work runs. A suppression window would swallow that edit
and would still pass a naive "one save, one run" test (§8, E1).

**What "the sequence stops" costs, measured.** The skip is Dagu's, and Dagu
skips *after* enqueueing rather than before, so the loop terminates with one run
that formats and one run that skips. See `STAGE_3_LOG.md` S6 for the counts and
for what that does to criterion 13's wording.

## What it does not do

It does not commit, and it does not tell you it ran. Read
`.devman/.runs/metadata.jsonl`, or run `devman doctor`, which reports what the
watcher last fired.
