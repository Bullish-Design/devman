# Kickoff prompt — finish Project 039 and clear what it uncovered

Run this from `~/Documents/Projects/devman`. Paste from the horizontal rule down.

---

You are finishing **Project 039 (tool de-pinning)**. Most of it is done and
deployed. What remains is five repository migrations, one blocked release lane,
and three pieces of housekeeping. **Every item below is blocked by something
specific, and the blocker is named. Clear the blocker first; do not work around
it.**

## 0. Read before you change a line

| Document | Read for |
|---|---|
| `.scratch/projects/039-tool-depinning/IMPLEMENTATION_LOG.md` §Stage 2, §Stage 3 | the audited state, dated 2026-09-16, and every measurement below |
| `.scratch/projects/039-tool-depinning/README.md` | current status and what remains |
| `.scratch/projects/039-tool-depinning/VENDOMAT_PROMPT.md` §5 phase 3 | the per-repository runbook, still accurate |
| `repoman/.scratch/projects/039-repoman-depin/FINAL_REPORT.md` | the repoman half |
| `CLAUDE.md` properties 4, 6 and 10 | the charter this work is measured against |

## 1. The machine state you are starting from

Verify these before trusting anything below. They were true on 2026-09-16.

```bash
readlink -f /run/current-system/sw/share/repoman/module/devenv.nix   # repoman v0.8.2
readlink -f /run/current-system/sw/share/vendomat/consumer-module.nix # vendomat v0.4.1
cd /tmp && env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman doctor
```

Expected: `devman doctor` exits 0 with **6 findings**, none new. Plane
invariants — pointer `generations/3`, **48** projects, DAG digest
`395882db05afe769…`:

```bash
PLANE="$HOME/.local/state/vendomat/devman/active"
readlink "$PLANE"
find -L "$PLANE/projects" -mindepth 1 -maxdepth 1 -type d | wc -l
find -L "$PLANE/dags" -type f -name '*.yaml' -exec sha256sum {} + | sort | sha256sum
```

**Any migration that changes the plane count or digest is wrong. Stop.**

Ten of fifteen vendomat consumers are migrated and pushed: `flora-qc`, `tyo3`,
`shellij`, `argentic`, `eventic`, `flora`, `loci.nvim`, `poddantic`, `pyllij`,
`repoman`. Do not revisit them.

## 2. Item 1 — devman is off-canonical, and it blocks its own release

`gitman` refuses every operation in `~/Documents/Projects/devman`:

```
Gitman status — OFF-CANONICAL
Reason: lane(s) 021-changelog have a divergent change-id (one change → multiple commits)
```

`gitman reconcile` **cannot fix this** — it was run twice and reports the same
thing each time. A divergent change-id needs a human decision.

**`021-changelog` is not residue.** It carries 2 unique commits and 5068
insertions across 51 files, including a whole `groups/changelog/` group —
workflows, templates, a `writes.toml`. Measure it yourself before deciding:

```bash
git diff main...021-changelog --stat | tail -20
git merge-base --is-ancestor 021-changelog main && echo merged || echo unique
```

Decide deliberately: land it, or rebuild it as a fresh lane. **Do not abandon it
to clear the status.** If you land it, `groups/changelog/` needs its own README
entry per `CLAUDE.md`, and `devman doctor` must exit 0 before the commit.

### Then land the 039 documentation

Four documentation commits are finished, verified (`base:check` passes) and
**unpushed**. They are anchored two ways because `gitman reconcile` twice
deleted the branch ref out from under them:

```
branch 039-tool-depinning-docs  -> f080fc2
tag    039-docs-safety          -> f080fc2
```

The chain is `a313a81 → c6600d6 → c7c1197 → f080fc2`, all Project 039 docs.
**Confirm the tag still resolves before anything else**, and re-create it if a
reconcile removed it:

```bash
git log --oneline origin/main..f080fc2
```

devman lands on `main` through a **pull request**, never a direct push. Note
that plain `git push -u origin <branch>` was refused by the harness in the
previous session while `gitman push` succeeded in every other repository.

### A colocation hazard you will meet

devman is jj-colocated and its **git index goes stale**, reporting ~131 files as
`DA`/`MM` when the working tree is byte-identical to `HEAD`. It is an index
artifact, not content loss. Confirm before reacting:

```bash
git diff f080fc2 --stat        # empty (or only known stray files) = tree is fine
sha256sum <a file> ; git show f080fc2:<that file> | sha256sum
```

## 3. Item 2 — five repositories, one shared blocker

`flora-core`, `nix-nvim`, `paloma-text-pipeline`, `loci-core`, `nix-paseo` still
declare a `vendomat` input. **Each carries an uncommitted, unlanded Project 038
devman-consumer migration in its working tree** — the `devman` input and the
`devman = { … }` block removed, `.devman/project.toml` added. `flora-core` also
has its repoman pin rewritten to `57473ad`.

```bash
for p in flora-core nix-nvim paloma-text-pipeline loci-core nix-paseo; do
  echo "== $p"; git -C ~/Documents/Projects/$p status --short | head
done
```

**`paloma-text-pipeline` additionally holds 67 file deletions** under
`experiments/diffusion/` and `docker/`. Treat that as someone's in-flight work.
Confirm with its owner before committing or reverting any of it.

**Land or abandon the 038 work in each repo first.** Only then migrate. Do not
adopt an unrelated changeset into a migration lane — that trap has already been
hit three times in this project.

### The per-repository recipe, proven on ten repositories

For each, **one lane, one repository, both halves in one transition**:

1. **Central** — add the import to `~/.config/devman/projects/<p>/devenv.local.nix`:
   ```nix
   /run/current-system/sw/share/vendomat/consumer-module.nix
   ```
   **31 of 51 central files write `imports` on a single line.** Inserting a line
   after `imports = [ … ];` produces `syntax error, unexpected path`. Expand the
   list to a block first, then gate every edit:
   ```bash
   for f in ~/.config/devman/projects/*/devenv.local.nix; do nix-instantiate --parse "$f" >/dev/null || echo "PARSE FAIL: $f"; done
   ```
2. **`devenv.yaml`** — delete the `vendomat:` input and the `- vendomat/modules`
   import. Keep `- repoman` where present. Rewrite any comment that described
   the input rather than orphaning it.
3. **`devenv.nix`** — move the settings to manifests, do not delete them.
4. **`vendomat.toml`** — write the settings that moved.
5. Verify, then `gitman start` / `save` / `land` / `push`, then commit the
   central file separately in `~/.config/devman`.

### What each of the five needs

| Repo | `vendomat.toml` | `cliProvider` |
|---|---|---|
| flora-core | `[toolchain] enable = false` | **leave in `devenv.nix`** |
| nix-nvim | `[toolchain] enable = false` | **leave in `devenv.nix`** |
| paloma-text-pipeline | `[toolchain] enable = false` | **leave in `devenv.nix`** |
| loci-core | `[knowledge] enable = true` | n/a |
| nix-paseo | none — dead input, delete only | n/a |

**Why `cliProvider` stays in `devenv.nix` for three of them.** They still pin
repoman at `57473ad`, which predates v0.8.2 and rejects `cliProvider` as an
unknown manifest field. The throw is **lazy** — it does not fire on
`config.repoman.cliProvider`, it fires when `managers` is forced, which every
real shell does. Writing that field before their repoman pin is removed breaks
the repository. Measured, not assumed.

`nix-paseo` declares the input and never imports the module: delete the input
and take no other action. It needs no central import and no manifest.

### The trap that is not in the original prompts

**Creating a `vendomat.toml` installs a pre-push git hook.** `publish.enable`
defaults to `true` and the gate is file presence, in both the old pinned modules
and the v0.4.1 machine module:

```nix
(lib.mkIf cfg.publish.enable {
  enterShell = ''if [ -f vendomat.toml ]; then ${vendomatCli}/bin/vendomat install-hook; fi'';
})
```

Every `vendomat.toml` you write must also carry:

```toml
[vendor.publish]
enable = false
```

Then check `test -f .git/hooks/pre-push` afterwards. Ten repositories were
migrated this way and none gained a hook.

### Verification — check that a tool resolves, not that a variable is set

This is the check whose absence let three repositories ship broken through a
whole release. `REPOMAN_MANAGERS` populates even when nothing is on `PATH`.

```bash
cd ~/Documents/Projects/$P
devenv shell -- sh -c 'echo "PROVIDER=$REPOMAN_CLI_PROVIDER TOOLCHAIN=[$REPOMAN_TOOLCHAIN_BIN]"; for c in gitman copyroom repoman; do printf "%-10s " $c; command -v $c || echo MISSING; done'
test -f .git/hooks/pre-push && echo "HOOK INSTALLED - fix the manifest"
grep -c 'vendomat' devenv.yaml devenv.lock
```

Expected for the three toolchain opt-outs: `PROVIDER=venv`, `TOOLCHAIN=[]`,
every manager resolving under `~/.local/share/repoman/venv/bin`. For
`loci-core`: `PROVIDER=store` and the toolchain resolving to
`repoman-toolchain-core`.

Re-check the plane invariants after **each** repository.

### The lock trap

`devenv shell` rewrites `devenv.lock` with machine-local paths, and the fleet
gate refuses a push carrying `/home/<user>/`. Fix with `relock`, never
`--no-verify`, and run it immediately before `gitman save` with no `devenv
shell` call in between.

## 4. Item 3 — `~/.config/devman` has no remote

It was rescued from a detached HEAD in the previous session: 67 commits now on
`main`, working tree clean. **It still has no git remote**, so the machine-side
half of the whole link plane has no off-machine copy. Losing it silently
un-configures every repository in the fleet.

Create a **private** remote and push. Read the contents first — it holds
machine-local configuration and may contain personal paths or settings you do
not want published. Confirm with the user before creating anything public.

## 5. Item 4 — after the five land

1. **Collapse the pins.** Exactly two vendomat references should remain:
   `nix-meta/flake.nix` (the machine pin) and vendomat's own `devman` input
   (the packager's pin — keep permanently). Verify:
   ```bash
   grep -l '^  vendomat:' ~/Documents/Projects/*/devenv.yaml
   ```
2. **Clean three stale devman lock entries**: `nix-meta`'s `devenv.lock` holds
   `devman` at `v0.4.0`, `nix-terminal` floats `devman` on `main`, and
   `pydantree` has an orphan `devman` path node its `devenv.yaml` does not
   declare.
3. **`nix-desktop` and `nix-paseo` consume repoman through an unpinned
   `git+file://` path**, so they track its working tree live. That is how the
   `cliProvider` default flip reached three repositories unnoticed. Decide
   whether they move to the machine module or take a pinned tag.

## 6. Do not

- Do not abandon `021-changelog` to clear a status line. It is 5068 lines of
  real work.
- Do not commit or revert `paloma-text-pipeline`'s 67 deletions without asking.
- Do not adopt a pre-existing changeset into a migration lane. Check
  `git diff --stat main -- .` after every `gitman start`.
- Do not write `cliProvider` into a manifest in a repo whose repoman pin
  predates v0.8.2.
- Do not write a `vendomat.toml` without `[vendor.publish] enable = false`.
- **Do not remove the compatibility fallbacks.** Both `repoman.cliProvider` /
  `repoman.managers` and vendomat's `config.vendor.*` reads stay for one
  release. They are what makes this migration reversible. Removing
  `repoman.cliProvider` before all ten opt-out repositories carry the manifest
  field puts them in the exact state `llgym` was measured in: shell enters,
  roster populates, no manager command on `PATH`.
- Do not run `vendomat plane update` during a consumer migration.
