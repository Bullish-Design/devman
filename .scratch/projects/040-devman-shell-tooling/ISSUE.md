# Issue — devman's dev shell ships the skills but not the tools

**Date:** 2026-09-16
**Found:** an agent session reported it "cannot access gitman" in this repository.
**Status:** open, diagnosed, not started.

## 1. TL;DR

devman's devenv shell provides **none** of the manager commands, and no `jj`.
The repository nevertheless ships agent skills that instruct an agent to run
those commands, and one devenv task that calls `gitman` by name.

The claim is accurate as a `PATH` fact and misleading as an availability fact:
gitman **is** installed on this machine (two copies, both 0.6.2). It is simply
not wired into this shell.

## 2. Measured, in `devenv shell` at the repo root

| Command | Result |
|---|---|
| `gitman` `copyroom` `docman` `templateer` `repoman` `testee` | **MISSING** |
| `jj` | **MISSING** |
| `ruff` `uv` `git` `nix` `dagu` `devman` `devman-link` `python` | present |

```
$ env | grep REPOMAN
(nothing — the repoman module is absent, not merely quiet)
```

Where gitman actually lives:

```
~/.local/share/repoman/venv/bin/gitman                     0.6.2   (shared toolchain venv)
/nix/store/z6ayz3iz…-repoman-toolchain-core/bin/gitman     0.6.2   (store closure)
/run/current-system/sw/bin/gitman                          DOES NOT EXIST
```

## 3. Why

**The manager commands reach a repository through repoman's devenv module**,
which prepends the toolchain bin directory to `PATH`. devman gets that module
from neither direction:

- `devenv.yaml` / `devenv.nix` — declares no `repoman` input at all.
- `~/.config/devman/projects/devman/devenv.local.nix` — links only. It has **no
  `imports` block**, so no machine module. The file is dated 10 Sep and predates
  the machine-module pattern; it still uses the old `config.devman.project`
  shape rather than the `project ? null` form every 039-migrated repo now
  carries.

**Interactive shells hide this.** `nix-meta`'s `profiles/developer.nix` puts the
toolchain bin on the **login shell's** `PATH`, so `gitman …` typed at a prompt
works. An agent runs non-interactive bash, which does not source that profile,
so the identical command fails. That asymmetry is what produced the report.

## 4. Why it matters

**This repository ships instructions it cannot satisfy.** `.agents/skills/`
carries `copyroom`, `copyroom-adopt`, `copyroom-template-edit`, `gitman` and
`my-ai` — skills whose whole content is *run this command* — into a shell where
none of those commands exist. An agent following the routing table in
`CLAUDE.md` hits `command not found` and, as happened here, reports the tool
missing from the machine.

`devenv.nix:228` also defines a `gitman:commit-message` task, and
`.devman/workflows/gitman-commit-message.yaml` runs it. The surrounding comments
describe `gitman save -m …` as the consumer of its output.

`jj` matters for a narrower reason: gitman is jj-backed, and the documented
recovery from a divergent change-id (gitman issue **42** §7) is plain `jj`. This
session had to locate a matching binary in `/nix/store` by hand.

**What is NOT broken:** `base:check` (`ruff check .`) and `base:test`
(`nix flake check`) need none of these, so CI and the release gate are fine.
This is an agent-surface and interactive-ergonomics defect, not a build defect.

## 5. Options

Per the standing rule — *add missing tools to `devenv.nix` and measure; do not
model a bound instead* — the fix belongs in the shell, not in documentation.

1. **Import the machine repoman module** in the central overlay, as every
   039-migrated repo does:
   ```nix
   imports = [
     /run/current-system/sw/share/devman/link-module.nix
     /run/current-system/sw/share/repoman/module/devenv.nix
   ];
   ```
   Gives the whole roster with one line, and matches the fleet.
   **Two cautions.** The file still reads `config.devman.project`, which the
   migrated link module does not supply — it needs the `project ? null` +
   `fromTOML` conversion **in the same edit**, or it fails with `attribute
   'devman' missing`, the exact failure 038's first probe hit. And devman
   building the plane while consuming its own machine-delivered modules is a
   bootstrap question worth deciding deliberately, not as a side effect.

2. **Add the toolchain closure to `devenv.nix` `packages`** directly, without
   the repoman module. Smaller blast radius, no bootstrap question, but it
   duplicates a wiring the fleet already standardises.

3. **Add `jj` to `packages`** regardless of which of the above is chosen. It
   must match the `jj-lib` pyjutsu is built against — both were 0.44.0 on
   2026-09-16. A mismatched `jj` against a colocated repo is its own hazard.

Whichever is taken, the acceptance check is the one this project keeps
re-learning: **verify a command resolves, not that a variable is set.**

```bash
cd ~/Documents/Projects/devman
devenv shell -- sh -c 'for c in gitman copyroom docman templateer repoman testee jj; do printf "%-12s " $c; command -v $c || echo MISSING; done'
```

## 6. Workaround today

Use a full path; nothing is broken:

```bash
~/.local/share/repoman/venv/bin/gitman status
```

Every lane, land and push in the Project 039 session used the store-path
equivalent. The store hash changes when the toolchain is rebuilt, so the venv
path is the more durable of the two.

## 7. Cross-references

- `gitman/.scratch/projects/42-divergent-lane-bookmark-livelock/` — needs `jj`
- `.scratch/projects/039-tool-depinning/` — the machine-module pattern this
  would adopt, and the `project ? null` conversion it requires
- `CLAUDE.md` — the skills routing table that assumes these commands exist
