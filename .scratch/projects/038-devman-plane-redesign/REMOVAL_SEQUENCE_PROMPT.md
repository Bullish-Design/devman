# Project 038 — clean-session prompt for the removal sequence

Copy the text below into a clean implementation session.

---

You are continuing Project 038: the Devman machine-plane redesign.

Do not restart Project 038. Do not repeat the completed migration, comparison,
A-to-C bridge, Vendomat canary, or B extraction work.

B is complete and deployed. Your goal is what follows it: **close the
observation period, remove the renderer's duplicate link adapter, then work the
gated §11 removal sequence one item at a time.**

Each removal needs its own evidence. Do not batch them.

## Repositories

~~~sh
export DM_ROOT=/home/andrew/Documents/Projects/devman
export VM_ROOT=/home/andrew/Documents/Projects/vendomat
export RM_ROOT=/home/andrew/Documents/Projects/repoman
export NM_ROOT=/home/andrew/Documents/Projects/nix-meta
export DM_POLICY_ROOT=$DM_ROOT
~~~

Start in:

~~~sh
cd "$DM_ROOT"
~~~

The current Devman branch is `038-fixup-and-fanout`. Continue from it. Do not
create a new branch from stale main.

The latest Devman commit is:

~~~text
8974c4c docs: record Stage 16, the independent link adapter
~~~

The machine pins it. nix-meta `main` is at:

~~~text
d2e432b chore: pin devman at the independent link adapter
~~~

The operator has switched. `/run/current-system` is
`89javwy6hj41g4j8ihj198q95qqz6i3z-nixos-system-server-26.11.20260705.d407951`.

## Read before action

Read these files completely:

~~~text
$DM_ROOT/AGENTS.md
$DM_ROOT/AGENTS_GUIDE.md
$DM_ROOT/.scratch/projects/025-the-link-plane/CONCEPT.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/CONCEPT.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_GUIDE.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/LINK_ADAPTER_B_GUIDE.md
$VM_ROOT/AGENTS.md
$RM_ROOT/AGENTS.md
$NM_ROOT/AGENTS.md
~~~

Read implementation-log **Stage 16 in full**. It records what B built, what it
measured, and what it deliberately left. Stages 11 to 15 are background.

`IMPLEMENTATION_GUIDE.md` §11 is the removal list. Note the numbering: the log
calls it "§11", and it is the implementation guide's §11, not `CONCEPT.md`'s.

Read these skills before using their commands or editing their files:

~~~text
Devman
Devman adoption
Gitman
my-ai
writing
~~~

Run verification and tools inside devenv. Do not call bare uv, python, pytest,
ruff, or copier.

## What B left on the machine

The independent component is `src/devman_link/`, with the pure contract in
`src/devman_contract/`. `nix/link-adapter.nix` builds those two alone, from
`packaging/devman-link/pyproject.toml`, and its install check runs a real
`status` against a repository no registry has heard of.

`services.devman-dagu.installLinkAdapter` defaults to true, so
`/run/current-system/sw/bin/devman-link` is the independent adapter.

`devman.useLinkAdapter` in `modules/devenv.nix` defaults to **false**. Exactly
one repository has it on: Devman itself, in its own `devenv.nix`.

Three things are still duplicated on purpose, and undoing them is your work:

1. `pyproject.toml` still maps `devman-link` to `devman.link:cli`, the old
   registry-driven command.
2. `nix/renderer.nix` still builds that copy and smoke-tests it.
3. `src/devman/link.py` is still the implementation behind it, and behind
   `devman link status --all`.

## Non-negotiable safety rules

These Devman files have protected, unrelated worktree changes:

~~~text
src/devman/link.py
src/devman/watch.py
tests/unit/test_link.py
tests/unit/test_watch.py
~~~

**They are formatter reflows from the `devman/format` watcher, nothing more.**
Do not modify, stage, discard, or commit them while they remain dirty.

**This is the one rule that blocks your first task.** Removing the renderer's
adapter copy means deleting `src/devman/link.py` and `tests/unit/test_link.py`,
which is a change to two protected files. **Stop and ask the operator to land
or discard those four worktree changes before you start.** Do not work around
it by leaving a dead module, and do not stage a protected file.

RepoMan has a protected pre-existing `devenv.lock` change. Do not modify,
unstage, discard, or commit it. Do not format RepoMan's two pre-existing
unformatted files.

Do not modify the central configuration checkout `$HOME/.config/devman`. Read
its status only.

Do not hand-edit generated files:

~~~text
$HOME/.local/share/devman
$HOME/.local/state/devman
$HOME/.local/state/vendomat/devman
$HOME/.local/share/dagu
~~~

Do not run `gitman reconcile`. Gitman is **not on this repository's shell
PATH**; `devenv shell -- gitman status` fails with `gitman: not found`. Use the
explicit raw Git fallback in the commit section. Do not force-push.

## Inspect state first

~~~sh
for repo in "$DM_ROOT" "$VM_ROOT" "$RM_ROOT" "$NM_ROOT"; do
  printf '\n== %s ==\n' "$repo"
  git -C "$repo" status --short --branch
  git -C "$repo" log -1 --oneline --decorate
done
git -C "$HOME/.config/devman" status --short --branch
~~~

Record the live baseline outside every project shell, with both Python path
variables cleared:

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman doctor
env -u PYTHONPATH -u NIX_PYTHONPATH dagu --dagu-home "$HOME/.local/share/dagu" ls

PLANE="$HOME/.local/state/vendomat/devman/active"
readlink "$PLANE"
find -L "$PLANE/projects" -mindepth 1 -maxdepth 1 -type d | wc -l
find -L "$PLANE/dags" -mindepth 1 -maxdepth 1 -type f -name '*.yaml' | wc -l
find -L "$PLANE/dags" -type f -name '*.yaml' -exec sha256sum {} + | sort | sha256sum
~~~

**Stage 16 measured this, and you must re-measure rather than copy it:**

~~~text
doctor          exit 1, mode plane, 4 findings
active pointer  generations/2, 46 projects, 146 DAG files
DAG digest      5acf4cc3be671f7118643e33eb01f37d708ed780ee228027956dce0dcee6022b
dagu ls         147 lines
~~~

The four doctor findings are `flora-037-part-e:devenv.local.nix: create`;
dirty, unpinned Vendomat source; dirty, unpinned RepoMan source; and the
unpinned `git+file:` repair advice. Doctor exit 1 is a finding result. A
passing test does not erase a finding. Do not repair unrelated drift.

## Phase 1 — close the observation period

B switched one repository and swept the rest read-only. Turn that into
evidence before removing anything.

Re-run the read-only fleet sweep with the installed adapter:

~~~sh
for d in "$HOME/.config/devman/projects"/*/; do
  p=$(basename "$d"); r="/home/andrew/Documents/Projects/$p"
  [ -d "$r" ] || continue
  env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
    status --root "$r" --overlay "$HOME/.config/devman" >/dev/null 2>&1
  printf '%s %s\n' "$?" "$p"
done | sort | uniq -c -w2
~~~

**Stage 16 measured 51 repositories with a checkout: 44 exit 0, 7 findings.**
The seven are `copyroom`, `docman` and `mypi-agent` refusing for a missing
manifest, and `forgelab`, `image-gen-pipeline`, `lodestar` and `repoman`
carrying real link drift. Confirm the set. A NEW repository in that list is a
regression and must be diagnosed before you remove anything.

Then observe a second repository on the new hook. This needs a repin, because
every consumer pins Devman by revision and `devman.useLinkAdapter` does not
exist in their pinned module.

1. Pick one migrated repository with a manifest and no current drift.
2. Update its `devenv.yaml` devman input to the current Devman commit.
3. Set `devman.useLinkAdapter = true` in its `devenv.nix`.
4. Enter its shell once, with both Python path variables cleared.
5. Confirm the realized link script calls `devman-link-<version>/bin/devman-link
   reconcile` with no `--registry` and no `--state`. Find it with:

~~~sh
newest=$(ls -t .devenv/shell-*.sh | head -1)
rg -n -A2 devman-link "$newest"
~~~

6. Break one link deliberately, re-enter, and confirm `repoint` and repair.
7. Compare the active pointer, project count, DAG count and DAG digest.

**Direnv will re-enter the shell and repair a broken link before an explicit
entry runs.** Stage 16 misread this once: the explicit entry printed `ok`
because direnv had already fixed it. Run the hook's own script directly to see
the true state.

Only after two repositories are stable should you widen. Do **not** flip the
module default to true and re-pin the fleet in one commit.

## Phase 2 — remove the renderer's adapter copy

**Ask the operator first.** This deletes protected files.

The order is: prove nothing calls the old path, then delete it.

1. Inventory every caller:

~~~sh
rg -n "devman-link|devman\.link:cli|from \. import link|from devman import link" \
  src modules nix tests flake.nix pyproject.toml "$VM_ROOT" "$RM_ROOT" "$NM_ROOT"
~~~

2. `devman link status --all` is the one real consumer of `src/devman/link.py`.
   Decide its fate explicitly. It enumerates the compatibility registry, which
   §11 item 4 has not removed yet, so it probably stays — but it must then stop
   depending on the old adapter's reconciler. Re-point it at `devman_link` and
   keep only the enumeration in `devman.link`, or move the enumeration into
   `cli.py` and delete the module. **State the choice in the log before coding.**

3. Remove `devman-link` from `[project.scripts]` in `pyproject.toml` and from
   `nix/renderer.nix`'s install check.

4. Remove the `useLinkAdapter = false` branch from `modules/devenv.nix` and the
   option with it, once every consumer is repinned and switched. Not before.

5. Delete `src/devman/link.py` and `tests/unit/test_link.py`. Confirm
   `tests/unit/test_link_adapter.py` covers every case the deleted file
   asserted; add the missing ones first.

Use separate commits. After each, run the full verification and the canary.

## Phase 3 — the gated §11 removals

Work them one at a time, in this order, each with its own evidence and commit.
Item 1 is done (Stage 14 removed `scripts.devman-resync.exec`).

| Item | What | Gate |
|---|---|---|
| 2 | duplicate resolver or renderer code | needs every consumer off the compatibility resolver |
| 3 | routine consumer Devman lock updates | needs the central overlay to stop requiring `config.devman.project` |
| 4 | compatibility registry writes | needs a supported replacement for the remaining consumers |
| 5 | compatibility mode | needs the last supported consumer to leave it |
| 6 | obsolete documentation and flags | follows the others |

**Item 3 has a measured blocker.** Stage 14 probed it on Vendomat: removing the
`devman` input, the module import and the option block made shell entry fail at
Nix evaluation with `attribute 'devman' missing`, because
`~/.config/devman/projects/vendomat/devenv.local.nix` reads
`config.devman.project`. The edits were reverted. Items 2 through 4 are gated
on that. Do not retry the probe without a design for how the central file gets
its identity without the Devman Nix module.

**Item 5 is blocked** by three manifest-placement decisions (`copyroom`,
`docman`, `mypi-agent`), seven detached-HEAD branch decisions, and the
compatibility-only projects. Those are operator decisions. Ask; do not guess a
placement.

Do not remove a fallback because one canary passed. Do not delete old registry
state or an active generation.

## Verify in layers

~~~sh
cd "$DM_ROOT"
devenv tasks run -v base:check
devenv tasks run -v base:unit
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
devenv shell -- nix build .#packages.x86_64-linux.devman-link --no-link
~~~

**Stage 16 measured `base:unit` at 631 passed in 8.73s.** A removal that drops
the count must say which tests went and why.

`base:test` runs `nix flake check`, which includes `checks.<system>.link-adapter`
— the package build and its no-registry install check. The `python-tests`
fileset is `./src ./tests ./pyproject.toml ./groups ./nix/nixos-module.nix`.
**A new source or test file outside that fileset passes locally and is invisible
here.** Update the fileset in the same commit.

`flake.nix` has two module checks you can break without noticing:
`shell-variable-unset` requires every new `devman_*=` assignment in
`modules/devenv.nix` to appear in the `unset` block, in the same commit; and
`hook-path-refusal` cuts a refusal block out by literal path.

`devman doctor` must exit 0 — or exit 1 with only the four known findings —
before a change to `modules/`, `groups/`, `nix/` or `src/devman/` is committed.

If nix-meta changes:

~~~sh
cd "$NM_ROOT"
nixos-rebuild build --flake .#server
~~~

Verify the built system before handing it over:

~~~sh
SYS=$(readlink -f result)
readlink -f "$SYS/sw/bin/devman-link"
readlink -f "$SYS/sw/bin/devman"
~~~

**Sudo needs an interactive password and you cannot supply it.** Commit and push
the nix-meta change, then give the operator this exact command:

~~~sh
sudo nixos-rebuild switch --flake .#server
~~~

nix-meta commits go direct to `main`, no PR.

If Vendomat files change: `cd "$VM_ROOT" && devenv shell -- testee verify --mode quick`.
If RepoMan files change: `cd "$RM_ROOT" && devenv tasks run -v base:check` and `base:test`.

## The canary, after every removal

~~~sh
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
  status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"

env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman link \
  status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
~~~

Both must return 0 with five `ok` states and the central configuration path.
Then confirm the active pointer, project count, DAG count, DAG digest and
`dagu ls` line count are unchanged, and run doctor again.

If a result changes when the two Python path variables are cleared, stop and
diagnose environment shadowing before changing code.

**Inside Devman's own devenv shell, `devman-link` resolves to the repository's
build, not the system adapter.** That is the renderer copy, and it is why
Phase 2 exists. Measure the live system from `/tmp`, not from the repository
shell.

## Rollback

Keep every rollback reviewable. A rollback is a source or machine-package
change, never an edit to a generated registry, a generated DAG, or a retained
generation.

Until Phase 2 lands, `devman.useLinkAdapter = false` returns one repository to
the renderer-provided adapter. After Phase 2 that path is gone, so Phase 2 is
the point of no return for the old adapter. Say so in the log.

## Commit and push

Keep commits small and separate by repository. Before every commit:

~~~sh
git diff --check
git status --short
git diff --cached --check
git diff --cached --name-status
~~~

Stage explicit paths only. Never run `git add .`, `git add -A`,
`git reset --hard`, or `git checkout --`.

Verify the staged name list excludes the four protected Devman files, unless
the operator has released them for Phase 2. Verify RepoMan's staged list
excludes `devenv.lock`.

Gitman is not on this repository's PATH, so use this explicit fallback:

~~~sh
git add -- <each-intended-path>
git diff --cached --check
git diff --cached --name-status
git commit -m "<message>"
git push origin 038-fixup-and-fanout
~~~

End every commit message with:

~~~text
Co-Authored-By: Claude <noreply@anthropic.com>
~~~

Never force-push.

## Implementation log

Add a dated stage entry to
`.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md` for **each
removal**, not one for the batch. Match the existing format: `## Stage N — a
lowercase descriptive phrase`, no per-stage date line, an opening sentence
beginning `On <date>, …`, and bolded lead-in labels rather than `###` headings.

Record: what was removed and what now owns it; the failure the removal risks
and the evidence it does not happen; exact commands and exit codes; the active
project and DAG counts before and after; every doctor finding; files changed per
repository; the protected-file and protected-lock checks; compatibility-mode
status; rollback behaviour; the migrated count and blocked repositories; and the
next incomplete phase.

Record failed attempts rather than erasing them. Stage 16's `lib` finding and
its misread direnv measurement are the model.

## Stop and ask the operator

- Phase 2 needs the four protected files released.
- A manifest placement decision is needed for `copyroom`, `docman` or
  `mypi-agent`.
- A detached migration branch has no clear destination.
- A caller still depends on an undocumented old CLI shape.
- A generated registry, DAG or retained generation appears to need hand editing.
- The machine needs a switch that sudo cannot perform.
- A removal would drop compatibility mode, compatibility registry writes,
  `registryDir` or a consumer pin without its gate passing.
- The live result changes when the Python path variables are cleared.

## Final report

Report files changed per repository; tests and exact results; the live active
generation, DAG count and digest; every doctor finding; commits and pushed
branches; confirmation that protected files were not staged; confirmation that
compatibility mode remains where its gate has not passed; the migrated count
and blocked repositories; the next incomplete phase; and any blocker needing
operator input.

Do not mark Project 038 complete until every §11 item has its own recorded
evidence.
