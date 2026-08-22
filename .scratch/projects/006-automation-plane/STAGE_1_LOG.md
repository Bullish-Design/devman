# STAGE 1 — what was measured while building it

`FINDINGS.md` holds the five investigations. This holds what stage 1 found
while turning them into code, in the same shape: the answer, the versions, the
exact command, the evidence, and the charter impact.

**Environment for every entry below**, unless it says otherwise:

| Fact | Value |
|---|---|
| Host | NixOS 26.11.20260705, hostname `server`, Nix 2.34.7 |
| Machine nixpkgs | `/nix/store/ifpab9hxqmk2biwy594da8ipxzsp3y4s-source` |
| Dagu | 2.15.0, from `nix/dagu.nix` |
| devenv | **2.1.2** (2.2.2 is in the store and was not used; C1 and C2 found no difference) |
| Date | 2026-08-22 |
| devman rev | branch `dagu-devenv-automation-eli5` |

---

## S1 — A DAG is keyed by its file's base name, so §9.2's layout hides workflows

**Answer:** pointing Dagu's `dags_dir` at `~/.local/share/devman/projects/`
makes every workflow name that two projects share **disappear from `dagu ls`,
from the web UI and from the scheduler**. The projection needs a second, flat
directory whose file names are machine-unique.

**Command:** two projects, each with a per-project subdirectory holding a
symlink to a group file. `projA` takes `base` and `python`, so its `check` is
python's; `projB` takes `base`.

```bash
export DAGU_HOME=/tmp/s1-dagu2            # ports moved to 18080 / 51055
# config.yaml: paths.dags_dir: /tmp/s1-registry/projects
#              dag_discovery: {recursive: true, symlinks: true}
ln -s $G/python/workflows/check.yaml  $REG/projects/projA/workflows/check.yaml
ln -s $G/base/workflows/full-test.yaml $REG/projects/projA/workflows/full-test.yaml
ln -s $G/base/workflows/check.yaml    $REG/projects/projB/workflows/check.yaml
dagu ls
```

**Evidence:**

```
warning: duplicate DAG file name "check": projA/workflows/check.yaml, projB/workflows/check.yaml
warning: duplicate DAG name "check":      projA/workflows/check.yaml, projB/workflows/check.yaml
NAME
full-test
```

**Both** copies of `check` are gone. `full-test`, whose name is unique, is
listed — and listed by its base name, not by its path.

Upstream states the behaviour it produces. From
`internal/persis/file/dag/store_test.go`, `TestRecursiveDiscoveryExcludesAndRecoversConflicts`:

```go
_, err = store.GetSpec(ctx, "shared")     // assert.ErrorIs(err, persis.ErrDAGNotFound)
_, err = store.GetSpec(ctx, "a/shared")   // require.NoError
```

So a shadowed DAG stays reachable by path and unreachable by name. Confirmed
against the running daemon: `dagu status projA/workflows/check` got past
resolution to "no status data", while `dagu ls` listed nothing.

### The route out that is closed

A per-DAG `name:` key would make the names unique without moving any file.
`dagu validate` rejects it, which A5 already recorded and this re-confirmed on
a single-document file:

```
$ printf 'name: projA-check\nqueue: light\nsteps:\n  - name: x\n    run: "true"\n' > /tmp/s1-named.yaml
$ dagu validate /tmp/s1-named.yaml
Error: Validation failed for /tmp/s1-named.yaml
- entrypoint document must not define name
```

`start` and `enqueue` tolerate it, so shipping it would make `devman doctor`
report every projected file as broken (§10, check 1).

### And a second name for the same DAG

`dagu enqueue <name>` resolves the name as a path under the DAG directory
rather than through the discovery index:

```
$ dagu enqueue projA-probe -- DEVMAN_PROJECT_DIR=/tmp/s1-projA
Error: failed to load DAG from projA-probe: failed to read file
       "/tmp/s1-registry/projects/projA-probe.yaml": no such file or directory
```

The same DAG enqueues as `projA/workflows/projA-probe` and lists as
`projA-probe`. One DAG, two names, and §8's trigger has to know which is which.

### What stage 1 does instead

```
~/.local/share/devman/
├── projects/<project>/workflows/<workflow>.yaml   -> the group file or the repo's own
└── dags/<project>-<workflow>.yaml                 -> ../projects/<project>/workflows/<workflow>.yaml
```

`dags_dir` points at `dags/`. Verified:

```
$ dagu ls
NAME
projA-check
projA-full-test
projA-probe
projB-check
projB-probe
```

Five names, no warnings, and Dagu follows the two-link chain to the group file
in the store.

**Charter impact:** **changes §9.2.** Applied in its own commit.

---

## S2 — `${DEVMAN_PROJECT_DIR}` does not interpolate inside a handler's `run:`

**Answer:** in `base.yaml`'s `handler_on.exit`, `${context.*}` interpolates and
the run **parameter** does not. The parameter does reach the step's
environment, so the handler must use the shell form `$DEVMAN_PROJECT_DIR`.

**Command:** `base.yaml` with the Dagu form, then the shell form.

**Evidence — the Dagu form, `>> '${DEVMAN_PROJECT_DIR}/.devman/.runs/metadata.jsonl'`:**

```
└─onExit (0s) [failed]
  │   /tmp/dagu_script-3828283976.sh:1: no such file or directory:
  │   ${DEVMAN_PROJECT_DIR}/.devman/.runs/metadata.jsonl
  └─error: exit status 1
```

The text reached the shell unresolved. This is A3's unresolved-variable
failure — Dagu creating a literally-named directory — one level worse, because
a redirect cannot create the parent.

**Evidence — the shell form, `>> "$DEVMAN_PROJECT_DIR/.devman/.runs/metadata.jsonl"`:**

```
└─onExit (0s) [succeeded]
$ cat /tmp/s1-projA/.devman/.runs/metadata.jsonl
{"dag":"projA-probe","run_id":"034Bct9LtJNp8m8FKoNE1t","attempt":"781d34",
 "status":"succeeded","started_at":"2026-08-22T15:08:23Z","log":"/tmp/s1-projA/..."}
```

All six `${context.*}` references resolved. The failure path records
`"status":"failed"`, so §9.2's "on both the success and the failure path" holds:

```
{"dag":"projA-boom", ... ,"status":"failed", ...}
```

**Charter impact:** **none.** §9.2 says the machine puts a `handler_on.exit` in
`base.yaml`, and it does. This is how.

---

## S3 — NixOS pins a user unit's PATH, so `devenv` is not on it

**Answer:** §4's "a user service has the developer's Nix profile already" is
true of the login environment and **false of the unit**. NixOS writes
`Environment=PATH=` from `systemd.user.services.<n>.path`, whose default is
coreutils, findutils, gnugrep, gnused and systemd. Every workflow step runs
`devenv tasks run` (§6), so without a fix the plane cannot run anything.

**Command:**

```bash
nix eval --impure -f /tmp/s1-eval.nix --json   # renders the unit file
```

**Evidence — before:**

```
Environment="PATH=/nix/store/...coreutils-9.11/bin:/nix/store/...findutils-4.10.0/bin:
             /nix/store/...gnugrep-3.12/bin:/nix/store/...gnused-4.9/bin:
             /nix/store/...systemd-260.2/bin: ...(the same five, sbin)"
```

No profile directory of any kind.

**After**, with `services.devman-dagu.servicePath` prepending the profile roots:

```
Environment="PATH=%h/.nix-profile/bin:/etc/profiles/per-user/%u/bin:
             /run/current-system/sw/bin:/nix/var/nix/profiles/default/bin: ...the five..."
```

systemd expands `%h` and `%u` per user, which is what a per-user service needs.

**Charter impact:** **none, and worth a sentence if §4 is next edited.** §4's
list — `$HOME`, Nix profile, `~/.cache`, git credentials, SSH agent — is right
about why a user service is the correct shape, and wrong that all five arrive
free. `$HOME` does. `PATH` is set by the module.

---

## S4 — Criterion 7, as a paired delta

**Answer:** the stage-1 module adds **+2.04 ms** to a warm `devenv shell --
true`, against the same repo with `devman.enable = false`. Criterion 7 allows
10 ms. The delta is not distinguishable from zero at this sample size.

**Tested:** devenv 2.1.2, warm cache, 10 warm-up entries per variant discarded,
ordinary desktop load.

**Command:** the variants are interleaved one entry at a time, because C2 found
load drift larger than the effect and one sequential sweep reported the enabled
repo as the faster one.

```bash
N=80 python3 /tmp/s1-paired.py \
  "off_enable-false|/tmp/s1-time/off" \
  "on_stage1-guard|/tmp/s1-time/on"
```

Both repos are byte-identical apart from `enable`, and both import the module,
so the delta is registration alone rather than the cost of the input.

**Evidence — 80 paired runs:**

```
variant                  mean      sd  median   min   max   runs=80
off_enable-false       244.1    28.6   249.8   159   311
on_stage1-guard        246.2    28.4   251.2   150   291

paired delta (on_stage1-guard) - (off_enable-false) = +2.04 ms
  sd 23.71   95% CI [-3.16, +7.24]   spread [-80.9, +65.2]
```

The spread is wider than the effect in both directions, which is the same
picture C2 recorded and the reason the criterion is a paired difference rather
than an absolute number.

`enterShell` fires twice per entry (C1), so the per-firing cost is **about
1 ms**, and that firing now does more than C2's guard measured: the `.devman/`
whitelist listing, the local-workflow glob, two parameter substitutions, the
entry comparison, and the `.git/info/exclude` guard. All of it forks nothing.

**Charter impact:** **none.** Criterion 7 is met.

---

## S5 — The ignore rule can be located without forking

**Answer:** yes, and it agrees with `git rev-parse --git-path info/exclude` in
every shape that occurs. C4 chose `.git/info/exclude` and located it with `git
rev-parse`; the hook cannot afford that fork on every entry (C1, C2). Two file
reads replace it.

A `.git` **directory** holds `info/exclude`. A `.git` **file** is a linked
worktree: it holds `gitdir: <path>`, and that directory holds `commondir`,
which points back at the main repository. That second case is exactly why C4
rejected the literal path.

**Command:**

```bash
bash /tmp/s1-exclude.sh   # derives the path both ways in four shapes
```

**Evidence:**

| shape | fork-free derivation | `git rev-parse --git-path info/exclude` | |
|---|---|---|---|
| plain repo | `/tmp/s1x/main/.git/info/exclude` | same | **match** |
| linked worktree | `.../worktrees/linked/../../info/exclude` | `/tmp/s1x/main/.git/info/exclude` | **match** after `readlink -f` |
| this repository | `.../worktrees/special-dragon/../../info/exclude` | `/home/andrew/Documents/Projects/devman/.git/info/exclude` | **match** |
| no `.git` | empty — no rule | no repo | **agree** |

The `..` components are left in place deliberately: `open()` resolves them, and
normalising them would cost the fork the exercise exists to avoid.

**Charter impact:** **none.** §9.2 says to locate the file with `git rev-parse`,
which remains the right instruction for anything that may fork. The hook may
not, and this is what it does instead.

---

## S6 — Stage 1 against §14, criterion by criterion

Entered shells, not evaluated configurations. Registry at `/tmp/s1t/registry`,
four throwaway repos pinning `path:/tmp/devman-src`.

| # | Criterion | Result |
|---|---|---|
| 1 | one flake, two interfaces, one version | **holds** — `nix flake check` passes, both modules come from one rev |
| 2 | a repo adopts in three lines | **holds** — `enable`, `project`, `groups` |
| 3 | a repo may take no groups | **holds** — `projC`, `groups = [ ]`, its own `smoke.yaml` projects |
| 4 | a repo may rename or replace every default | **holds** — `projB` shadows `check`, invents `ci`, then drops `ci`; the projection and the Dagu view both follow |
| 7 | devenv stays on the fast path | **holds** — +2.04 ms paired, budget 10 ms (S4) |
| 8 | registration is idempotent | **holds** — two further entries, `metadata.json` mtime unchanged to the nanosecond |
| 9 | only opted-in repos register | **holds** — `projOff` never appears |
| 10 | no workflow contains an absolute path | **holds** — `grep -rn '/home/\|/tmp/\|/nix/store' groups/` is empty; the registry's absolute paths are `metadata.json`'s `path` and the symlink targets, which is what a registry is for |
| 11 | identity survives a move | **holds** — `projA` moved *and* renamed keeps its project and rewrites `path` |
| 16 | devman adopts itself | **holds** — this repository registers |
| 17 | there is one way in | **holds** — registry deleted, three shells entered, restored byte for byte |

And the two refusals, which are the branches a developer actually sees (C5):

```
$ cd /tmp/s1t/projA-second && devenv shell -- true
devman: refusing to register 'projA'
devman:   already registered at /tmp/s1t/renamed-elsewhere, which still exists
devman:   this repo is        /tmp/s1t/projA-second
devman:   set a different devman.project in one of them

$ mkdir -p /tmp/s1t/projB/.devman/context && cd /tmp/s1t/projB && devenv shell -- true
devman: refusing to register 'projB'
devman:   .devman/ holds entries devman does not recognise: context
devman:   only workflows/ and .runs/ may be there
devman:   move them, or unset devman.enable in this repository
```

Criteria 5, 6, 12, 13, 14 and 15 belong to stage 2 and 3, or need real
workflows first.
