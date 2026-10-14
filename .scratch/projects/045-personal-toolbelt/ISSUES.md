# Issues — personal toolbelt cutover

Date: 2026-10-13.

## Keep RepoMan router skills in the central overlay

The 23 `repoman/SKILL.md` files live under
`~/.config/devman/projects/<project>/agents/skills/`. Project `.agents` links
expose these central files. They are not tracked copies inside project repos.
Repoman generates each skill from that repo's `.repoman/project.toml` roster.
The manager list therefore records project-specific interaction capabilities.
Keep these files until RepoMan gains a central output contract that preserves
the same roster information and doctor checks.

## Keep Gitman workspace state

The active `.gitman/` directories contain local Markdown work and some workspace
data. The current Gitman uses `.gitman/workspaces/`. Do not remove these
directories as stale config. The current Gitman does not read project-root
`gitman.toml` files.

Gitman commit `81883af` rewrote the CLI as a two-command jj workspace helper
and removed its release module and config reader. The current CLI exposes
`work` and `done`; project `[publish]` tables and comments that say
`gitman release` are retired. LinkMan, Pyjutsu, and loci.nvim still contain
such comments. Their release-tag workflows need a separate project-owned
update; deleting the retired config does not change existing tags or pins.

DevMan still reads `~/.config/devman/gitman.toml` to select the central overlay's
trunk. Its `main` value matches DevMan's fallback, but the file remains a live
configuration contract. Keep it until DevMan replaces that setting.

## Keep workspace snapshots until their work is reviewed

The audit found 80 `.worktrees/` copies, two `.gitman/workspaces/` copies, and
three copies under `gitman-workspaces/`. They are snapshots inside separate
workspace checkouts, not root config in the canonical project checkouts. Some
workspaces have uncommitted changes or stale jj working copies. Leave these
files until each workspace is resumed or discarded; the current cleanup
removes the active project-root configs.

## Defer `nix-meta-channel4/gitman.toml`

`nix-meta-channel4` has a large uncommitted initial import, including a staged
`gitman.toml`. Do not edit that checkout during this cleanup. The canonical
machine config is `nix-meta`.

## LinkMan Nix package omits Mancore

The LinkMan `v0.1.1` Nix package omits its declared Mancore runtime dependency.
The standalone CLI fails to import without it. `nix-meta` pins Mancore `v0.1.0`
and adds it to the LinkMan Python application at package construction time.
The complete `server` system build passes with this adjustment. This packaging
issue does not block the host install.

## Leave alternate nix-meta workspaces untouched

`gitman-workspaces/` contains old nix-meta workspace branches. Two clean
workspaces still carry historical `gitman.toml` files. Other workspaces contain
unfinished changes, and one workspace has a stale jj working copy. The
`devman-testee-audit` directory is not a jj workspace. These are not the
canonical checkout, so leave them unchanged and review them when their branches
are resumed or discarded.

## Preserve existing CopyRoom previews during audit

Before this migration, CopyRoom already had pending preview state for
`agentman` and `flora-qc` under `.copyroom-previews/`, with journals in each
project's `.copyroom-local/journal`. At that point, both were preserved because
their source would restore the RepoMan input. The final section records the
fresh updates and the safe discard of those obsolete previews.

## Cleanup counts

The current Gitman no longer reads project-root `gitman.toml` files. The earlier
inventory counted 61 tracked project-root configs and one in `template-nix`; a
wider history scan found 65 jj repositories with a historical file plus the
non-jj `nix-meta-channel4` repo. These counts cover different scopes. The
current immediate-root scan finds four physical files:
`nix-meta-channel4/gitman.toml`, `terminal-state/gitman.toml`,
`testee/gitman.toml`, and `webdantic/gitman.toml`. `nix-meta-channel4` remains
because that checkout has unrelated staged work. The other three remain on
preserved active worktrees; their deletion commits are already pushed on `main`,
while their active branches hold unrelated changes. The `template-nix` file is
removed. `atuout` was already deleted before this task and was not changed.
DevMan's central `~/.config/devman/gitman.toml` remains because DevMan reads it.
The file sets `trunk = "main"`, which matches the fallback. `template-py` has
no root config file.

## 2026-10-13: project tool pin migration

Removed per-project RepoMan module pins from 16 consumers and moved their
module imports into the central Devman overlays. Removed the old tagged Devman
module input from mnemonix and its local RepoMan path input. Added
`.devman/project.toml` plus `base:check` and `base:test` task bodies to mnemonix,
so the link-only host module can read project identity and the base group has
its required tasks.

`devenv-py` no longer pins RepoMan or CopyRoom packages in `devenv.nix`. Its
central overlay imports the installed RepoMan module. `mancore` no longer pins
RepoMan or Vendomat modules, or Vendomat's nested RepoMan, CopyRoom, and Gitman
inputs. Its central overlay imports the installed Devman link, RepoMan, and
Vendomat consumer modules. The imports preserve `.repoman/project.toml` and the
`vendor.toolchain.enable` project option. They also preserve Testee checks and
all repository-owned task bodies.

Removed pydantree's ignored `devenv.local.yaml` path override to the devman
checkout. The project already uses the machine-installed link module from its
central overlay.

`devenv eval shell.drvPath` passed for 19 changed consumers: agentman,
argentic, devenv-py, eventic, flora, flora-core, flora-qc, forgelab,
inferference, linkman, llgym, mancore, mnemonix, poddantic, pyllij,
scopeman, shellij, talkee, and pydantree. Testee input pins remain in
repositories whose tests use Testee. Fifteen touched consumers kept their
existing Testee lock nodes. Eventic kept its declared Testee input and gained
the missing lock node during eval. Forgelab and mnemonix have no Testee input.

The host Testee `0.7.0` runner supports project modules pinned to `0.6.x`.
The `0.6.1` module emits supported manifest schemas and does not install a
runner in the project environment. The project pin therefore locks the module
that defines its checks, while nix-meta supplies one compatible CLI version.
Avoid restoring `0.5.x` pins; that module adds runner behavior to the project
environment and predates commit verdicts.

The central overlay now imports the installed RepoMan module in 18 project
overlays. The local merge is `e3cbe249`; it includes the reviewed overlay
change and preserves the existing active local changes. The
`~/.config/devman` checkout has no Git remote, so this local configuration
cannot be pushed. Its active files now point to
`/run/current-system/sw/share/repoman/module/devenv.nix`.

### Retained references

- `repoman` keeps its `path:./modules` input to develop and test its own
  module from the working tree. This is self-hosting, not a consumer version pin.
- `nix-systems` keeps its Vendomat input because its AGENTS.md defines Vendomat
  as the machine-role composition dependency. It has no Devman project overlay.
- `vendomat-demo` remains a standalone Vendomat example, outside the personal
  Devman overlay.
- `nix-meta-channel4` and `nix-terminal` still carry old machine-config Devman
  and RepoMan references. `nix-meta` is canonical; these alternate machine
  configs were outside the project-consumer edit and need the archive decision.

## 2026-10-13: CopyRoom answer migration

Twenty tracked `.copyroom-local.json` markers retained 62 retired RepoMan or
Devman answer values. CopyRoom stores normalized answers in both the marker's
top-level fields and `layers.base`; these fields are changed only through its
update flow. The promoted Templateer sources now omit those fields. Preserve
all Testee answers because these are project test dependencies.

Argentic's base layer update applied from
`/tmp/copyroom-toolbelt-argentic-base-20261013-001`. CopyRoom status reports no
conflicts or pending preview, and the marker retains its Testee answer. Its
preview conflict resolution retained active project-owned files and reviewed
the merged README update.

Pytuin's first preview at `/tmp/copyroom-toolbelt-pytuin-base-20261013-001`
had conflicts in `.gitignore`, `AGENTS.md`, `README.md`, `devenv.nix`, and
`devenv.yaml`; it was discarded. A second preview at
`/tmp/copyroom-toolbelt-pytuin-base-20261013-002` resolved those conflicts with
the active project files. Its reviewed diff changed only `.copyroom-local.json`,
removed both `repoman_ref` answer copies and the template pin, and retained
`testee_ref`. That preview applied. The source digest includes template-py's
`cbb54b1` Testee CLI guidance correction.

The Nix module layer update applied in mnemonix, nix-desktop, nix-nvim,
nix-paseo, and nix-secrets. Each reviewed preview changed only its marker,
removed the module layer's `devman_ref` and `repoman_dev_root` answers and
template pin, and preserved project module files.

The initial Nix base-layer update failed with an output path collision because
the base source emits `.devman/project.toml`, which each repository already
owns. CopyRoom now supports repeated `--omit-path` values per layer. Commit
`c4ee8f41` adds that feature. `nix-meta` pins it in commit `28a17360`.
Its server build passed and the built CopyRoom command accepts `--omit-path`.

All six base markers now use the guarded preview and apply flow. Their five
omitted project paths match the original trees. Their Testee module records did
not change. Main is pushed in all six repositories: mnemonix `34273b2b`,
loci.nvim `21ba6c83`, nix-desktop `3268647b`, nix-nvim `f57b653d`,
nix-paseo `a0d668fa`, and nix-secrets `8cf72cbd`. Four Nix repositories keep
their earlier module-layer render mismatch. Mnemonix also keeps its older
conflicting preview.

The other ten eligible Python markers were normalized through CopyRoom. The two
existing prepared previews for agentman and flora-qc remain untouched. The
original fleet inventory found 14 project Testee answers, repeated 28 times
across top-level and per-layer records; all updated Python markers retain their
Testee answers. Five Nix module layers were normalized, but their base-layer
answers still retain legacy fields due to the manifest collision.

At this checkpoint, four tracked legacy answer occurrences remained: two
`repoman_ref` copies in each of agentman and flora-qc. The final section records
their removal. All 28 Testee answer occurrences remain. Scopeman's
Testee answer now records `v0.6.1`; its project pin and checks remain.
Scopeman's update is on local bookmark `toolbelt-testee-answer` at `6822007b`.
Testee has no verdict for that commit, so it remains unpushed.

## 2026-10-13: nix-terminal machine input audit

`nix-meta` now sets `nix-terminal.inputs.devman.follows = "devman"` and
`nix-terminal.inputs.repoman.follows = "repoman"`. The old nix-terminal DevMan
and RepoMan nodes and their nested inputs were removed from `nix-meta/flake.lock`.
Nix-terminal still declares those older defaults in its own flake for standalone
consumers; nix-meta overrides them without editing that repository.

The terminal profile sets `programs.nix-terminal.devman.enable = false`, and
the evaluation contains no additional Home Manager DevMan package. The current
DevMan system package remains owned by nix-meta's DevMan module. The inactive
nix-terminal RepoMan Home Manager module was removed from the developer profile.
The old module generated no active config or activation. RepoMan v0.14.1 has no
global `repoman.toml` reader, so only the active shell aliases were retained.

The final nix-meta change makes Vendomat's DevMan and RepoMan inputs follow
nix-meta's canonical root inputs. The lock has no duplicate `devman_2` or
`repoman_2` nodes. Vendomat's older RepoMan and Gitman commands remain filtered
from interactive PATH. Its built renderer and runtime use canonical DevMan
0.6.0 and RepoMan 0.14.1.

## 2026-10-13: CopyRoom feature build and activation check

The canonical `nix-meta` main commit `28a17360` pins CopyRoom commit
`c4ee8f41`, which adds base-layer path omissions. The server toplevel build
passed at
`/nix/store/yqhvqy6ckx8l2kcrfvds6z16wcrp3nyp-nixos-system-server-26.11.20260705.d407951`.
The built CopyRoom command accepts `update --omit-path`.

The user reported a rebuild. At the next inspection, `/run/current-system`
still resolved to the earlier generation
`/nix/store/8qniji16qglv6x43xcki973xnymdg9xp-nixos-system-server-26.11.20260705.d407951`.
The active `copyroom` command also lacked `--omit-path`. This confirms the new
generation was not active in that shell at inspection. The user can activate it
with `sudo nixos-rebuild switch --flake /home/andrew/Documents/Projects/nix-meta#server`.

Project Testee pins remain because project tests use them. The host Testee
runner is `0.7.0`; the project Testee module remains pinned at `0.6.1`.

## Preserve existing project work while landing Gitman config deletions

The cutover used per-repository commits for root `gitman.toml` removals. In
parsedantic, structured-agents-v2, and nixvim, JJ split the deletion from
unrelated active work and saved the remaining work under local `local-*work`
bookmarks. The mancore codebase-status report was already an uncommitted
addition before this cutover; it remains unchanged and outside the migration.

Two of the 18 separately audited repos could not push: llama-infernal's local
commit has a pre-existing undescribed ancestor, and nvim-review has no Git
remote. Their deletion commits are local and the ancestry/remote state remains
unchanged. Talkee-futo also has a local-only remote, so its deletion commit is
local. No remote force push was used.

Vendomat's `AGENTS.md` forbids raw Git and jj. Its installed Gitman exposes only
`work` and `done`, so it has no command to commit this deletion. The user later
authorized landing the required cleanup on `main`. The deletion was isolated,
rebased onto current `main`, and pushed as `cf86ab1a`. The remote ref now points
to that commit. No other Vendomat files changed in that commit.

## `nix-meta-channel4` alternate config

This checkout still pins DevMan `v0.7.0` and RepoMan `v0.9.2`. Every repository
file is staged on a no-commit local branch whose upstream is gone. Preserve the
staged state. `nix-meta` is the canonical machine config; retire or clean this
alternate after its staged work is resolved.

## 2026-10-13: changes landed for the next nix-meta rebuild

CopyRoom main is pushed at `c4ee8f41`. `nix-meta` main is pushed at
`28a17360`, and its lock pins that CopyRoom commit. The lock metadata confirms
the commit is on `refs/heads/main`. The server toplevel build passed for this
lock.

The template cleanups are also on main. `template-py` is at
`696bce412acaf67ad5b82c4e15034bc55567c8ea`; `template-nix` is at
`5eec9b94ad53a88ab106f82d9df37eae507c`. These source changes do not affect the
NixOS rebuild. No tests or template checks ran for these commits.

The template-py remote main is current, but its default checkout remains
behind and dirty. Its goldens have the landed edits; `.copyroom_sim/` is
untracked, and JJ reports deletions inside the nested `source` checkout.
Preserve this checkout until its nested-repository state is reviewed.

The user then switched to the built generation. `/run/current-system` now
resolves to the server build path above.

The active Home Manager session file adds the candidate
`developer-toolchain-commands/bin` path to `PATH`. A clean shell resolves
CopyRoom there and exposes `--omit-path`. This agent shell still has the old
toolchain path appended to `PATH`; start a new login shell to use the active
toolbelt consistently.

## 2026-10-13: final main pin and marker cleanup

CopyRoom main now includes `1805d197`, which updates its module header to
describe the host toolbelt and the central RepoMan import. It follows the
path-omission feature commit `c4ee8f41`. `nix-meta` main is `55d052b8`; its flake
and lock now pin `1805d197`. The remote main ref matches. This CopyRoom commit
changes guidance only. The prior server build used `c4ee8f41` and remains the
active generation. No build or tests ran after the guidance-only pin update.

The active CopyRoom command resolves to
`/nix/store/1ifamjw7pdsax38pjlw1nh0hrbzng302-developer-toolchain-commands/bin/copyroom`.
Its help lists `update --omit-path`. `/run/current-system` resolves to the
server generation built with the path-omission feature.

The old prepared previews for agentman and flora-qc were stale and would restore
the removed RepoMan module input. A first fresh preview attempt passed
`--source` and could not resolve the root-repo commit through the nested
`template-py/source` repository. The correct route was `--ref` without
`--source`; CopyRoom then reused each marker's recorded repo root and `source`
subdirectory.

Both fresh previews used template-py main `696bce41` and preserved their
omitted test files. Their six generated-file conflicts were resolved with the
current project files. The reviewed diff against each `main` changed only
`.copyroom-local.json`: it removed both `repoman_ref` answer copies, retained
Testee `v0.6.1`, and moved the template pin to `696bce41`. CopyRoom applied the
previews. The changes are pushed to main: agentman `5ec4227d`, flora-qc
`7c0774a2`. CopyRoom inspect reports no conflicts, marker mismatches, or pending
previews. The two obsolete previews were discarded through CopyRoom.
