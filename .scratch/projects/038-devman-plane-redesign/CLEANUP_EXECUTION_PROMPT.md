# Project 038 cleanup — execution prompt

Copy the text below into a fresh session.

Written 2026-09-15, after the investigation session closed workstream A's
diagnosis. It supersedes `CLEANUP_INVESTIGATION_PROMPT.md` for everything except
that document's ground-truth section. **Read this file, not that one, for what
to do.** Read that one only for the original framing.

---

You are finishing the cleanup after Project 038, the Devman machine-plane
redesign. **The investigation is complete.** Do not re-run it. Four pieces of
work remain, and their order is fixed.

## What the investigation already established — do not re-derive this

**Workstream A is diagnosed and closed.** The fleet-wide "staged empty blob"
symptom was **not** index corruption and **not** `git add -A`. It is
**Jujutsu's colocated working-copy export**. Every gitman command snapshots the
working copy through jj-lib in-process (pyjutsu), and that snapshot writes
`.git/index`. A file jj tracks that git has never committed becomes an
**intent-to-add** entry: blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`, zeroed
stat cache, `flags 20004000` (`CE_EXTENDED | CE_INTENT_TO_ADD`).

Measured, 2026-09-15: **28 repositories, 140 paths — not 40 and several
hundred.** All 28 are jj-colocated. Zero non-colocated repositories are
affected. Reproduced exactly with jj 0.44.0 and git 2.54.0.

Severity, measured rather than assumed:

| `git status --short` | In `HEAD`? | Count | What a commit does |
|---|---|---|---|
| `" A "` | no | 138 | Plain `git commit` ignores it, even with other files staged. `git commit -a` records the **real content**. No loss is reachable. |
| `"DA"` | yes | 2 | Plain `git commit` records a **deletion**, not an empty file. |

**No commit anywhere in the fleet since 2026-06-01 recorded the empty blob for a
file that had content.** Verified with `git log --all --raw` across every
repository. Zero hits.

**Therefore: do not repair the 138 `" A "` paths.** That state is normal, it is
load-bearing (Nix flake evaluation only sees the git tree), and the next gitman
command re-creates it. `forgelab` is in the archive set — leave it alone
entirely.

Already done in the investigation session, verified:

- **vendomat's 2 `DA` paths repaired.** `git restore --staged` on
  `src/vendomat/plane.py` and `tests/test_plane.py`. The staged
  `1517 deletions(-)` is gone; the index matches `HEAD`; both files intact.
- **The gitman issue is written**:
  `~/Documents/Projects/gitman/.scratch/projects/41-colocated-index-intent-to-add/ISSUE.md`.
  Untracked. Step 1 below decides its home.
- **devman's gates are green at `4c9927a`**: `base:check` clean,
  `base:unit` 590 passed.

## Ground truth, measured 2026-09-15 — re-measure before you rely on it

```text
devman             main @ 4c9927a, working tree clean but for .scratch prompts
active generation  3, 48 projects, 152 DAG files
dagu_digest        sha256:d3bbe557424a1137700d5cad5b35f983489313227ea1f8c92161be7ee5cf1278
dagu               2.15.0
reload markers     absent
system             nixos-system-server 26.11.20260705.d407951
fleet sweep        47 clean, 1 refusal (image-gen-pipeline) — the known baseline
```

**The installed `devman` binary lags the repository and is not a valid gate.**
Until step 3 lands, run every plane check from the repository's source:

```sh
cd /tmp
env -u PYTHONPATH -u NIX_PYTHONPATH \
  PYTHONPATH=/home/andrew/Documents/Projects/devman/src \
  /run/current-system/sw/bin/devman doctor
```

That reports 48 projects, 152 workflows and **9 findings**. Eight are expected.
The ninth, `literal dir /tmp/${DEVMAN_PROJECT_DIR}`, appears only when `doctor`
runs from `/tmp`; it is a leftover directory from 2026-09-14, not a plane fault.
Remove it or leave it, but say which.

---

## Step 1 — gitman: give the issue record a home

**Check before you commit. `gitman` is on a detached `HEAD`**, 1 ahead and 3
behind `origin/main`, with `devenv.lock`, `devenv.nix` and `devenv.yaml` dirty.
Do not commit onto a detached HEAD.

1. Fetch. Work out whether the 1 local commit is already on `origin/main` by
   content, exactly as repoman's turned out to be (step 2). Report what you find.
2. Get onto a real branch off `origin/main`, then add **only**
   `.scratch/projects/41-colocated-index-intent-to-add/ISSUE.md`. Leave the three
   dirty devenv files alone and report them.
3. Land through a pull request.

The issue proposes a `gitman doctor` check that classifies on `status` code plus
`HEAD` presence — never on the blob hash, because that reproduces the false
alarm inside the tool. **Do not implement the check in this session.** The issue
is the deliverable.

## Step 2 — repoman: fast-forward, then one lock-bump commit

**repoman's branch already landed.** `origin/main` is at
`74d4103 Merge pull request #22 from Bullish-Design/039-devman-item3-repoman`,
and `e55e525` is an ancestor of it. Local `main` is 3 behind. There is **no PR
to open and no feature work to commit**. What looks like 23 dirty paths is
`origin/main`'s own content sitting in a working tree whose HEAD is stale — 21
of the 23 are byte-identical to `origin/main`.

The jj conflict marker that was in `AGENTS.md` is already resolved:
`origin/main` carries the resolution, and the working-tree file was reverted to
match it byte for byte (`883afd34`). **Do not edit `AGENTS.md`.**

```sh
cd ~/Documents/Projects/repoman
git fetch origin
git checkout main
git merge --ff-only origin/main          # 57473ad -> 74d4103
git status --short                        # expect: devenv.lock only
```

Both commands are non-destructive here: every affected file already matches
`origin/main`, and the branch is fully merged there. Verify that claim yourself
before running them — compare `git hash-object <file>` against
`git rev-parse origin/main:<file>` for each dirty path.

Then commit the one real change. `devenv.lock` holds an uncommitted relock
moving copyroom `v0.7.4` → `v0.7.7`. **This is correct and approved.** Measured:
`v0.7.7` is copyroom's latest tag, and nine repositories already use it,
including `nix-meta` and `vendomat`.

1. Branch off `main`.
2. Run repoman's own gates first:
   `repoman-sync`, `devenv tasks run -v base:check`,
   `devenv tasks run -v base:test`.
3. Commit `devenv.lock` alone, as a lock bump. Name the old and new tag in the
   message.
4. Land through a pull request with a merge commit. Never squash, never
   force-push.
5. Delete the merged `039-devman-item3-repoman` branch, local and remote.

**Follow-up, not this session:** seven repositories still pin copyroom `v0.7.4`
— `shellij`, `pyllij`, `poddantic`, `flora-qc`, `flora-core`, `eventic`,
`argentic`. Record them; do not bump them here.

## Step 3 — devman: tag `v0.7.0`, then rebuild the machine

This is the workstream that makes the installed CLI current. `main` is **56
commits ahead** of the machine's pin and describes as `v0.6.0-79-g4c9927a`.

### 3a. Tag and push

Gates are already green at `4c9927a`, but re-run them — the tag is a published
artifact.

```sh
cd ~/Documents/Projects/devman
devenv tasks run -v base:check
devenv tasks run -v base:unit            # 590 tests at 4c9927a
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
devenv shell -- nix build .#packages.x86_64-linux.devman-link --no-link
```

Then tag `4c9927a` as `v0.7.0` and push the tag. An annotated tag, with a
message naming what the release carries: the whole-plane `doctor` (item 5), both
reload-script fixes (item 4), the 600 s reload deadline (item 8), the watcher
reload test (item 6), the VM reload subtests (item 7), the equal-roots refusal
(item 10), the identity-fallback removal (item 14), and the documentation sweep
(item 15).

### 3b. nix-meta: pin the tag and rebuild

`nix-meta` is dirty in three files, and **that dirty state is the 038 cutover
itself** — the running machine was built from it, so it is load-bearing and
untracked. Read it before you change it:

- `profiles/devman.nix` — adds
  `registryDir = "$HOME/.local/state/vendomat/devman/active"`, which is what
  makes `doctor` report `mode plane`.
- `flake.nix` — moves the devman input from tag `v0.5.2` to the bare rev
  `28b05a7044aa12eebd4aaf8da4c4eb302d79bf6d`.
- `flake.lock` — the matching lock.

Change the `flake.nix` input from that bare rev to
`?ref=refs/tags/v0.7.0`, which restores the fleet's tag convention, and rewrite
the comment above it accordingly — it currently explains why a bare rev was
used, and that reason is gone.

Then:

```sh
nixos-rebuild build --flake ~/Documents/Projects/nix-meta#server
nix store diff-closures /run/current-system ./result     # report this
nixos-rebuild boot   --flake ~/Documents/Projects/nix-meta#server
nixos-rebuild switch --flake ~/Documents/Projects/nix-meta#server
```

**Timing.** The rebuild restarts the Dagu user service. Forty-five DAGs fire
together at 00:05 daily, and a scheduled run is not gated by `run.trigger`
(accepted limitation, `.scratch/projects/025-the-link-plane/CONCEPT.md` Stage 3
item 5). Do not switch within an hour of 00:05, and do not switch while a run is
active.

Commit `nix-meta`'s three files and land them.

### 3c. The acceptance test

One line decides this step. After the switch, from `/tmp`, with **no**
`PYTHONPATH` override:

```sh
cd /tmp
env -u PYTHONPATH -u NIX_PYTHONPATH devman doctor
```

It must report **48 projects, 152 workflows**. If it still says 3 projects, the
switch did not take.

Then confirm the plane survived:

- Both reload markers absent under `~/.local/state/devman`.
- `dagu ls` resolves 152 DAGs under generation 3.
- The digest is unchanged:
  `sha256:d3bbe557424a1137700d5cad5b35f983489313227ea1f8c92161be7ee5cf1278`.
- The canaries return 0 with five `ok` states:

```sh
cd /tmp
VM_ROOT=/home/andrew/Documents/Projects/vendomat
env -u PYTHONPATH -u NIX_PYTHONPATH devman-link \
  status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
env -u PYTHONPATH -u NIX_PYTHONPATH devman \
  link status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
```

- The fleet sweep still reads `47 0` and `1 1 image-gen-pipeline`:

```sh
cd /tmp
for d in "$HOME/.config/devman/projects"/*/; do
  p=$(basename "$d"); r="/home/andrew/Documents/Projects/$p"
  [ -d "$r" ] || continue
  env -u PYTHONPATH -u NIX_PYTHONPATH devman-link \
    status --project "$p" --root "$r" --overlay "$HOME/.config/devman" >/dev/null 2>&1
  printf '%s %s\n' "$?" "$p"
done | sort | uniq -c -w2
```

A new refusal is a regression. Diagnose it before continuing.

## Step 4 — vendomat: land the machine-plane migration

Unlike repoman, **this branch is real**: `038-devman-plane-redesign` at
`5517878` is **15 commits ahead of `origin/main`, 0 behind**, and not merged.

Its two `DA` index entries are already repaired. Eight dirty paths remain:
`README.md`, `devenv.lock`, `devenv.nix`, `devenv.yaml`, `flake.lock`,
`flake.nix`, `src/vendomat/cli.py`, `tests/test_cli.py`.

1. Read the branch. Decide whether each dirty path belongs to the branch's
   purpose or is unrelated drift. **Report anything unrelated rather than
   committing it.**
2. Run vendomat's own gates — read its `AGENTS.md` first. They are:
   ```sh
   devenv shell -- testee verify --mode quick
   VENDOMAT_E2E=1 devenv shell -- testee verify --mode quick
   devenv shell -- nix build .#repoman-toolchain-core --no-link --print-out-paths
   ```
3. Land through a pull request with a merge commit. Never squash, never
   force-push, never move a branch — devman's own record cites these SHAs.
4. Re-run the source-path (or, after step 3, the bare) `devman doctor`. The
   `local sources` line for vendomat must go quiet.

**Deliberately out of scope.** `pyjutsu`, `docman` and `zelligate` each carry the
same "uncommitted, consumed unpinned" finding with one consumer, and `pytuin`
pins `atuout` at `3acdf1e9` against a `HEAD` of `26e05f97`. Report them as a
follow-up. Do **not** start a pinning campaign: `doctor`'s own docstring records
that 91 of 93 local inputs on this machine are unpinned and that a pin-updating
workflow would have produced 52 empty branches
(`src/devman/doctor.py:1126-1153`, project 016 §12 rule 4). The finding is about
**dirty** sources, not unpinned ones.

---

## Traps, already measured

1. **`base:test` reads the git tree.** `nix flake check`'s `python-tests`
   fileset is `./src ./tests ./pyproject.toml ./groups ./nix/nixos-module.nix`.
   An unstaged new file fails hermetically while `base:unit` passes. In a
   colocated repository jj's intent-to-add export is what makes a new file
   visible at all — that is the behaviour workstream A explains, and it is why
   suppressing it would break the fleet.
2. **`git status --short` codes `DA`, `D ` and `AD` are the ones that matter.**
   A bare `" A "` is normal colocated state.
3. **Measure the live system from `/tmp`**, not a repository shell, and clear
   both Python path variables.
4. **direnv can repair a link before your explicit shell entry runs.**
5. **A queue name that does not exist is accepted silently** at concurrency 1.
6. **A local checkout may be stale rather than dirty.** repoman proved it and
   gitman may repeat it. Before treating uncommitted paths as work, compare each
   against `origin/main` with `git hash-object` and `git rev-parse`.

## Stop conditions

Stop and ask when any of these is true.

1. A commit would record a deletion or an empty blob for a file that has
   content.
2. `devman doctor` gains a finding outside the nine listed above.
3. The active pointer, project count, DAG count or digest changes without an
   intended activation.
4. The rebuild would switch while a run is active, or within an hour of 00:05.
5. The fleet sweep gains a refusal.
6. A branch's dirty work has no clear owner or destination.
7. A gate fails, or you would skip one.

## How to work

- **Simplified Technical English.** Short sentences, active voice, one word for
  one meaning, no filler. `.agents/skills/writing/SKILL.md`.
- **One branch per step, then a pull request against `main`.** A direct push to
  `main` is refused. Merge with a merge commit; do not squash.
- **No `Co-Authored-By` trailers**, and no agent attribution in pull request
  bodies.
- **Record each step in `IMPLEMENTATION_LOG.md`** as its own stage section, in
  the fixed shape: the answer, the versions, the exact command, the evidence,
  the charter impact, and what the entry left on the machine. Put artifacts
  under
  `.scratch/projects/038-devman-plane-redesign/artifacts/<UTC timestamp>-<slug>/`.
  **Workstream A needs its own stage section** recording the jj diagnosis and
  correcting the `git add -A` attribution at `IMPLEMENTATION_LOG.md:2098-2099`
  and `:2160-2164`.
- **Record failed attempts rather than erasing them.**
- **Prefer a loud refusal to a silent default.**

## Report at the end

Files changed per repository; tests and exact results; the live active
generation, project count, DAG count and digest; every `devman doctor` finding,
from the source-path invocation before step 3 and from the bare invocation
after; the closure diff; canary and fleet-sweep results; commits, branches, tags
and merge commits; which steps closed and which remain; and any blocker needing
operator input.
