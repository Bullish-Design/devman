# Guide 02 — the config repository and the link plane

**Goal:** one central git repository holds every machine-local file, and one
reconciler makes each project repository's filesystem match a declaration.

**Size:** ~2.5 days. Three stages, each independently useful and reversible.
**Depends on:** nothing. **Unblocks:** Guide 01 (the agent surface), Guide 03, Guide 04.
**Concept:** [`CONCEPT.md`](CONCEPT.md) §5 and §8.

---

## 1. What you are building

A **link** has a **canonical** side and a **view** side. The canonical side holds
the content; the view side is a symlink to it. One reconciler makes the filesystem
match.

**Declarations live in `devenv.local.nix`, not `devenv.nix`** — by the boundary
test (`CONCEPT.md` §P0) they are *my* wiring, and a collaborator's clone must not
carry them. Verified: a symlinked `devenv.local.nix` sets `devman.link` and the
module reads it.

```nix
# devenv.nix — TRACKED, three lines, the only devman fact the project owns
devman = { enable = true; project = "flora"; };
```

```nix
# devenv.local.nix — symlinked from ~/.config/devman/projects/flora/
{ ... }: {
  devman.link = {
    ".agents"           = { canonical = "central";  path = "projects/${project}/agents"; };
    ".devman/workflows" = { canonical = "central";  path = "projects/${project}/workflows"; };
    ".envrc"            = { canonical = "central";  path = "common/envrc"; };
    ".loci"             = { canonical = "external"; path = "~/Notes/1_Projects/${project}"; };
  };
}
```

**`devenv.local.nix` needs no declaration of its own.** The module always links it
from `<overlayDir>/projects/<project>/devenv.local.nix` when that file exists — the
**implicit bootstrap link**. Everything else is declared inside it.

⚠ **Never leave a dangling `devenv.local.nix`.** Nix evaluates it before any hook,
so a broken link fails shell entry with a trace nothing can intercept. Create the
canonical file before the link.

Five states, one function:

| View side is… | Action |
|---|---|
| the correct symlink | nothing |
| a symlink to the wrong target | repoint |
| **a real file or directory** | **promote content → canonical, then link** |
| absent | link it |
| absent, **and canonical absent** | create canonical (`mkdir -p`, or render `template`), then link |

Three behaviours from that one declaration: the symlink, the
`.git/info/exclude` line, and the drift assertion.

---

## 2. State on disk, measured 2026-09-10

**devman has uncommitted work of its own** — unrelated to this guide, but land or
stash it first so your diffs read cleanly:

```
flake.nix          +21   the `shell-variable-unset` check is being ADDED
modules/devenv.nix  +1   one variable added to the unset block
src/devman/project.py +41/-8  a `_sweep` fix: remove only links this projection published
src/devman/doctor.py, tests/unit/{test_doctor,test_project}.py
```

The `_sweep` change matters to Guide 04 — it makes the projection remove only what
it published, which is exactly the ownership discipline the DAGs directory needs.

**Nothing else is in the way.** `grep -rn registryDir */devenv.nix` returns **0
hits**, so no repository pins the path.

---

## 3. Stage 1 — the config repository (½ day)

Reversible by deleting one directory.

```bash
mkdir -p ~/.config/devman && cd ~/.config/devman
git init && gitman init --colocate --trunk main
```

Create:

```
~/.config/devman/
  .gitignore
  common/envrc
  common/claude.json
  notes/                    loci init
  projects/                 empty for now
  devenv.nix devenv.yaml    so it has a `check` task
```

**`.gitignore` — the rule that keeps it portable:**

```gitignore
# Derived: absolute links and generated state. Relative links are tracked.
projects/*/repo
projects/*/workflows
projects/*/agents/index
dags/
**/.runs/
```

> **In this repository, relative links are tracked; absolute links are ignored.**
> A relative link points at content the repository owns; an absolute link points at
> a machine fact. Verified by cloning: mode `120000`, relative target, resolves in
> the clone.

**`common/envrc` converges real drift.** Five repositories have an `.envrc` today
and **all five differ**; two pin *different* devenv `direnvrc` revisions —
`nixvim` at `95f329d4`, `PyGentic` at `82c01476`. Thirty-one more repositories
gitignore `.envrc` and have none. Write one pinned file.

**~~`notes/` is one loci vault, not 52.~~ WITHDRAWN — see
[`GUIDE-03-notes-repair.md`](GUIDE-03-notes-repair.md).** The config repository
creates **no** `notes/` directory. `~/Notes` is a running service's data
directory with its own git repository and auto-commit timer; it stays where it is
and the config repository gets a derived, gitignored link only (`CONCEPT.md` §8.1).
Add `notes/` to the `.gitignore` in this stage.

**A `check` task that evaluates every `projects/*/devenv.local.nix`.** A store
whose Nix does not evaluate breaks every repository at once
(`024-personal-overlay/CONCEPT.md` §3.7).

---

## 4. Stage 2 — the option and the reconciler (2 days)

### 4.1 The option

In `devman/modules/devenv.nix`, beside `registryDir` (`:484-488`, the shape to
copy):

```nix
overlayDir = mkOption {
  type = types.str;
  default = "$HOME/.config/devman";
  description = "The config repository root. `$HOME` is expanded by the shell hook, not by Nix.";
};

link = mkOption {
  type = types.attrsOf (types.submodule {
    options = {
      canonical = mkOption { type = types.enum [ "central" "repo" "external" ]; default = "central"; };
      path      = mkOption { type = types.str; default = ""; };
      template  = mkOption { type = types.nullOr types.str; default = null; };
    };
  });
  default = {};
};
```

`path` is relative to `overlayDir`. It stays a **formula** over `devman.project` —
principle 5 holds: no absolute project path enters Nix
(`devman/AGENTS.md:67`).

### 4.2 The CLI

devman's CLI is **argparse, not Typer** (`src/devman/cli.py:84`). Follow the
`project` subcommand exactly (`cli.py:166-172`):

```python
p_link = sub.add_parser("link", help="reconcile this repository's links (§5)")
p_link_sub = p_link.add_subparsers(dest="link_command", required=True)
link.add_arguments(p_link_sub.add_parser("reconcile", ...))
link.add_arguments(p_link_sub.add_parser("status", ...))
```

and register it in `handler()` at `cli.py:188-192`.

**Take the project name as an argument outside the plane; default from
`devman.project` inside it.** Never infer it from the directory name — that is the
defect recorded in `024-personal-overlay/CONCEPT.md` §8, and §3.5 there settles the
shape:

```
devman link reconcile                     # in-plane: name from devman.project
devman link reconcile --project scippy    # anywhere else: name stated
devman link status
```

New module `src/devman/link.py` — the five states of §1, in Python, per property 7
(`devman/AGENTS.md:74-75`: Python for core logic; shell stays a thin wrapper).

### 4.3 Refuse-don't-clobber, and promote

Model the return on `copyroom/src/copyroom/agent/files.py:161-176` — `ok`,
`created`, `refused` — and **never replace a regular file without promoting it
first**.

Three safety rules on promote:

- **Record the content hash when the link is made.** If canonical has *also*
  changed since, **refuse and report the conflict**. Never merge.
- **Land the promotion in a gitman lane** named `promote/<project>-<file>`. Never
  trunk. `devman/AGENTS.md:129`: *"An unattended write to trunk has no tier … A
  lane carries a name and a diff instead."*
- **Never delete.** Promote overwrites canonical; the config repository is
  version-controlled, so a wrong promotion is one `gitman undo` away.

### 4.4 The hook

Build a narrow entry point as its own derivation, mirroring `projectScript`
(`modules/devenv.nix:445-451`):

```nix
linkScript = pkgs.writeShellScript "devman-link-${projectName}" ''
  exec ${renderer}/bin/devman-link reconcile \
    --overlay "$2" --root "$1" --project ${projectName}
'';
```

Call it from the hook **guarded by `[ -d ]` on the project's central directory**,
so it forks nothing when absent — the guard shape at `modules/devenv.nix:832-838`.

⚠ **`devman/flake.nix:80-95` (`shell-variable-unset`) requires every new
`devman_*=` assignment to appear in the `unset` block ending in `devman_cur`
(`modules/devenv.nix:841-847`). Add them in the same commit** or the flake check
fails. That check is itself being added in devman's uncommitted work (§2).

### 4.5 The exclude lines

Extend the writer at `modules/devenv.nix:821-827`. It appends `.devman/.runs/`
today; it will append one rule per link-in whose view lands inside a git
repository. Keep its worktree awareness (`:798-827`): a `.git` *file* is a linked
worktree whose `commondir` points back, and a repo with no `.git` correctly gets no
rule.

### 4.6 The doctor check

`devman doctor` gains `link drift`: for each declared link, report which of the
five states it is in. Follow the cheap shape of `check_local_sources`
(`src/devman/doctor.py:1080-1083`) — work proportional to registered projects, no
fork per project.

---

## 5. Stage 3 — adopt it, one repository at a time (½ day)

**A repository with no `devman.link` reconciles an empty set.** Stage 2 is a no-op
for 52 of 52 until you opt one in. Do them in this order:

1. **One repository you work in daily.** Declare `devenv.local.nix` only. Enter the
   shell. Confirm the link, the exclude line, and `devman link status`.
2. **The four with a real `devenv.local.nix`** — `foreman`, `forgelab`,
   `image-gen-pipeline`, `lodestar`. These hit **state three**: they are
   **promoted, not clobbered**, and land in a lane for review.
   `foreman/devenv.local.nix:5` holds `devman.enable = lib.mkForce false`
   (*"Backburner"*, 2026-09-08) — that file is your first promotion, and the opt-out
   keeps working, now version-controlled.
3. **`.envrc`, fleet-wide.** The 31 repositories that gitignore it and have none
   get `common/envrc` linked. The 5 that have one are **promoted first**, so the
   divergent revision pins surface as a reviewable diff instead of being
   overwritten.
4. **Then Guide 01** — the agent surface is just another `devman.link` entry.

---

## 6. Verify

```bash
# every declared view is a symlink pointing where it should
devman link status --all

# no absolute link is tracked in the config repo
git -C ~/.config/devman ls-files -s | awk '$1==120000{print $4}' | while read l; do
  case "$(readlink ~/.config/devman/$l)" in /*) echo "ABSOLUTE TRACKED: $l";; esac
done

# the config repo's own Nix evaluates
cd ~/.config/devman && devenv tasks run check

# the plane is still healthy
devman doctor
```

`devman doctor` must exit 0 before any change to `modules/`, `groups/`, `nix/` or
`src/devman/` is committed (`devman/AGENTS.md:88-94`).

**Also confirm the clone property** — it is what makes the config repository
portable:

```bash
git clone ~/.config/devman /tmp/cfgclone
ls -la /tmp/cfgclone/projects/*/          # relative links present, absolute ones absent
cat /tmp/cfgclone/notes/*/[a-z]*.md       # tracked note content resolves
rm -rf /tmp/cfgclone
```

---

## 7. Do not do these

1. **Do not use dotbot.** It works mechanically — absolute targets outside the base
   directory are accepted — but it **never converges**: dropping a link from its
   config leaves an orphan forever, and `clean` removes dead links only with
   `force: true`, the same flag that destroyed real user data in testing
   (`CONCEPT.md` §5.6).
2. **Do not use Home Manager `mkOutOfStoreSymlink`.** It is the right NixOS idiom
   and the wrong fit: it is static, so a repository cloned today would need a
   rebuild, which breaks *"the registry is populated by shell entry, never by
   scanning"*. Only one file in your `~/.config` is HM-managed today.
3. **Do not put declarations in `devenv.local.yaml`.** Measured: devenv **silently
   ignores** an unknown top-level key there and exits 0. `devenv.local.nix` is
   typed and fails at eval.
4. **Do not link individual files where a directory link will do.** Rename-based
   writers (`sed -i`, `os.replace`, `jq + mv`) replace a **file** symlink with a
   real file, silently. Directory links are immune (`CONCEPT.md` §5.5, §5.7).
5. **Do not infer the project name from the directory.** §4.2.
6. **Do not move the registry yet.** That is Guide 03. Stage 1–3 leave
   `~/.local/share/devman/` exactly where it is.
7. **Do not touch the workflow projection.** Guide 04.

---

## 8. The one test to run during this guide

It changes what Guide 01 links:

```bash
# link one repo's .claude/settings.local.json to a central file,
# approve one permission in that repo, then:
test -L <repo>/.claude/settings.local.json && echo "survived" || echo "BROKEN"
```

If Claude Code renames on save, that link breaks on every permission approval.
Drop it from the link set and hoist the shared allowlists to
`~/.claude/settings.json` instead. It changes nothing else.

---

## 9. What must be preserved

1. **Stated identity, never inferred** (`devman/src/devman/registry.py:33-36`).
2. **The duplicate-registration refusal** (`modules/devenv.nix:778-786`).
3. **The plane holds no project fact** (`devman/AGENTS.md:67`) — link paths are a
   formula over `devman.project` and `overlayDir`.
4. **The tier table**, and that an unattended write to trunk has no tier
   (`devman/AGENTS.md:120-131`).
5. **Prefer a loud refusal to a silent default** (`devman/AGENTS.md:63-67`).
6. **The exclude writer's worktree awareness** (`modules/devenv.nix:798-827`).
7. **Refuse-don't-clobber** (`copyroom/src/copyroom/agent/files.py:161-176`).
