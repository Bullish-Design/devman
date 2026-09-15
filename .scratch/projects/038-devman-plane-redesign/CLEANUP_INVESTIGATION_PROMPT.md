# Project 038 cleanup — investigation and repair prompt

Copy the text below into a fresh session.

Written 2026-09-15, after Wave 3 item 15 closed (PR 172, merge commit
`4c9927a`). It scopes the residue Wave 3 left: two dirty source repositories,
one stale machine pin, and one fleet-wide Git index defect the Wave 3 item 1
repair did not cover.

---

You are cleaning up after Project 038, the Devman machine-plane redesign.

**This is investigation first, then repair.** Three workstreams are named below.
Two of them have a measured defect and a known shape. One of them — workstream A
— has a measured symptom across 40 repositories and **no diagnosis yet**. Do not
write a fleet-wide repair loop before you can explain how the defect was
produced.

**Wave 3 is closed. Do not reopen it.** Its records are in
`.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md`, Stages
1–46. Read the stage you are about to cite; do not read the log end to end.

## Read first

1. `CLAUDE.md` — the ten properties. Rules 1, 2, 4 and 10 settle most arguments.
2. `AGENTS_GUIDE.md` §3 and §4 — the three registry roots, the `doctor` check
   list, and the reload gate. Wave 3 item 15 rewrote both sections.
3. `.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md` Stage 46
   (item 15), Stage 45 (identity), Stage 44 (generation 3), and the **Stage 38
   repair** section — Stage 38 hit the same `git add -A` index corruption
   workstream A is about, and its repair is the precedent.
4. `.scratch/projects/038-devman-plane-redesign/WAVE_3_EXECUTION_PROMPT.md`
   item 1 — the nineteen staged-empty manifests, and the per-repository verify
   → repair → verify shape. **Reuse that shape. Do not write a blind loop.**

## Ground truth, measured 2026-09-15 14:00 UTC

Re-measure before you rely on any of it.

```text
devman             main @ 4c9927a, working tree clean
active generation  3, 48 projects, 152 DAG files
dagu_digest        sha256:d3bbe557424a1137700d5cad5b35f983489313227ea1f8c92161be7ee5cf1278
dagu               2.15.0
reload markers      absent
system             nixos-system-server 26.11.20260705.d407951
```

### The measurement that changes the picture

**The installed `devman` binary lags the repository, and it hid five findings.**
`/run/current-system/sw/bin/devman` predates Wave 3 item 5 (`cd0aac5`, "fix:
make plane doctor read active generation"). It enumerates the stable state root
and sees 3 projects. Run it with the repository's source instead:

```sh
cd /tmp
env -u PYTHONPATH -u NIX_PYTHONPATH \
  PYTHONPATH=/home/andrew/Documents/Projects/devman/src \
  /run/current-system/sw/bin/devman doctor
```

That reports **48 projects, 152 workflows**, and its `local sources` finding is
six lines, not one:

```text
!!  local sources   vendomat: uncommitted changes, consumed unpinned by 6 project(s)
                    repoman:  uncommitted changes, consumed unpinned by 6 project(s)
                    pyjutsu:  uncommitted changes, consumed unpinned by 1 project(s)
                    docman:   uncommitted changes, consumed unpinned by 1 project(s)
                    zelligate: uncommitted changes, consumed unpinned by 1 project(s)
                    pytuin: pins atuout at 3acdf1e9, and its HEAD is 26e05f97
```

**Use the source-path invocation for every gate in this session**, until
workstream C lands. The installed binary is not a valid gate.

The only other finding is `literal dir /tmp/${DEVMAN_PROJECT_DIR}`, a leftover
of the Wave 3 investigation's isolated `${DAG_NAME}` experiment, dated
2026-09-14 14:12. `check_literal` searches `Path.cwd()`, so it appears only when
`doctor` runs from `/tmp`. Decide whether to remove that directory; it is not a
plane fault.

---

## Workstream A — the staged empty-blob index defect

**The symptom.** A file is staged in the index as the empty blob
`e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` at mode `100644`, while the working
tree holds real content. A commit in that repository writes an empty file over
the real one. Wave 3 item 1 repaired nineteen `.devman/project.toml` instances.
**The defect is not limited to that path.**

Reproduce the scan:

```sh
cd ~/Documents/Projects
for d in */; do
  p=${d%/}; [ -d "$p/.git" ] || continue
  git -C "$p" ls-files -s 2>/dev/null \
    | awk '$2=="e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"{$1="";$2="";$3="";sub(/^   /,""); print}' \
  | while IFS= read -r f; do
      [ -s "$p/$f" ] && printf '%s :: %s\n' "$p" "$f"
    done
done
```

**Measured 2026-09-15: 40 repositories, several hundred paths.** The `[ -s ]`
test is what separates the defect from a legitimately empty tracked file such as
`__init__.py`, `py.typed` or `.gitkeep`. Every hit below is a real file in the
working tree staged as empty.

The affected paths fall into four groups, and they are probably not one cause:

| Group | Examples | Note |
|---|---|---|
| central-overlay views | `gitman.toml` in 20+ repositories, `.agents/skills/gitman/SKILL.md`, `.devman/project.toml` in `copyroom`, `docman`, `mypi-agent` | **Checked: these are regular files, not symlinks.** Confirm that before assuming |
| `*.devman-promoted` leftovers | `image-gen-pipeline/.agents.devman-promoted/**`, `nixvim/.envrc.devman-promoted`, `interplay/.loci.devman-promoted/**` | promote-drift residue; `image-gen-pipeline` is also the fleet sweep's one refusal |
| real source and tests | `vendomat/src/vendomat/plane.py` (39k), `vendomat/tests/test_plane.py` (18k), `repoman/src/repoman/devman/migrate.py` (4.7k), `repoman/tests/test_devman_migrate.py` (1.8k), `inferference/src/inferference/llama_placement.py` | **the dangerous group** |
| `.scratch/` records | `inferference/.scratch/**` (60 paths), `fsdantic/.scratch/**`, `forgelab/**` | large but low-risk |

**Investigate before you repair.** Answer these, with evidence:

1. **What produced it?** Stage 38's repair blamed `git add -A`. Test that
   claim. `git log -g`, `atuin` history (the author column separates human from
   agent commands), and file mtimes are the instruments.
2. **Does the repair differ by group?** `git restore --staged <path>` restores
   from `HEAD`. That is correct only when `HEAD` holds the file. Measured:
   `vendomat`'s two files **are** in `HEAD`; `repoman`'s two **are not** — they
   are new files staged as empty, so `restore --staged` unstages them into
   untracked, which is a different outcome. Handle both.
3. **Is any repository already damaged?** Look for a commit that recorded an
   empty blob for a file that had content in the previous commit. That is the
   failure this workstream exists to prevent, and it may have already happened.
4. **Can `devman doctor` catch it?** A check that reads each registered
   repository's index for this blob is cheap — one `git ls-files` per project.
   Property 4 favours a check that can fail. Propose it; do not build it before
   the diagnosis is written.

**Repair rule.** Per repository: verify, repair, verify again, exactly as Wave 3
item 1 did. Never a blind loop. Never touch unrelated dirty state. Several of
these checkouts sit on feature branches with real work in them.

---

## Workstream B — Vendomat and RepoMan

Both are dirty, both sit on unmerged feature branches, and six registered
projects consume each of them through an unpinned `git+file:` input. An unpinned
local input has no `rev` in `devenv.lock` and `fetchTree` resolves it **live**,
so those twelve consumers currently build from these working trees.

```text
vendomat  branch 038-devman-plane-redesign, HEAD 5517878
          "vendomat: complete the machine plane migration"
          10 dirty paths, including devenv.nix, devenv.yaml, flake.nix,
          src/vendomat/cli.py, tests/test_cli.py
          2 of them carry the workstream A defect: src/vendomat/plane.py,
          tests/test_plane.py — both present in HEAD

repoman   branch 039-devman-item3-repoman, HEAD e55e525
          "refactor: remove Devman consumer integration"
          23 dirty paths, including modules/devenv.nix, src/repoman/cli.py,
          AGENTS.md, README.md, devenv.lock
          2 of them carry the workstream A defect:
          src/repoman/devman/migrate.py, tests/test_devman_migrate.py —
          NEITHER is in HEAD
```

**Order matters. Repair the index defect first, in both repositories, before any
commit.** A commit before the repair empties four files, two of which are 39k
and 4.7k of live source.

Then, per repository:

1. Read the branch. Decide whether the dirty work belongs to that branch's
   purpose or is unrelated drift. Report anything unrelated rather than
   committing it.
2. Run that repository's own gates. Vendomat and RepoMan each define their own;
   read their `AGENTS.md` first.
3. Land through a pull request with a merge commit. **Never force-push. Never
   move a branch.** Devman's own record cites SHAs, so do not squash.
4. Re-run the source-path `devman doctor`. The `local sources` line for that
   repository must go quiet.

`pyjutsu`, `docman` and `zelligate` carry the same "uncommitted, consumed
unpinned" finding with one consumer each. `pytuin` pins `atuout` at `3acdf1e9`
against a `HEAD` of `26e05f97`. These are smaller instances of the same
question. Decide whether they belong in this session or in a follow-up, and say
which.

**The open question worth answering, not assuming:** should local consumers be
pinned at all? `doctor`'s own docstring records the measurement that killed the
obvious answer — 91 of 93 local inputs on this machine are unpinned, and a
pin-updating workflow would have produced 52 empty branches
(`src/devman/doctor.py:1126-1153`, project 016 §12 rule 4). The finding is about
**dirty** sources, not unpinned ones. Fix the dirt; do not start a pinning
campaign without an argument against that measurement.

---

## Workstream C — rebuild the machine so the plane's own CLI is current

`nix-meta` holds this machine's `nixosConfigurations`. It pins Devman at
`28b05a7044aa12eebd4aaf8da4c4eb302d79bf6d` (2026-09-13, "devman: expose the link
module in the system profile"). **`main` is 56 commits ahead of that pin**, and
those 56 commits include every Wave 3 item: the whole-plane `doctor` (item 5),
both reload-script fixes (item 4), the 600 s reload deadline (item 8), the
watcher reload test (item 6), the VM reload subtests (item 7), the equal-roots
refusal (item 10), the identity-fallback removal (item 14), and the
documentation sweep (item 15).

```text
nix-meta   branch main, dirty: flake.lock, flake.nix, profiles/devman.nix
           devman input:  git+https://github.com/Bullish-Design/devman
                          rev 28b05a7…, ref refs/heads/main
           second node `devman_2` pins github:Bullish-Design/devman at
           d8a302c8 — a much older rev reached through another input.
           Find out which input pulls it, and whether it matters.
```

Work:

1. Explain the dirty `nix-meta` state before changing it. `profiles/devman.nix`
   is the machine's Devman profile; read what is uncommitted there.
2. Bump the Devman pin to `4c9927a` (or to a published tag, if the fleet
   convention is a tag — check what the other consumers pin).
3. Build before you switch: `nixos-rebuild build`, then `boot`, then `switch`.
   Report the closure diff.
4. **Verify the CLI moved.** After the switch, bare
   `env -u PYTHONPATH -u NIX_PYTHONPATH devman doctor` from `/tmp` must report
   **48 projects, 152 workflows** with no `PYTHONPATH` override. That single
   line is the whole acceptance test for this workstream.
5. Re-run the canaries and the fleet sweep (below). A new refusal is a
   regression.
6. Confirm the reload path: the rebuild restarts the Dagu user service, so check
   that both reload markers are absent afterwards and that `dagu ls` still
   resolves 152 DAGs under generation 3.

**Weigh the order.** The rebuild restarts Dagu on a machine with 45 DAGs firing
at 00:05 daily. A scheduled run is not gated by `run.trigger`, so it can overlap
a reload — an accepted limitation, recorded in
`.scratch/projects/025-the-link-plane/CONCEPT.md` Stage 3 item 5. Do not switch
close to 00:05.

---

## Verification

Devman's own gates, from the repository:

```sh
devenv tasks run -v base:check
devenv tasks run -v base:unit          # 590 tests as of 4c9927a
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
devenv shell -- nix build .#packages.x86_64-linux.devman-link --no-link
```

The plane, from `/tmp`, with both Python path variables cleared:

```sh
cd /tmp
VM_ROOT=/home/andrew/Documents/Projects/vendomat
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
  status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman \
  link status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
```

Both must return 0 with five `ok` states and the central configuration path.

The fleet sweep, in the shape the hook calls:

```sh
cd /tmp
for d in "$HOME/.config/devman/projects"/*/; do
  p=$(basename "$d"); r="/home/andrew/Documents/Projects/$p"
  [ -d "$r" ] || continue
  env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
    status --project "$p" --root "$r" --overlay "$HOME/.config/devman" >/dev/null 2>&1
  printf '%s %s\n' "$?" "$p"
done | sort | uniq -c -w2
```

Baseline: `47 0` clean, `1 1 image-gen-pipeline` — the known promote drift. A
new refusal is a regression; diagnose it before continuing.

## Traps, already measured

1. **`base:test` reads the git tree.** `nix flake check`'s `python-tests`
   fileset is `./src ./tests ./pyproject.toml ./groups ./nix/nixos-module.nix`.
   An unstaged new file fails hermetically while `base:unit` passes.
2. **Check `git status --short` for `D `, `DA` or `AD` before committing
   anywhere.** That is workstream A's symptom in `status` form.
3. **Measure the live system from `/tmp`**, not from a repository shell, and
   clear both Python path variables.
4. **direnv can repair a link before your explicit shell entry runs**, which
   made an earlier stage misread a measurement.
5. **A queue name that does not exist is accepted silently** at concurrency 1.

## Stop conditions

Stop and ask when any of these is true.

1. A commit would record the empty blob for a file that has content.
2. A repository already holds a commit that emptied a file, so the repair is a
   history question, not an index question.
3. `devman doctor` gains a finding outside the ones listed above.
4. The active pointer, project count, DAG count or digest changes without an
   intended activation.
5. The rebuild would switch the running system while a run is active, or within
   an hour of 00:05.
6. A branch's dirty work has no clear owner or destination.
7. The fleet sweep gains a refusal.

## How to work

- **Simplified Technical English.** Short sentences, active voice, one word for
  one meaning, no filler. `.agents/skills/writing/SKILL.md`.
- **One branch per workstream, then a pull request against `main`.** A direct
  push to `main` is refused. Merge with a merge commit; do not squash.
- **No `Co-Authored-By` trailers**, and no agent attribution in pull request
  bodies.
- **Record each workstream in `IMPLEMENTATION_LOG.md`** as its own stage
  section, in the fixed shape: the answer, the versions, the exact command, the
  evidence, the charter impact, and what the entry left on the machine. Put
  artifacts under
  `.scratch/projects/038-devman-plane-redesign/artifacts/<UTC timestamp>-<slug>/`.
- **Record failed attempts rather than erasing them.**
- **Prefer a loud refusal to a silent default.**

## Report at the end

Files changed per repository; tests and exact results; the live active
generation, project count, DAG count and digest; every doctor finding, from the
**source-path** invocation until workstream C lands and from the bare
invocation after; canary and fleet-sweep results; commits, branches and merge
commits; which workstreams closed and which remain; and any blocker needing
operator input.
