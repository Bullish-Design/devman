# Kickoff: implement the toolchain refactor (project 023)

Paste this whole file as the first message of a clean session. Work **one phase
per session**; the phase boundaries are the safe stopping points.

**Start the session in the repository named by that phase's "Session root".** It
decides which `AGENTS.md`, agent skills and per-project memory load. The
evidence paths below are absolute and readable from any root.

---

## What you are doing

The machine's Python tooling has three distribution mechanisms competing for one
job. Move each tool to the correct side of one line and remove every second
owner of a name.

**The governing rule:**

> A console script is a property of the machine. An import is a property of the
> repository that imports it. **No repository imports across a repository
> boundary.**

The end state:

```
pyjutsu — native library
   built ONCE by vendomat: hermetic, relocated, manylinux-tagged
   published to a GitHub release from that same store file
   eventually: consumed only by the gitman package derivation

gitman · repoman · copyroom · docman · templateer — CLIs
   built once as Nix Python applications, all at Python 3.13
   composed into one roster closure, on PATH everywhere

the other ~60 repos
   declare ZERO first-party Python dependencies
   call console scripts; their venvs hold only their own application deps
```

---

## Read first, in this order

All under `/home/andrew/Documents/Projects/devman/.scratch/projects/023-toolchain/`:

1. `TARGET.md` — the design. **Authoritative; it supersedes the others where
   they disagree.**
2. `RUNBOOK.md` — the step-by-step, with commands, verification and rollback.
3. `PROBLEMS.md` — P1-P10, the defects being fixed.
4. `GRAPH.md` §2 — how the environment propagates across each boundary.
5. `MEASUREMENTS.md` — the numbers. Do not re-measure these.
6. `VENDOMAT.md`, `FLEET.md` — background. Both carry a supersede banner.

Then, for the phase you are on, the repository's own `AGENTS.md`, plus:

- `vendomat/.scratch/projects/03-shared-repoman-toolchain/CONCEPT.md` (Phase 4)
- `gitman/.scratch/projects/32-loci-core-adoption-issues/ISSUES.md` §G3 and
  `35-wheel-distribution/OUTCOME.md` (Phase 3 — read before touching wheels)
- `devman/.scratch/projects/021-changelog/DESIGN.md` and
  `022-templateer-changelog/KICKOFF.md` (Phase 2)

Repositories in scope: `devman`, `gitman`, `pyjutsu`, `templateer_v2`,
`repoman`, `vendomat`, `nix-meta`, `nix-terminal` — all under
`/home/andrew/Documents/Projects/`.

---

## Facts already measured. Do not re-derive them.

- `devenv shell -- python3 -c 'import pyjutsu'` **fails**; `devenv shell --
  gitman` **works**. RepoMan's module lends console scripts through `PATH`;
  `PATH` does not set `sys.path`. This is P1 and it breaks
  `groups/changelog/workflows/changelog.yaml` today.
- A Dagu step does **not** inherit the daemon environment. It re-derives from
  `/etc/profile` + Home Manager session vars. `env_passthrough_prefixes` is
  `[DEVMAN_]`, so `GPU_LLM_*` reach a step only as DAG `params:`.
- Three interpreters are live: Home Manager `repoman` on **3.12**, the toolchain
  venv on **3.13.13**, every devenv on **3.13.14**. The 3.13.13/3.13.14 split is
  *not* an ABI problem — it is a `sys.path` problem. The 3.12 split **is** an ABI
  wall: `ImportError: _pyjutsu.abi3.so: undefined symbol: Py_GetConstantBorrowed`.
- Vendomat's nix-built wheel becomes a portable manylinux artifact after two
  mechanical steps (`--compatibility`, then relocate). Proven: it imports in a
  clean venv and needs only `libgcc_s`, `libm`, `libc`, `ld-linux`.
- `devman` has **no `uv.lock`** and its devenv venv is empty. `import yaml` was
  resolving through a stray `.pth`.
- Warm `devenv shell --` costs ~0.755 s; cold (after any edit to a `git+file:`
  source repo) ~6.05 s. `changelog.yaml` pays it four times.
- The `inferference-router` is **up and correctly configured** through
  `nix-meta/machines/server.nix`. Leave it alone.

---

## Do not reverse these

1. **`gitman/pyproject.toml`'s `[tool.uv.sources]` pyjutsu URL stays.** It is the
   fix for issue G3 and it is what makes gitman adoptable in a repo with no Nix.
   `TARGET.md` keeps it; the store wheelhouse becomes an accelerator that emits
   *the same bytes*, never a replacement.
2. **The loud failure on an unset `${DEVMAN_PROJECT_DIR}`.** A run must record
   `Failed`. Do not add a default.
3. **`devman` gets no `uv.lock` and no populated venv.** Its `devenv.nix`
   already argues this ("one name, two installs, resolved by order"). The whole
   point of Phase 2 is that a workflow calls console scripts, so devman needs
   no Python dependencies at all.
4. **`GPU_LLM_BASE_URL` / `GPU_LLM_MODEL` stay as DAG `params:`.** Nothing about
   the endpoint belongs in Nix.
5. **The five queue names, `DEVMAN_PROJECT_DIR`, `DEVMAN_SELF_DIR`,
   `.devman/.runs/`.** Changing any of these changes devman's charter.

---

## Phases

Do these in order. Each is independently useful and independently revertible.

### Phase 0 — stop the bleeding (zero risk, one sitting)

**Session root:** `~/Documents/Projects/devman`


Delete the stray `_agent_factory_spike_siblings.pth`; `uv tool uninstall
gitman`; `nix profile remove devenv`. `RUNBOOK.md` Phase 0 has the commands.

Success: `devenv shell -- python3 -c 'import templateer'` now **fails**. That is
the point — the masked dependency becomes visible.

### Phase 1 — one owner per name (low risk, one NixOS rebuild)

**Session root:** `~/Documents/Projects/nix-meta` — its memory carries
`no-ai-commit-attribution`, which applies to the commits this phase makes.


`uv` into `home.packages`; the toolchain venv onto `home.sessionPath` (LAST, so
it cannot shadow a Nix binary); remove the Home Manager `repoman`; record
**Python 3.13** as the baseline in writing; move `repoman/flake.nix` from
`python312Packages` to `python313Packages`.

Success: `type -a repoman` prints exactly one line, in a login shell and in a
devenv. `zsh -lic 'gitman status'` works.

### Phase 2 — make the changelog workflow correct (medium risk)

**Session root:** `~/Documents/Projects/devman` — this phase needs the
`devman-workflow` and `gitman` skills and devman's `AGENTS.md`.


This is the phase that fixes P1. In order:

1. Add `gitman log --revset '<a>..<b>' --json` to gitman. It does not exist;
   the CLI is all lane-lifecycle verbs, which is why the direct `pyjutsu` import
   was justified. Emit `change_id` and `description`; JSON to stdout only;
   non-zero exit on a bad revset with the revset in the message.
2. Tag `templateer_v2` and reference it as
   `git+https://github.com/Bullish-Design/templateer_v2@vX.Y.Z`. It is pure
   Python — it needs neither `relocate_wheel.py` nor the
   `_PYTHON_HOST_PLATFORM` unset.
3. Add `templateer` to `repoman.lock` so its console script joins the shelf.
4. Rewrite `changelog.yaml`: no `import pyjutsu`, no `PYTHONPATH`, no
   `TEMPLATEER_PATH`, no `uv run --project <sibling>`.
   `TEMPLATEER_TEMPLATE_PATH` resolves through `$DEVMAN_SELF_DIR`.
5. **Add a `finish_reason` check.** Measured on the live endpoint: gemma returns
   `content: ""` with `finish_reason: "length"` on a short token budget — an
   HTTP 200 carrying nothing. Fail the step on anything but `stop`.
6. Add the interpreter probe as a check that runs the way a *step* runs it.
   Both `repoman doctor` and `gitman doctor` report `pyjutsu` green while a step
   fails, because each asks its own interpreter.

### Phase 3 — repair the vendomat builder, then reproducibility (medium risk)

**Session root:** `~/Documents/Projects/vendomat`. Note it carries no `gitman`
skill and no memory — read `gitman/.agents/skills/gitman/SKILL.md` explicitly
before any version-control operation.


**Read `TARGET.md` in full before starting, and gitman project 35.**

1. `vendomat/lib/mkMaturinWheel.nix`: pass `--compatibility manylinux_2_39` and
   run the relocate step in `postBuild`. Reuse `pyjutsu/scripts/relocate_wheel.py`
   rather than reimplementing it.
2. `vendomat publish <lib>` uploads **that exact store file** to the GitHub
   release, so hash equality is by construction.
3. Invert `UV_NO_BUILD_PACKAGE`: a missing store wheel falls back to the declared
   URL. A broken wheelhouse must never take down a devenv shell again.
4. One `vendomat.toml` per editable manager (`gitman`, `repoman`, `copyroom`,
   `docman`) so `repoman.lock`'s four live working trees become pinned refs.
   Preview with `vendomat publish --dry-run` before pushing anything.
5. Pin `repoman.lock`'s `git-pyjutsu` entry to the release URL, removing the
   `UV_FIND_LINKS` precondition from the machine bootstrap.
6. Scope Face A down in vendomat's README, and remove the `vendomat/modules`
   import from the ten repos that enable no face.

### Phase 4 — the shared command closure (large; a separate project)

**Session root:** `~/Documents/Projects/vendomat`. Same caveat as Phase 3.


Follow `vendomat/.scratch/projects/03-shared-repoman-toolchain/CONCEPT.md` §6
phasing exactly: `copyroom` and `repoman` first, `gitman` and native last.
Do not begin before Phases 0-3 are stable.

Decide §8.2 before writing code: is Vendomat's flake lock authoritative in store
mode, or does `repoman.lock` gain a `toolchain:` source kind? Either needs a
mismatch check, not implicit precedence.

---

## Decisions that are the owner's, not yours

Ask; do not choose:

1. `pkgs.devenv` (2.1.2) or the `devenv v2.2` that `nix-meta/flake.nix` pins and
   nothing installs. Moving ~60 devenvs is its own change.
2. Whether `gitman log` belongs in gitman at all — it is a read verb in an
   otherwise lane-lifecycle CLI. The alternative is that the changelog group
   declares `pyjutsu` and accepts the coupling.
3. Whether `templateer` belongs on the shared shelf or stays scoped to the
   `changelog` group. The 022 kickoff says not to make it a dependency of every
   devman adopter.
4. Whether to push the wheelhouse to cachix.

---

## Verification

Per repository, use that repo's own documented gate — read its `AGENTS.md`;
several are `testee verify`, devman's are below. Do not invent a command.

For devman, all three must exit 0 before committing anything under `modules/`,
`groups/`, `nix/` or `src/devman/`:

```bash
devenv tasks run -v base:check
devenv tasks run -v base:test
devman doctor
```

After every phase, the ladder in `RUNBOOK.md` "Verification ladder":

```bash
for c in python3 repoman devenv gitman uv templateer; do type -a $c; done
#   ...in a login shell AND in a devenv. Exactly one line each.

zsh -lic 'bash .scratch/projects/023-toolchain/evidence/probe.sh'
devenv shell -- bash .scratch/projects/023-toolchain/evidence/probe.sh
#   Compare against INVENTORY.md §3.
```

**A devenv is not a Dagu step.** Prove Phase 2 in a real step, in a disposable
adopter, through real `gitman start` / `save` / `land` and the real post-hook
chain — plus both refusals (empty batch, second unreviewed lane). The evidence
directory has a working disposable-DAG recipe; note that `dir:` is now
`working_dir:` and `env` is a reserved step id.

---

## Version control

- **devman:** route every mutation through gitman — lane, `save`, `publish`, PR
  to `main`. Never raw `git`/`jj`. Do not batch unrelated phases into one lane.
- **Other repos:** follow that repository's own rules; read its `AGENTS.md`.
- Preserve unrelated worktree changes. devman's tree currently has a large
  number of unrelated modifications — **do not clean them up.**
- Do not commit or push investigation notes unless asked.

---

## Evidence to retain

Write into `.scratch/projects/023-toolchain/evidence/` as you go:

- The before/after of each `type -a` and probe run.
- The Dagu step log proving the rewritten `changelog.yaml` works.
- `vendomat publish --dry-run` output for each manifest.
- The relocated-wheel smoke test, if you change `mkMaturinWheel.nix`.
- Every gate's exit code.
- Anything that contradicts `MEASUREMENTS.md` — that matters more than a pass.

---

## Stop conditions

Stop and write a design note rather than choosing silently if:

- `repoman doctor` refuses the toolchain venv after adding `templateer` — its
  `pydantic-ai-slim[openai]` + `minijinja` tree may not coexist with gitman's.
  That answers an open question; it does not authorise weakening the check.
- `repoman-sync`'s `wheel:` source parser rejects a PEP 508 direct reference.
  Add a `url:` source form; do not bend `wheel:`.
- Making `changelog.yaml` work needs an absolute sibling path, or weakens the
  fixed-lane collision refusal or the empty-batch refusal.
- A relocated nix-built wheel fails its smoke test — that would contradict
  `TARGET.md`'s central measurement and the design must be revisited, not
  patched around.
- Anything requires `sudo` beyond `nixos-rebuild`, or would touch a running
  service other than through a declared Nix option.

## Non-goals

- Do not re-run the investigation. It is in this directory.
- Do not touch `inferference` — the router is up and correctly declared.
- Do not fix the `git+file:` dirty-input cost (P5) here. It is real, measured,
  and a separate project.
- Do not garbage-collect the 43 GB uv cache or the 6.9 GB cargo target as part
  of a phase. `RUNBOOK.md` Phase 5 holds them.
- Do not add a queue, a secret, a scheduler, or a hosted model.
