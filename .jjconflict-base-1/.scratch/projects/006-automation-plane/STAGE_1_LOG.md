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

**Answer:** the stage-1 module's cost is **not distinguishable from zero** at
this sample size, against the same repo with `devman.enable = false`. Two
sweeps of 80 paired entries measured **+2.04 ms** and **-0.85 ms**. Criterion 7
allows 10 ms.

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

**Evidence — two sweeps of 80 paired runs.** The second is the module as
shipped; the first is the module before S8 changed group resolution to
`builtins.readFile`, and it is kept because two sweeps of one effect say more
about the noise than one does.

```
sweep 1                  mean      sd  median   min   max   runs=80
off_enable-false       244.1    28.6   249.8   159   311
on_stage1-guard        246.2    28.4   251.2   150   291
paired delta = +2.04 ms   sd 23.71   95% CI [-3.16, +7.24]   spread [-80.9, +65.2]

sweep 2, as shipped      mean      sd  median   min   max   runs=80
off_enable-false       218.5    36.5   225.8   147   275
on_stage1-final        217.6    40.1   222.6   134   286
paired delta = -0.85 ms   sd 26.01   95% CI [-6.55, +4.85]   spread [-82.2, +53.3]
```

The second sweep is *negative*, which is the same artefact C2 warned about
arriving in a paired measurement rather than a sequential one: the effect is
smaller than the noise, so its sign is not meaningful. What both sweeps do
establish is a bound — the 95% intervals put the cost under 8 ms in the worse
sweep and under 5 ms in the other, against a 10 ms budget.

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

## S7 — devenv rejects a bare task name, so the charter's examples do not run

**Answer:** every task name needs a namespace. `CONCEPT.md` §5, §6 and §7.4 all
write `tasks."lint".exec = ...`, and none of them evaluates.

**Command:** the first attempt to adopt this repository, with §5's own example.

**Evidence:**

```
$ devenv shell -- true
  × Invalid task name: lint. Task names must be in format 'namespace:name'
    and can only contain alphanumeric characters, ':', '-', and '_'.
    The '@' character is reserved for dependency suffix notation.
```

`tasks."base:lint"` is accepted, and `devenv tasks run base:lint` resolves.

**The namespace is the group's own name.** §7.1 already says task names are
group-local convention and never reserved, so this makes the rule literal
rather than changing it, and it means two groups' `lint` cannot collide in a
repository that takes both. §7.1's closed list of three global names is
untouched: task names were never on it, because a group is content, not
contract.

The cost is real and worth stating. A repository taking `base` and `python`
defines `base:lint`, `base:test`, `python:lint`, `python:typecheck` and
`python:test` — five names for three commands, because python shadows `check`
and `validate` while base's `full-test` survives and still calls its own. §7.4
already answers it: to be rid of one, do not take its group. Both group
READMEs say so.

**Charter impact:** **changes §5, §6, §7.2 and §7.4.** Applied in its own
commit.

---

## S8 — devenv's evaluation cache does not see a group file's content change

**Answer:** interpolating a group file's **path** copies it to the store, and
devenv's evaluation cache does not track that. The projection kept pointing at
the previous store path on every subsequent shell entry, and Dagu kept running
the old workflow. `builtins.readFile` is a read the cache does track.

**Tested:** devenv 2.1.2. Spike A established that devenv hashes content rather
than mtime; this is the case it does not hash at all.

**Command:** edit `groups/base/workflows/check.yaml`, re-enter the shell, look
at what the projection points at.

**Evidence — before, with a plain path:**

```
$ grep -n "devenv tasks run" groups/base/workflows/check.yaml
8:    run: devenv tasks run base:lint          <- edited
$ devenv shell -- true
$ readlink ~/.local/share/devman/projects/devman/workflows/check.yaml
/nix/store/8ql5x3441s1wqav5kk6a4by6vzw0vs68-check.yaml
$ grep "devenv tasks run" ~/.local/share/devman/projects/devman/workflows/check.yaml
    run: devenv tasks run lint               <- the OLD content
```

Repeated entries did not help. The DAG ran and failed with
`Task does not exist: lint`, which is at least loud — but only because the old
name had been renamed. An edit that changes what a step *does* would have run
the old step silently.

**Evidence — after, with `builtins.readFile` and `pkgs.writeText`:**

```
$ printf '# cache-probe-1\n' >> groups/base/workflows/check.yaml
$ devenv shell -- true
$ grep -c cache-probe-1 ~/.local/share/devman/projects/devman/workflows/check.yaml
1                                            <- tracked
$ sed -i '/cache-probe-1/d' groups/base/workflows/check.yaml
$ devenv shell -- true
$ grep -c cache-probe ~/.local/share/devman/projects/devman/workflows/check.yaml
0                                            <- the removal too
```

**Who meets this.** A repository pinning a rev with `git+https` never does: a
changed group file is a changed rev, and the whole input re-resolves. A
repository importing `./modules` meets it on every edit — which is exactly this
repository, adopting itself under criterion 16.

**Charter impact:** **none.** §9.3 says the registry is derived and the
repository is canonical; this is a case where the derivation silently stopped
re-deriving.

---

## S9 — Dagu seeds example DAGs into an empty DAG directory

**Answer:** on first start Dagu writes five example DAGs into `dags_dir`. The
DAG directory is the registry, so the registry acquires five workflows
belonging to no project. `skip_examples: true` stops it.

**Evidence:** the NixOS test, before the flag:

```
$ dagu ls
demo-check
example-01-basic-sequential
example-02-parallel-execution
example-03-scheduling
example-04-nested-workflows
example-05-template-and-file
```

`skip_examples` is a real config key — `internal/cmn/config/loader.go:355` —
though `config.schema.json` does not list it. The NixOS test now asserts that
no `example-` name appears.

**Two things Dagu still writes there, and both are fine.** After adopting this
repository and running one workflow:

```
$ ls -a ~/.local/share/devman/dags/
.dag.index   devman-check.yaml   devman-full-test.yaml   devman-validate.yaml   wiki/
```

`.dag.index` is Dagu's discovery cache and `wiki/` is an empty directory it
creates. Neither is a DAG, neither is listed, and the projection's cleanup
touches neither — it removes only links whose target it recognises. Worth
recording because it means `dags/` is Dagu's view of the registry rather than
devman's private directory, and a `doctor` that treats every file there as its
own would be wrong.

**Charter impact:** **none.** It is a setting, and the module sets it.

---

## S10 — Stage 1 against §14, criterion by criterion

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
| 10 | no workflow contains an absolute path | **holds** — `grep -rnE '(^\|[^A-Za-z0-9_])/(home\|tmp\|nix/store\|var\|Users)/' groups/` is empty, and so is the same grep over the projection's file contents. The registry's own absolute paths are `metadata.json`'s `path` and the symlink targets, which is what a registry is for |
| 11 | identity survives a move | **holds** — `projA` moved *and* renamed keeps its project and rewrites `path` |
| 16 | devman adopts itself | **the registration half holds** — this repository registers, and `devman-check` ran `devenv tasks run base:lint` here through Dagu and recorded it. §11's cross-repo workflows need a second registered repository and are stage 2 |
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

---

## S11 — `devman 0.2.0`: removed from the profile

**Answer:** it arrived through **`programs.nix-terminal.devman.enable`** in
`/home/andrew/Documents/Projects/nix-meta/profiles/terminal.nix`. The option is
now `false`, committed there as `03b80a7`. **The rebuild is not run** — that is
the user's, and STAGE_1_PROMPT §8 forbids it here.

The first draft of this entry recommended leaving it, on the grounds that the
switch also removes a workspace launcher the developer uses. **That was wrong,
and measuring it is what showed why:** the launcher was already inert.

### Finding it

**Command:**

```bash
readlink -f /etc/profiles/per-user/andrew/bin/devman
nix-store -q --referrers-closure /nix/store/...-devman-0.2.0 | head -3
grep -rln devman /home/andrew/Documents/Projects/nix-meta --include='*.nix'
```

**Evidence:**

```
/nix/store/i1cpdmw9w0hflws2fzm544r2v1scxkd5-devman-0.2.0/bin/devman
  -> devman-env -> home-manager-path

nix-meta/profiles/terminal.nix:72
  programs.nix-terminal.devman = { enable = true; withClaudeCode = false; withCodexCli = false; };
```

The option is nix-terminal's, at `modules/terminal.nix:159`, and it adds
`devman.lib.mkDevmanEnv { ... }` to `home.packages`. nix-terminal takes devman
as a flake input, pinned to `github:Bullish-Design/devman` rev `d8a302c` — an
old revision of this same repository.

### What is actually lost

The option's own description calls it "the devman workspace orchestrator
(tmuxp + Claude Code + Neovim)", which is why the first draft of this entry
recommended keeping it. Measuring it says otherwise:

```
$ ls /nix/store/...-devman-env/bin/
devman
$ nix-store -q --references /nix/store/...-devman-env
/nix/store/i1cpdmw9w0hflws2fzm544r2v1scxkd5-devman-0.2.0
$ command -v tmuxp
(not on PATH)
$ command -v nv
/etc/profiles/per-user/andrew/bin/nv      <- nix-nvim, not devman
```

**One binary, and its tmuxp launcher had no tmuxp to launch.** `withClaudeCode`
and `withCodexCli` were already `false`, so the env had been reduced to devman
itself. `claude` comes from `profiles/agent.nix` and `nv` from nix-nvim;
neither moves.

What the developer does lose is `devman up`, `down`, `switch`, `bootstrap` and
`index` as commands. `up` could not have worked without `tmuxp`; the others
were not tested one by one.

### The change, and how it was checked

`profiles/terminal.nix` now reads `devman.enable = false;`, with the reasoning
in a comment beside it. Checked by evaluation, with the old value stashed back
in as a control so that an empty result is evidence rather than a query that
finds nothing:

```
with enable = true   home.packages -> ["devman-env"]
with enable = false  home.packages -> []
```

49 packages either way.

**The user ran the rebuild, and it took:**

```
$ command -v devman
                          <- nothing
$ command -v nv
/etc/profiles/per-user/andrew/bin/nv
```

`nv` and `claude` are unaffected, as predicted. §13's stage-1 cleanup 1 is
done.

### Why this was worth doing before the CLI exists

§3.3 and §10 say stage 1 either replaces 0.2.0 in the profile or takes a
different name, and "does not ship alongside it". Stage 1 ships no CLI, so the
*name* collision is not live yet. The **destructive** hazard is:
`devman 0.2.0`'s `init --force` calls `shutil.rmtree` on a `.devman/` it does
not recognise (§15.2, D6). Today this repository's `.devman/` holds only
`.runs/`, which is derived and git-ignored. The moment a repository tracks
`.devman/workflows/` — stage 2 — that command deletes canonical state.

**Charter impact:** **none.** §13's stage-1 cleanup 1 is now done, bar the
rebuild.

---

## S12 — What stage 1 did not do

| Item | Why |
|---|---|
| the watcher (§8) | stage 3. The module is shaped so it is a second user service reading the same registry |
| the CLI (§10) | stage 3, and §10 says to prove the conventions by hand first |
| activating the removal of `devman 0.2.0` | S11 — the one line in `nix-meta` is changed and committed; `nixos-rebuild switch` is the user's |
| installing the NixOS service on this machine | needs `nixos-rebuild switch`, which STAGE_1_PROMPT §8 forbids. The module is proved by a NixOS VM test instead, and by a hand-run Dagu against the real registry |
| `.devman/workflows/` in this repository | §11's cross-repo workflows need a second registered repository, which is stage 2 |
