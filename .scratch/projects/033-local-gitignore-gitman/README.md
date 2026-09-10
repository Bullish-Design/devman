# Local Git Exclude Files and gitman

**Date:** 2026-09-10

## Result

Each reconciled repository now has a canonical per-project
`.local.gitignore` at:

```text
<overlay>/projects/<project>/.local.gitignore
```

The repository's `.git/info/exclude` is a symlink to that file. The Python
reconciler owns both the link view and the exclusion projection. It supports a
normal `.git` directory and a linked Git worktree whose `.git` is a file. It
does not write `.gitignore`.

## Before and after

Before this change, reconciliation appended the required patterns directly to
the repository's `.git/info/exclude`. There was no central per-project exclude
file, so the same machine-local rules could not be managed as one central
view.

The reconciler now creates or migrates the central file, promotes existing
exclude contents before replacing the repository file with a symlink, and
records the central file's hash in the existing link state. A changed central
file and a changed local exclude file are refused as a two-sided edit. Missing
files and incorrect links are repaired deterministically. A jj-only gitman
workspace has no `.git` marker, so it receives no Git exclusion projection.

## gitman compatibility

The primary colocated checkout works with gitman: a temporary integration
fixture reconciled the link, then `gitman status` exited 0. A linked gitman
workspace created with `gitman start --workspace` also returned status 0; it is
jj-only and therefore does not need a second `.git/info/exclude` link.

devman does not invoke gitman or commit the central file. If the central
configuration repository tracks these files, their first creation or later
edits appear as central-repository work and must be committed through a
gitman lane. The live central configuration's ignore policy does not currently
ignore `projects/*/.local.gitignore`, so whether these canonical files should
be tracked or treated as generated machine state remains an explicit policy
decision. This implementation does not mutate the live central configuration.

## Verification and limits

- Link, migration, and two-sided-edit refusal tests cover the new behavior.
- The full Python unit suite and Ruff checks pass.
- Live configuration and representative repositories were inspected
  read-only. No registry projection, system rebuild, `doctor --prune`, or
  mutation of `~/.config/devman` was performed.
- Stage 3 state separation remains deferred.
- Stage 4 direct workflow links remain deferred; workflow files are still
  generated registry projections.
