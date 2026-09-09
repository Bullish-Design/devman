# 024 — personal per-repo overlay measurement

## Answer

Choose Option B. Rule 1 fired first: A3 modified the tracked `devenv.lock`.
Therefore `devenv.local.yaml` is dead in Option A. Option A survives for Nix
only. Option B avoids projected files, ignore entries, and ordering cost.

The direct Option B import loaded the personal module and its relative common
import. A V1→V2 edit landed on the next shell entry. The guarded absence path
worked. The residual risk is path handling: the overlay must keep relative
imports valid from its canonical location, and every read must stay behind
`builtins.pathExists`.

## Versions and baseline

Exact commands:

```text
devenv shell -- devenv version
devenv shell -- nix --version
devenv shell -- git --version
devenv shell -- gitman status --json
```

Raw output:

```text
devenv 2.2.2+b8030c5 (x86_64-linux)
nix (Nix) 2.34.7
git version 2.54.0
"commit_id": "d1550f0a7fef125a4dbe5082aef9a8f8ff32ca0e"
"canonical": true
```

The baseline command `git status --porcelain` produced empty output after the
three requested files were committed.

## Experiment A — symlink

### A1 and A2

Command:

```text
ln -s /tmp/ovl-store/projects/probe/devenv.local.nix devenv.local.nix
devenv shell -- ovl-repo 2>&1; echo "exit=$?"
devenv shell -- ovl-common 2>&1; echo "exit=$?"
```

Raw output:

```text
OVL_REPO_V1
exit=0
OVL_COMMON_V1
exit=0
```

Devenv reads the symlink. Nix resolves `../../common/hello.nix` through the
symlink target. The `common/` model works for the Nix file.

### A3

Command:

```text
ln -s /tmp/ovl-store/projects/probe/devenv.local.yaml devenv.local.yaml
devenv shell -- true 2>&1; echo "exit=$?"
git status --porcelain
git diff --stat devenv.lock
rg -n 'nixpkgs-unstable' devenv.lock
```

Raw output:

```text
exit=0
 M devenv.lock
?? devenv.local.nix
?? devenv.local.yaml
 devenv.lock | 19 ++++++++++++++++++-
51:        "ref": "nixpkgs-unstable",
56:    "nixpkgs-unstable": {
76:        "nixpkgs-unstable": "nixpkgs-unstable"
```

This kills the YAML projection. The personal input entered the tracked lock.

### A4

Command:

```text
sed -i 's/OVL_REPO_V1/OVL_REPO_V2/' /tmp/ovl-store/projects/probe/devenv.local.nix
devenv shell -- ovl-repo 2>&1
sed -i 's/OVL_COMMON_V1/OVL_COMMON_V2/' /tmp/ovl-store/common/hello.nix
devenv shell -- ovl-common 2>&1
```

Raw output:

```text
OVL_REPO_V2
OVL_COMMON_V2
```

Each target edit landed on the first shell entry. This did not reproduce the
interpolated-path cache failure documented at `modules/devenv.nix:88-96`.

### A5

Command:

```text
printf '/devenv.local.nix\\n/devenv.local.yaml\\n' >> .git/info/exclude
git restore devenv.lock
git status --porcelain
git stash list
git diff
```

Raw output was empty for status, stash, and diff. Excludes hide the symlinks,
but they do not prevent A3's lock change.

### A6

Command:

```text
unlink devenv.local.nix; unlink devenv.local.yaml
sh -c 'ln -s /tmp/ovl-store/projects/probe/devenv.local.nix devenv.local.nix && devenv shell -- ovl-repo' 2>&1
devenv shell -- ovl-repo 2>&1
```

Raw output:

```text
OVL_REPO_V2
OVL_REPO_V2
```

The first invocation saw the symlink. There is no ordering defect in this
devenv version.

### A7

Command:

```text
mv /tmp/ovl-store /tmp/ovl-store-absent
devenv shell -- true 2>&1; echo "absent-exit=$?"
```

Raw terminating output:

```text
error: path '/tmp/ovl-store/projects/probe/devenv.local.nix' does not exist
absent-exit=1
```

The failure is loud but confusing. It includes a long Nix evaluation trace.

## Experiment B — evaluation-time import

The copy was `/tmp/ovl-devman`. The consumer used `url: path:/tmp/ovl-devman`
and imported `devman/modules`. This changed only throwaway paths.

### B1

The copied module traced `builtins.getEnv "HOME"`.

Command:

```text
devenv shell -- true 2>&1; echo "shell-exit=$?"
devenv test 2>&1; echo "test-exit=$?"
devenv tasks run -v probe:noop 2>&1; echo "tasks-exit=$?"
```

Raw output:

```text
✖ trace: OVL_HOME=/home/andrew
shell-exit=0
✖ trace: OVL_HOME=/home/andrew
test-exit=0
✓ Running probe:noop in 10.9ms
{}
tasks-exit=0
```

Evaluation is not pure in this test. `HOME` was `/home/andrew`. No warning
appeared. The explicit-option fallback was not needed.

### B2

The copied module used:

```nix
imports = lib.optional
  (builtins.pathExists /tmp/ovl-store/projects/probe/devenv.local.nix)
  /tmp/ovl-store/projects/probe/devenv.local.nix;
```

Command:

```text
devenv shell -- ovl-repo 2>&1
devenv shell -- ovl-common 2>&1
devenv test 2>&1; echo "exit=$?"
devenv tasks run -v ovl-repo 2>&1; echo "exit=$?"
```

Raw output:

```text
OVL_REPO_V2
OVL_COMMON_V2
exit=0
Task does not exist: ovl-repo
exit=1
```

Shell and test worked. The task result is inconclusive because the probe
defined scripts, not an `ovl-repo` task. The valid `probe:noop` task passed
in B1.

### B3

Command:

```text
sed -i 's/OVL_REPO_V2/OVL_REPO_V1/' /tmp/ovl-store/projects/probe/devenv.local.nix
devenv shell -- ovl-repo 2>&1
sed -i 's/OVL_REPO_V1/OVL_REPO_V2/' /tmp/ovl-store/projects/probe/devenv.local.nix
devenv shell -- ovl-repo 2>&1
rg -o '/nix/store/[A-Za-z0-9]+-devman-plan-probe.json' .devenv/shell-*.sh | tail -1
```

Raw output:

```text
OVL_REPO_V1
OVL_REPO_V2
.devenv/shell-61a10295de3f913a.sh:/nix/store/yxyam575bis4smpaphq91819pmwj52vm-devman-plan-probe.json
```

The direct import was fresh on the first entry. The same plan path appeared
before and after the edit.

The requested `builtins.readFile` plus `builtins.toFile` workaround was also
tested. Its raw terminating output was:

```text
error: path '/common/hello.nix' does not exist
exit=1
```

The workaround changes the relative-import base to the generated store file.
It does not work with the requested relative common import. This is a path
failure, not a cache-staleness result. The existing cache rationale is at
`modules/devenv.nix:88-96` and `modules/devenv.nix:350-402`.

### B4

Command:

```text
mv /tmp/ovl-store /tmp/ovl-store-b4-absent
devenv shell -- true 2>&1; echo "absent-exit=$?"
```

Raw output:

```text
✖ trace: OVL_HOME=/home/andrew
absent-exit=0
```

The guarded import works without the personal directory. `pathExists` is
sufficient when the read stays inside the guarded branch. An unguarded
`readFile` is not sufficient.

### B5

Command:

```text
git status --porcelain
git diff --stat devenv.lock
git check-ignore -v devenv.local.nix devenv.local.yaml
```

Raw output:

```text
 M devenv.lock
 M devenv.nix
 M devenv.yaml
 devenv.lock | 52 +++++++++++++++++++++++++++++++++++++++++-----------
.git/info/exclude:8:/devenv.local.nix\\tdevenv.local.nix
.git/info/exclude:9:/devenv.local.yaml\\tdevenv.local.yaml
```

The tracked changes are the throwaway B wiring. No personal overlay file
appears. Option B needs no exclude entry. A real implementation must obtain
the personal directory without recording that personal path in tracked source.

### B6

Command:

```text
rg -o '/nix/store/[A-Za-z0-9]+-devman-plan-probe.json' .devenv/shell-*.sh | sort -u
```

Raw output contained only:

```text
/nix/store/yxyam575bis4smpaphq91819pmwj52vm-devman-plan-probe.json
```

The overlay did not change `planFile`. Option B needs zero new guard bash
lines. The comparison is at `modules/devenv.nix:371-402` and
`modules/devenv.nix:833`.

## Shared cost

Exact command:

```text
/nix/store/pgrhba5bp8ghfx0jm7rijr92xkmm9waf-hyperfine-1.20.0/bin/hyperfine --warmup 1 --runs 5 'devenv shell -- true'
```

Raw reports (the first A baseline used ten runs; the other cases used five):

```text
A no overlay:   1.296 s ± 0.049 s, 10 runs
A present:      1.342 s ± 0.051 s, 5 runs
A changed:      1.323 s ± 0.054 s, 5 runs
B present:      1.332 s ± 0.015 s, 5 runs
B changed:      1.410 s ± 0.043 s, 5 runs
```

The command printed means, not medians. Therefore the requested median is
inconclusive from this capture. All measured means exceed the 10 ms budget by
about two orders of magnitude. The budget is documented at
`.scratch/projects/007-standard-workflows/STAGE_7_LOG.md:2896-2959`.

## Charter impact

Amend the charter to state that personal configuration remains outside repo
history, that the repo module may perform an optional guarded eval-time import,
and that its relative imports must resolve from the canonical personal tree.
Reject personal YAML projection because it changes the consumer lock. State
that external content does not enter `planFile`, so no extra guard block is
needed. Preserve principle 5 from `AGENTS.md`.

Relevant devman claims are at `modules/devenv.nix:78-96`,
`modules/devenv.nix:350-402`, and `modules/devenv.nix:833`.

## Decision rule and recommendation

Rule 1 fired. A3 dirtied `devenv.lock`, so `devenv.local.yaml` is dead in A.
A2, A4, B1, B2, B3, B4, and B6 did not disqualify the surviving mechanisms.
Under rule 5, choose B. Implement a guarded direct import and document the
canonical path contract. Do not use the `readFile`/`toFile` workaround with a
relative common import.

