# `python-format` — a tombstone, not a group

**This directory ships nothing on purpose.** The group was renamed to `format`
at stage 7 (`PROPOSAL.md` §6): under §3's rule a group exists because of what
taking it costs — a trigger and a write to your own source — and not because of
a language.

## Why an empty directory is still here

`modules/devenv.nix` throws when a repository names a group that does not
exist, and the throw is an **evaluation** failure: a repository that re-pins to
a stage-7 rev while still listing `python-format` could not enter its shell at
all. A directory that ships no `workflows/` evaluates and projects nothing
(`modules/devenv.nix:63`), so a stale pin keeps working and the repository
renames its group when it is next edited rather than when the plane forces it.

**It holds a `README.md` because git cannot carry an empty directory**, and a
tombstone that vanishes on `git+https` is not a tombstone (`STAGE_7_LOG.md`,
S-3).

## It must never hold a `triggers.toml`, and that is measured

A `triggers.toml` here would keep firing `format` in every stale repository —
a workflow the repository no longer projects. Measured at stage 7: the registry
entry carries the mapping, `devman doctor` prints it without objecting, and
every matching save forks a `devman run` that refuses with exit 1. Waste, plus
a complaint in a journal nobody reads.

## When it goes

One full rollout after wave 4. Rename your group and delete this line:

```nix
groups = [ "base" "format" ];   # was [ "base" "python-format" ]
```
