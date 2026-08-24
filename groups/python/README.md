# `python` — a tombstone, not a group

**This directory ships nothing on purpose.** The group was deleted at stage 7.

Its whole content was two workflows that ran a linter and a type checker in
order. **That order is a task graph, and devenv holds task graphs.** Written as
a graph it is one line in the repository, where the developer can also run it by
hand:

```nix
tasks."base:check".after = [ "python:lint" "python:typecheck" ];
tasks."base:test".after  = [ "python:test" ];
```

Written as a workflow it was a second copy of the same fact, in a file the plane
promises never to parse (`PROPOSAL.md` §1.1).

**A language is not a reason for a group.** A language differs in what a task
*is*. Once a workflow is one step calling one task, a language group's whole
content is a namespace prefix — the file is identical in every group — and
§16's promotion rule ("a group begins when a second repository wants the same
file") cannot be satisfied by a file that is the same file.

## Why the directory is still here

`modules/devenv.nix` throws on an unknown group, and the throw is an
**evaluation** failure: a repository that re-pins while still listing `python`
could not enter its shell. A directory with no `workflows/` evaluates and
projects nothing, so a stale pin keeps working. It holds this `README.md`
because git cannot carry an empty directory (`STAGE_7_LOG.md`, S-3).

## When it goes

One full rollout after wave 4. Drop the word:

```nix
groups = [ "base" ];   # was [ "base" "python" ]
```
