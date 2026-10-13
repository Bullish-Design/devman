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

## Preserve existing CopyRoom previews

Before this migration, CopyRoom already had pending preview state for
`agentman` and `flora-qc` under `.copyroom-previews/`, with journals in each
project's `.copyroom-local/journal`. These are not migration previews. Leave
them intact and inspect them before running a new update for either project.
Both journals are prepared base-layer updates. Applying another marker update
would make each preview stale, so their answer normalization is deferred until
the existing previews are resolved by their owner.

## Cleanup counts

The current Gitman no longer reads project-root `gitman.toml` files. The initial
fleet inventory found 61 tracked root configs in project repositories and one
in `template-nix`. The current top-level project scan finds one file:
`nix-meta-channel4/gitman.toml`. It remains because that checkout has unrelated
staged work. Thus 60 project-root configs and the `template-nix` config have
been removed; the final project config is deferred. DevMan's central
`~/.config/devman/gitman.toml` remains because DevMan reads it. The file sets
`trunk = "main"`, which matches the fallback. `template-py` has no root config
file.

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

The Nix base layer update failed for all six Nix markers, including loci.nvim,
with `output path collision: .devman/project.toml and .devman/project.toml`.
The promoted base source now emits `.devman/project.toml`, which collides with
the existing repo-owned manifest. CopyRoom created no preview. Preserve all six
manifests and leave their base layer markers unchanged until CopyRoom supports a
safe ownership transition. `copyroom update --answers` only overrides schema
answers; it has no output omission or ownership transfer option. CopyRoom's
preflight classifies the existing manifest as a project-only path and rejects
the rendered output. `copyroom adopt` is an initial adoption flow and does not
provide a safe path to replace an existing layered marker. loci.nvim has no
`module` layer, so neither layer's answers could be normalized.

The other ten eligible Python markers were normalized through CopyRoom. The two
existing prepared previews for agentman and flora-qc remain untouched. The
original fleet inventory found 14 project Testee answers, repeated 28 times
across top-level and per-layer records; all updated Python markers retain their
Testee answers. Five Nix module layers were normalized, but their base-layer
answers still retain legacy fields due to the manifest collision.

The remaining tracked legacy answer occurrences are 4 `repoman_ref` values in
agentman and flora-qc, plus 12 each of `devman_ref` and `repoman_dev_root` in
the six Nix base layers. All 28 Testee answer occurrences remain.

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
0.6.0 and RepoMan 0.14.1. Vendomat's active generation 4 was not updated; no
plane plan or update was run.

## Host activation needs interactive sudo authentication

The final nix-meta server build passed at
`/nix/store/8qniji16qglv6x43xcki973xnymdg9xp-nixos-system-server-26.11.20260705.d407951`.
The live system still points to
`/nix/store/bqm07rlvmdavvpm52hsarww8x22q520r-nixos-system-server-26.11.20260705.d407951`.
`sudo -n true` failed because sudo needs an interactive password. The system
switch and Vendomat plane update were not run. To activate the built config,
run:

```sh
sudo nixos-rebuild switch --flake /home/andrew/Documents/Projects/nix-meta#server
```

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
