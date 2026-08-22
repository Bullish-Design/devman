# Kickoff — Stage 1, the flake foundation

## Your task

Build stage 1 of the devman automation plane, as `CONCEPT.md` §13 defines it.
The investigations are over. **This is the first session that ships code
intended to survive.**

Work in the git worktree described in §3. Commit each piece as it works.

---

## 1. The one rule that keeps this session useful

> **The charter is now evidence-backed. Do not re-derive it, and do not
> re-measure it.**

Five investigations — A, E, B, C, D — are closed, and `CONCEPT.md` was
reconciled against all five on 2026-08-22. Every claim you are about to
implement has a measurement behind it in `FINDINGS.md`. If something surprises
you, **read the finding before you re-run the experiment**; the answer is
almost certainly already recorded, along with the exact command that produced
it.

If you find the charter is *wrong* about something, that is a real result. Say
so plainly, record it the way the investigations did, and **do not silently
implement something else.**

**What "done" means here is different from the investigations.** They delivered
answers. This delivers a working plane that a repository can adopt in three
lines. Prefer a smaller thing that runs to a larger thing that evaluates.

---

## 2. Read these first

1. `.scratch/projects/006-automation-plane/CONCEPT.md` — the charter, fully
   reconciled. Read **all of it**; it is the specification. Pay closest
   attention to §3.1–§3.3 (the flake and its two rules), §4 (machine), §5.2
   (registration — the most-changed section), §7 (the contract), §9 (state),
   §13 stage 1, §14 (the criteria you must meet), §15.
2. `.scratch/projects/006-automation-plane/FINDINGS.md` — **the evidence, and
   the reason for every non-obvious decision.** Do not read it end to end;
   it is 5,600 lines. Read:
   - the final section, **"Reconciliation input — every charter change, by
     section"** — this is the index. Start there.
   - the five `## Summary` sections, one per investigation.
   - any individual finding the index points you at.
3. `modules/devenv.nix` and `nix/nixos-module.nix` — **the existing scratch
   pair.** They work and they are measured, but they are Investigation B and C
   artifacts, not stage 1. §6 below says exactly what each still lacks.

---

## 3. Where you are — read this before you open a file

| Fact | Value |
|---|---|
| Working directory | `/home/andrew/.paseo/worktrees/1n48r26y/special-dragon` |
| Branch | `dagu-devenv-automation-eli5` |
| Main checkout | `/home/andrew/Documents/Projects/devman` — different branch |
| Host | NixOS 26.11.20260705 (hostname `server`), Nix 2.34.7 |
| devenv | 2.1.2 installed; **2.2.2 is in the store** and behaves identically (see §7) |
| Dagu | 2.15.0, via `nix/dagu.nix`, pinned to the tag |
| Machine nixpkgs | `/nix/store/ifpab9hxqmk2biwy594da8ipxzsp3y4s-source` |

### What already exists and works

| Path | State |
|---|---|
| `flake.nix` | `packages`, `overlays.default`, `nixosModules.default`, `nixosModules.devman-dagu` |
| `nix/dagu.nix` | Dagu 2.15.0. Resolves byte-identically under the machine's nixpkgs and a repo's (B2) |
| `nix/nixos-module.nix` | `systemd.user.services.dagu`, `config.yaml`, `base.yaml`, `restartTriggers` on both. **The restart is verified to fire** (C7) |
| `modules/devenv.nix` | `enable`, `project`, `groups`, `registryDir`, `installClient`. Registers in `enterShell` behind a fork-free guard costing ~4 ms (C2) |
| `.scratch/.../c-scratch/` | A NixOS VM test that proves the user-service restart. Reuse its shape for stage-1 tests |

### What was cleaned up already, so you do not redo it

- `src/devman/` — **already absent** from this repo.
- `processes.dagu` — **removed** from `devenv.nix`. It held 8080 and 50055,
  which the plane's own service needs. Do not restore it; run a throwaway Dagu
  by hand with its own `DAGU_HOME` if you need one.
- The two committed run logs under `.devman/.runs/` — **untracked**, and
  `.devman/.runs/` added to `.git/info/exclude` (not `.gitignore` — §9.2).
- `linger` for `andrew` — **already `yes`**, set imperatively. See §8.

---

## 4. Six facts that will bite you if you rediscover them

All measured. All in `FINDINGS.md`.

**1. The devenv module file must be `modules/devenv.nix`.** devenv resolves
`<input>/<subdir>` to `inputs.<input> + /<subdir>` and then requires
`devenv.nix` inside it. A `default.nix` is never consulted, and the error names
a file you did not write. (B4)

**2. `git+file` does not pin.** It records neither `rev` nor `narHash` and
silently follows the branch head, so a test repo built at one commit picks up
your next one. `git+https` pins properly. **For local iteration, copy the
worktree to a fixed path** (`git archive HEAD | tar -x -C /tmp/...`) and point
test repos at `path:/tmp/...`. Investigation C did exactly this. (B4)

**3. `enterShell` runs TWICE per `devenv shell`.** devenv runs the whole hook
in a throwaway subprocess just to snapshot `env`, then again for real. Two
consequences you must design around, not discover:
- **Anything in `enterShell` must be idempotent.** Every side effect happens
  twice.
- **Anything in `enterShell` must fork nothing.** Four forks per entry became
  +23 ms; bash builtins made it +4 ms. (C1, C2)

**4. Registration cannot print anything on the branch that writes.** devenv
discards the capture subprocess's stdout *and* stderr, and by the time the real
shell runs the hook the guard is silent. **A "devman: registered" line is
impossible.** Design the user-visible path as a refusal or as `doctor`. (C5)

**5. Dagu creates a missing `working_dir` and reports success.** `dagu
validate` exits 0. A projection pointing at a deleted repo passes forever, in an
empty directory it creates. Only §10's stale-entry check ever notices. (C6)

**6. `restartTriggers` on a user unit really does restart it in the same
activation** — `switch-to-configuration` visits the user scope and runs the
same unit comparison as the system scope. **It reaches exactly the users
`logind` lists**, which is why §4 requires `linger`. (C7)

---

## 5. What stage 1 must deliver

From §13, with §14's criteria as the acceptance test.

```
nixosModules.default    one Dagu service, config, state paths, ports as options
modules/devenv.nix      selection and identity — fork-free, idempotent
workflows/base          check, validate, full-test
workflows/python        one ecosystem group, to prove shadowing
registration            enterShell, hash-guarded (§5.2)
```

**Adopt in exactly one repo — this one** (criterion 16).

### The criteria stage 1 can actually meet

Do not chase the ones that belong to later stages. These are yours:

| # | Criterion | How you will know |
|---|---|---|
| 1 | one flake, two interfaces, one version | the machine and this repo import the same rev; `nix flake check` passes |
| 2 | a repo adopts in three lines | `enable`, `project`, `groups` and nothing else |
| 3 | a repo may take no groups | `groups = []` plus its own `.devman/workflows/` |
| 4 | **a repo may rename or replace every default** | drop `check`, define `smoke`; nothing in devman objects |
| 7 | devenv stays on the fast path | **≤ 10 ms paired delta** — see §7 below |
| 8 | registration is idempotent | enter twice, one write, mtime unchanged |
| 9 | only opted-in repos register | no `devman.enable`, no entry |
| 11 | identity survives a move | move *and* rename, re-enter, same project |
| 17 | there is one way in | delete the registry, re-enter, it comes back exactly |

Criteria 5, 6, 12, 13, 14, 15 and 16 are stage 2 and 3, or need real workflows
first. Criterion 10 is a grep you can run at any point.

---

## 6. What the existing pair still lacks

Both modules are honest scratch artifacts. Neither is stage 1. Here is the gap,
so you do not have to derive it.

### `modules/devenv.nix`

- **The registry entry is a flat JSON file.** §9.2 specifies a
  **directory** per project — `projects/<project>/metadata.json` plus
  `workflows/*.yaml`. The projection does not exist at all yet.
- **No collision handling.** §9.1 now specifies refuse-if-the-recorded-path-
  still-exists, with a replace on a path that is gone. A working implementation
  was written and exercised during C5 and deliberately **not** merged; the
  finding quotes it, and the reconciled §9.1 is the spec.
- **No ignore rule.** §9.2 says registration adds `.devman/.runs/` to
  `.git/info/exclude`, located with `git rev-parse --git-path info/exclude`.
  That shells out, which fact 3 says you cannot afford on every entry —
  **you will need a guard that skips the work when the rule is already there,
  without forking to find out.**
- **No `.devman/` whitelist check.** §15.2: only `workflows/` and `.runs/` may
  be present; anything else refuses and reports.
- **No group resolution.** §7.3's precedence is unimplemented.

### `nix/nixos-module.nix`

- **Ports are hard-coded.** §4 now requires them as options — 8080 and 50055.
- **`Restart=on-failure` is unbounded.** §4 requires it capped, or a bind
  failure retries every five seconds forever.
- **It does not read the registry.** No projection, so no per-project DAG
  directory and nothing for `dag_discovery.recursive` to find.
- **`base.yaml` has no `handler_on.exit`.** §9.2's `metadata.jsonl` depends on
  it.
- **No watcher.** §8 is stage 3; do not build it now, but do not design the
  module in a way that makes adding one awkward.

---

## 7. How to measure criterion 7, which is the one that traps people

Criterion 7 is **no longer an absolute number**. It is a paired delta.

```bash
# a bare devenv repo measures 0.164s quiet and 0.231s under load on this
# machine. The absolute figure measures the machine, not the plane.
```

Three rules, all learned the hard way in C2:

1. **Interleave the variants one entry at a time.** `hyperfine` runs each to
   completion in turn, and ordinary load drift is larger than the effect — one
   sequential sweep reported the *enabled* repo as faster. C2 used a small
   paired-difference script; reuse or rewrite it.
2. **Report mean, standard deviation, and the spread of the delta.** A timing
   without a spread is not a timing.
3. **Remember the hook fires twice.** The per-firing budget is half of whatever
   the criterion says.

`hyperfine` is not installed; `nix build nixpkgs#hyperfine` first, or use a
paired script. **devenv 2.2.2 is already in the store** at
`/nix/store/cvz3j052k1z95pscj1w2iki187ywfcjw-devenv-wrapped-2.2.2` and behaves
identically to 2.1.2 on every C1 and C2 result — use whichever, and say which.

---

## 8. The machine, and what you may and may not do to it

**Do not run `nixos-rebuild switch`. Do not edit `/etc/nixos/`. Ask first if
you believe you need either.** Stage 1 can be built and tested without them:

```bash
# build a VM and activate a specialisation inside it — the C7 pattern
nix build .#checks.x86_64-linux.<name>          # a NixOS test, headless
nixos-rebuild build-vm --flake .#<name>         # an interactive VM

# read the activation logic rather than guessing
nix eval .#nixosConfigurations.<name>.config.systemd.user.services.dagu --json
```

Define any test `nixosConfigurations` **inside a scratch flake**, as
Investigations B and C did. `.scratch/.../c-scratch/` is a working example.

**Set `devman.registryDir` to a `/tmp` path in every test repo.** The real
registry at `~/.local/share/devman/` does not exist yet, and creating it is the
plane's job, not a test's.

### Two open machine-side items, both deliberately left for you and the user

**`devman 0.2.0` is still installed** at
`/etc/profiles/per-user/andrew/bin/devman`. It owns the `devman` command, ships
its own `doctor` and `init`, and its `init --force` calls `shutil.rmtree` on a
`.devman/` it does not recognise (§3.3, §15.2). It arrives through
**home-manager's `home.packages`** — traced via `devman-env` →
`home-manager-path` — but **the home-manager configuration is not in
`/etc/nixos/`, and the previous session could not locate it.** Ask the user
where it lives. Removing it needs their rebuild, not yours.

**`linger` is `yes` for `andrew`, but set imperatively**, not declaratively —
`grep linger /etc/nixos/*.nix` finds nothing. It works today and would not
survive a fresh machine. §4 requires it; the module should either set
`users.users.<name>.linger = true` itself or document that the machine must.

---

## 9. Rules

1. **Report what happened, not what should have happened.** Record versions and
   exact commands. An error message is evidence; a summary of one is not.
2. **A timing without a spread is not a timing.**
3. **Throwaway is fine for tests.** `/tmp` repos, scratch flakes, `/tmp`
   registries. **Not for the modules** — those ship.
4. **`CONCEPT.md` is the specification now, not a proposal.** If you must
   change it, change it deliberately, in its own commit, and say which finding
   forces the change.
5. **Do not modify the machine.** No `nixos-rebuild switch`, no `/etc/nixos/`
   edits, no writes to `~/.local/share/devman/` outside a deliberate adoption
   step you have agreed with the user.
6. **Commit and push at regular intervals**, on the current branch. Commit each
   working piece rather than saving one commit for the end.
7. **Prefer running code to evaluating code.** A module that `nix flake check`
   passes but was never entered has not been tested.

---

## 10. The single most important instruction

**Criterion 17 is the load-bearing one — "there is one way in."** It is what
lets the registry be derived, lets §9.3 promise reconstruction, and lets §5.2
have no manual register command. C1 verified every ordinary entry path takes it.

**If anything you build gives the registry a second entry path — a `devman
register`, a hand-written entry, a fallback scan, a "just this once"
initialisation step — stop and say so before writing it.** Every convenience
that adds a second way in costs the property the whole design is built on.

The same goes for §15.1: **do not solve any problem by scanning the filesystem
for repositories.** Reading devman's own registry is not scanning; walking the
disk to find repos is. The distinction matters and C6 relies on it.
