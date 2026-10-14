# Template migration issues

Date: 2026-10-13.

## CopyRoom shell reports unrelated Pi configuration warnings

Entering CopyRoom's devenv emits a MyPi `MYPI_AGENT_ROOT must stay within
project root` traceback and SecretSpec warnings. CopyRoom commands continue.
These warnings did not block template work.

## Template renders and goldens are current

The first candidate runs differed from the old goldens because the templates
removed RepoMan and Devman pins and added the Nix project identity manifest. I
reviewed and refreshed the goldens. `copyroom template-test py` passed the Python
basic and probe scenarios. After the Devman group correction,
`copyroom template-test nix` passed the Nix base basic, custom, home, none, and
probe scenarios. The Nix module goldens matched. Both template repos passed
their schema-sync and render checks.

## Python isolated checks need the central overlay and host Testee CLI

`copyroom update-test py basic` fails at `devenv test` because the disposable
project has no `devenv.local.nix` importing the central RepoMan module. A
temporary import of `/run/current-system/sw/share/repoman/module/devenv.nix`
allowed `devenv shell -- true` to pass. With that import,
`devenv test` then failed because `.devenv/test-state/venv/bin/testee` was
missing. The project pins Testee's Nix module for its check definitions; the
Testee CLI comes from the host profile.

The required `copyroom release-check py` gate also fails at `devenv test` in
its isolated rendered scenario with `The option repoman does not exist`. It
exits before Testee checks run. The generated test project does not receive the
central RepoMan overlay.

## Nix isolated check needs the central overlay

`copyroom update-test nix basic` fails at `devenv test` when the disposable
project has no central RepoMan module. Adding a temporary
`devenv.local.nix` that imports
`/run/current-system/sw/share/repoman/module/devenv.nix` allowed `devenv test`
to pass.

## Candidate checkout created nested VCS metadata

`copyroom template-checkout nix` created `.git/` and `.jj/` under
`template-nix/source/base`. The outer workspace then reported the source files
as deleted even though they remained on disk. After discarding the candidate, I
removed only those generated metadata directories. The outer workspace again
tracked the source edits normally; no source files were lost.
