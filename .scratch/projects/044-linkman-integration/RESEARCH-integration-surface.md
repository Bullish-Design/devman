# Research — the devman/Linkman integration surface

Answers sections A, B and C of `INVESTIGATION_PROMPT.md`.

Measured 2026-10-05 against devman trunk `f4a245f` (working copy clean except
this project directory) and linkman `06de662` (tag `v0.1.0`, working tree clean).
Every count and timing below carries the date it was taken. Where a document and
the code disagree, the code wins and the disagreement is named.

---

## A. Is the gate green?

### A1. No. The gate is red for two independent reasons.

Command and result:

```
$ devenv tasks run -v base:test          # devenv.nix:125 -> "nix flake check"
error: failed to build attribute 'checks.x86_64-linux.python-tests'
       builder failed with exit code 2
✖ Running base:test in 51.5s (failed)
```

**Failure 1 — `checks.x86_64-linux.python-tests`.** Three test modules fail at
collection:

```
> tests/unit/test_cutover_gate.py:15: in <module>
>     from tools.cutover.gate import (
> E   ModuleNotFoundError: No module named 'tools'
> ERROR tests/unit/test_cutover_convert.py
> ERROR tests/unit/test_cutover_gate.py
> ERROR tests/unit/test_cutover_snapshot.py
> ========================= 1 skipped, 3 errors in 1.96s =========================
```

Root cause, `flake.nix:158-167`:

```nix
158  source = nixpkgs.lib.fileset.toSource {
159    root = ./.;
160    fileset = nixpkgs.lib.fileset.unions [
161      ./src
162      ./tests
163      ./pyproject.toml
164      ./groups
165      ./nix/nixos-module.nix
166    ];
167  };
```

`./tools` is absent. The pytest call at `flake.nix:179` is bare, relying on
`pyproject.toml:97` (`pythonpath = [".", "src", "tests"]`) to put the repo root
on `sys.path`. That works in the working tree, where `tools/cutover/` exists; the
hermetic build materialises only the five paths above, so `tools/` never lands.
`tools/cutover/` is tracked (`git ls-files tools/` returns
`__init__,compare,convert,gate,restore,snapshot`).

**"Red since Lane 2" is true and precisely datable.** Commit `1be7863`
"m14 l2: snapshot and restore tooling for the cutover" (2026-10-01 13:06) added
`tools/cutover/{__init__,snapshot,restore}.py`, added `tests/unit/test_cutover_snapshot.py`,
and edited `pyproject.toml` to add `.` to `pythonpath` — and did not touch
`flake.nix`. `416b402` (l4) and `6b909ac` (l6) repeated the pattern.
`git log -- flake.nix` contains none of the three. The fileset has not changed
since before Lane 2. This is Lane 8.0's scope exactly as blocker B1 described it
(`m14-lanes-8-10-readiness-review.md:187-236`).

**Failure 2 — `checks.x86_64-linux.dagu-service`. This is new. No existing
document records it.** Measured directly:

```
$ nix build .#checks.x86_64-linux.dagu-service --no-link
> File ".../devman-0.6.0/lib/python3.14/site-packages/devman/doctor.py", line 2261, in main
>     check_link_drift(rep)
> File ".../devman/doctor.py", line 1620, in check_link_drift
>     lane_only = central.check_c3_lane_only(views, central_root, trunk)
> File ".../devman/central.py", line 369, in check_c3_lane_only
>     tracked = tracked_paths(central, trunk)
> File ".../devman/central.py", line 212, in tracked_paths
>     return set(_git(central, "ls-tree", "-r", "--name-only", trunk).splitlines())
> File ".../devman/central.py", line 206, in _git
>     raise InfraError("git is not on PATH; cannot read trunk's tree")
> devman.central.InfraError: git is not on PATH; cannot read trunk's tree
> !!! Test "devman doctor reports nothing on a healthy plane" failed
```

`nix/devman-cli.nix:67-70` wraps `devman` with `dagu` and `watchexec` on PATH. It
does not add `git`. `check_link_drift`'s C3 arm needs `git ls-tree` to read the
overlay trunk, so **`devman doctor` crashes outright on any machine without git
on PATH** — it does not degrade, and it does not report. This is a product
defect, not a test artefact, and it matches the shape AGENTS.md property 4 exists
to catch, inverted: a check that cannot run takes the whole command down with it.

**Status of every check, 2026-10-05:**

| `checks.x86_64-linux.*` | Result | Wall clock |
|---|---|---|
| `groups-validate` | green | cached, 0 s |
| `identity-grammar` | green | cached, 0 s |
| `link-adapter` | green | cached, 0 s |
| `module-assertions` | green | cached, 0 s |
| `python-tests` | **red** — `tools/` not in fileset | 51.5 s to failure |
| `dagu-service` | **red** — `git` not on devman's PATH | ~99 s |

Everything else is healthy. `devenv tasks run -v base:check` (ruff) exits 0,
"All checks passed!". The fast loop is fully green:
`devenv shell -- python -m pytest tests/unit -x -q` → **676 passed in 9.29 s**,
including all three cutover modules. So the code and the tests are correct; only
the hermetic inputs are wrong.

**Finding that changes the plan: Lane 8.0 as scoped does not make the gate
green.** The readiness review scoped Lane 8.0 as "add `./tools` to the fileset"
(`m14-lanes-8-10-refactoring-guide.md:150-171`). That fixes one of two failures.
The gate is the publish verify hook (`gitman.toml` `[publish] verify = ["nix","flake","check"]`),
so until both are fixed, no lane in this milestone can land through the normal
path. Lane 8.0 must absorb the `git`-on-PATH fix, or a Lane 8.0b must precede
everything. See `PLAN-lanes.md`.

### A2. `checks.link-adapter` and what a `linkman` dependency rebuilds

`nix flake check` does build `checks.link-adapter`, and it is the **literal same
derivation** as `packages.devman-link`. `flake.nix:59` and `flake.nix:68` both
call `pkgs.callPackage ./nix/link-adapter.nix { }` with identical arguments;
`nix eval` resolves both to
`/nix/store/6h5sm1vrfsq342z19knsjj4qzzvfsvqk-devman-link-0.6.0.drv`.

What rebuilds if the adapter gains `linkman`:

- `checks.link-adapter` and `packages.devman-link` — one build, not two.
- `checks.python-tests` has **no Nix-level dependency edge** on the adapter. Its
  `nativeBuildInputs` (`flake.nix:171`) are `python313.withPackages (ps: [ ps.pytest ps.pyyaml ])`
  and `dagu`; it never references `link-adapter.nix`. **But** its fileset
  (`flake.nix:161`) includes `./src` wholesale, which contains `src/devman_link`
  and `src/devman_contract`. So a Nix-only change to `dependencies` rebuilds just
  the adapter — while a *paired source edit* under `src/` changes `python-tests`'
  fileset hash, rebuilds it, and **fails**, because its interpreter carries only
  `pytest` and `pyyaml`.

That is the identical failure shape as the `tools/` omission: two derivations
draw from overlapping source with no shared dependency declaration, so one falls
silently out of step with the other. Any lane adding `linkman` to a derivation
must add it to `checks.python-tests`' interpreter in the same commit.

**Timing against `verify_timeout = 3600`.** I did not measure a full green run,
because the gate is red — stating that rather than estimating. The evidence
available: 51.5 s to the first failure with four checks cached; ~99 s for the
NixOS VM test alone; the four green checks at 0 s cached. The dominant cost is
`dagu-service` (a QEMU VM boot) and the one-off download of a new Python closure.
Nothing here approaches 3600 s. The timeout is not the constraint; correctness is.

---

## B. Wiring Linkman in

> **SUPERSEDED, 2026-10-05, later the same day.** A step-back review chose to
> consume Linkman as a **CLI binary on PATH**, installed by nix-meta, rather than
> as a Python library via a flake input — see `DECISIONS.md` D23-D26 and
> `PLAN-lanes.md` §0.
>
> **B1, B1a, B2, B3, B4 and B6 are therefore moot, not wrong.** Every
> measurement in them stands; the work they describe is no longer needed, because
> devman's `flake.nix` and `nix/nixos-module.nix` do not change at all under the
> chosen architecture. Three specific reversals:
>
> - **B1a's blocker dissolves.** nix-meta already carries private `git+ssh`
>   inputs (`silverbullet-server` at `flake.nix:211`, `inferference` at `:259`)
>   and already solves root's SSH declaratively at
>   `machines/server.nix:435-448`, exercised on every rebuild. There is no new
>   credential requirement and no operator decision needed.
> - **B6's recommendation is withdrawn.** No devman derivation gains a Linkman
>   dependency, so no interpreter needs pinning for Linkman's sake. The
>   ships-on-3.14.7 / tests-on-3.13.15 split that B6 *discovered* is still real
>   and still undocumented — it is now `OPEN-QUESTIONS.md` O5, on its own merits.
> - **B3's correction still matters historically.** It showed the lane docs named
>   the wrong derivation. Under the CLI route no derivation is named at all.
>
> **B0 and B5 remain live.** B0 documents the package being consumed and its
> `checks.overlay` precedent. B5's sequencing of `pyproject.toml:35-39` still
> holds, for the reason given there.
>
> Section A and section C are unaffected and remain the basis of the plan.

### B0. Verified facts about the package being consumed

Measured 2026-10-05 in `/home/andrew/Documents/Projects/linkman`:

- `linkman/flake.nix:40-41` — `systems = [ "x86_64-linux" "aarch64-linux" ]`.
  No darwin. Confirmed.
- `linkman/nix/linkman.nix:38` — `python3Packages.buildPythonPackage {`.
  Confirmed `buildPythonPackage`, not `buildPythonApplication`.
- `linkman/nix/linkman.nix:59-63` — `dependencies = with python3Packages; [ pydantic pyyaml typer ];`.
  `typer` is a hard runtime dependency, as the operator decided.
- `linkman/nix/linkman.nix:65` — `pythonImportsCheck = [ "linkman" ]`.
- `linkman/nix/linkman.nix:46` — `pythonSetFor = pkgs: pkgs.python313Packages;`
  (its own nixpkgs' bare `python3` is 3.14.7, measured).
- `linkman/flake.nix:69-75` — `overlays.default` appends to
  `pythonPackagesExtensions`, adding the attribute `linkman`, built with
  `python3Packages = pyFinal`. So the overlay is **interpreter-agnostic**: it
  yields `python3Packages.linkman`, `python313Packages.linkman`, and so on, each
  built with its own set.
- `linkman/flake.nix:62` — `linkman = python.toPythonApplication linkman-lib;`
  is the CLI; `linkman-lib` is the library.
- `v0.1.0` is an **annotated** tag (`git cat-file -t v0.1.0` → `tag`). Its object
  hash is `7d51edc8…`; it dereferences to commit `06de662`, which equals linkman
  HEAD. `git ls-remote --tags origin` shows both, so it is pushed.

The input URL resolves from this machine today:

```
$ nix flake metadata 'git+ssh://git@github.com/Bullish-Design/linkman?ref=refs/tags/v0.1.0' --no-write-lock-file
Resolved URL:  git+ssh://git@github.com/Bullish-Design/linkman?ref=refs/tags/v0.1.0
Locked URL:    ...&rev=06de662dc8c09714a2663166e9fef1a97fec07b0
Revision:      06de662dc8c09714a2663166e9fef1a97fec07b0
Inputs:
└───nixpkgs: github:NixOS/nixpkgs/a7868a72... (2026-10-03 17:36:20)
```

`linkman/flake.nix:101-121`'s `checks.overlay` is a precedent worth copying: it
imports a fresh nixpkgs with the overlay applied, then asserts a bare
`import linkman` succeeds *and* that neither `typer` nor `yaml` enters
`sys.modules`. That is a check that can fail, about the exact route devman will
use.

### B1. The flake diff, and why `legacyPackages` forces a change

`flake.nix:31` is:

```nix
31  forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
```

`f` receives a `pkgs`, never a `system`. `nixpkgs.legacyPackages.${system}` is an
already-instantiated package set; an overlay cannot be applied to it in place.
`pkgs.extend` exists, but using it here would re-instantiate nixpkgs once per
`forAllSystems` call site and hide that cost. **So yes — consuming
`overlays.default` forces the move to `import nixpkgs { inherit system; overlays = [ … ]; }`.**

Proposed diff. **Not applied. This is a proposal.**

```diff
--- a/flake.nix
+++ b/flake.nix
@@ -23,9 +23,19 @@
   inputs = {
     nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
+
+    # Linkman supplies the symlink engine the link plane ports onto (025 §P0,
+    # M14 Lane 9c). Consume it through `overlays.default`, never through
+    # `packages.${system}.linkman-lib`: the overlay adds `linkman` to
+    # `pythonPackagesExtensions`, so it builds against *this* flake's nixpkgs
+    # and interpreter. Taking the package output directly mixes Python packages
+    # from two nixpkgs revisions, which is how an ABI mismatch arrives.
+    linkman = {
+      url = "git+ssh://git@github.com/Bullish-Design/linkman?ref=refs/tags/v0.1.0";
+      inputs.nixpkgs.follows = "nixpkgs";
+    };
   };
 
-  outputs = { self, nixpkgs, ... }:
+  outputs = { self, nixpkgs, linkman, ... }:
     let
       systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
-      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
+      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs {
+        inherit system;
+        overlays = [ linkman.overlays.default ];
+      }));
```

Three notes on that diff:

1. **`inputs.nixpkgs.follows = "nixpkgs"` is not optional.** Without it the
   closure carries two nixpkgs revisions (devman's `ffb3c9b`, 2026-08-19; and
   linkman's `a7868a72`, 2026-10-03) and `python3Packages.linkman` would be built
   from one while devman's own packages come from the other.
2. **`follows` has a cost worth stating.** It builds Linkman against nixpkgs
   `ffb3c9b` — a revision Linkman's own `checks` have never exercised. The
   mitigation is a devman-side check modelled on `linkman/flake.nix:101-121`.
3. **Do not add `linkman.overlays.default` to devman's exported
   `overlays.default`** (`flake.nix:35-37`, currently just `dagu`). That overlay
   is consumed externally; adding Linkman would force a private input on every
   consumer. Keep the overlay application internal to `forAllSystems`.

### B1a. The blocker nobody has recorded: a private input changes who can build devman

This is the single most consequential finding in section B, and it is not in any
existing document.

- `nix-meta/flake.nix:238-239` pins devman as
  `url = "git+https://github.com/Bullish-Design/devman?ref=refs/tags/v0.7.0"` —
  anonymous HTTPS.
- Linkman is **private** and reachable only over `git+ssh`.
- Adding it as a devman input makes **devman's flake unevaluable without SSH
  credentials for a second private repository.** Every `nix flake check`, every
  `nix build .#devman`, and every `nixos-rebuild` that imports
  `devman.nixosModules.default` acquires that requirement.
- The `nix flake metadata` call above succeeded as user `andrew`, whose agent
  holds the key. `nixos-rebuild switch` evaluates as **root** under `sudo`, with
  a different (usually absent) SSH agent. I did not test a rebuild — the prompt
  forbids it — so this is an untested hazard, not a measured failure.

**This is an operator decision and I am not deciding it.** Recorded as Q7 in
`DECISIONS.md` and `OPEN-QUESTIONS.md`.

### B2. Four systems, two of them darwin

`flake.nix:30` declares `[ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ]`.
`packages` and `checks` are defined for all four via `forAllSystems`.
`nix/dagu.nix:36-43` deliberately carries darwin release binaries and hashes.

What actually breaks: applying `linkman.overlays.default` on darwin does **not**
fail at evaluation — the overlay is a plain `final: prev:` function and adding an
attribute to `pythonPackagesExtensions` is system-independent. The break comes
only when a darwin output *builds* `python3Packages.linkman`, because Linkman
declares no darwin platform. So `nix flake check --all-systems` fails on the
darwin instances of whichever outputs take the dependency.

**Recommendation: gate the linkman-dependent outputs with the idiom already in
this file.** `flake.nix:183` already does exactly this:

```nix
183  // nixpkgs.lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
```

for `module-assertions` and `dagu-service`. Use the same wrapper for the new
linkman-dependent check. Reasons, in order of weight:

1. Precedent in the same file, so the next reader needs no new concept.
2. The adapter is installed by a **NixOS** module (`nix/nixos-module.nix:697-700`),
   so its Linux-only nature is structural, not incidental.
3. Narrowing devman's `systems` would silently drop the darwin `dagu` support
   that `nix/dagu.nix:36-43` was written to provide.
4. Asking Linkman to widen costs an upstream change for zero present consumer —
   the plane has no darwin machine.

Rejected: narrowing `systems` (loses darwin dagu). Rejected: asking Linkman to
widen (no consumer, and it would force a platform claim nobody can test).

### B3. Which derivations need `linkman` — and the lane docs have this wrong

The honest answer follows from which fileset contains the import.

**`nix/link-adapter.nix:71` (`dependencies = [ ]`) — does NOT need `linkman`,
not yet.** Its fileset (`:41-49`) is `src/devman_link`, `src/devman_contract`,
`packaging/devman-link/pyproject.toml`, `modules/link.nix`. `src/devman` is
deliberately excluded. Nothing under `src/devman_link` imports `linkman` — the
only import is `src/devman/linking.py:44`, which is not in this fileset. The
adapter needs `linkman` **only** when Lane 9b-1 moves engine selection into
`src/devman_link/cli.py`, because that is when the adapter's own code starts
importing it.

**`nix/devman-cli.nix:63` (`dependencies = [ python3Packages.pyyaml ]`) — DOES
need `linkman`.** Its fileset (`:57-60`) is `../src` wholesale, which includes
`src/devman/linking.py`. That module imports `linkman` at `:44` and drives the
full seven-call pipeline. It survives today only because `src/devman/cli.py:423`
defers the import inside `_link_reconcile_with_linkman`, and the flag is
default-off — the comment at `cli.py:414-419` says so explicitly.

**`checks.python-tests` (`flake.nix:171`) — DOES need `linkman`**, and this is
the highest-value addition of the three. `tests/unit/test_linking.py:28` is
`pytest.importorskip("linkman")`. Today the whole Linkman integration test
**skips** inside the gate — the `1 skipped` in the A1 output. Adding `linkman` to
that interpreter converts a test that cannot fail into one that can. That is
directly AGENTS.md's "Could it succeed while doing nothing?" test, and the
answer today is yes.

So the lane docs' framing of 9c as "rewire the adapter" names the wrong
derivation for the wrong reason. The correct 9c scope is `nix/devman-cli.nix:63`
plus `flake.nix:171`; `nix/link-adapter.nix:71` belongs to 9b-1.

### B4. Does `linkman` violate the adapter's independence?

It satisfies it, with one condition.

`nix/link-adapter.nix:17-22` states the property: "`src/devman` is absent, so an
`import devman.registry` inside the component fails the install check below
rather than reaching a machine." The property is **"the adapter does not reach
the workflow plane"** — not "the adapter has no dependencies". A third-party
symlink library is categorically different from devman's own registry. Adding
`linkman` leaves the property intact; adding `src/devman` would destroy it. The
condition is that the dependency stays `linkman` and the fileset keeps excluding
`src/devman`.

**The no-registry fixture does still pass today** — `checks.link-adapter` is
green (A1). But it will not keep testing the right thing. `link-adapter.nix:75-135`
writes a fixture `devenv.local.nix` in devman's own `devman.link` attribute-set
format, then asserts exit 1 plus two literal strings:

```
*"central config $fixture/overlay/projects/fixture-demo/devenv.local.nix"*
*"fixture-demo:.agents"*
```

Linkman reads `links.yaml`, not `devenv.local.nix`, and its exit codes are a
different API (0/1/10/11/12/13). So once 9b-1 lets the adapter delegate to
Linkman, this fixture exercises only the legacy branch.

**Recommendation: extend the fixture with a second arm in the same lane that
moves the flag** — the same fixture repo, plus a `links.yaml`, run once with
`DEVMAN_LINK_ENGINE` unset and once set to `linkman`, asserting the documented
exit code each time. One build then proves both engines, and the legacy arm
keeps guarding the old path until Lane 9d deletes it. The precedent is
Linkman's own `installCheckPhase` (`linkman/nix/linkman.nix:81-134`), which
builds a fixture repo, asserts `check` exits 1 with `"status": "missing"`,
applies, verifies the raw symlink with `readlink`, and asserts a second `check`
exits 0.

### B5. `pyproject.toml:35-39` — keep it, and delete it in Lane 10.1

```toml
35  [project.optional-dependencies]
36  cutover = ["linkman", "pytest"]
38  [tool.uv.sources]
39  linkman = { path = "../linkman", editable = true }
```

Two different things still need the sibling checkout, and they retire at
different times:

1. `tests/unit/test_linking.py:28` needs `linkman` **importable** in the dev
   venv. A published tag satisfies this as well as the editable path does.
2. `tools/cutover/gate.py` has
   `DEFAULT_LINKMAN_BIN = "~/Documents/Projects/linkman/.devenv/state/venv/bin/linkman"`.
   This needs the sibling checkout's **built venv**, not merely an importable
   package. No published tag satisfies it.

Item 2 also violates AGENTS.md property 5 — an absolute path to another
project, hard-coded in the plane. It is dev-only tooling, so it has not caused
harm, but it is the reason the editable source cannot go early.

**Recommendation: change nothing here in Lane 9c.** The editable path is what
makes the fast loop fast, no gate stands behind it, and editing it is churn that
buys nothing. Delete `[project.optional-dependencies] cutover` and
`[tool.uv.sources]` together with `tools/cutover/` in Lane 10.1, in one commit,
so the hard-coded path and its only consumer leave together.

Rejected: switching `[tool.uv.sources]` to the git tag in 9c. It would make the
fast loop fetch over SSH on every lock refresh, slowing the loop that exists to
be fast, and it would not remove the `gate.py` path anyway.

### B6. Interpreters — the prompt's premise is inverted

Measured 2026-10-05. devman's locked nixpkgs is `ffb3c9b700e759be2ef13237c9d8f953b32a1e46`,
`lastModified` 2026-08-19.

```
$ nix eval --impure --raw --expr '(builtins.getFlake (toString ./.)).inputs.nixpkgs.legacyPackages.x86_64-linux.python3.version'
3.14.7
$ nix eval --impure --raw --expr '(builtins.getFlake (toString ./.)).inputs.nixpkgs.legacyPackages.x86_64-linux.python313.version'
3.13.15
$ nix eval --impure --expr '(builtins.getFlake (toString ./.)).inputs.nixpkgs.legacyPackages.x86_64-linux ? python314'
true
```

So devman's bare `python3` has **already rolled to 3.14.7** — the same roll that
made Linkman pin `python313Packages`. What each devman derivation actually uses:

| Derivation | Interpreter source | Version |
|---|---|---|
| `packages.devman` (`nix/devman-cli.nix:43`) | unpinned `python3Packages` | **3.14.7** |
| `packages.devman-link` (`nix/link-adapter.nix:36`) | unpinned `python3Packages` | **3.14.7** |
| `checks.link-adapter` | same derivation as above | **3.14.7** |
| `checks.python-tests` (`flake.nix:137`) | `pkgs.python313` | **3.13.15** |
| `base:unit` (`devenv.nix:24`) | `pkgs.python313` | **3.13.15** |

Verified off `nativeBuildInputs` (`python3-3.14.7`, `python3.14-hatchling-1.31.0`)
because `.pythonModule.version` does not resolve on this nixpkgs'
`buildPythonApplication` output. Independently corroborated by the VM test log in
A1, which shows `devman-0.6.0/lib/python3.14/site-packages/`.

**devman already ships on 3.14.7 and tests on 3.13.15.** That split predates
Linkman entirely and nobody recorded it. `pyproject.toml` requires `>=3.13`, so
both satisfy it and the split is silent — the exact shape of a check that passes
while testing something other than what ships.

Does the overlay route produce a consistent interpreter? **Within each package
set, yes.** `linkman/flake.nix:69-75` builds Linkman with `python3Packages = pyFinal`,
so `python3Packages.linkman` is a 3.14.7 build and `python313Packages.linkman` is
a 3.13.15 build. The inconsistency is devman's own, not the overlay's.

**Recommendation: pin all three linkman-touching derivations to
`python313Packages` in the lane that adds the dependency.** Reasons:

1. 3.13 is the only interpreter Linkman's own `checks` exercise
   (`linkman/nix/linkman.nix:46`). Building it on 3.14.7 is untested ground.
2. It closes the ships-on-3.14/tests-on-3.13 split, so the suite finally tests
   what ships.
3. It is one line in each of `nix/link-adapter.nix` and `nix/devman-cli.nix`.

Rejected: pinning to `python314Packages`. Linkman has never been built or tested
there, and `pydantic` on 3.14 would be a second unverified variable. Rejected:
leaving the derivations unpinned. That makes the interpreter a function of
whenever nixpkgs last rolled, which is how this split arrived unobserved.

---

## C. The two undisclosed consumers

### C1. `doctor.py:63` — the prompt's framing is half wrong, and the half that is right is subtler

**`check_link_drift` does not use the state file at all.** `doctor.py:1582-1657`
calls only:

```
1617  views     = central.reverse_index(fleet=fleet, central=central_root)
1618  trunk     = central.trunk_name(central_root)
1619  missing   = central.check_c2_missing(views)
1620  lane_only = central.check_c3_lane_only(views, central_root, trunk)
1647  hollow    = central.check_c5_empty_surface(views, central_root)
```

Every one is present-tense: a filesystem walk, a `gitman.toml` read, and
`git ls-tree <trunk>`. Its own docstring (`:1607-1611`) records that it was
*deliberately rewritten off* any durable record — "the registry is empty and the
link-state ledger is stale by 34 projects". devman's `041/DECISIONS.md:13-50`
(D1) is the decision behind it, with the measurements: 0 of 48 registry entries
declare a link against 325 live views; the ledger held 450 entries across 82
projects against 66 live.

Further: **`doctor.py` makes zero function calls into `devman_link`.** Of its six
mentions, one is the import at `:63` and four (`:1676`, `:1678`, `:1720`,
`:1768`) are prose inside docstrings. It reads the ledger's raw bytes itself via
`_read_ledger_raw` (`:1660-1669`), using `STATE_FILE` purely as a filename
constant.

So the prompt's claim that both checks "rest on a concept the replacement does
not have" holds for `check_ledger_stale` only.

**What each check asserts, separating property from mechanism:**

| | Property | Mechanism | Needs history? |
|---|---|---|---|
| `check_link_drift` C2 | every live view's target exists | `os.path.exists` on the one-hop raw target | no |
| `check_link_drift` C3 | every live view's target is reachable from the overlay's trunk | `git ls-tree -r --name-only <trunk>` | no |
| `check_link_drift` C5 | every directory target holds trackable content | directory scan | no |
| `check_ledger_stale` | the ledger holds no entry for a project whose directory is gone | ledger keys vs `fleet/<name>.is_dir()` | the ledger itself |

`check_ledger_stale` is a check *on a record*, not on the link graph. Its
docstring (`:1705-1713`) is explicit: "Liveness is the repository directory on
disk, and nothing else — never the registry."

**What the ledger exists to detect.** Its one functional purpose is the
two-sided-edit promotion guard, `src/devman_link/reconcile.py:201-210`:

```python
201  if result.state == "promote":
202      if link.canonical_path.exists():
203          previous = state.get(link.key, {})
204          expected = previous.get("hash")
205          actual = content_hash(link.canonical_path)
206          if not expected or expected != actual:
207              raise LinkError(
208                  f"refusing promotion for {link.key}: canonical changed"
209                  " since the link was made; review both sides"
210              )
```

The recorded hash answers a question current state cannot: *did the canonical
side change since I linked it?* Worked example — Monday, reconcile links
`view → canonical` and records `hash: abc123`. Tuesday, someone edits
`canonical` directly; it is now `def456`. Wednesday, `view` has become a real
file with its own content, so reconcile sees state `promote`. Without Monday's
hash, "canonical is untouched, promoting is safe" and "canonical already
diverged, promoting discards Tuesday's edit" are indistinguishable — current
state carries only Wednesday's numbers for both sides.

**Can Linkman's pipeline express it? Yes, differently, and that is why D2 could
delete state.** Linkman asks a present-tense question instead: *do both sides
hold real, conflicting content right now?* That is `MigrationCollisionError`
("both migration sides hold conflicting real content", `linkman/src/linkman/errors.py`),
raised from `migrate`, surfaced as a refusal in `MigrationResult.refused`
(`linkman/src/linkman/api.py:388-389`) and as exit 11. It is strictly weaker: it
cannot detect "canonical changed while the view stayed a correct symlink" — but
that case is a no-op, so nothing is lost that matters. **No state file is needed
and none should be proposed.** D2 is settled and Trap 5 names re-adding it.

**But the ledger does not disappear, and this corrects both the prompt and the
original guide.** `src/devman/linking.py:51` imports `read_state, write_state`
and uses them at `:138`, `:143`, `:146` — the Linkman bridge already persists the
exclude-projection baseline that `ensure_local_gitignore` reads. Under D5, the
`.git/info/exclude` projection stays devman's. So **devman keeps a state file of
its own**, and that is not a D2 violation: D2 binds Linkman, not its consumers.
The readiness review's F2 correction (`m14-lanes-8-10-readiness-review.md:381-391`)
says the same, against the original guide's claim that the file "disappears with
`devman_link` anyway".

**Therefore:**

- `check_link_drift` needs no Linkman feature and no port. It keeps working
  unchanged. Its only outstanding problem is the `git`-on-PATH defect in A1.
- `check_ledger_stale` **survives**, and its schema does not change.
  `ensure_local_gitignore` reads and writes the same `{canonical, hash}` record
  (`src/devman_link/excludes.py:107-110`, `:139-142`), using the hash for the
  same two-sided-edit refusal. Only the key set shrinks — from one entry per
  `project:view` to one exclude-projection entry per project, about 345 rows
  down to about 59. The real Lane 9a work is pruning and ownership, not a
  schema change, and it is devman-internal rather than a port.
- **What devman must keep owning**, none of it expressible from Linkman's
  pipeline, all of it by Linkman's own non-goals (concept §3) and D5: the
  fleet-wide reverse index; trunk-reachability (Linkman has no VCS knowledge by
  design); empty-surface detection; the `.git/info/exclude` projection and its
  baseline; `BOOTSTRAP_CENTRAL_FILE` content; the copyroom template call.

### C2. The check-reporting gap is NOT a dependency for Lane 9a

`check_link_drift` does depend on detecting a dangling symlink — through C2,
`src/devman/central.py:270-272`:

```python
270  def check_c2_missing(views: list[View]) -> list[View]:
271      """C2 — every live view's target exists on disk."""
272      return [v for v in views if not os.path.exists(v.target)]
```

over `central.py:173-184`:

```python
173  def _normalize_target(link: Path) -> str | None:
174      """The absolute, normalized path a symlink's raw target names.
175
176      Normalized rather than resolved: resolving would follow a second hop and
177      report the wrong path if the target is itself a symlink.
178      """
179      raw = os.readlink(link)
180      target = Path(raw) if os.path.isabs(raw) else (link.parent / raw)
```

`os.readlink` plus `normpath`, never `.resolve()`. **devman computes this itself
and is already Trap-6 compliant** — it compares the raw target one hop deep, and
the comment at `:176-177` shows the trap was understood when it was written.

So the answer is no. **devman never asked `linkman check` this question and must
not start.** This was already decided in devman's own
`041/DECISIONS.md:329-358` (D10): "The check must not use `linkman check`; it is
devman's own code", on the measurement that `linkman check` reports `clean: true`
on a dangling target, with the reason that target existence is outside Linkman's
boundary by design and devman owns the content at the target. D10 also records
the gap as **O7, for Linkman's owner**, and states "this project is forbidden
from designing around a Linkman change."

I verified the gap independently in Linkman's code and it is exactly as the
report describes — `classify_status` (`linkman/src/linkman/planning.py:20-32`)
switches only on `actual.link.kind` and never reads `actual.target.kind`;
`api.check` (`linkman/src/linkman/api.py:158`) sets
`observed_kind=actual_link.link.kind` and discards `actual_link.target`;
`LinkStatusReport` has no target-kind field. The data exists one layer down and
is thrown away.

**Reported as the prompt asked: this deferred gap does not become a real
dependency.** It would only become one if a future lane tried to replace
devman's C2 with `linkman check`, which D10 forbids.

### C3. `watch.py:58` — Linkman is strictly more expressive here

`src/devman/watch.py:58` is `from devman_link import LinkError, reconcile`. There
is exactly one call site. The prompt's `dispatch_command` (`:360`) and
`supervise` (`:417`) do **not** touch links — `grep -n "reconcile(\|LinkError"`
returns only lines 58, 606 and 622.

`devman_link.reconcile` (`reconcile.py:174-231`) takes
`(declarations, *, overlay, root, project)` and returns `list[LinkResult]`.
`watch.py:606-611` calls it and **discards the return value**, then catches
`LinkError` at `:622-629`, prints two stderr lines, sets `code = 1`, and
continues the loop.

Mapping onto Linkman:

| `devman_link` raise site | Condition | Linkman equivalent | Exit |
|---|---|---|---|
| `reconcile.py:207` | promotion refused, canonical changed | `MigrationCollisionError` | 11 |
| `reconcile.py:84-98` | refusing to replace a real view | `SafetyError` | 11 |
| `reconcile.py:95-97` | promotion backup already exists | `SafetyError` | 11 |
| `reconcile.py:105-116` | dir/file type mismatch on promotion | `UnsupportedLinkTypeError` / `MigrationCollisionError` | 11 |
| `reconcile.py:136-150` | `copyroom` missing or non-zero | **no equivalent — stays devman's** (D5) | n/a |
| uncaught `OSError` | filesystem failure | `OSError` → `Exit.OS` | 12 |

**`devman_link` collapses cases Linkman separates, not the reverse.** All four
deliberate refusals and both tool-failure cases raise the single `LinkError`
type, differing only in message text; `watch.py` catches by type
(`:619` `RegistryError`, `:622` `LinkError` — no string matching, `str(exc)` is
used only for display) and flattens everything to `code = 1`.

Linkman splits this three ways and the distinction is deliberate: exit 11 is a
safe refusal, exit 13 a real failure, per `linkman/src/linkman/cli.py:44-52` and
`error_exit_code` at `:55-65`. `apply_plan` returns an `ApplyResult` carrying
`.applied`, `.refused` and `.failed` lists, and per-link failures are collected
rather than raised (`linkman/src/linkman/reconcile.py:212-222`).

So the port is a **gain, not a risk**, and it fixes a real hole. Today
`reconcile` raises on the first failing view mid-loop
(`devman_link/reconcile.py:193-224`), leaving earlier views applied and later
ones untouched, with no rollback — and `watch.py` cannot tell "nothing applied"
from "three applied, one refused", because the return value is discarded and the
exception carries only a string. Porting onto `apply_plan` gives `watch.py` the
per-link lists it needs to report that honestly.

One caveat to carry into the lane: `watch.py:622-629`'s single handler must
become two, or the 11/13 distinction is thrown away at the boundary exactly as
it is today. `src/devman/cli.py:411-449` already does this correctly —
`_link_reconcile_with_linkman` returns 13 on `apply_result.failed`, 11 on
`apply_result.refused`, 0 otherwise. Copy that shape.

### C4. The remaining importers — and the prompt's list of 17 is wrong

Authoritative grep, 2026-10-05: only **four** first-party source files import
`devman_link`.

| File | What it imports and uses | Phase |
|---|---|---|
| `src/devman/linking.py:46-51` | `Declaration`, `ensure_local_gitignore`, `ProjectIdentity`, `resolve_project_identity`, `ResolvedLink`, `BOOTSTRAP_CENTRAL_FILE`, `link_path`, `read_state`, `write_state` | **D — move out.** All devman policy per D5. Its own docstring (`:22-27`) says Lane 8 moves them into devman unchanged. |
| `src/devman/cli.py:50` | `run`, `DEFAULT_OVERLAY`, `LinkAdapterError`, `format_results`, `format_results_json` | **E — port.** This is the engine-selection seam; `_link_reconcile_with_linkman` already implements the Linkman side. |
| `src/devman/watch.py:58` | `LinkError`, `reconcile` | **E — port.** See C3. |
| `src/devman/doctor.py:63` | `STATE_FILE` only | **Neither.** A filename constant. It follows the ledger's schema change (C1), not a port. |

**`registry.py`, `central.py`, `devman_contract/__init__.py`,
`devman_contract/manifest.py` and `devman_contract/identity.py` do not import
`devman_link` at all.** Every hit in those five files is a comment or docstring —
`registry.py:26,49,123`; `central.py:51`; `devman_contract/__init__.py:4`,
`manifest.py:8`, `identity.py:4`. The prompt lists them as importers; they are
not. Verified by reading each file.

`devman_contract` sits **under** `devman_link`, not over it:
`devman_link/identity.py` imports from `devman_contract`, never the reverse. It
is 559 lines of identity grammar and manifest schema with no Dagu, Nix or
registry dependency, consumed by three parties (`devman`, `devman_link`, and
Vendomat per `manifest.py:8`). **It survives an engine swap untouched and is not
a deletion candidate** — it is the one piece both the move-out and the port keep.

`src/devman_link/` itself is 1,427 lines across 11 modules. Splitting by
ownership:

- **Pure link mechanics, replaced by Linkman:** `reconcile.py` (270, the
  five-state machine), `paths.py` (121, resolution math), `state.py` (65, the
  promotion hash), `errors.py` (25).
- **devman policy, must move out (Phase D):** `excludes.py` (143, the
  `.git/info/exclude` projection — D5), `reconcile.py`'s
  `BOOTSTRAP_CENTRAL_FILE` and copyroom call, `declarations.py` (65) +
  `config.py` (299) + `paths.py`'s three canonical kinds (devman's own
  Nix-evaluated declaration format, distinct from Linkman's `links.yaml`),
  `identity.py` (117, mostly delegating to `devman_contract`).

**Tests.** `test_link_adapter.py` (1,086 lines) pins `devman_link`'s own state
machine and file formats — it needs a rewrite, not a port, and most of it simply
retires with the engine. `test_identity.py` pins `resolve_project_identity` and
`validate_link_configuration`, both devman_link-specific, though its grammar
assertions (via `devman_contract`) survive. `test_cli.py` monkeypatches
`cli.devman_link.run`/`format_results` as a black box and survives, except the
hard-coded module-name assertion at `:50`. `test_linking.py` already tests the
Linkman side and carries one transitional liveness assertion (`:71-72`,
`devman_link.run is not None`) meant to be deleted at the end.
`test_cutover_convert.py` patches the cutover tool's own functions, never
`devman_link`'s API, and survives untouched.
