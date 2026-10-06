# M14 Lane 9c+ — devman/Linkman integration: investigation and planning session

You are working in `/home/andrew/Documents/Projects/devman`.

Written 2026-10-05, from the linkman repository, immediately after Linkman was
published as a pinnable Nix package. Every line number below was verified that
day against devman trunk `f4a245f`.

## Scope — read this twice

**This session investigates and plans. It does not implement.**

No file edits outside this project directory. No lane creation. No `links.yaml`
changes. No linking. No `nixos-rebuild`. No engine-default flip. No deletion of
`devman_link`.

End with written findings and a concrete lane plan, then stop and report. If you
believe an edit is unavoidable to answer a question, say so and ask first.

The one exception: you may create the documents named under **Deliverables**,
inside this directory, and nothing else.

## Why this session exists now

Linkman's publishing blocker is cleared. devman's own research doc records it as
the thing that gated everything:

> `.scratch/projects/041-central-autoland/RESEARCH-cutover-interlock.md:266`
> ```
> 5. OPERATOR DECISION (Q1): publish Linkman as a fetchable, pinnable
>    package. Outward-facing (new repository visibility), so it is the
>    user's call, not an agent's, per the review's own framing.
>    BLOCKS: Lane 9c entirely ("nothing here starts without it").
> ```

Q1 is now answered. As of 2026-10-05, Linkman is published:

- Repo: `github.com/Bullish-Design/linkman` — **private**
- Tag: **`v0.1.0`** at commit `06de662`
- Flake input URL: `git+ssh://git@github.com/Bullish-Design/linkman?ref=refs/tags/v0.1.0`
- Outputs: `packages.{linkman,linkman-lib,default}`, `overlays.default`,
  `apps.default`, `checks.{linkman,overlay}` — systems `x86_64-linux`,
  `aarch64-linux` only
- Its own nixpkgs is pinned to `a7868a72`; interpreter is `python313Packages`

### Two things about that package you must not get wrong

1. **It is a `buildPythonPackage`, not a `buildPythonApplication`.** This is
   deliberate and it differs from `nix/link-adapter.nix`. An application wraps
   its output so no other Python package can import it — correct for a leaf
   command, fatal here, because devman's adapter must `import linkman`. The CLI
   is `toPythonApplication` applied to the same build.

2. **Consume it through `overlays.default`, not through
   `packages.${system}.linkman-lib`.** The overlay adds `linkman` to
   `pythonPackagesExtensions`, so devman builds it with *devman's own* nixpkgs
   and interpreter. Taking the package output directly mixes Python packages
   built from two nixpkgs revisions, which is how an ABI mismatch arrives.
   Vendomat already handles `pyjutsu` this way for gitman — that is the
   precedent.

Already proven upstream: a throwaway separate flake pinning the tag built a
hermetic `buildPythonApplication` whose binary printed
`adapter imported linkman 0.1.0`, exit 0. So the mechanism works. What is
unproven is every devman-specific question below.

## Verified state of devman right now

Confirmed by direct read on 2026-10-05; treat line numbers as current but
re-verify before relying on any one of them.

**Version control.** gitman-managed. `gitman.toml` sets `trunk = "main"` and
`[publish] verify = ["nix", "flake", "check"]` with `verify_timeout = 3600`.
Trunk was at `f4a245f fix: prune orphaned compatibility DAG links`, working copy
clean — except for this project directory, which the linkman session added.

**The gate.** `devenv.nix:125` — `"base:test".exec = "nix flake check"`. So
`nix flake check` is both the publish verify hook and the test task. The
lanes-8-10 readiness review claims it has been **red since Lane 2**. Confirm or
refute that first; everything downstream is scheduled around it.

**Linkman's current stand-in.**
```
pyproject.toml:35-36   [project.optional-dependencies]
                       cutover = ["linkman", "pytest"]
pyproject.toml:38-39   [tool.uv.sources]
                       linkman = { path = "../linkman", editable = true }
```
An editable sibling checkout. No hermetic build can use it.

**The hermetic builds that must change.**
```
nix/link-adapter.nix:35-38   { lib, python3Packages, nix }:
nix/link-adapter.nix:43-49   the fileset (src/devman_link, src/devman_contract,
                             packaging/devman-link/pyproject.toml, modules/link.nix)
nix/link-adapter.nix:70      build-system = [ python3Packages.hatchling ];
nix/link-adapter.nix:71      dependencies = [ ];
nix/devman-cli.nix:62-63     build-system = [ python3Packages.hatchling ];
                             dependencies = [ python3Packages.pyyaml ];
```
Neither lists `linkman`.

**The flake.**
```
flake.nix:24-26   inputs = { nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable"; };
flake.nix:44      packages = forAllSystems (pkgs: ...
flake.nix:62      checks  = forAllSystems (pkgs: ...
```
Single input. Idiom is a hand-rolled
`forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system})`
over four systems including darwin — note Linkman ships Linux only.

**The engine flag.**
```
src/devman/cli.py:556   and os.environ.get("DEVMAN_LINK_ENGINE") == "linkman"
                        inside _link_command (def at :535)
src/devman/cli.py:410   _link_reconcile_with_linkman (docstring at :412)
```
One read site. No default literal — anything not `"linkman"` takes the legacy
branch, so it is default-off. The readiness review's blocker B5 says this flag
has never governed a real shell entry.

**Everything still importing `devman_link`** (17 files):
```
src/devman/watch.py          src/devman/cli.py        src/devman/doctor.py
src/devman/linking.py        src/devman/registry.py   src/devman/central.py
src/devman_contract/__init__.py   src/devman_contract/manifest.py
src/devman_contract/identity.py   src/devman_link/api.py
nix/link-adapter.nix
tests/unit/{test_cutover_convert,test_linking,test_link_adapter,
            test_doctor,test_identity,test_cli}.py
```

**The two undisclosed consumers, precisely located:**
```
src/devman/doctor.py:63    from devman_link.state import STATE_FILE
                           used by check_link_drift (:1582),
                           check_ledger_stale (:1691),
                           _write_ledger (:1660), _read_ledger_raw (:1672)
src/devman/watch.py:58     from devman_link import LinkError, reconcile
                           used in dispatch (:564), dispatch_command (:360),
                           supervise (:417)
```

**The NixOS install path.**
```
nix/nixos-module.nix:400   installLinkAdapter = mkOption { ... default true (:402)
nix/nixos-module.nix:697-700  environment.systemPackages = ...
                              ++ lib.optional cfg.installLinkAdapter linkAdapter;
nix/nixos-module.nix:706-707  environment.pathsToLink = ... [ "/share/devman" ]
modules/link.nix              77 lines; canonical enum at :43 —
                              types.enum [ "central" "repo" "external" ]
```

## Required reading, in this order

Linkman's contract documents live in the other repo. Read them there; do not
copy them here.

1. `/home/andrew/Documents/Projects/linkman/.loci/projects/000-Initial-concept/linkman-concept.md`
   — §3 (non-goals), §12 (the nine invariants), §14 (the devman relationship and
   its six-step flow), §15 (the API surface)
2. `/home/andrew/Documents/Projects/linkman/.loci/projects/000-Initial-concept/decisions.md`
   — all 19; D2, D5, 13, 16 and 17 bear directly on this session
3. `/home/andrew/Documents/Projects/linkman/.loci/projects/001-devman-cutover/m14-lanes-8-10-readiness-review.md`
   — the current lane order and blockers B4/B5; **this supersedes the original
   `m14-refactoring-guide.md` for Lanes 8-10**
4. `/home/andrew/Documents/Projects/linkman/.loci/projects/001-devman-cutover/m14-lanes-8-10-refactoring-guide.md`
   — Lanes 8.0, 8a-8c, 9a-9e, 10.1-10.2, 11
5. `/home/andrew/Documents/Projects/linkman/.loci/projects/001-devman-cutover/b4-reconcile-trigger-endorsement.md`
   — the reconcile-trigger recommendation
6. `/home/andrew/Documents/Projects/linkman/.loci/projects/002-check-reporting-gap/check-reporting-gap.md`
   — a known Linkman reporting gap, deferred, **not** a blocker
7. `/home/andrew/Documents/Projects/linkman/flake.nix` and
   `/home/andrew/Documents/Projects/linkman/nix/linkman.nix` — the actual
   package you are consuming, including its install check
8. This repo: `.scratch/projects/041-central-autoland/RESEARCH-cutover-interlock.md`,
   `DECISIONS.md`, `LANE-ASSESSMENT-devman.md`

Precedence rule, from Linkman's own contract: **decisions override the concept
where they disagree; the guide is followed where it conflicts with judgment —
and any conflict found must be called out rather than silently resolved.**

## Questions to answer

### A. Is the gate green?

A1. Run `nix flake check` and report the actual result with output. Is the
"red since Lane 2" claim true today? If red, what exactly fails, and is it
Lane 8.0's scope or something new?

A2. Does `nix flake check` currently build `checks.link-adapter`? If the adapter
gains a `linkman` dependency, what else in `checks` rebuilds, and how long does
the gate then take against `verify_timeout = 3600`?

### B. Wiring Linkman in

B1. Write out — as a proposal, not an edit — the exact diff to `flake.nix` to add
the `linkman` input and apply `linkman.overlays.default`. devman's
`forAllSystems` uses `nixpkgs.legacyPackages.${system}`, which is **not**
overlayable in place. State precisely how the overlay gets applied given that
idiom, and whether it forces a move to
`import nixpkgs { inherit system; overlays = [...]; }`.

B2. devman's flake covers four systems including two darwin ones. Linkman ships
Linux only. What breaks on `nix flake check --all-systems`, and what is the
right resolution — narrow devman's systems, gate the linkman-dependent outputs
with `optionalAttrs ... isLinux`, or ask Linkman to widen? Recommend one.

B3. Which derivations need `linkman` in `dependencies` —
`nix/link-adapter.nix:71` only, or `nix/devman-cli.nix:63` too? Justify from
which code paths actually import it.

B4. `nix/link-adapter.nix` exists to be independent: its fileset excludes
`src/devman`, and its install check proves it. Does adding `linkman` violate the
spirit of that independence, or satisfy it? Does the no-registry fixture install
check still pass, and does it need extending to cover the Linkman path?

B5. What happens to `pyproject.toml:35-39` — the `cutover` extra and the
editable `../linkman` source? Removed now, or kept until the lane that deletes
the cutover tooling? Note what still needs the editable path (the tests under
`tests/unit/test_cutover_convert.py`?) and sequence accordingly.

B6. Linkman's package pins `python313Packages` because its own nixpkgs' bare
`python3` has rolled to 3.14. Which interpreter does devman's
`nixpkgs.legacyPackages` give you, and does the overlay route produce a
consistent interpreter across `link-adapter`, `devman-cli` and `python-tests`?
Show the versions you actually observe.

### C. The two undisclosed consumers — the real design work

C1. **`doctor.py:63` imports `from devman_link.state import STATE_FILE`.**
Linkman has **no state file**: concept §4 and decision D2 delete durable
ownership state outright, on the grounds that it "stopped working after a
repository move, in CI, in a container, and on a second machine." So
`check_link_drift` (:1582) and `check_ledger_stale` (:1691) rest on a concept the
replacement does not have.

This is not a port. Answer: what do these two checks actually assert, what does
the ledger exist to detect, and can that property be expressed from Linkman's
seven-call pipeline — `discover_repository → load_layers → build_desired_state →
validate_topology → inspect_state → build_plan → apply_plan` — plus
`classify_status`? If it cannot, say so plainly and name what devman must keep
owning. Do **not** propose re-adding a state file to Linkman; D2 is settled and
Trap 5 names re-adding it as the specific thing not to do.

C2. While you are there: read
`/home/andrew/Documents/Projects/linkman/.loci/projects/002-check-reporting-gap/check-reporting-gap.md`.
`linkman check` reports a **dangling** symlink as `status: "correct"`,
`clean: true`, exit 0 — correct by its six-status model, which describes only the
link side. Does `check_link_drift` depend on detecting exactly that case? If so,
this deferred gap becomes a real dependency for Lane 9a and must be reported as
such.

C3. **`watch.py:58` imports `LinkError, reconcile`.** Map `reconcile`'s contract
onto the pipeline. Where does `LinkError` map in Linkman's taxonomy
(`ConfigError`, `ResolutionError`, `TopologyError`, `SafetyError`,
`MigrationError`)? Does `watch.py`'s error handling distinguish cases Linkman
collapses, or vice versa? Note Linkman's exit codes are an API: `0` ok, `1`
drift, `10` config, `11` refusal, `12` OS, `13` partial — and `11` vs `13` is a
deliberate distinction between a safe refusal and a real failure.

C4. The remaining four `src/` importers — `linking.py`, `registry.py`,
`central.py`, and the three `devman_contract` modules. For each: what does it use
`devman_link` for, and is it Phase D (move the feature out), Phase E (port onto
Linkman), or neither?

### D. Reaching real shell entry — blocker B5

D1. Trace the actual shell-entry path end to end. `modules/link.nix` is reported
to call `/run/current-system/sw/bin/devman-link` directly on `enterShell`. Confirm
that, and confirm whether `devman_link/cli.py` reads `DEVMAN_LINK_ENGINE` at all.
If it does not, the flag has never governed a real reconcile — state that as a
finding with evidence.

D2. Given that, what is the minimum change that makes the engine selectable at
shell entry? Evaluate the options and recommend one, with the rollback for each.

D3. The live system binary is reported as `devman-link-0.6.0` from
`/run/current-system/sw/bin`. Confirm the current store path and version. What is
the full chain from a devman tag to that binary — through `nix-meta`'s pin and
`nixosModules.default` — and how many `nixos-rebuild` cycles does a flip
actually cost?

### E. The reconcile trigger and the Nix attribute set — blocker B4

E1. `b4-reconcile-trigger-endorsement.md` endorses "option 2": keep a minimal
central Nix file whose only job is the `enterShell` reconcile hook. Its second
argument is that both `devenv.local.nix` and `links.yaml` currently declare the
same links for the central projects that have both — a live duplication of
"source or projection, never a copy."

Verify that duplication against the live tree. **Note the counts have moved:** the
M14 review recorded 78 central project directories; on 2026-10-05 there were
**60, and all 60 carried `links.yaml`**. Recount and report what you find, and
say which figure any downstream plan should use.

E2. Lane ordering: the readiness review corrected the original plan so that 9e
(retire the central attribute set) runs **before** 9d (delete the adapter
package), because the original order would have bricked shell entry in all live
projects. Confirm that reasoning still holds given E1's recount, and flag any
other ordering hazard you find.

E3. `modules/link.nix:43` still lists `"repo"` in its canonical enum. Linkman
decision 16 drops that kind — 0 live uses, and its path/content inversion
violates Linkman's repository-link-path invariant. Which lane removes it, and
what else references it (`tests/unit/test_link_adapter.py`, `paths.py`)?

### F. Sequencing

F1. Produce a lane plan: one lane per landable unit, in dependency order, each
with scope (file-level), prerequisite, verification command, gate, and rollback.
Follow the existing `m14-lN-<slug>` naming.

F2. For each lane state whether it is reversible, and name the single
hard-to-reverse step. Those go last.

F3. Say explicitly which lanes are *not* in this milestone.

## Do not re-litigate

These are settled. If you think one is wrong, say so in one paragraph and move
on — do not redesign around it.

- **D2** — no durable state in Linkman. Trap 5 names re-adding it.
- **D5** — `.git/info/exclude` projection, template rendering and bootstrap
  content stay devman's. Linkman grows no version-control knowledge.
- **D-b** — the seven-call pipeline is the whole API. A `(repo, config)`
  convenience wrapper was rejected; `test_api_surface.py` pins `__all__`.
- **Linkman never runs Nix** — so no converter can live there.
- **typer stays a hard runtime dependency of Linkman** (operator decision,
  2026-10-05). Do not propose moving it to an extra.
- **Raw-target classification.** Linkman classifies by the raw symlink target,
  never the resolved one. Comparing resolved targets is Trap 6 and it is what
  let eleven projects hide a real rewrite. Any comparator you design compares raw
  targets as **bytes**.

Two contract documents are known wrong; trust the code:
- concept §14 names `linkman.inspect(repo, config)` / `linkman.apply(repo, config)`
  — neither exists
- concept §15 shows `load_layers(repo)` — the real signature takes the two
  resolved file paths; `linkman.api.load` shows the correct call

## Deliverables

Write all of these into this directory,
`.scratch/projects/044-linkman-integration/`, which already exists and holds this
prompt. Match the structure and tone of `041-central-autoland`.

1. `RESEARCH-integration-surface.md` — answers to A, B and C with evidence.
   Every claim cites `path:line` or a command and its output. Where a document
   and the code disagree, say which you verified and when.
2. `RESEARCH-shell-entry.md` — answers to D and E, including the recount.
3. `PLAN-lanes.md` — F's lane plan, as a table plus a paragraph per lane.
4. `DECISIONS.md` — every decision this session reaches, each with the rejected
   alternative and the reason. Mark anything that is an operator call as such and
   do not decide it yourself.
5. `OPEN-QUESTIONS.md` — what you could not resolve, what evidence would resolve
   it, and what it blocks.

## Process rules

- Run everything inside `devenv shell`. Never invoke bare `uv`, `python`,
  `pytest`, `ruff`, `git` or `jj`.
- All version control through **gitman**. This session should not need a lane at
  all — you are writing planning documents. If you do create one, say why.
- Start at the `repoman` skill for lifecycle routing if you touch anything beyond
  the five documents above.
- `nix flake check` is the gate and it may take a while; `verify_timeout` is 3600.
- Report counts with the date you measured them. The 78→60 drift is exactly what
  an undated count costs.

## How to finish

Stop after the five documents. Report: what you verified, what contradicted the
existing docs, the lane plan in brief, the operator decisions waiting on the
user, and what you would do first. Do not begin Lane 1.
