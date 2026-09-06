# Kickoff — Investigation B, one flake and two module interfaces

## Your task

Run Investigation B from `KICKOFF_PROMPT.md` §2. Answer B1 through B4 with
evidence, and append the answers to `FINDINGS.md` in this directory.

**The question is whether one flake can carry a NixOS module and a devenv module
at one version, without either constraining the other's nixpkgs.** Build the
smallest pair that answers it. Nothing you build here needs to survive.

---

## 1. The one rule that keeps this session useful

A build investigation fails in a predictable way: it starts building the real
thing. Guard against that with a single filter.

> **You are proving that one flake can hold both interfaces. You are not
> building stage 1.**

The deliverable is a yes/no plus the scratch flake that produced it. A NixOS
module that starts Dagu with one queue is enough. A devenv module that writes one
file at shell entry is enough. If you find yourself implementing §7.3's
resolution order or §9.2's projection, stop — that is stage 1, and it is not
this session.

**A "no" is the most valuable result available here.** If the module must pin its
own nixpkgs, the plane ships two flakes and §3.1's anti-drift argument weakens to
a convention. Say so plainly. It is cheaper to learn that now.

---

## 2. Read these first

1. `.scratch/projects/006-automation-plane/CONCEPT.md` — the charter. **It was
   reconciled on 2026-08-22** against Investigations A and E, so it is no longer
   the proposal the earlier prompts describe. Read §3 (the flake), §4 (machine
   responsibility), §5.2 (registration), §12.3 (this investigation's claim).
2. `.scratch/projects/006-automation-plane/KICKOFF_PROMPT.md` — §0 for the rules,
   §2 for B, §5 for the reporting shape, §6 for what "done" means.
3. `.scratch/projects/006-automation-plane/FINDINGS.md` — Investigations A and E,
   in full. Long, but §"Summary" at the end of each gives you the decisions
   without the evidence.

---

## 3. Where you are — read this before you open a file

**This work lives in a git worktree, not the main checkout.**

| Fact | Value |
|---|---|
| Working directory | `/home/andrew/.paseo/worktrees/1n48r26y/special-dragon` |
| Branch | `dagu-devenv-automation-eli5` |
| Main checkout | `/home/andrew/Documents/Projects/devman` — **on a different branch**, and it does not have this work |
| Host | NixOS 26.11.20260705 (Zokor), Nix 2.34.7 |
| Machine config | `/etc/nixos/configuration.nix` |

If you open the main checkout you will not find `CONCEPT.md`, `FINDINGS.md`, or
`nix/dagu.nix`. Work in the worktree.

### What the repo already has

| Path | State |
|---|---|
| `flake.nix` | exists — carries `packages.<system>.dagu`, `.default`, and `overlays.default` |
| `nix/dagu.nix` | exists — the Dagu 2.15.0 release tarball, pinned to the tag |
| `devenv.nix` | exists — Dagu on `PATH`, `processes.dagu`, `DAGU_HOME` |
| `devenv.yaml` | exists — and it already imports another flake's module directory |
| `nixosModules.default` | **does not exist** — you create it |
| `modules/` | **does not exist** — you create it |
| `src/devman/` | **does not exist.** §13 stage 1's "delete `src/devman/`" is already satisfied; `pyproject.toml` carries tool config only |

### The collision this investigation is about is already live

`flake.nix` pins one nixpkgs and `devenv.yaml` pins another:

```nix
# flake.nix
inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
```

```yaml
# devenv.yaml
inputs:
  nixpkgs:
    url: github:cachix/devenv-nixpkgs/rolling
```

That is §12.3's "residual unknown" in the repository already. You do not have to
construct the disagreement. You have to find out what it costs.

### The import-path precedent

`devenv.yaml` already imports another flake's module directory, which is exactly
the `<input>/<subdir>` form B4 asks you to confirm:

```yaml
inputs:
  shellij:
    url: path:/home/andrew/Documents/Projects/shellij
imports:
  - shellij/modules
```

Note that `shellij` is a **path** input. It confirms the import form. It does not
confirm how the form behaves under the `git+` pin §3.2 requires, which is part of
B4.

---

## 4. What reconciliation already decided about the module you build

Do not re-derive these. They are measured and recorded in `FINDINGS.md`, and they
are now in `CONCEPT.md`. They tell you what "the smallest **honest** pair" means
— honest, because a module that ignores all five would prove nothing about the
real one.

**The NixOS module writes a systemd _user_ service.** Not `systemd.services.dagu`
but `systemd.user.services.dagu`. Every workflow step runs a developer's own
`devenv` in a developer's own checkout, so the service needs that developer's
`$HOME`, Nix profile, and credentials (§4).

**It writes two Dagu files, not one.**

| File | Must contain | Why |
|---|---|---|
| `config.yaml` | the queue definitions and their limits | §7.1 |
| | `env_passthrough_prefixes: [DEVMAN_]` | without it no `DEVMAN_*` variable reaches a DAG |
| | `dag_discovery.recursive: true` and `symlinks: true` | both default to off; the projection needs both |
| `base.yaml` | `working_dir: ${DEVMAN_PROJECT_DIR}` | inherited by every DAG (§7.2) |
| | `log_dir: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs` | |
| | a default `queue:` | so a workflow naming none is still governed |

**A config change requires a service restart.** A new DAG file does not. If the
module rewrites `config.yaml`, it must restart the service in the same
activation, or the CLI and the server disagree silently (§5.2).

**`DAGU_HOME` belongs at `~/.local/share/dagu`**, beside the registry, not in
`/var/lib` (§4).

You may stub any of this in the scratch module. Do not contradict it.

---

## 5. What to answer

Restated from `KICKOFF_PROMPT.md` §2. Go there for the framing.

**B1 — Do both modules evaluate, each under its own nixpkgs?** Does the devenv
module evaluate cleanly under the repo's `devenv-nixpkgs/rolling` while the NixOS
module evaluates under the machine's nixpkgs? Evaluate both from **one** flake at
**one** revision.

**B2 — Does the Dagu package resolve in both?** `nix/dagu.nix` is called by both
interfaces today (§3.1). Does it build under each nixpkgs, or does it need its
own pin? It installs a release tarball rather than building from source, so the
answer may be cheaper than it looks — check, do not assume.

**B3 — What breaks first when the two disagree on a shared input?** Force a
disagreement and record the actual failure: the error text, which evaluation
produced it, and whether it is an eval failure, a build failure, or a silent
divergence in what each side gets.

**B4 — Is `modules/` the right import path?** Confirm the `<input>/<subdir>` form
against the `shellij/modules` precedent above, and then confirm it **under a
`git+` pin**, which is what §3.2 mandates and what the path input does not
exercise.

**Deliverable:** the scratch flake, plus a yes/no on whether the module must pin
its own nixpkgs.

---

## 6. How to prove it without touching the running machine

**Do not run `nixos-rebuild switch`. Do not edit `/etc/nixos/`.** Ask first if you
believe you need either. Neither is required to answer B — a NixOS module can be
evaluated and built without being activated.

```bash
# does the whole flake evaluate and do its checks pass
nix flake check

# build a test NixOS configuration without activating it
nix build .#nixosConfigurations.<name>.config.system.build.toplevel

# see the evaluated service unit without building the world
nix eval .#nixosConfigurations.<name>.config.systemd.user.services.dagu --json

# actually start the service, in a throwaway VM
nixos-rebuild build-vm --flake .#<name>
```

Define the test `nixosConfigurations.<name>` **inside your scratch flake**, not
in `/etc/nixos/`. That is what makes this reversible.

For the devenv side, make a throwaway repo under `/tmp` with its own
`devenv.yaml` that imports your flake's `modules/`, and enter it. Two dummy
repos are better than one, because §7.2's portability claim is about more than
one consumer.

Use `nix flake metadata` and `nix flake archive --json` to see what each input
actually resolves to when you suspect a collision.

---

## 7. How to report

Append to `FINDINGS.md` in this directory. Continue the numbering with `B1`
onward. One section per ID, in the shape Investigations A and E used:

```markdown
## B1 — Do both modules evaluate under their own nixpkgs?

**Answer:** <one sentence, first>
**Tested:** <nix version, nixpkgs revs, on <date>>
**Command:** <the exact thing you ran>
**Evidence:** <output, trimmed to the part that proves it>
**Charter impact:** <one of the four below>
```

`Charter impact` is the field that matters:

- **none** — the charter stands
- **changes §N** — name the section, state the change in one sentence
- **deletes §N** — say what the charter should drop
- **kills §N** — the design must be rethought; say what you would do instead

End by extending the summary list at the bottom of `FINDINGS.md`, so every
`changes`, `deletes`, and `kills` stays in one place. That list is what the next
reconciliation pass reads.

---

## 8. Rules

1. **Report what happened, not what should have happened.** Record the Nix
   version, the input revisions, and the exact command. An error message is
   evidence; a summary of an error message is not.
2. **Throwaway is fine.** A scratch flake, `/tmp` repos, a stub module. Do not
   build toward the real thing.
3. **Timebox.** B1 through B4 are the session. If the pair takes all of it, stop
   and report.
4. **Do not edit `CONCEPT.md`.** It was reconciled on 2026-08-22 and the next
   edit is a later pass, over everything at once. Record what a finding
   contradicts and leave it.
5. **Do not start Investigation C or D.** C's questions are independent of B and
   deserve their own session. If you finish early, say so and stop.
6. **Do not modify the machine.** No `nixos-rebuild switch`, no `/etc/nixos/`
   edits, no changes to the running Dagu instance's state. Ask first.
7. **Commit and push at regular intervals.** Work on the current branch. Commit
   each finding as you confirm it, rather than saving one commit for the end.

**If B returns a no, stop and say so plainly before writing anything else.** §3.1
argues that one flake at one version is what removes drift between the Dagu
config, the queue names, the registry layout, and the repo integration. If that
premise fails, four sections rest on a convention rather than a property, and the
reconciliation pass needs to know before it reads anything else.
