# Lockfile churn investigation — 2026-10-03

## Finding

The installed `devenv 2.2.2+b8030c5` validates `devenv.lock` during startup.
It writes a new lock when the current inputs and locked inputs differ. A stale
`shellij` input caused the measured rewrite in `image-gen-pipeline`. The locked
`devenv` revision did not change. The CLI and module revision mismatch did not
cause this measured rewrite.

The installed source calls `validate_and_load` during startup
([startup](https://github.com/cachix/devenv/blob/b8030c5/devenv/src/devenv/mod.rs)).
The validator computes a lock from current inputs and writes it only when the
lock graph changes
([lock validator](https://github.com/cachix/devenv/blob/b8030c5/devenv-nix-backend/src/lib.rs)).
The local binary reported `devenv 2.2.2+b8030c5`.

## Live test

`image-gen-pipeline` was clean before the test. Its tracked `devenv.yaml`
declared `nixpkgs`. Its lock also named `shellij` as a root input. The first
`devenv shell -- gitman status` changed `devenv.lock`:

```diff
     "root": {
       "inputs": {
         "devenv": "devenv",
-        "nixpkgs": "nixpkgs",
-        "shellij": "shellij"
-      }
-    },
-    "shellij": {
-      "flake": false,
-      "locked": {
-        "type": "git",
-        "url": "file:///home/andrew/Documents/Projects/shellij"
-      },
-      "original": {
-        "type": "git",
-        "url": "file:///home/andrew/Documents/Projects/shellij"
+        "nixpkgs": "nixpkgs"
       }
     }
```

The lock hash changed from `cd60507af270` to `3838d7aeadbb`. The `devenv`
node stayed at `0fd5e6d3a9b2`. `uv.lock` stayed at `4918aeba6ce3`.
A second `devenv shell -- true` left both hashes unchanged. `diff -u` against
the first entry's lock returned no output. This proves a fixpoint for this
repository and these inputs. It does not prove every repository has one.

`boomtube` ran `devenv:python:uv` during `devenv shell -- gitman status`.
Both lockfile hashes stayed unchanged. devenv warned that its CLI was newer
than the locked module and suggested `devenv update`. That mismatch did not
rewrite this repository's lock on entry.

`fornix` refused shell activation because SecretSpec required a reason.
Neither lockfile changed. No further probe used this repository.

For all three repositories, `git status --short` returned no paths at the end.
Both current lockfile hashes matched `git show main:<lockfile>` for each
repository. The test restored `image-gen-pipeline/devenv.lock` with a plain
file write from `main`. No lane, commit, or push was made.

## Scope and separate uv path

A read-only scan found 60 parseable `devenv.lock` files with 26 distinct
locked `devenv` revisions. Fifty-nine had a `devenv.yaml`; `nix-meta` did not.
One additional lock (`loci.nvim`) was invalid JSON.
Twenty-five parseable locks had a root `shellij` input absent from both their
current `devenv.yaml` and any active `devenv.local.yaml`. These are candidates,
not 25 live confirmations. The different revisions rule out one shared pin
as the explanation for this specific stale-input pattern.

devenv's Python module runs `uv sync` from its `devenv:python:uv` task when
`languages.python.uv.sync.enable` is true and its checksum changes
([Python module](https://github.com/cachix/devenv/blob/b8030c5/src/modules/languages/python/default.nix)).
uv can update `uv.lock` during `uv sync` or `uv run` when project metadata
requires a new resolution
([uv locking guide](https://docs.astral.sh/uv/concepts/projects/sync/)).
The boomtube task ran without a lock change. No `uv.lock` rewrite was
reproduced here, so the exact cause of the earlier `uv.lock` reports remains
unconfirmed. Some reported repositories do not enable `uv.sync` in their own
`devenv.nix`; imported modules or other entry tasks need review there.

## Recommendation

Use fix **(a)** for `devenv.lock`: accept the normalized lock in one
lockfile-only lane per affected repository, after two shell entries give the
same content. Check each repository's active local input overlay before the
first entry. Verify a further shell entry after the commit. This recommendation
rests on the measured fixpoint in `image-gen-pipeline`; each remaining
repository still needs its own check.

The installed `devenv shell --help` exposes no lock-update suppression flag.
The startup validator has no read-only branch. `--offline` changes fetching,
not validation. No supported suppression control was found for fix **(b)**.
Fix **(c)** would update many independent pins but would not remove an
undeclared `shellij` root input. Fix **(d)** already ignores gitignored paths
in gitman's hook snapshot; the lockfiles are tracked
([gitman hook source](../../../../gitman/src/gitman/hooks.py)). Fix **(e)**
failed in boomtube commit `e8c8f131`, which contains an unrelated 84-line
`devenv.lock` change under a docs message. Do not rewrite that commit.

Treat `uv.lock` as a separate investigation. If a repository reproduces an
entry-time uv change, capture the diff and identify the invoking task. uv
offers `--locked` to fail instead of changing the lock, and devenv exposes
`languages.python.uv.sync.arguments`; test that negative case before adopting
it ([uv guide](https://docs.astral.sh/uv/concepts/projects/sync/),
[devenv Python options](https://devenv.sh/languages/python/)).

## Implementation — 2026-10-03

The follow-up assessed all 25 locks whose root inputs still listed `shellij`.
For each committed lock, the first shell entry normalized the graph. A second
entry and a post-land entry left the lock content unchanged. Checks named below
passed. `uv.lock` stayed unchanged in these repositories. The operator approved
the pushes. All 13 lock commits are now on origin.

| Repository | Local `main` commit | Verification |
|---|---|---|
| agentman | `7dd6d12607c72815f28d0a1e85c2afdea2b5f99f` | `repoman doctor` exit 0 |
| argentic | `cd5abb9b4abdb6da32ac544feb40b546f3aa7d16` | `base:check` |
| cairn | `12db2adc7ff820d1e41692bf863648423bec8cfc` | `base:check` |
| embeddy | `25f4cbf4d89178ddc0adc273f6a6cedd974fa86f` | `base:check` |
| eventic | `08a5f644f22783af3e87c5ce394d16dfdc12f798` | `base:check` |
| flora | `dc6043308beb6adb7e9cd5235e48f0864be386ef` | `base:check` |
| fornix | `308ab37b11067d72189a78144c11864a57723245` | `base:check` |
| image-gen-pipeline | `9414a076693a398120de2e0877064aaffafa4b65` | `base:check` |
| llgym | `eb9f644595a61f0fdb6b1e00bf5dff022f332abc` | `base:check` |
| nix-desktop | `f3d36d76bf14fb5282da2fc3eac07ae406342a84` | `base:check`, `base:test` |
| nix-paseo | `8c2f8157c4567535e620a328d8ba67657626e7f8` | `base:check`, `base:test`, `nix flake show` |
| observantic | `7ede25a59980aaf0deb837551568a40cd5c71098` | `base:check`, `base:test`: 103 passed, 4 skipped |
| pydantree | `abaf884a09a7716a74e1eb21c30bb402a25e6ae9` | lint, type checks, 379 passed, 1 expected failure |

Some broad diffs removed unreachable `home-manager` and Nixpkgs nodes and
renumbered aliases. The agents checked the retained declared input revisions
before landing. The declared pins did not change. A `gitman status` after each
land reported a canonical tree with no lanes. `gitman doctor` also reported
healthy in the four repositories that briefly showed a colocated-ref warning
after land.

`flora-core` has a described lock-only lane. Its `base:check` fails on an
existing Ruff import-order error in `src/flora_core/__init__.py`, so the lane
was not landed. Existing lanes or conflicts blocked `forgelab`, `lodestar`,
`nix-nvim`, `nixvim`, and `pyjutsu`. The agents restored all probe writes in
those repositories after the final shell entry. `PyGentic` could not load its
existing lock because `flake-compat` points to a missing node. `docman` has
invalid `devenv.yaml` syntax. Its attempted repair was abandoned and restored.
The locks in `browsee`, `mypi-agent`, `nixbuild`, and `testee` are ignored or
untracked, so shell normalization cannot contaminate a tracked commit there.
The agents restored their ignored lock files to the pre-probe bytes.

The follow-up reproduced a separate `uv.lock` change in `interplay`.
Its `enterShell` hook ran `uv sync --extra dev`; uv changed the local
`loci-core` dependency version from 0.4.3 to 0.4.5. A second entry made no
change. Commit `d043c578b5633a18f06e8fa7bc005e9e81144da4` refreshed
`uv.lock` and changed the hook to `uv sync --locked --extra dev`. A negative
test with the old lock showed uv's stale-lock error and left the lock hash
unchanged. With the new lock, shell entry succeeded and left both locks
unchanged. `base:check` passed; `base:test` passed 158 tests. The hook keeps
its existing warning behavior when sync fails, and its banner now tells the
user to run `uv lock` after dependency metadata changes. uv documents that
[`--locked` refuses to update a stale lock](https://docs.astral.sh/uv/concepts/projects/sync/).

`boomtube`, `devman`, `gitman`, `linkman`, and `pytuin` were also entered during
the follow-up. Their lock hashes did not change. `pytuin` has an unrelated
existing lane; the follow-up did not edit it. The devman report and prompt
remain untracked, as the kickoff prompt requires.

The operator also approved the `interplay` push. `gitman push` succeeded for
all 14 completed branches. A post-push `gitman status` in each repository
reported CANONICAL, zero lanes, and `main` in sync with origin. Earlier local
commits on ahead branches were included in the approved pushes.

## Remaining work — 2026-10-03

This section records the follow-up pass. It supersedes the earlier paragraph
above that described the remaining repositories as untouched or abandoned.
Each repository's `AGENTS.md` was read. Before shell-entry probes, the operator
saved the lock bytes and hashes. The probe sequence was `devenv shell --
gitman status`, a second shell entry, the repository's real check tasks, and a
post-land shell entry where a fix landed. `uv.lock` was checked independently.
`gitman status` supplied lane and trunk state. Input revisions were compared
before accepting graph pruning. No raw Git or jj command changed a worktree or
history.

### flora-core

The starting lock hash was
`0fcaba404dce55109d5a837625b23b1609d7a97538431b2f9252e281f2f73239`; the
starting `uv.lock` hash was
`de3753d2ae8359487d4ad031bf2f24226cac750b89e28ac941b3f551c8fec6ba`. The
repository instructions referenced a retired skill path that was absent from
this checkout; the available repoman skill was read. The
first shell entry did not change either file. `base:check` initially failed
with Ruff `I001` in `src/flora_core/__init__.py`. The import was moved into
sorted order, and a stale `devenv.nix` comment was corrected. `base:check` and
`base:test` then passed; `base:test` ran 275 tests. The checks were repeated
after the lock lane sync and passed again. The check commands were
`devenv tasks run -v base:check` and `devenv tasks run -v base:test`.

The lock diff removes only the undeclared root `shellij` edge and its file
input node. The declared revisions stayed fixed: devenv
`190959a9a4bb52d4802f076a90c3c4e3aa2e6fa2`, nixpkgs
`256551e45f6303e142ab4a98be1bf243feb77dc0`, nixpkgs-src
`c8f90650c15282fa8656a041bfbbd2403997a9a7`, and repoman
`57473ad47365da67d7c4ad666cfc37facf94d21c`. The second shell entry and the
post-land entry left both lockfiles unchanged.

The source fix was split with `gitman split --paths
src/flora_core/__init__.py --paths devenv.nix --into flora-core-import-order
-m "fix: sort flora_core public imports"`. Gitman classified `devenv.lock` as
a foreign path while the source lane was active. The source commit therefore
also contains the normalized lock:
`b9785ddbc301b7dd9133acdb8dffc08d7fc8ba1d` (`fix: sort flora_core public
imports`). The described lock lane then had no remaining diff and was landed
as empty commit `fe74aaffd28fee10b8acaecf6be69a8351819d27`
(`chore: normalize devenv lock`). `gitman doctor` reported healthy; final
`gitman status` was canonical with zero lanes and `main` in sync with origin.
The two commits were pushed by `gitman push`. No unrelated local commits were
included. Both lockfiles still match their starting hashes after the final
shell entry.

### forgelab

The initial `devenv.lock` hash was
`7dca9898f6e5b4060664cfb66cb6bfe8c04bb495360c96547ff93296dfce866e`; the first shell entry produced
`707ac4c83069fa83f6e7ec97881767371bc326e2b63453b18db21629fd062f90`. The exact lock diff
removes the root `shellij` edge and its input node. Retained declared input
revisions did not change, and there is no `uv.lock`. The second and post-land
entries were stable. `base:check` passed. `base:test` did not pass: 45 of 85
errors reported `ModuleNotFoundError: No module named 'pyjutsu'`.

The check command was `devenv tasks run -v base:check && devenv tasks run -v
base:test`. `gitman push` pushed the lock commit.

The lock-only commit `62f1cebe5f0fdfbcc10dcf2570a0fb3816af6b5b` was pushed;
origin is in sync. The existing `adopted-f6dc8109` lane remains intact. Its
`repoman.lock` has a two-sided conflict, and Gitman reports one commit behind.
The owner must choose or prepare the intended `repoman.lock` resolution before
that lane can sync or land. No unrelated lane work was changed.

### lodestar

The initial `devenv.lock` hash was
`8c19adf999a849ccf5af46203d1405f8aef71e060439edce99869c5db291c645`; the first shell entry produced
`849b35c8e456c24b157e5397e730b8739e8a45b1e2c6799b4219fc4bca6f8d59`. It removed the undeclared `shellij` input only; retained declared
input revisions did not change. The initial `uv.lock` hash was
`15bdaa7f3298728247870c6d6f6fff7e2433af5e7949f1c0d3f5401326972d31`.
That file already differed from trunk before the probe (including a testee
version change from 0.2.0 to 0.3.0), so it was preserved in a separate
`preexisting-uv-lock` lane. Both locks were stable on the second and post-land
entries. `base:check` and `base:test` passed; tests reported 59 passed and 16
skipped.

The check command was `devenv tasks run -v base:check && devenv tasks run -v
base:test`. `gitman push` pushed the lock commit.

Lock commit `b491148acecb8cfef8b5fe552f94e7a55a70cf57` was pushed; origin is
in sync. The pre-existing `preexisting-wip` lane remains intact with 87 files
(+2891/−1) and is 53 commits behind. The separate `preexisting-uv-lock` lane
also remains unpushed. Those lanes need their owner's review and sync plan;
neither was folded into the lock commit.

### nix-nvim

The initial lock hash was
`86eaad87878dc1a2a3228106cac401b7b781eb5c53c4f6a7fb083e61c3726791`; the first shell entry produced
`d35d131bb340c0b09cc2402db145a933bbf5c5ad5e9c7ec31e7cbed1a854b8fd`. It removed the root `shellij` edge and node only. The pinned devenv, nixpkgs, and repoman revisions
were unchanged. No `uv.lock` exists. The second and post-land entries were
stable. `base:check` and `base:test` passed.

The check commands were `devenv tasks run -v base:check` and
`devenv tasks run -v base:test`; `gitman land` and `gitman push` landed and
pushed the lock commit.

Lock commit `edac5777c3f26940516d11628ede2d9efce2edce` was pushed; origin is
in sync. The `stray-devenv` lane remains intact (3 files, +67/−77; 17 commits
behind). Gitman sync reported conflicts in `devenv.lock`, `devenv.nix`, and
`devenv.yaml`. The owner must decide how the unreviewed lock and YAML edits
combine with the normalized lock and recent Loci/devenv changes.

### nixvim

The initial lock hash was
`d7946d5b8715b1a1e35d189fead87aa01f67c77952f9d7c902dcedb73501bd2b`; the first shell entry produced
`7c16e4f2a930ee848539989362f452226fb42718a06e494c465c5113d536c43f`. It pruned unreachable home-manager, shellij, and duplicate
nixpkgs nodes. The root nixpkgs and devenv revisions did not change. No
`uv.lock` exists. The second and post-land
entries were stable. `base:check` and `base:test` passed. Nix reported all
flake checks passed, with the existing warning about unknown output
`homeManagerModules`. The checks were `devenv tasks run -v base:check` and
`devenv tasks run -v base:test`; `gitman land` and `gitman push` landed and
pushed the lock commit.

Lock commit `314cc61bc8e863747c5bd8db8010d36fdcf71d56` was pushed; origin is
in sync. The existing `038-devman-preexisting-nixvim` lane remains intact
(30 files, +30,441/−11; 5 commits behind). Its lane devenv repeatedly failed,
and Gitman reported “repo not initialized.” A later attempt to switch the
active worktree back to main could not start Gitman because shell evaluation
failed first with duplicate option `devman.link` declared in
`/run/current-system/sw/share/devman/link-module.nix`. The owner must restore
the Gitman/devman initialization and remove the duplicate option declaration
before this lane can sync or the worktree can return to main. The lane content
remains intact and unresolved; the worktree is still switched to it.

Before the failed switch attempt, the lane `devenv.lock` was saved at hash
`c37d157c35790cf869b3297c6c6641b4542c38e5f83eb208125c16b73d19288d`. Two
shell entries both failed evaluation and produced hash
`99558441f849cc6bef8d3d5ca45208ae892b163b02300faf607d04296ecef6e4`. Their
lock diff changed the `devman` input from `refs/tags/v0.4.0`, revision
`49ac3016db1c548908a63f8bb58f368265b568b9`, to `refs/tags/v0.5.1`, revision
`8311f1434d6959ab0f50533cada8a451f5eab70e`; no uv lock exists. The saved lock
bytes were restored after the second probe, so the lane remains at its
original hash.

### pyjutsu

The first shell entry changed `devenv.lock` from
`9af97556a458f2758b2ae5bd961d91627c2501127ba5a9655b5daa47b00f0607` to
`9e8f4486b50d23675649d2816ccd5c5294d54a075c775587d63d899f41d08aa0`, removing the root `shellij` edge and
unreachable home-manager and nixpkgs_3 nodes. Shared input revisions were
unchanged. `uv.lock` stayed at
`c7c7a786e7b94fbf566b94e1d31b0f943c155ac66d92d59d2229794552ca02ad`. A second entry and the post-land
entry left both locks stable. `base:check` passed. `base:test` passed the
build, pytest, and 7 Rust tests. Gitman reported 24 pre-existing lanes; they
were preserved, and `gitman doctor` reported healthy.

The verification command was `SECRETSPEC_REASON='normalize devenv lockfiles'
devenv shell -- bash -lc 'devenv tasks run -v base:check && devenv tasks run
-v base:test'`. The land and push command was `SECRETSPEC_REASON='normalize
devenv lockfiles' devenv shell -- bash -lc 'gitman describe -m "chore:
normalize devenv lock" && gitman land && gitman push && gitman status'`.
Commit `78689c3331c58291f5d9bf69687d68167ab6f17f` (`chore: normalize devenv
lock`) was landed and pushed; origin is in sync.

### PyGentic

The initial `devenv.lock` hash was
`14fa0518c613f94f8a7207499d3a08f5b36930dbb2d20c931e981d4fad05d91d`; `uv.lock`
was `a8d9555ae618480e9cf7d8072b5c23501080b5becf55f7a6dd4f760021f7e736`. Shell
activation failed because the lock referenced missing node `flake-compat`.
`devenv update pre-commit-hooks` failed for the same reason. The broken
`pre-commit-hooks` node pointed at nixpkgs revision
`18b9261cb3294b6d2a06d03f96872827b8fe2698`, but its referenced
`flake-compat` and `gitignore` nodes were absent. The repair restored the
previously committed, valid pre-commit subgraph from `e9bdf99`: pre-commit
revision `623c56286de5a3193aa38891a6991b28f9bab056`, flake-compat revision
`9100a0f413b0c601e0533d1d94ffd501ce2e7885`, gitignore revision
`637db329424fd7e46cf4185293b9cc8c88c95394`, and the then-current shared
nixpkgs revision `aff8a0b28396750446e5537a96461bc4facdb287`. No unexplained
input upgrade was made. Shell entry then pruned stale shellij, home-manager,
and nixpkgs_3 nodes without changing other declared revisions. The resulting
lock hash is
`f65ab27a8aaa3217528afa32ab61c68f4d94bb727cabb170920c35254d43ddaa`; `uv.lock`
remained unchanged. The second shell entry and later checks preserved both.

The repair is isolated in described Gitman lane `043-devenv-lock`; the
pre-existing citation-documentation lane was preserved. Its diff restores
the valid pre-commit/flake-compat/gitignore subgraph and prunes the stale
shellij closure. The repository's task declarations are commented out; there
is no real check task. `devenv test` exits 0 but reports
`devenv:enterTest Not implemented` and one skipped test, so it is not a
passing gate. `repoman doctor` exits 2 because `REPOMAN_*` variables are
missing. The existing docs lane already records the no-working-verify-task
condition. The lock lane is not landed or pushed. The owner must provide or
approve a real repository verification gate before it can land. The
post-land check is therefore pending.

### docman

The initial ignored `devenv.lock` hash was
`222b215d7e26de914b222ecd8a21272107f8e88afb08f2e25ab942ef736f8503`; `uv.lock`
was `36cb638a4fe30fd7ca2bfacef96fb7cf378b73b85ee07fcf1d89c06062bf0b8c`. In
`devenv.yaml`, `imports: []` was followed by an indented `- ./dev`, which made
the file invalid. The intended import is `./dev`; the repair changed the
header to `imports:` and kept that item. After the edit, shell activation
succeeded. The first shell entry normalized the ignored lock to
`050ac0dbc576f62445be985f3bf0fc74031d1ace0f37d05589aa3df69cb93d02`, removing
the shellij root edge and node and pruning home-manager/nixpkgs_4. `uv.lock`
did not change. Later shell entries, checks, and the post-land entry preserved
both files.

`base:check` and `base:test` passed; tests reported 19 passed. The YAML change
was committed as `3bce98506c47f2dc5d8a99b68c5f011e20076309` (`fix: repair
devenv dev import list`) and pushed. Final Gitman status was canonical with
zero lanes and origin in sync. `devenv.lock` remains ignored by `.gitignore`
and untracked; it was not force-added and has no tracked-lock commit.
The lane used `gitman start --adopt-all`; Gitman described, landed, and pushed
the change. The checks were `devenv tasks run -v base:check` and
`devenv tasks run -v base:test`.

### Final state for this pass

| Repository | Work completed | Verification | Origin | Remaining blocker |
|---|---|---|---|---|
| flora-core | Ruff import order and normalized lock landed; both lockfiles unchanged on final shell entry | `base:check`, `base:test` (275); healthy doctor | In sync | None |
| forgelab | Lock normalized and landed; pre-existing lane preserved | `base:check`; `base:test` has 45 missing-pyjutsu errors | In sync | Owner must resolve `repoman.lock` conflict in `adopted-f6dc8109` |
| lodestar | Lock normalized and landed; prior uv and work lanes preserved | `base:check`; `base:test` (59 passed, 16 skipped) | In sync | Owner review/sync needed for 53-behind `preexisting-wip` and unpushed `preexisting-uv-lock` lanes |
| nix-nvim | Lock normalized and landed; existing lane preserved | `base:check`, `base:test` | In sync | Owner decision for three-file `stray-devenv` conflict (17 commits behind) |
| nixvim | Lock normalized and landed; existing lane preserved | `base:check`, `base:test`; lane shell now fails on duplicate `devman.link` | In sync | Restore Gitman/devman initialization and remove duplicate option declaration; worktree remains on unresolved lane |
| pyjutsu | Lock normalized and landed; 24 existing lanes preserved | `base:check`, `base:test`; healthy doctor | In sync | None for lock fix |
| PyGentic | Dangling lock graph repaired in isolated lane; no post-land probe | No usable repo check; `devenv test` skips unimplemented test; `repoman doctor` lacks env | Not pushed | Real verification gate required before land |
| docman | Invalid import syntax fixed and pushed; ignored lock left untracked | `base:check`, `base:test` (19) | In sync | None |

### Rechecked ignored and untracked locks

The four `AGENTS.md` files were read. The probes saved each lock's bytes and
hashes, ran two shell entries, checked `uv.lock` separately, and restored any
entry-time rewrite. The ignored/untracked policy has not changed, so no tracked
lock commit is needed. The probe command for browsee and mypi-agent was
`SECRETSPEC_REASON='normalize devenv lock' devenv shell -- sh -c 'gitman
status; sha256sum devenv.lock uv.lock 2>&1'`; nixbuild and testee used
`SECRETSPEC_REASON='normalize devenv lockfiles' devenv shell -- bash -lc
'gitman status; sha256sum devenv.lock uv.lock 2>&1'`.

| Repository | Current policy and probe result | Origin | Lock action |
|---|---|---|---|
| browsee | `.gitignore` lines 11–12 ignore both locks. `devenv.lock` stayed `cba1db88a0219bc7822bef3ead6e7ada71a2f3267e15532b3df096a288de5a29`; `uv.lock` stayed `c588315bd765628aee0a4c689ecec981739e3f8c01b90ad8a5ead9141752b6f5`. Diffs empty. | `main` `b9a8d3b55e49f782e304ca0baf694f66f8a6503e`, in sync; zero lanes | No commit |
| mypi-agent | `.gitignore` lines 11–12 ignore both locks. `devenv.lock` started at `a0c55b330b5bc12915aafb9562afec797b19bd8465211210c56315ab760813c5`, normalized to `6ac198971870abdca04193d72af306597ed90471ed42fe4711cf59351a1cafe6`, then was restored to the initial bytes. Diff removed home-manager, nixpkgs_2, and shellij nodes. `uv.lock` stayed at `01d06796c5623ee242f778ef746d55e534eca6231442362cab49f67480767b2b` and was also restored. | `main` `de71959125fa27420ab95feb6d61f7ea820e3eb9`, in sync; zero lanes | No commit |
| nixbuild | `.gitignore` line 4 ignores `devenv.lock`; `uv.lock` is absent. `devenv.lock` started at `6a0631a760a155620436134c3b386812ef2ab959ddea865a09b24464ae18fed5`, normalized to `2b65f9b1fee536206e575a0075c9553568d2f8037aabf35c6d08d0d2b1badeae`, then was restored to the initial bytes. Diff pruned stale shellij, home-manager, and nixpkgs nodes and renumbered aliases. Comparison of declared inputs showed no root revision change beyond the stale shellij removal. | `main` `85305722aa2f028182f3154b2760bb25c19f78ec`, in sync; zero lanes | No commit |
| testee | `.gitignore` lines 15–16 ignore both locks. `devenv.lock` started at `6a0631a760a155620436134c3b386812ef2ab959ddea865a09b24464ae18fed5`, normalized to `2b65f9b1fee536206e575a0075c9553568d2f8037aabf35c6d08d0d2b1badeae`, then was restored. The graph diff matched nixbuild's stale-input pruning and alias renumbering; declared revisions did not change except removal of stale shellij. `uv.lock` stayed at `888e306a2b4aea9d679f206d52f4e29dbecb75c06302516233cb62e6015eaa30` and was restored. | `main` `0335c7bea1394c491357bd658333dd73a9dedc8d`, in sync; zero lanes | No commit |

The agent probes ran no repository test tasks in these four repositories.
Startup emitted existing missing-playwright and agent-root warnings for
browsee and mypi-agent. All Gitman statuses were canonical with zero lanes.

The earlier-completed repositories remain complete: agentman, argentic, cairn,
embeddy, eventic, flora, fornix, image-gen-pipeline, llgym, nix-desktop,
nix-paseo, observantic, pydantree, and interplay. The locks in browsee,
mypi-agent, nixbuild, and testee remain outside tracked-lock commits because
they are ignored or untracked under current repository policy.

## Project status by repository

All 26 repositories in this project pass were checked against their
`AGENTS.md`. These instructions did not change the recorded lock fixes or
origin states. The completed nix-paseo checks include both required Nix
commands, `nix flake check` and `nix flake show`.

| Repository | Work and verification | Origin | Remaining blocker |
|---|---|---|---|
| agentman | Lock normalized; `repoman doctor` passed | In sync | None |
| argentic | Lock normalized; `base:check` passed | In sync | None |
| browsee | Locks remain ignored; two shell entries left both unchanged | In sync | None |
| cairn | Lock normalized; `base:check` passed | In sync | None |
| docman | Invalid `./dev` import fixed; `base:check`, `base:test` (19) passed; ignored lock not added | In sync | None |
| embeddy | Lock normalized; `base:check` passed | In sync | None |
| eventic | Lock normalized; `base:check` passed | In sync | None |
| flora | Lock normalized; `base:check` passed | In sync | None |
| flora-core | Ruff import order fixed; lock normalized; `base:check`, `base:test` (275) passed; both locks stable after landing | In sync | None; source commit also carries lock diff, followed by empty lock commit |
| forgelab | Lock normalized; `base:check` passed; `base:test` has 45 missing-pyjutsu errors | In sync | Owner must resolve `repoman.lock` conflict in `adopted-f6dc8109` |
| fornix | Lock normalized; `base:check` passed | In sync | None |
| image-gen-pipeline | Lock normalized; `base:check` passed | In sync | None |
| interplay | uv lock refreshed; `--locked` stale-lock guard verified; `base:check`, `base:test` (158) passed | In sync | None |
| llgym | Lock normalized; `base:check` passed | In sync | None |
| lodestar | Lock normalized; `base:check`, `base:test` (59 passed, 16 skipped) passed | In sync | Owner review/sync for 53-behind `preexisting-wip` and unpushed `preexisting-uv-lock` lanes |
| mypi-agent | Ignored lock normalized on entry, then restored to original bytes; uv lock unchanged | In sync | None; no tracked lock policy |
| nix-desktop | Lock normalized; `base:check`, `base:test` passed | In sync | None |
| nix-nvim | Lock normalized; `base:check`, `base:test` passed | In sync | Owner decision for three-file `stray-devenv` conflict (17 commits behind) |
| nix-paseo | Lock normalized; `base:check`, `base:test`, `nix flake show` passed | In sync | None |
| nixbuild | Ignored lock normalized on entry, then restored; no uv lock | In sync | None; no tracked lock policy |
| nixvim | Lock normalized; checks passed; saved lane lock restored after failed shell probes | In sync | Resolve duplicate `devman.link` option so Gitman can start; worktree remains on intact unresolved lane |
| observantic | Lock normalized; `base:check`, `base:test` (103 passed, 4 skipped) passed | In sync | None |
| pydantree | Lock normalized; lint/type checks and 379 tests passed, 1 expected failure | In sync | None |
| pyjutsu | Lock normalized; `base:check`, `base:test` and 7 Rust tests passed | In sync | None for lock fix |
| PyGentic | Dangling graph repaired in isolated lane; `devenv test` skips unimplemented test | Not pushed | Real verification gate required before land |
| testee | Ignored lock normalized on entry, then restored; uv lock restored unchanged | In sync | None; no tracked lock policy |

The report and kickoff prompt were untracked at the end of the original
investigation. The user later authorized this follow-up to record both files in
the Devman scratch project. The lock-churn findings remain intact.
