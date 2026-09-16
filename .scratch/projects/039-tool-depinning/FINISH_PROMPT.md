# Kickoff prompt — finish Project 039: land the docs, clear the five

Run this from `~/Documents/Projects/devman`. Paste from the horizontal rule down.

Scope: three items — commit three rescued documents, land the 039 documentation,
and migrate the last five vendomat consumers. The broader backlog (a remote for
`~/.config/devman`, phase-4 pin cleanup) is in `NEXT_SESSION_PROMPT.md` and is
**out of scope here**.

---

You are finishing **Project 039 (tool de-pinning)**. Ten of fifteen vendomat
consumers are migrated, repoman `v0.8.2` is released and deployed, and the
`021-changelog` livelock that blocked `devman` has been cleared — the repository
is CANONICAL again.

Three things remain. **Do them in this order.** Item A is two minutes and
prevents the trap that caused most of the trouble in the previous session.

## 0. Verify the starting state

```bash
cd ~/Documents/Projects/devman && gitman status      # expect CANONICAL
cd /tmp && env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman doctor
```

`doctor` must exit 0 with **6 findings**, none new. Record the plane invariants
and re-check them after **every** repository:

```bash
PLANE="$HOME/.local/state/vendomat/devman/active"
readlink "$PLANE"                                                   # generations/3
find -L "$PLANE/projects" -mindepth 1 -maxdepth 1 -type d | wc -l   # 48
find -L "$PLANE/dags" -type f -name '*.yaml' -exec sha256sum {} + | sort | sha256sum
#                                                                     395882db05afe769…
```

**A migration that changes the count or the digest is wrong. Stop.**

Machine state: repoman `v0.8.2` and vendomat `v0.4.1` are installed at
`/run/current-system/sw/share/{repoman/module,vendomat}/`.

### `devman` reports ~135 dirty files. That is not data loss.

It is the colocated intent-to-add artifact (gitman issue **41**): jj's snapshot
exports to `.git/index`, and files jj tracks but git never committed read as
`A`/`DA`/`MM`. Confirm before reacting to it:

```bash
git diff f080fc2 --stat     # empty, or only the three 023 files = tree is fine
```

## Item A — commit the three rescued 023 documents (do this first)

Three files sit uncommitted in `devman`'s working tree:

```
.scratch/projects/023-toolchain/OVERLAY.md                   132 lines
.scratch/projects/023-toolchain/prompts/03c-lock-overlay.md  136 lines
.scratch/projects/023-toolchain/prompts/05-close-out.md      178 lines
```

They were rescued from an abandoned commit during the `021-changelog` recovery
and are blob-verified against it. `main` has no
`.scratch/projects/023-toolchain/` directory, so **these three are the only
copies.** `OVERLAY.md` records why the `vendomat.toml` publish path for
`repoman.lock` was superseded — architecture the fleet still rests on.

Give them their own lane. They are project-023 documents and must not ride along
in a 039 commit; being swept into an unrelated lane is exactly what caused the
livelock.

```bash
cd ~/Documents/Projects/devman
gitman start 023-toolchain-docs
git diff --stat main -- .        # MUST show only the three files
gitman save -m "docs: restore the 023 toolchain design notes"
gitman land 023-toolchain-docs
```

**Commit them before creating any other file in this repository.** A file
created while `@` sits on another lane is snapshotted into that lane and then
vanishes from disk when you switch away.

## Item B — land the 039 documentation

Four finished commits, verified (`devenv tasks run -v base:check` passes), sit
unpushed on an anchor tag:

```
039-docs-safety -> f080fc2
  f080fc2 docs: record Project 039 stages 2 and 3
  c7c1197 docs: record the audited state of Project 039
  c6600d6 docs: correct the 039 option-value measurements
  a313a81 docs: add Project 039 kickoff prompts for repoman and vendomat de-pinning
```

Confirm the tag resolves before anything else — `gitman reconcile` twice deleted
the branch ref that held these:

```bash
git log --oneline origin/main..f080fc2     # expect the four above
```

**devman lands on `main` through a pull request, never a direct push.** In the
previous session plain `git push -u origin <branch>` was refused by the harness
while `gitman push` succeeded in every other repository — so prefer the gitman
path, or open the PR with `gh`.

Landing these also picks up this file and `NEXT_SESSION_PROMPT.md`, which are
untracked additions in the same directory. Include them deliberately or leave
them out; do not let them arrive unnoticed.

## Item C — the last five consumers

`flora-core`, `nix-nvim`, `paloma-text-pipeline`, `loci-core`, `nix-paseo` still
declare a `vendomat` input.

### The shared blocker — read this before touching any of them

**Each carries an uncommitted, unlanded Project 038 devman-consumer migration**
in its working tree: the `devman` input and the `devman = { … }` option block
removed, `.devman/project.toml` added.

```bash
for p in flora-core nix-nvim paloma-text-pipeline loci-core nix-paseo; do
  echo "== $p"; git -C ~/Documents/Projects/$p status --short | head
done
```

Expected dirty counts: `flora-core` 4, `nix-nvim` 3, `loci-core` 2,
`nix-paseo` 3 — and **`paloma-text-pipeline` 81, including 67 deletions** under
`experiments/diffusion/` and `docker/`.

**Land or abandon the 038 work in each repository first.** Do not adopt it into
a vendomat lane. That trap fired three times across this project; the last time
it produced the livelock.

**`paloma-text-pipeline` needs its owner's decision** on the 67 deletions before
anything else. If that is not available, migrate the other four and leave it.

### Per-repository requirements

| Repo | `vendomat.toml` | `cliProvider` | Central imports |
|---|---|---|---|
| flora-core | `[toolchain] enable = false` | **leave in `devenv.nix`** | multi-line |
| nix-nvim | `[toolchain] enable = false` | **leave in `devenv.nix`** | **single-line — expand first** |
| paloma-text-pipeline | `[toolchain] enable = false` | **leave in `devenv.nix`** | multi-line |
| loci-core | `[knowledge] enable = true` | verify — it declares no repoman input | **single-line — expand first** |
| nix-paseo | none — dead input, delete only | n/a | **single-line — expand first** |

**Why `cliProvider` stays in `devenv.nix` for three of them.** They still pin
repoman at `57473ad`, which predates `v0.8.2` and rejects `cliProvider` as an
unknown manifest field. The throw is **lazy**: it does not fire on
`config.repoman.cliProvider`, it fires when `managers` is forced, which every
real shell does. Writing that field before their repoman pin is removed breaks
the repository. Measured, not assumed.

`loci-core` declares **no** repoman input — confirm how it gets the module
before deciding whether it can take a manifest `cliProvider`.

`nix-paseo` declares the vendomat input and never imports the module. Delete the
input and take no other action: no central import, no manifest.

### The recipe, proven on ten repositories

One lane, one repository, both halves in one transition.

1. **Central** — `~/.config/devman/projects/<p>/devenv.local.nix` gains:
   ```nix
   /run/current-system/sw/share/vendomat/consumer-module.nix
   ```
   **Three of the five write `imports` on a single line.** Inserting a line
   after `imports = [ … ];` yields `syntax error, unexpected path`. Expand to a
   block first, then gate every edit:
   ```bash
   for f in ~/.config/devman/projects/*/devenv.local.nix; do
     nix-instantiate --parse "$f" >/dev/null || echo "PARSE FAIL: $f"
   done
   ```
2. **`devenv.yaml`** — delete the `vendomat:` input and `- vendomat/modules`.
   Keep `- repoman`. Rewrite any comment that described the input rather than
   orphaning it; the knowledge in those comments is real.
3. **`devenv.nix`** — move settings to the manifest, do not delete them.
4. **`vendomat.toml`** — write what moved, **always including**:
   ```toml
   [vendor.publish]
   enable = false
   ```
   `publish.enable` defaults to `true` and the gate is file presence, so
   creating a `vendomat.toml` otherwise installs a **pre-push git hook**:
   ```nix
   (lib.mkIf cfg.publish.enable {
     enterShell = ''if [ -f vendomat.toml ]; then ${vendomatCli}/bin/vendomat install-hook; fi'';
   })
   ```
5. Verify, then `gitman start` / `save` / `land` / `push`. Commit the central
   file separately in `~/.config/devman`.

### Verification — check that a tool resolves, not that a variable is set

`REPOMAN_MANAGERS` populates even when nothing is on `PATH`. Skipping this is
what let three repositories ship broken through an entire release.

```bash
cd ~/Documents/Projects/$P
devenv shell -- sh -c 'echo "PROVIDER=$REPOMAN_CLI_PROVIDER TOOLCHAIN=[$REPOMAN_TOOLCHAIN_BIN]"; for c in gitman copyroom repoman; do printf "%-10s " $c; command -v $c || echo MISSING; done'
test -f .git/hooks/pre-push && echo "HOOK INSTALLED — fix the manifest"
grep -c vendomat devenv.yaml devenv.lock
```

Expected for the three toolchain opt-outs: `PROVIDER=venv`, `TOOLCHAIN=[]`,
every manager resolving under `~/.local/share/repoman/venv/bin`.
For `loci-core`: `PROVIDER=store`, toolchain at `repoman-toolchain-core`.

Then re-check the plane invariants from §0.

### The lock trap

`devenv shell` rewrites `devenv.lock` with machine-local paths, and the fleet
gate refuses a push containing `/home/<user>/`. Fix with `relock`, never
`--no-verify`, and run it immediately before `gitman save` with no `devenv
shell` call in between.

## Gitman hazards this project has already paid for

- **`gitman start` adopts the whole working copy.** Run
  `git diff --stat main -- .` immediately after every `start` and confirm the
  scope before `save`. Three incidents traced to this.
- **Creating a file while `@` is on another lane** snapshots it into that lane;
  it then disappears from disk on `switch`/`start`. Recovery is
  `gitman split --into <lane> --paths <path>`, which works cleanly.
- **`gitman reconcile` deletes colocated git refs it does not recognise**,
  including branch refs holding unpushed commits. Anchor important work with a
  **tag**, not a branch — but delete that tag before any `jj abandon`, because
  jj's immutable set includes `tags()` and the tag will block the rewrite.
- Filed as gitman issues **31**, **38**, **41** and **42**; issue 42 is this
  project's, at `gitman/.scratch/projects/42-divergent-lane-bookmark-livelock/`.

## Do not

- Do not commit or revert `paloma-text-pipeline`'s 67 deletions without asking.
- Do not adopt a pre-existing changeset into a migration lane.
- Do not write `cliProvider` into a manifest in a repo whose repoman pin
  predates `v0.8.2`.
- Do not write a `vendomat.toml` without `[vendor.publish] enable = false`.
- **Do not remove the compatibility fallbacks** — `repoman.cliProvider`,
  `repoman.managers`, and vendomat's `config.vendor.*` reads all stay for one
  release. They are what makes this migration reversible.
- Do not run `vendomat plane update` during a consumer migration.
- Do not touch `forgelab` or `lodestar`; both are archive-set.

## Done means

```bash
grep -l '^  vendomat:' ~/Documents/Projects/*/devenv.yaml
```

returns nothing (or only `paloma-text-pipeline`, if its owner deferred), the
plane digest is unchanged, `devman doctor` exits 0 on its 6 findings, and the
fleet link sweep still reports 47 ok with the single pre-existing
`image-gen-pipeline` refusal.
