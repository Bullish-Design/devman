# Lane plan — the Linkman cutover

Answers section F. Written 2026-10-05 against devman trunk `f4a245f`.

**Revised the same day**, after a step-back review chose a different architecture
from the one M14 lanes 8-10 assumed. The four choices are recorded in
`DECISIONS.md` §A as D23-D26. The architecture rests on four verified premises,
listed in §0 — none of it is assumed.

This plan supersedes
`linkman/.loci/projects/001-devman-cutover/m14-lanes-8-10-refactoring-guide.md:926-954`.
It is shorter than that guide, not because it does less, but because the CLI
route removes whole categories of work rather than sequencing them.

**Verification vocabulary.** `base:check` = ruff. `base:unit` = pytest (3.13.15).
`base:test` = `nix flake check`, also the `gitman.toml` `[publish] verify` hook.
`doctor` = `devman doctor`, must exit 0. **devman does not use Testee**; the
guide's `testee verify` commands for devman are wrong
(`m14-lanes-8-10-readiness-review.md:67-71`).

---

## 0. The architecture, and the four premises it rests on

**Shape.** nix-meta installs the `linkman` CLI on the system profile. devman's
shell-entry hook writes the bootstrap file, runs `linkman apply`, then projects
`.git/info/exclude`. `links.yaml` is the only declaration. devman keeps no link
mechanics.

**P1 — the CLI takes everything devman needs. VERIFIED.**
`linkman apply --repo-root X --overlay Y --name Z` reproduces
`devman-link reconcile --root X --overlay Y --project Z` exactly
(`linkman/src/linkman/cli.py:36-41`; `repository.py:42-59`). `apply --json`
emits `applied[]`, `refused[]`, `failed[]` per link with messages and
`error_type` (`models/results.py:87-96`), so devman gets *more* structure than
`devman_link.reconcile` gives it today. Demonstrated against live /tmp fixtures.

**P2 — the exclude projection decouples. VERIFIED.** `exclusion_entries`
(`src/devman_link/excludes.py:50-58`) reads only `link.declaration.view` and
`link.declaration.canonical`, and its `in {"central","external"}` filter
collapses to one binary test — is the resolved target inside the repo root —
which is exactly `TargetScope` at `linkman/src/linkman/topology.py:52-53`.
Computable from `links.yaml` + repo root with `pyyaml` and no Linkman import.
Cross-checked per key against the real `devenv.local.nix` for `devman`, `gitman`
and `flora`: no mismatch. Everything else in `excludes.py` —
`git_exclude_path`, `append_entries`, `local_gitignore_path`, `State`,
`content_hash`, `link_path` — is already generic.

**P3 — the private input is a solved problem. VERIFIED.** nix-meta already
carries `git+ssh` inputs (`silverbullet-server` at `flake.nix:211`,
`inferference` at `:259`), and `machines/server.nix:435-448` already configures
root's SSH declaratively for exactly this reason, exercised on every
`sudo nixos-rebuild switch --flake .#server`. A private `linkman` input adds no
new credential plumbing. This dissolves what I had recorded as operator question
Q7.

**P4 — the 60 central files do not need to change in this push. VERIFIED.**
All 60 overlay projects carry both `links.yaml` and `devenv.local.nix`, and
`links.yaml` is a **superset**: 4 are identical, and 56 differ only by the
`devenv.local.nix` self-link that `links.yaml` carries *extra*. So switching the
engine to read `links.yaml` loses no declaration. `modules/link.nix` keeps its
option *declarations* (so Nix evaluation still succeeds in all 60 files) while
its hook changes — the `devman.link` attribute sets simply go **inert**.

P4 is what makes the scope choice possible. The hardest, most operator-gated,
hardest-to-reverse work — rewriting 60 files in a repository an agent cannot
land into — moves out of this push without blocking the engine swap.

---

## The lanes

| # | Lane | Where | Scope | Prereq | Reversible |
|---|---|---|---|---|---|
| 1 | `m14-l8.0a-tools-fileset` | devman | `flake.nix` | — | yes |
| 2 | `m14-l8.0b-doctor-git-path` | devman | `nix/devman-cli.nix`, `nix/tests/dagu-service.nix` | — | yes |
| 3 | `m14-l9v-diff-all-projects` | devman (`.scratch/`) | a verification report, no source | 1, 2 | n/a — read-only |
| 4 | `m14-l9w-excludes-on-links-yaml` | devman | `src/devman/linking.py`, new `src/devman/excludes.py` | 3 | yes |
| 5 | `m14-l9x-adapter-calls-linkman` | devman | `src/devman_link/` only — **not** `modules/link.nix` | 4 | yes |
| 6 | `m14-l9y-port-watch-and-cli` | devman | `src/devman/watch.py`, `src/devman/cli.py` | 5 | yes |
| 7 | `m14-l9z-install-linkman` | **nix-meta** | `flake.nix` inputs, a profile | 6 | yes |
| 8 | `m14-l9z2-pin-and-switch` | **nix-meta** | `flake.lock`, one rebuild | 7 | yes — generation rollback |

Eight lanes, down from fifteen. Lanes 7 and 8 are in nix-meta, not devman.

---

## Lane by lane

**1. `m14-l8.0a-tools-fileset`. ✅ DONE 2026-10-06.** `flake.nix` now includes
`./tools` in the Python test source. The first hermetic run then exposed a
missing `nix-instantiate`, so the check also takes `pkgs.nix`. The targeted build
exited 0 in 15 s. It ran all three cutover modules: 720 passed, 26 skipped in
11.36 s. Remove the `./tools` entry when the cutover tooling is deleted.

**2. `m14-l8.0b-doctor-git-path`. ✅ DONE 2026-10-06.** The CLI wrapper now puts
`git` on PATH. The VM then reached doctor's universal-pool check. Its fixture
now supplies a minimal `writing/SKILL.md`. The targeted VM build exited 0 in
121 s, and VM doctor printed "Nothing to report." D29 records the O4 decision.

**Combined verification, 2026-10-06:** `base:check` exited 0 in 6 s;
`base:unit` exited 0 in 20 s with 745 passed and 1 skipped; the whole
`base:test` exited 0 in 29 s with "all checks passed!"; host `devman doctor`
exited 0 in 2 s with "Nothing to report." Both source commits landed and
pushed on devman main at `651af40`. See `RESEARCH_REPORT.md` for the failure
sequence and full command evidence.

**3. `m14-l9v-diff-all-projects`. ✅ DONE 2026-10-05. Report:
`VERIFY-diff-all-projects.md`.**

**Verdict: the cutover is a complete no-op on every project it could be run
against.** Measured across all 60 overlay projects (59 with a live checkout;
`foreman` has none, per O7):

- `linkman check`: exit 0 and `clean: true` for all 59. **283 of 283 links
  `correct`. Zero refusals.**
- `linkman diff`: exit 0 for all 59. **All 283 planned actions are `noop`.**
- **Disjoint-namespace risk (O1): 0 of 60 would refuse.** Only
  `~/Documents/Projects/linkman/links.yaml` exists as a repo-level declaration,
  and it declares no links and no vars.
- **Exclude-set equality: 58 of 59 identical**, once `flora`'s one hand-written
  scratch-file line is correctly classified as not-owned by the projection.
- Zero dangling targets, zero unresolved `${env.*}`/`${vars.*}`, zero
  `real_file`/`real_dir`/`special`, zero parse failures, zero non-empty stderr
  across 177 invocations.

Independently spot-checked by the orchestrator: `devman`, `gitman`, `flora`,
`repoman` each exit 0, `clean: true`, all links `correct`.

**This is the evidence the whole plan was built to obtain, and it came back
clean.** The engine swap changes no link on any project. That is a far stronger
guarantee than the abandoned 7-day flag hold would have produced.

**One item must be settled before lane 4 — see O0, and it is not a lane-4
bug.** `linkman`'s own overlay `links.yaml` omits `.loci`, which every
comparable project declares. The directory is real, untracked, 336K across 17
files, and `~/Notes/1_Projects/linkman` does not exist. The legacy `.loci` line
in its `.local.gitignore` survives lane 4 untouched, because `append_entries`
never removes lines — so the cutover is unaffected. Fix it anyway: those 17
files are this cutover's governing documents and they have no second copy.

This lane is the single highest-value item in the plan, because it converts the
whole cutover risk into evidence *before* anything changes. Three things it must
specifically look for:

- **Disjoint-namespace refusals.** `load_layers`
  (`linkman/src/linkman/config.py:44-76`) treats the repo layer and the overlay
  layer as a disjoint namespace, **not** an override: the same link name in both
  raises `ConfigError`. Any project carrying its own repo-level `links.yaml`
  that names a key the overlay also names will refuse where `devman_link`
  silently resolved. Count them.
- **Every refusal and every non-`correct` status**, per project, with the
  `safe_next_step` Linkman supplies.
- **Exclude-set equality.** For each project, compute the exclude entry set from
  `links.yaml` by P2's binary test and diff it against the current
  `.local.gitignore`. Any difference is a lane-4 bug found before lane 4 is
  written.

Gate: a written report with per-project results. No source change, so nothing to
roll back. If this lane finds systematic refusals, the plan stops here and is
re-made — which is the point of running it third rather than eighth.

**4. `m14-l9w-excludes-on-links-yaml`.** Reimplement the exclude projection
against `links.yaml`, per P2. Drop `_as_resolved_links`, `Declaration` and
`ResolvedLink` from `src/devman/linking.py:105-129` — that adapter exists solely
so `ensure_local_gitignore` can run unmodified, by its own docstring at `:24-27`,
and it carries no information the projection needs. Reuse `git_exclude_path`,
`append_entries`, `local_gitignore_path`, `State`/`content_hash` and `link_path`
verbatim. The target interpolation (`${vars.*}`, `${env.*}`, `${repo.name}`) is
~100 lines already written standalone at `linkman/src/linkman/resolve.py:1-161`;
port or reimplement, do not import.

Gate, and it is the gate this milestone has never had: `.git/info/exclude` is
**byte-identical** before and after, across all 60 projects. Lane 3 produced the
baseline. Rollback: revert. Reversible.

**5. `m14-l9x-adapter-calls-linkman`.** The lane that swaps the engine.

**Scope correction, 2026-10-05: `modules/link.nix` needs no edit at all.** The
hook keeps calling `devman-link reconcile`; the substitution happens inside the
binary. So the live `link-module.nix` — still built from tag `v0.7.0` — does not
change, and neither does any of the 60 central files that import it. One package
changes.

**Orchestration already exists, in Python, in the right order.**
`src/devman_link/api.py:82-114` does identity → bootstrap → validate →
reconcile today, and `reconcile.py:33-37`'s docstring states the reason:
"Nix evaluates `devenv.local.nix` before any hook runs, so the canonical file
must exist before the link does." This lane replaces **one call** — step 4's
`reconcile()` — with `linkman apply --repo-root --overlay --name`. It is a
substitution, not new orchestration.

Find the binary with `shutil.which("linkman")` and raise a typed error with a
`repair:` line if absent. That is the house style, with five precedents —
`central.py:197-209`, `config.py:166-185`, `reconcile.py:139-157`,
`doctor.py:296-333`, `reconcile.py:600-618` — all `check=False`, **never
`check=True`**. The `makeWrapper` route used for `dagu`/`watchexec`
(`nix/devman-cli.nix:65-70`) is unavailable, because D23 forbids Linkman as a
Nix build input of any devman derivation.

**Gate exclude-projection on `apply --json`'s `applied[]`.** If `linkman apply`
partially fails, projecting an exclude line for a view that was never linked
would leave the two inconsistent. Only the Python wrapper can see the
`applied`/`refused`/`failed` partition and act on it. Reuse the 0/11/13
translation already written at `src/devman/cli.py:440-448`.

Deleted here: `reconcile.py`'s five-state machine, `paths.py`'s resolution math,
`declarations.py`, `config.py`'s Nix evaluation, `state.py`'s promotion hash —
roughly 1,000 of `src/devman_link`'s 1,427 lines. The promotion guard's job
passes to Linkman's present-tense `MigrationCollisionError`, which needs no
stored hash.

**Also removed here: the `template` branch** (`reconcile.py:138-157`) and its
field in `declarations.py:36,53-59`, `config.py:102-112` and the
`modules/link.nix:50-53` option. Per D27 this is removal, **not** abandonment —
central-overlay templating is wanted and becomes its own initiative, at adoption
time in devman's CLI. The branch goes now because it could never have worked:
it locates copyroom with `shutil.which`, and copyroom is never on `$PATH` by
design (RepoMan invokes it by absolute path via `$REPOMAN_TOOLCHAIN_BIN`). Its
failure mode is also the worst available — a `LinkError` here aborts the whole
project's reconcile, and `enterShell` discards the exit code (O9).

**This lane carries the `025/CONCEPT.md` §11.1 amendment** that CLAUDE.md
property 2 requires: templating moves from "the reconciler renders any declared
`template`" to adoption, through the CLI, by absolute path. §11.1's reasoning is
untouched — auto-template stays legitimate in the central config repo and only
there.

**`modules/link.nix` keeps its option declarations and changes only its hook**
(`:70-75`). Per P4 the 60 `devman.link` attribute sets go inert, not away. The
`repo` kind stays in the enum, inert, for the same reason. Do not narrow the
enum here — it would spend a `nixos-rebuild` to remove a type nothing uses, and
`modules/link.nix` ships inside the adapter derivation.

Gate: the no-registry install check (`nix/link-adapter.nix:75-135`) rewritten
against `links.yaml` — same fixture repo, asserting the documented Linkman exit
code. Keep the fixture; it is the check that proves the adapter needs no
registry. Rollback: revert. Reversible — nothing has shipped to the machine yet.

**6. `m14-l9y-port-watch-and-cli`.** `watch.py:606-611` discards `reconcile`'s
return value and `:622-629` flattens four refusals plus two tool failures into
`code = 1`. Replace with a parse of `linkman apply --json`, distinguishing
refused (11) from failed (13) per link. `src/devman/cli.py:411-449` already has
the correct shape; `_link_reconcile_with_linkman` and the
`DEVMAN_LINK_ENGINE` branch at `:554-558` both retire here — per D24 the flag is
abandoned, so there is no dual-engine period to serve. Gate: a fixture that
refuses returns 11 and one that fails returns 13, distinctly. Rollback: revert.

**7. `m14-l9z-install-linkman`. In nix-meta.** Add the input following the
`silverbullet-server` precedent, and put
`inputs.linkman.packages.${system}.linkman` on `environment.systemPackages` via
a profile, following the `profiles/agent.nix:39-46` pattern. Profiles are
`inputs: { … }` functions composed by `profiles/default.nix`, and
`mkMachine` passes `specialArgs = { inherit inputs; }`, so no new plumbing is
needed. `bin/` is linked into the system profile by default — no `pathsToLink`
entry required. Gate: `/run/current-system/sw/bin/linkman --help` exits 0.
Rollback: revert and rebuild. Reversible.

**8. `m14-l9z2-pin-and-switch`. In nix-meta. The one step that reaches the
machine.** Tag devman, bump nix-meta's `devman` input (currently locked at
`4c9927a`, tag `v0.7.0`, 2026-09-15 — five-plus commits behind trunk), and
`sudo nixos-rebuild switch --flake .#server`. One rebuild, because lanes 7 and 8
can be combined into a single switch if preferred.

**Rollback is a NixOS generation activation** — one atomic, already-tested
command, which is the whole reason D24 abandoned the env flag. Gate: sample
shell entry across 10 projects, confirm `.git/info/exclude` unchanged, confirm
`doctor` exits 0, then 59 of 60 projects entering cleanly. Record the generation
number before switching.

---

## F2. Reversibility

**Seven of the eight lanes are reversible by `gitman undo` or a revert.** Lane 3
mutates nothing at all.

**There is no hard-to-reverse lane in this push.** That is the main gain over the
previous plan, which had two — rewriting 60 files in a repository an agent cannot
land into, and deleting the adapter package from the system profile.

**The single hardest-to-reverse step is lane 8's `nixos-rebuild switch`**, and
its rollback is the best-tested mechanism on the machine: boot or activate the
previous generation. It goes last, and it is the only lane whose effect is
visible in all 59 projects at once.

---

## F3. Not in this milestone

- **Emptying the 60 central `devenv.local.nix` files.** Deferred by P4 and by
  the scope decision. It needs operator question Q3 (the hook's permanent home),
  Q6 (the one project of 60 importing a different module), and an operator
  `gitman land` into `~/.config/devman` that the permission classifier correctly
  denies to an agent (`041/DECISIONS.md:297-326`, D9). Nothing in lanes 1-8
  depends on it.
- **Deleting `installLinkAdapter`, `nix/link-adapter.nix` and
  `packaging/devman-link/`.** The adapter survives this push, shrunk by ~1,000
  lines and calling Linkman. Deleting the package is only worthwhile once the
  60 files stop importing `link-module.nix`, which is the deferred item above.
- **Narrowing the `canonical` enum / removing the `repo` kind.** Zero live uses
  (180 `central`, 52 `external`, 0 `repo`), and `links.yaml` schema v1 has no
  kind field at all, so it disappears with the attribute set rather than needing
  migration.
- **Deleting `tools/cutover/`** and with it the hard-coded
  `~/Documents/Projects/linkman/.devenv/state/venv/bin/linkman` in `gate.py`, an
  AGENTS.md property 5 violation. Lane 3 still uses that binary.
- **Linkman's dangling-target reporting gap.** Filed as O7 for Linkman's owner
  by `041/DECISIONS.md:329-358` (D10). devman computes dangling detection itself
  and must keep doing so, so it blocks nothing here.
- **Central-overlay templating, rebuilt.** Wanted (operator intent,
  2026-10-05) and recorded as D27, but it is a **new capability, not cutover
  work**. It needs: a home in devman's CLI at adoption time, copyroom located
  by absolute path rather than `shutil.which`, and an answer to where template
  intent is declared now that `links.yaml` cannot carry it
  (`OPEN-QUESTIONS.md` O3). Lane 5 removes the broken call; nothing in lanes
  1-8 depends on the replacement existing.
- **The silently-swallowed `enterShell` failure** (`OPEN-QUESTIONS.md` O9).
  Pre-existing, measured, and not caused by the cutover. Worth its own fix
  because it makes every shell-entry correctness claim advisory.
- **Render-to-link** (`025/CONCEPT.md` §6.2a) and **`registryDir` →
  `~/.config/devman`** (Stage 3 item 2). Both independently deferred.
- **The library route.** Not chosen, not partially taken. If devman ever needs
  Linkman's `environ` override — the one capability with no CLI equivalent — that
  is the trigger to revisit, and `OPEN-QUESTIONS.md` O6 records it.

Two small corrections to fold into whichever lane next touches the file, rather
than giving either a lane: `AGENTS.md` property 6 records generation 3 with 48
projects, where the live pointer is **generation 4** with 44; and the installed
`link-module.nix` at `/run/current-system/sw/share/devman/` still carries a
compatibility fallback that trunk has dropped, so the live module and the repo
copy already differ.
