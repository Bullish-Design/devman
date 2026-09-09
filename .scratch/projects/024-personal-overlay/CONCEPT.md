# 024 — the personal per-repo configuration overlay

## 1. What the overlay is

Personal development configuration for every repository lives in **one central
git repository**, the *store*. The store holds `common/` for shared Nix modules
and `projects/<name>/` for per-repo configuration.

Each working repository carries two symlinks into the store:

```text
~/Documents/Projects/scippy/
├── devenv.local.nix   -> <store>/projects/scippy/devenv.local.nix
└── devenv.local.yaml  -> <store>/projects/scippy/devenv.local.yaml
```

`.git/info/exclude` keeps both out of that repository's history. devenv consumes
them. The goal is personal tooling per repository, versioned in one place,
sharing common pieces, never entering anyone else's clone.

**The symlink is not only transport. It is the documentation.** `ls -la` shows
the link, `$EDITOR devenv.local.nix` edits the canonical file in place, and an
agent reading the repository can see that the repository is not its own source.

---

## 2. The settled facts, and the evidence for each

### 2.1 The symlink transport works

Measured in `MEASUREMENT_LOG.md`, experiment A. devenv reads a symlinked
`devenv.local.nix` (A1). Nix resolves relative `../../common/*.nix` imports
through the symlink target (A2). An edit to the store lands on the next shell
entry, with no cache staleness (A4). The first shell entry after creating the
link already sees it (A6).

Versions: `devenv 2.2.2+b8030c5`, `nix 2.34.7`, `git 2.54.0`.

### 2.2 Personal flake inputs cost a modified `devenv.lock`, and that cost is accepted

**This supersedes `MEASUREMENT_LOG.md`, which recorded this as disqualifying and
declared `devenv.local.yaml` dead.** The measurement is correct. The conclusion
drawn from it was not, and it is reversed here.

Re-measured on 2026-09-09 in a fresh probe repository, same devenv version, with
a tracked `devenv.lock` and a clean baseline. A symlinked personal
`devenv.local.yaml` declaring one extra input:

```text
$ git status --porcelain          $ git diff --stat devenv.lock
 M devenv.lock                     devenv.lock | 19 ++++++++++++++++++-
```

```diff
+    "nixpkgs-unstable": { "locked": { "rev": "19a27817106f...", ... } },
     "root": {
-        "nixpkgs": "nixpkgs"
+        "nixpkgs": "nixpkgs",
+        "nixpkgs-unstable": "nixpkgs-unstable"
```

**Why it happens.** devenv merges `devenv.yaml` and `devenv.local.yaml` into one
input set before it locks anything. After the merge no line remembers its file.
devenv pins the merged set and writes the result to `devenv.lock`. There is one
lock path per project, there is no local lock, and no flag redirects the write —
`devenv --help` and `devenv shell --help` offer `--override-input` and
`--offline`, and nothing for lock location.

`inputs:` is the only `devenv.yaml` key with a persisted artifact. Every other
key affects evaluation only, and evaluation writes nothing tracked. Measured:
the same symlink carrying `allowUnfree: true` left the lock clean, and devenv
proved it reads the file by aborting on a deliberate syntax error inside it —
`Failed to parse ./devenv.local.yaml`.

**The decision: take the personal inputs.** These are personal repositories. The
lock churn is a permanently modified tracked file, and a CI relock step removes
it from any repository that ever needs a clean lock — a runner never sees the
symlink, because the symlink is untracked. See §5 for the stated limit that
remains.

### 2.3 Visibility is the governing property

An invisible variant was measured, worked, and was rejected anyway. See §3.8.

### 2.4 No new library is needed, and no existing one fits

All seven plausible owners were surveyed and scored 1-3 out of 5. Each would have
to reverse a documented decision. Not re-surveyed here. Summary retained:
copyroom (managed⇒tracked⇒committed), repoman (fleet scope refused), fleetman
(read-only by charter), vendomat (read-only store path), gitman (repo-scoped),
siteman (documented decision against symlinks), my-ai (deleted its own file
distributor).

### 2.5 dotbot adds nothing

The link map is a **formula**, not a map. One rule keyed on the project name
covers every repository. Dotbot's value is a hand-authored list of arbitrary
pairs. Its `force` default also deletes real files, which is the opposite of the
refuse-don't-clobber behaviour this needs.

### 2.6 The job is small, and it already works by hand

Four repositories carry an untracked, working `devenv.local.nix` today:
`foreman`, `forgelab`, `image-gen-pipeline`, `lodestar`. 38 of 64 devenv
repositories already gitignore `devenv.local.nix`. The registry holds 52
projects (`~/.local/share/devman/projects`).

---

## 3. The decisions

### 3.1 Q1 — devman owns the exclude line and the visibility check. Do not split `modules/`

**Decision: devman owns it, in the module it already ships. Reject the two-import
split.**

devman already writes `.git/info/exclude`, worktree-aware and idempotent
(`modules/devenv.nix:788-827`). It already ships `doctor`. Its module already
runs in every repository. Nothing else on this machine has a registry or a
repository path (§2.4).

The scope objection — that devman is the reactive automation layer and this is
not that — is answered by a name, not by a file split. devman's repository
already holds two things: **membership** (`enable`, `project`, `registryDir`,
the registry, the exclude writer) and **automation** (`groups`, Dagu, workflows,
triggers). The identity layer is already wider than the automation layer. The
overlay attaches to membership.

**The split was examined and it is not viable.** Three findings, each mechanical:

1. `modules/` is not a flake output. `flake.nix:34-53` exports `overlays`,
   `nixosModules`, `packages` and `checks`, and no `devenvModule`. devenv reaches
   `modules/` as a raw subdirectory. A split is therefore two directories, each
   holding a file named `devenv.nix` (`modules/devenv.nix:18-21`), and **an
   edited `imports:` list in all 52 registered repositories** — the concrete
   cost, paid once per repository, for no new capability.

2. The two halves are entangled by construction, not by accident. The membership
   guard's relink loop reads `devman_names`, which is seeded from the automation
   fold `resolved` (`modules/devenv.nix:593`). The guard's single most important
   condition compares `planFile` (`modules/devenv.nix:833`), which
   `modules/devenv.nix:388-389` records as "the only thing that notices a changed
   group file, a changed trigger map, or a changed renderer". `planFile` is named
   by the membership identity and filled with automation values
   (`modules/devenv.nix:390-400`). A split needs a shared base module exporting
   `projectName`, `registryDir`, `renderer` and the resolved attrsets.

3. **Two flake checks would break.** `flake.nix:80-95` (`shell-variable-unset`)
   greps one file and requires one `unset` block ending in `devman_cur`
   (`modules/devenv.nix:841-847`). `flake.nix:136-176` (`hook-path-refusal`)
   cuts the refusal block out of `${./modules/devenv.nix}` by literal path.

Splitting now is speculative generality. Revisit it when a second consumer of
the membership half actually exists.

### 3.2 Q2 — the store is `~/Documents/Projects/devman-personal`, a plain git repo

**Decision: `~/Documents/Projects/devman-personal/`. Plain git, and a devenv
repository. Not adopted into the plane for v1. Overridable by a Nix option
`devman.overlayDir`.**

The two candidates in the source concept are both taken:

- `~/.config/devman/` does not exist on this machine, and it is the natural home
  for the devman tool's own configuration. Do not squat it.
- `~/.local/share/devman/projects/` **is the registry**, holding 52 project
  metadata directories (`src/devman/registry.py:36`,
  `modules/devenv.nix:486`). A hard collision.

The stronger argument is §2.3. **The store is source you edit every day, not
machine state.** Source lives with source. A store under `~/.config` or
`~/.local/share` is exactly the invisibility already rejected: `ls
~/Documents/Projects` would not show it. vendomat already treats
`~/Documents/Projects` as this machine's source root
(`VENDOMAT_DEV_ROOT`), so the placement is consistent rather than novel.

Make it a devenv repository, so it gets a `check` task that evaluates the Nix it
holds — a store whose `common/` does not evaluate breaks every repository at
once (§3.7). Do **not** adopt it into the plane in v1; that creates a bootstrap
loop, and the overlay must work before the plane does.

Follow `registryDir` for the option shape (`modules/devenv.nix:484-488`): a
machine-level path with a default, not a per-project value. This keeps principle
5 intact — see §6.

### 3.3 Q3 — two symlinks, not three

**Decision: link `devenv.local.nix` and `devenv.local.yaml`. Do not link
`.modules`.**

Both linked names are consumed by devenv at fixed names in the repository root.
There is no alternative location for either, and §2.2 makes the `.yaml` required
rather than optional.

`.modules` is different in kind. It is reachable through `devenv.local.nix`'s
own `imports` list, and A2 measured that relative imports resolve correctly
through the symlink target. It therefore buys no capability.

Its only argument is discoverability, and the thread already exists: you see
`devenv.local.nix`, you open it, and its `imports` name the modules. The
discoverability requirement is that **a thread exists**, not that every file sits
at the root. The cost is a dotfile in the root of 64 repositories, a third
exclude line, and a second link to keep correct.

Both are reversible. Start with two. Add `.modules` if the imports thread proves
insufficient in practice.

### 3.4 Q4 — copyroom is the right owner for store content, and it is sufficient. Defer it

**Decision: copyroom, not a direct Copier integration. Not in v1.**

§2.4 rejected copyroom as the owner of the **projection**, because its invariant
is managed⇒tracked⇒committed and a project repository must not track these files.
Question 4 asks something different: who manages the store's *own* content.

Inside the store that invariant holds. The files there **are** tracked and
committed by design (§1). `projects/<name>/` rendered from a
`templates/project/` template is precisely copyroom's job, and it needs no new
feature. Its `require_clean_worktree` default
(`copyroom/src/copyroom/project/config.py:53`) is a condition the user controls
in their own store, unlike in a project repository.

Nothing is missing. What is missing is the **need**. The store has zero projects
today. A template that has never been evolved is a guess about which files will
change together. Adopt copyroom at the second structural change to an existing
project's layout — that is the first moment template evolution beats editing two
files.

v1 writes a starter `devenv.local.nix` of about five lines and nothing else.

### 3.5 Q5 — yes, a repo outside the plane can have an overlay, through the CLI

**Decision: the CLI does the work. The module only calls it. `devman overlay
link` works in any git repository.**

The symlink is a file. devenv reads `devenv.local.nix` whether or not devman
exists. The only thing a non-plane repository lacks is something to *run* the
code, because it has no shell-entry hook.

So put the logic in the CLI, not in the hook. This follows property 7 — Python
for core logic, shell stays a thin wrapper — and it settles three questions at
once: non-plane repositories (this one), worktrees (§3.6), and testability.

The command needs a project name. **Take it as an explicit argument outside the
plane; never infer it from the directory name.** Directory-name inference is the
exact defect recorded in §8. Inside the plane it defaults from `devman.project`.

```text
devman overlay link                     # in-plane: name from devman.project
devman overlay link --project scippy    # anywhere else: name stated
devman overlay status
```

### 3.6 Q6 — worktrees do not break, but the module never reaches them

**Decision: accept it. The CLI covers the worktree case. Do not touch the
refusal.**

The exclude-file sharing is harmless, and for the same reason `.devman/.runs/`
is harmless. Git treats `info/` as a common path, so a linked worktree shares
its main repository's exclude file — "per checkout" is really per clone
(`006-automation-plane/CONCEPT.md:1061-1066`). The rules are
`/devenv.local.nix` and `/devenv.local.yaml`, and both are right in every
worktree of the same repository. Sharing them is a convenience: the worktree
inherits the lines already written.

**The real finding is different, and it is structural.** A linked worktree has
the same `devman.project` — the name is stated in the tracked `devenv.nix` — at a
different path, while the recorded path still exists. That is exactly the
duplicate-registration refusal at `modules/devenv.nix:778-786`. The refusal
branch returns, so the `else` branch at `modules/devenv.nix:788` never runs.
**A worktree therefore reaches neither the exclude writer nor anything attached
to it.**

That refusal is load-bearing: `modules/devenv.nix:780-782` records it as §9.1 and
as what keeps criterion 11 working (C5). Do not weaken it to carry the overlay.
Run `devman overlay link` in the worktree instead.

### 3.7 Q7 — `doctor` must catch the dangling link. The shell-entry failure cannot be improved

**Decision: add a `doctor` check. Accept the Nix trace, and prevent the dangling
link at creation time.**

A7 measured an absent store: `error: path '...' does not exist`, exit 1, with a
long Nix evaluation trace. The exposure is larger than one repository. **The
store is one directory serving every repository at once**, so a moved store, a
renamed store, or a new machine with the store not yet cloned breaks the whole
fleet simultaneously.

Three parts to the answer:

1. **The shell-entry failure cannot be intercepted.** Nix evaluates
   `devenv.local.nix` before any `enterShell` hook runs. No module code can stat
   the link first. This is not fixable, and it should not be worked around.

2. **It is acceptable as-is.** The message names the exact missing path. That is
   loud and it carries the thread to pull. Principle 4 asks for a loud refusal
   over a silent default, and confusing is not silent.

3. **`doctor` catches it first, fleet-wide.** A new check reads the registry, and
   for each project stats `<path>/devenv.local.nix`; if it is a symlink whose
   target is absent, it reports the project and the target. This is the cheap
   shape `check_local_sources` uses (`src/devman/doctor.py:1080-1083`): work
   proportional to registered projects, with no fork per project.

Additionally, `devman overlay link` creates the target file before it creates the
link, so it never produces a dangling link itself. Only a later move or delete
can.

### 3.8 Retained rejection — the invisible Nix-import variant

`modules/devenv.nix` could import `<store>/projects/${devman.project}` at
evaluation time behind `builtins.pathExists`. It passed every measurement: it
works under `devenv shell` and `devenv test` (B2), handles an absent store
gracefully (B4), needs no exclude entry (B5), and does not change `planFile`, so
it costs zero guard bash (B6).

**It is rejected on discoverability.** With it, `ls -la` shows nothing,
`git status` shows nothing, an agent reading the repository cannot see it, and a
repository behaves differently from its own source with no thread to pull. That
is a silent default affecting everything — the failure principle 4 exists to
prevent.

**`MEASUREMENT_LOG.md:363-369` recommends this variant** ("Under rule 5, choose
B"). That recommendation is superseded. The log weighed only what it could
measure, and discoverability is not measurable by shell exit codes. A later
reader must not take the log as current.

---

## 4. What the plane must not learn

Stated so a future change does not reverse it by accident.

- The plane holds no project fact. The overlay path is the formula
  `<overlayDir>/projects/<devman.project>/`. `overlayDir` is a machine-level
  option and `devman.project` is a **name**. No absolute project path enters a
  workflow, and no per-project option enters Nix. Principle 5 holds.
- The store is canonical. The symlink is derived. Never edit through the link's
  repository as if the repository owned the file — it is the same inode.
- The overlay is membership, not automation. It runs no workflow, needs no Dagu,
  and no group ships it.

---

## 5. The stated limits

1. **`devenv.lock` stays modified in any repository that declares a personal
   input.** It never converges: CI relocks it clean, and the next shell entry
   re-dirties it. This is accepted (§2.2). The residual risk is that
   `git commit -a`, or an agent running `git add -A`, publishes the personal
   input into project history. `.git/info/exclude` cannot prevent this, because
   `devenv.lock` is tracked.

2. **A repository with no `.git` gets no exclude rule.** This is correct — there
   is nothing to ignore — and it matches the existing writer's behaviour
   (`006-automation-plane/CONCEPT.md:1061-1062`).

3. **A linked worktree gets nothing from the module** (§3.6).

4. **A moved or absent store breaks every overlay repository at once**, with a
   Nix trace and no interception possible (§3.7).

5. **Not verified, and worth checking during implementation:** whether a
   permanently modified `devenv.lock` interferes with gitman lane operations,
   and whether devman's own lock readers — `check_local_sources`
   (`src/devman/doctor.py:1061`) and `check_path_inputs`
   (`src/devman/doctor.py:1138`) — produce noise when they encounter a personal
   input. Both read `devenv.lock` across the whole registry.

---

## 6. What the charter has to change

Three amendments. Each is required by a decision above.

1. **Principle 3 gains names.** It currently reads "Four names are shared by
   every repository at once: the six queue names, `DEVMAN_PROJECT_DIR`,
   `DEVMAN_SELF_DIR`, and the `.devman/.runs/` path shape." The overlay adds a
   fifth and a sixth: **the two exclude rules `/devenv.local.nix` and
   `/devenv.local.yaml`**, and **the store path shape
   `<overlayDir>/projects/<name>/`**. Principle 3 says adding one changes the
   charter, because every repository inherits it. This is that change, made
   deliberately.

2. **The tier table gains a stated exception.** A personal `inputs:` entry
   modifies existing tracked source — `devenv.lock` — outside a lane. The tier
   table has no tier for that, and calls the shape out by name. Record it as a
   deliberate, user-accepted exception scoped to `devenv.lock` and to personal
   inputs only. It is not a licence for any other untiered write.

3. **`CONCEPT.md` §9 gains the overlay as a second thing the exclude writer
   writes.** Today it writes one rule. It will write three.

Principle 5 needs no change (§4). Property 7 is satisfied by §3.5.

---

## 7. The implementation plan, sized honestly

Nothing here is a product. The estimate is half a day of work plus the
documentation, and the documentation is the larger half.

| # | Work | Size |
|---|---|---|
| 1 | Create the store: `devman-personal` with `common/`, `projects/`, `README.md`, a devenv `check` task that evaluates `common/` | ~30 lines, one repo |
| 2 | `devman overlay link` / `overlay status` in the CLI. Refuse-don't-clobber, modelled on `copyroom/src/copyroom/agent/files.py:161-176` — return `ok`, `created` or `refused`, and **never replace a regular file** | ~120 lines Python |
| 3 | Extend the exclude writer to append the two rules (`modules/devenv.nix:821-827`) | ~6 lines shell |
| 4 | Add `devman.overlayDir`, shaped after `registryDir` (`modules/devenv.nix:484-488`) | ~8 lines Nix |
| 5 | Call `devman overlay link` from the hook, guarded by `[ -d ]` on the project's store directory so it forks nothing when absent — the guard shape at `modules/devenv.nix:832-838` | ~8 lines shell |
| 6 | `doctor` check `overlay links` — dangling-target detection over the registry (§3.7) | ~40 lines Python |
| 7 | Docs: `USER.md`, `AGENTS_GUIDE.md`, the `devman` skill, and the store's own `README.md` | the larger half |

**Order.** Items 1 and 2 first, and stop there. That combination is already
usable by hand in any repository, in or out of the plane, and it is what §2.6
shows four repositories are doing manually today. Items 3-5 only remove the
manual step. Item 6 before item 5, so the fleet-wide failure is detectable before
it becomes automatic.

**Verify before saving**, per `CLAUDE.md`:

```bash
devenv tasks run -v base:check
devenv tasks run -v base:test
devman doctor
```

Item 3 touches `modules/`, so `devman doctor` must exit 0 before it is committed.
Note that `flake.nix:80-95` will require any new `devman_*` variable in item 5 to
appear in the `unset` block at `modules/devenv.nix:841-847`.

---

## 8. Follow-on: publish the registry as a shared machine fact

**Record it. Do not chase it in this project.**

Three tools independently need "repository identity → path on this machine", and
only devman has it.

- **devman** — identity is **stated** in `devenv.nix`, and the registry is
  populated by shell entry, never by scanning. It lands at
  `~/.local/share/devman/projects/<name>/metadata.json`
  (`src/devman/registry.py:36`).
- **fleetman** — `src/fleetman/models.py:26` reads `name: str  # directory name
  (authoritative identity)`. Renaming a directory changes the identity. devman
  refuses this exact inference because it loses run history. **This is a latent
  bug**, and §3.5 avoids repeating it.
- **vendomat** — `VENDOMAT_DEV_ROOT`, default `~/Documents/Projects`, described
  in its own documentation as a deliberately unused seam.

The registry is already JSON at a documented path. The likely answer is to
**publish it as a shared machine fact**, not to extract it into a new repository.
That is a separate project with its own measurement.
