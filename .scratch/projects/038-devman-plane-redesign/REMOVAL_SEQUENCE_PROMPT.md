# Project 038 — clean-session prompt for the §11 removal sequence

Copy the text below into a clean implementation session.

---

You are continuing Project 038: the Devman machine-plane redesign.

Do not restart Project 038. Do not repeat the migration, the comparison, the
A-to-C bridge, the Vendomat canary, the B extraction, or the Stage 17 fleet
cutover. All of that is complete and deployed.

Your goal is the **§11 removal sequence**: four gated removals, worked one at a
time, each with its own evidence and its own commit. Do not batch them.

`IMPLEMENTATION_GUIDE.md` §11 is the list. Note the numbering: the log calls it
"§11", and it is the implementation guide's §11, not `CONCEPT.md`'s.

## Repositories

~~~sh
export DM_ROOT=/home/andrew/Documents/Projects/devman
export VM_ROOT=/home/andrew/Documents/Projects/vendomat
export RM_ROOT=/home/andrew/Documents/Projects/repoman
export NM_ROOT=/home/andrew/Documents/Projects/nix-meta
export DM_POLICY_ROOT=$DM_ROOT
cd "$DM_ROOT"
~~~

The Devman branch is `038-fixup-and-fanout`. Continue from it. Do not create a
new branch from stale main. nix-meta commits go direct to `main`, no PR.

## Read before action

~~~text
$DM_ROOT/AGENTS.md
$DM_ROOT/AGENTS_GUIDE.md
$DM_ROOT/.scratch/projects/025-the-link-plane/CONCEPT.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/CONCEPT.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_GUIDE.md
$DM_ROOT/.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md
$VM_ROOT/AGENTS.md
$RM_ROOT/AGENTS.md
$NM_ROOT/AGENTS.md
~~~

Read implementation-log **Stages 16 and 17 in full**. They record what the link
work built, what it measured, and what it deliberately left. Stages 11 to 15
are background.

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

## Where the link work landed

There is **one reconciler**. The independent component is `src/devman_link/`,
with the pure contract in `src/devman_contract/`. `nix/link-adapter.nix` builds
those two alone, from `packaging/devman-link/pyproject.toml`, and its install
check runs a real `status` against a repository no registry has heard of.

`services.devman-dagu.installLinkAdapter` defaults to true, so
`/run/current-system/sw/bin/devman-link` is the component. The `devman` package
installs `devman` and `devman-project` only — it no longer ships a `devman-link`
that shadows the machine one inside a devenv shell.

Every repository uses the component at shell entry. `devman.useLinkAdapter` is
gone, and so is the renderer's copy. **The rollback is the pin**: a repository
that needs the old behaviour pins a Devman revision before `ff8dbd1`.

`src/devman/link.py` is a 42-line re-export with one caller, `devman.watch`.
`devman.identity` and `devman.contract` are re-exports too. None of them holds
an implementation.

## Non-negotiable safety rules

Two Devman files have protected, unrelated worktree changes:

~~~text
src/devman/watch.py
tests/unit/test_watch.py
~~~

They are formatter reflows from the `devman/format` watcher. Do not modify,
stage, discard, or commit them while they remain dirty.

**This blocks one piece of cleanup, and only one.** `src/devman/link.py` exists
solely so `devman.watch` keeps importing a reconciler. Folding it into
`devman.watch` and deleting the module needs that file released. Ask the
operator; do not edit it, and do not leave a dead module behind instead.

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
explicit raw Git fallback below. Do not force-push.

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

**Stage 17 measured this. Re-measure rather than copy it:**

~~~text
doctor          exit 1, mode plane, 4 findings
active pointer  generations/2, 46 projects, 146 DAG files
DAG digest      5acf4cc3be671f7118643e33eb01f37d708ed780ee228027956dce0dcee6022b
dagu ls         147 lines
unit suite      604 passed
~~~

The four doctor findings are `flora-037-part-e:devenv.local.nix: create`;
dirty, unpinned Vendomat source; dirty, unpinned RepoMan source; and the
unpinned `git+file:` repair advice. Doctor exit 1 is a finding result. A
passing test does not erase a finding. Do not repair unrelated drift.

## The §11 removals

Item 1 is done: Stage 14 removed `scripts.devman-resync.exec`.

| Item | What | Gate |
|---|---|---|
| 2 | duplicate resolver or renderer code | every consumer off the compatibility resolver |
| 3 | routine consumer Devman lock updates | the central overlay stops requiring `config.devman.project` |
| 4 | compatibility registry writes | a supported replacement for the remaining consumers |
| 5 | compatibility mode | the last supported consumer leaves it |
| 6 | obsolete documentation and flags | follows the others |

**Item 3 is the keystone, and it has a measured blocker.** Stage 14 probed it on
Vendomat: removing the `devman` input, the module import and the option block
made shell entry fail at Nix evaluation with `attribute 'devman' missing`,
because `~/.config/devman/projects/vendomat/devenv.local.nix` reads
`config.devman.project`. The edits were reverted. Items 2 and 4 sit behind it.

**Do not retry that probe without a design first.** The question is how the
central file gets its project identity without the Devman Nix module, given
that the file itself is the one human-authored link declaration and must not
gain a second format (025, and Project 038's A-to-C guide §5.2). Two shapes
worth weighing, and there may be better ones:

- The adapter already supplies `config` when it evaluates the file. If the
  *devenv* side also supplied it, the module import would no longer be what
  makes `config.devman.project` resolve.
- The central file could stop reading `config.devman.project` and take the
  project as a function argument the adapter passes, keeping one `devman.link`
  attribute set and one file path.

Write the design into the log, with the failure it avoids, before changing a
consumer. Then probe one repository, not the fleet.

**Item 5 is blocked on operator decisions**: three manifest placements
(`copyroom`, `docman`, `mypi-agent`, whose identity lives in `dev/devenv.nix`),
seven detached-HEAD branch decisions, and the compatibility-only projects. Ask;
do not guess a placement.

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

A removal that drops the test count must say which tests went and why.

**Three traps that let a change pass locally and fail hermetically or silently:**

1. `base:test` runs `nix flake check`, whose `python-tests` fileset is
   `./src ./tests ./pyproject.toml ./groups ./nix/nixos-module.nix`. A new or
   renamed file outside it is invisible there. **The fileset reads the git
   tree, so an unstaged new file fails the hermetic check while `base:unit`
   passes.** Stage 17 hit exactly this.
2. `flake.nix`'s `shell-variable-unset` requires every new `devman_*=`
   assignment in `modules/devenv.nix` to appear in the `unset` block, in the
   same commit. `hook-path-refusal` cuts a refusal block out by literal path.
3. `tests/unit/test_cli.py` asserts the parser and `handler()` name the same
   commands. Removing a command from one side must remove it from both.

`devman doctor` must exit 0 — or exit 1 with only the four known findings —
before a change to `modules/`, `groups/`, `nix/` or `src/devman/` is committed.

If nix-meta changes:

~~~sh
cd "$NM_ROOT"
nixos-rebuild build --flake .#server
SYS=$(readlink -f result)
readlink -f "$SYS/sw/bin/devman" "$SYS/sw/bin/devman-link"
~~~

**Sudo needs an interactive password and you cannot supply it.** Verify the
built system, commit and push the nix-meta change, then give the operator this
exact command:

~~~sh
sudo nixos-rebuild switch --flake .#server
~~~

If Vendomat files change: `cd "$VM_ROOT" && devenv shell -- testee verify --mode quick`.
If RepoMan files change: `cd "$RM_ROOT" && devenv tasks run -v base:check` and `base:test`.

## The canary, after every removal

~~~sh
cd /tmp
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
  status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"

env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman link \
  status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
~~~

Both must return 0 with five `ok` states and the central configuration path.
Then confirm the active pointer, project count, DAG count, DAG digest and
`dagu ls` line count are unchanged, and run doctor again.

**Run the fleet sweep in the shape the hook actually calls** — `status` with an
explicit `--project`, which is what the shell hook passes. Stage 16 swept
without it, three repositories refused, and that predicted nothing about shell
entry:

~~~sh
cd /tmp
for d in "$HOME/.config/devman/projects"/*/; do
  p=$(basename "$d"); r="/home/andrew/Documents/Projects/$p"
  [ -d "$r" ] || continue
  env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
    status --project "$p" --root "$r" --overlay "$HOME/.config/devman" >/dev/null 2>&1
  printf '%s %s\n' "$?" "$p"
done | sort | uniq -c -w2
~~~

**Stage 17 measured 51 repositories: 47 clean, 4 with ordinary drift, 0
refusals.** The four are `forgelab`, `image-gen-pipeline`, `lodestar` and
`repoman`. A new refusal is a regression; diagnose it before removing anything.

Two measurement traps recorded in the log, so you do not re-learn them:

- **Direnv re-enters the shell and repairs a broken link before an explicit
  entry runs.** Stage 16 misread this as the adapter reporting `ok` for a state
  it had not found. Run the hook's own script directly to see the true state.
- **Measure the live system from `/tmp`, not from a repository shell**, and
  clear both Python path variables. If a result changes when they are cleared,
  stop and diagnose environment shadowing before changing code.

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

Verify the staged name list excludes `src/devman/watch.py` and
`tests/unit/test_watch.py`. Verify RepoMan's staged list excludes `devenv.lock`.

Gitman is not on this repository's PATH, so use this explicit fallback:

~~~sh
git add -- <each-intended-path>
git diff --cached --check
git diff --cached --name-status
git commit -m "<message>"
git push origin 038-fixup-and-fanout
~~~

**Do not add a `Co-Authored-By` trailer, a "generated with" note, or any other
agent attribution to a commit message or a PR body.** End the message at its
last body paragraph.

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

**Record failed attempts rather than erasing them.** Stage 16's `lib` finding
and its misread direnv measurement, and Stage 17's three build failures, are
the model.

## Stop and ask the operator

- Folding `src/devman/link.py` into `devman.watch` needs that file released.
- A manifest placement decision is needed for `copyroom`, `docman` or
  `mypi-agent`.
- A detached migration branch has no clear destination.
- Item 3 needs a design decision about how the central file gets its identity.
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
