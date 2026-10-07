# Task: adopt mancore's exit-code contract in devman (step 7)

Run this from the `devman` repo root (`/home/andrew/Documents/Projects/devman`).
You have no memory of any prior conversation — everything you need is below.

This is step 7 of a fleet-wide migration. Steps 1 (`testee`), 2 (`linkman`) and
3 (`loci-core`) are done. Steps 4 (`gitman`) and 6 (`docman`) were retired, not
migrated. `mancore/docs/MIGRATION.md`'s "Step 7 — devman" section sketched this
work earlier. **Treat every line number and claim in it as something to
re-verify, not a fact** — the same discipline every prior step in this fleet
has required. This prompt was written by re-grepping the real current code,
and it found three real corrections to the plan, spelled out below. Re-grep
again yourself before you edit; more time has passed since this was written.

## Part 0 — review and verify before changing anything

**Do this first, and do not skip it.** Prior steps in this fleet have had
unsupervised sessions leave unexpected state in a sibling repo, or push
without asking. You need to know exactly what you're starting from.

1. Run `git log --oneline -10` and `git status --short`. As of this writing,
   `HEAD` is `1e093b0 "feat: project git excludes from links.yaml"` and the
   tree is clean. If your status differs, stop and report what you found
   before proceeding.
2. Confirm `mancore` is really tagged and pushed before you depend on it:
   ```bash
   git ls-remote --tags https://github.com/Bullish-Design/mancore
   ```
   Expect `refs/tags/v0.1.0`. If it's missing, stop — the dependency this step
   needs does not exist yet.
3. `devman` already has a version/tag mismatch that predates this step and is
   **not yours to fix here**: `pyproject.toml` (and `nix/devman-cli.nix`,
   `packaging/devman-link/pyproject.toml`) declare `0.6.0`, but
   `git tag --sort=-creatordate` shows the newest tag is `v0.7.0`. This is
   `mancore/docs/MIGRATION.md` step 12's job (version hygiene), listed there by
   name. Don't touch it; don't let it block you; just don't be surprised by it.
4. Establish an honest baseline. This repo's tests run two ways — read both
   before picking one:
   ```bash
   devenv tasks run -v base:check   # ruff check .
   devenv tasks run -v base:unit    # pytest, under a hermetic Nix interpreter
                                     # carrying only pytest + pyyaml — nothing
                                     # else of devman's own dependency surface
   ```
   `base:unit`'s interpreter is deliberately minimal (`devenv.nix:24`:
   `pkgs.python313.withPackages (ps: [ ps.pytest ps.pyyaml ])`), so
   `tests/unit/test_linking.py` (which needs `linkman`) guards itself with
   `pytest.importorskip("linkman")` at module level and is silently skipped
   under this task — not a failure, see that file's own docstring. Record the
   pass/skip count. `devenv tasks run -v base:test` runs `nix flake check`,
   which builds a real NixOS VM and a live Dagu service — minutes, and the
   authoritative gate, but not the one to iterate against. Run it once near
   the end, not on every edit.

Only proceed once all four checks are done and understood. If anything
surprises you, report it instead of guessing at a fix.

## Background: mancore's contract

`mancore` (sibling repo, tagged `v0.1.0` on GitHub at
`https://github.com/Bullish-Design/mancore`) defines one exit-code contract
for the `*man` tool family:

- `0` — the tool ran, and found nothing to report (clean).
- `1` — the tool ran, and found something the caller must act on (a finding).
- `2` — the tool could not do its job (a fault).
- `130` — a signal interrupted the tool.

Two rules produce these codes: **a fault is an exception, and its type picks
the code** — never choose a code at a raise site — and **a finding is a
return value**. In practice, across tools that keep their own typed-exception
taxonomy instead of migrating onto `mancore.Report` (loci-core is the
precedent — see its own step 3 prompt), this is applied case by case: a given
exception class gets classified as a fault (exit `2`) or kept as a finding
(exit `1`), by what it *means*, not by a blanket "every exception is a fault"
rule. Keep that distinction in mind below — it is exactly where one part of
this step's original framing turned out to be wrong.

## devman is NOT getting a full report-model migration in this step

**This is the most important thing to get right.** `doctor.py` uses its own
four-state status vocabulary — `ok`, `..`, `!!`, `--` — documented in "THE
STATUS LEGEND" at `doctor.py:89-103` (verify with
`grep -n 'THE STATUS LEGEND' src/devman/doctor.py`). It is richer than
mancore's three-level `Level = Literal["ok","warn","fail"]`. A `..` row means
"the check could not run at all" (no `dagu` on PATH, no queue list in
config.yaml) and today is **deliberately never counted in the exit code** —
the legend says so outright: *"'I could not look' is not a finding about the
fleet."* `findings` (`doctor.py:122-138`) only counts `!!` rows.

**The decision for this step is: devman keeps this rule. Do not migrate
`doctor.py`'s reporting model onto `mancore.Report`/`Row` here, and do not flip
`..` to count toward the exit code.** The reasoning: mancore's own general
rule ("where a finding and a fault coexist, the fault wins" — lifted from
testee's `infra_error beats failed`) is about trusting a *single run's*
completeness. If testee's verify couldn't check everything, the whole report
is suspect. devman's `..` is different in kind: it is a fleet-wide survey
across many *unrelated* projects, where "couldn't check project X's `dagu`
reachability" says nothing about whether project Y's or Z's checks are
trustworthy. Flipping `..` to fault-wins would turn one missing binary on a
machine into a hard failure across every project doctor checks — noise, not
signal, for devman's actual job.

**A real conflict you will find if you read further, and must not resolve
yourself.** `mancore/CONCEPT.md` §9a and §10.9, and `mancore/docs/MIGRATION.md`
step 7 item 3, currently state the *opposite*: that mapping `..` to
`Report.incomplete` (exit `2`) was "Decided 2026-10-07" on §9's fault-wins
rationale. That text exists in the `mancore` repo today — this is not a straw
man, go read it yourself at those citations. The decision stated in the
paragraph above (devman keeps its own rule, full stop) supersedes it for the
purposes of this step, as given to the session that wrote this prompt. **Do
not edit `mancore/CONCEPT.md` or `mancore/docs/MIGRATION.md` to reconcile this
— that repo is out of scope here (see "What NOT to do").** Simply follow the
instruction above, and say in your closing summary that this conflict exists
and is unresolved in `mancore`'s own docs, so a human can reconcile the two
later. If this surprises whoever reads your summary, that is the point of
mentioning it — don't paper over it.

If devman's doctor is ever ported onto `mancore.Report` in some future step,
the rule to follow then is: do **not** put `..`-status checks into
`Report.incomplete` (which triggers `exit_for`'s fault-wins behavior) — keep
them out of the gating set entirely, the same as today, just inside whatever
envelope is used.

## Scope: a handful of integers, not a redesign

This step only touches places devman emits a *process exit code integer* that
doesn't match mancore's `0/1/2/130` contract, or where that integer's label is
confusing. It does not touch `doctor.py`'s reporting model (above), and — as
you'll see below — it turns out to be narrower than the plan expected, because
one of the plan's two "fixes" is not a bug once you read the code it's fixing.

## Fix 1 — the real bug: stale linkman numbering in `cli.py`

`src/devman/cli.py`'s `_link_reconcile_with_linkman` (the `DEVMAN_LINK_ENGINE=
linkman` path), confirmed at lines 445-449:

```python
    if apply_result.failed:
        return 13
    if apply_result.refused:
        return 11
    return 0
```

(verify with `grep -n 'return 13\|return 11' src/devman/cli.py`.) This is
devman calling linkman **in-process as a library** — it reads
`ApplyResult.failed`/`.refused` (plain lists on a return value, not an
exception) and picks its own number, chosen to mirror linkman's old, now-
retired 10-13 numbering from before linkman's own step 2 migration. Confirm
linkman's current numbers collapsed exactly as expected:

```bash
grep -n 'class Exit\|DRIFT\|REFUSAL\|PARTIAL\|CONFIG\|OS = ' /home/andrew/Documents/Projects/linkman/src/linkman/cli.py
```

You should see `REFUSAL = 1` and `PARTIAL = 1` (aliases of `DRIFT`), confirming
both of devman's old `11`/`13` map to linkman's collapsed `1`. Fix:

```python
    if apply_result.failed:
        return 1
    if apply_result.refused:
        return 1
    return 0
```

**No test asserts either value today.** `grep -rn '_link_reconcile_with_linkman\|== 13\|== 11' tests/ src/devman/cli.py`
turns up only the definition and the two `return` statements themselves —
`tests/unit/test_linking.py` tests the underlying `reconcile_with_linkman()`
library function and asserts directly on `result.apply_result.failed`/
`.refused` (lines 118-119), never the CLI wrapper's int return. Add a new test
in `tests/unit/test_cli.py` (or a new small test module beside it) that
monkeypatches `devman.linking.reconcile_with_linkman` to return a
`LinkingResult` whose `apply_result` is a fake object exposing `.applied`,
`.refused`, `.failed` (see `src/devman/linking.py:58-63`'s `LinkingResult`
dataclass for the real shape), and asserts `cli._link_reconcile_with_linkman(
args) == 1` for both the "refused only" and "failed" cases, and `== 0` for the
clean case. Re-grep `tests/unit/test_cli.py`'s existing fixtures (`SimpleNamespace`
is already imported there) before writing it, to match the file's style.

## Fix 2 — the plan's other "fix" is not a bug: do not change `RegistryError`

**This is the second thing to get right, and it corrects part of the original
plan for this session.** The brief this prompt was drafted from claimed that
`watch.py`'s dispatcher writes a misleading `"refused ({code})"` label because
`RegistryError` (currently exit `1`) should become a fault (exit `2`), and
that the label needs to distinguish it from `LinkError` (which should stay a
refusal, exit `1`). **Investigation does not support this.** Re-check it
yourself before trusting this correction:

1. `RegistryError`'s own docstring, `src/devman/registry.py:114-115`:
   ```python
   class RegistryError(Exception):
       """A refusal the developer must see. The CLI prints it and exits 1."""
   ```
   This is a stated design, not an oversight.
2. Sampling its ~20 raise sites across `registry.py`, `run.py`, `cli.py`
   (`grep -rn 'raise RegistryError' src/devman/`) shows it is used for things
   like "no project named 'x' in the registry", "this directory is not inside
   a registered repository", "no workflow named 'y'", "an override names no
   declared parameter", "a plane reload is pending — retry after it clears".
   These read as usage-level refusals a caller can act on, not infrastructure
   faults — the same category loci-core's own migration (step 3) kept as
   findings (`SourceConflictError`, `InvalidRequestError`), not faults.
3. `doctor.py:1550-1559` catches `RegistryError` around a manifest scan and
   treats it as "nothing to check" (`EMPTY` status), not a crash — a third
   confirmation that this exception means "nothing here", not "something
   broke".
4. Three existing, deliberately written tests pin today's behavior exactly:
   `tests/unit/test_watch.py:565-580` (`test_dispatch_refuses_while_reload_is_
   pending`) and `:655-692` (`test_a_refusal_is_recorded_and_the_rest_of_the_
   batch_still_fires`) both raise `RegistryError` and assert
   `watch.dispatch(...) == 1` and `"refused (1)"` in `fired.jsonl`. Re-grep
   `tests/unit/test_watch.py` for `refused (1)` to confirm these are still
   there and still green.

**Conclusion: leave `RegistryError` mapped to `1` everywhere it is today —
`cli.py:584`'s `except (RegistryError, devman_link.LinkAdapterError): return 1`,
and `watch.py:619-621`'s per-entry `except RegistryError: code = 1`.** Do not
touch `watch.py`'s `f"refused ({code})"` string at line 634 either: `code` in
that function is only ever `0` or `1` today (both `RegistryError` and
`LinkError` map to `1`), so there is no label collision to fix, and there
won't be one after Fix 1 above either, since Fix 1 is in a completely
different function (`cli.py`'s `_link_reconcile_with_linkman`) that `watch.py`
never calls. State this correction explicitly in your closing summary — don't
silently drop it, since it changes the shape of the step from what was asked.

## The one real open question: can the entry point be wrapped at all?

`mancore.cli` exports two helpers for a console-script entry point —
`run(app, tool)` for a Typer app, `wrap(entry, tool)` for a hand-parsed-`argv`,
int-returning `main()`. Read `mancore/src/mancore/cli.py` yourself; both are
short. **devman is the `wrap()` shape, not the `run()` shape**: `src/devman/
cli.py:579` defines `main(argv: list[str] | None = None) -> int`, parses `argv`
with `argparse`, and dispatches to a handler that returns an int — the same
pattern as loci-core's `apps/cli/main.py`, which is why loci-core's step 3
prompt is the right model to follow for the wrapper shape itself:

```python
def run() -> NoReturn:
    """Console-script entry point: run `main` under mancore's contract."""
    wrap(main, "devman")
```

…pointed at by `[project.scripts]` and by the `if __name__ == "__main__":`
block at `cli.py:591-592` (`sys.exit(main())` today), exactly as loci-core did.

**But before you write that: this repo has a constraint loci-core did not
have, and it changes whether this is even possible to ship.** Read the header
comment of `pyproject.toml` and `nix/devman-cli.nix` yourself. Three facts,
all independently verifiable:

1. `pyproject.toml`'s own header states plainly: *"nothing installs this
   package with pip"* — `devman` ships **only** from
   `nixosModules.default`, built by `nix/devman-cli.nix`'s
   `python3Packages.buildPythonApplication`, against a **fixed, minimal** Nix
   dependency list: `dependencies = [ python3Packages.pyyaml ];`
   (`nix/devman-cli.nix:64`). That is the *only* `devman` binary that actually
   reaches a machine.
2. `pyproject.toml` already explains, in its own comment above
   `[project.optional-dependencies]`, exactly why `linkman` (needed only for
   the `DEVMAN_LINK_ENGINE=linkman` opt-in path) is in an optional `cutover`
   group rather than a base dependency: *"`nix/devman-cli.nix` builds the
   shipped CLI hermetically against a fixed Nix dependency list
   (`python3Packages.pyyaml` only) — a base dependency the Nix build cannot
   resolve fails `pythonRuntimeDepsCheckHook`, as it did here on the first
   attempt."* `linkman` gets away with being optional because the import that
   needs it (`devman.linking`) is lazy, inside a function only reached behind
   an environment-variable flag — the base `import devman.cli` never touches
   it.
3. **`wrap()` cannot get the same treatment.** The console-script entry point
   runs unconditionally the moment anyone types `devman`. There is no flag to
   hide the `from mancore.cli import wrap` import behind — if `mancore` is not
   actually installed wherever the binary runs, the Nix-shipped `devman` would
   fail on its very first line with an `ImportError`, not a graceful skip.

`mancore` itself needs `pydantic>=2.10` and `typer>=0.15.4` at runtime
(`mancore/pyproject.toml:13-16`) — both exist in nixpkgs as
`python3Packages.pydantic`/`python3Packages.typer`, but **`mancore` itself
does not exist in nixpkgs** (confirmed: PyPI and GitHub both 404 for every
spelling, per `mancore/CONCEPT.md` §10.1 — it is only a git tag).

**Update, resolved by a later session: the Nix-packaging fork below is
closed. `mancore` is now wired into `nix/devman-cli.nix`'s closure and
confirmed importable there — read on for exactly how, before you touch
`wrap()` or `[project.scripts]`.**

The repo owner's decision, made after this prompt was first written: package
`mancore` as a **devenv output** (`outputs.mancore = config.languages.python
.import ./. {};` in `mancore/devenv.nix`, using devenv's own uv2nix-based
Python packaging, new in devenv 2.0 — see <https://devenv.sh/outputs/>), the
same mechanism `nixbuild/devenv.nix:53` already demonstrates for itself (`outputs
.nixbuild = config.languages.python.import ./src {};`), and the standard this
fleet now wants for everything, not a one-off `fetchFromGitHub` derivation.
That line now exists in `mancore/devenv.nix`, and `devenv build outputs.mancore`
builds it there.

**But devman does not consume it through devenv's cross-project
`inputs.<name>.devenv.config` bridge — that path was tried by hand and does
not work in the currently-installed devenv (2.4.0).** Devenv's own docs
(<https://devenv.sh/guides/polyrepo/>, "Referencing config across inputs")
show exactly this pattern — `inputs.mancore.devenv.config.outputs.mancore` —
but also carry a caution citing <https://github.com/cachix/devenv/issues/2205>:
"The remote repository must use devenv.nix only — devenv.yaml from imported
projects is not evaluated." Confirmed by hand, reproducibly, in a scratch
devenv project: referencing `inputs.mancore.devenv.config.outputs.mancore`
with `mancore` declared `flake: false` throws `error: nixpkgs input required`
at eval time, because mancore's own `devenv.yaml` — the file that pins the
`uv2nix`/`pyproject-nix`/`pyproject-build-systems` inputs
`languages.python.import` needs internally — is never read when mancore is
referenced this way. Nested `inputs:` under the referencing project's own
`mancore:` entry do not fix this either: Nix's flake-input-override mechanism
only overrides inputs of an *existing* flake input graph, and a `flake: false`
source has none to override (confirmed: such nested entries are silently
dropped from `devenv.lock`, every time, regardless of syntax). `flake: true`
isn't an option either — mancore carries no `flake.nix`, so devenv's own
locker fails outright trying to fetch one. In short: this specific combination
(referencing a `flake: false` devenv-only project that itself needs
non-default inputs) is not yet supported by devenv 2.4.0, docs notwithstanding.

**What actually works, and is now wired in:** `nix/devman-cli.nix` builds
`mancore` itself, directly with uv2nix — the exact same recipe
`languages.python.import` runs internally inside `mancore/devenv.nix`, just
run here by hand instead of through the broken bridge above. Concretely:

- `devman/devenv.yaml` and `devman/flake.nix` (two separate input graphs —
  see the comment at the top of `flake.nix`) each declare four new top-level
  inputs: `mancore` (`git+https://github.com/Bullish-Design/mancore?ref=refs
  /tags/v0.1.0`, `flake: false` — mancore is private, so this uses the
  `git+https://` form and the local git credential helper, not the `github:`
  shorthand, which 404s against a private repo's REST API without a token;
  `flake: false` because mancore has no flake.nix, and here it is used only
  for its raw source tree, not through the broken bridge above), plus
  `uv2nix`, `pyproject-nix`, and `pyproject-build-systems` (all real public
  flakes, `nixpkgs.follows = nixpkgs`) — the same three inputs mancore's own
  `devenv.yaml` carries, redeclared here because mancore's copies are
  unreachable for the reason above.
- `nix/devman-cli.nix` takes four new arguments (`uv2nix`, `pyprojectNix`,
  `pyprojectBuildSystems`, `mancoreSrc`, plus `pkgs` for `callPackage`), loads
  `mancoreSrc` as a uv2nix workspace, and builds `mancoreEnv` — a self-
  contained venv carrying mancore and its own runtime deps (pydantic, typer).
  It is **not** added to `dependencies` — mixing a `pyproject-nix.build
  .packages` derivation directly into `python3Packages.buildPythonApplication`
  's `dependencies` was tried by hand and silently drops mancore's own
  transitive deps (`ModuleNotFoundError: No module named 'pydantic'` at
  runtime) because the two ecosystems don't share a dependency-propagation
  attribute. Instead, `mancoreEnv`'s site-packages directory is put on
  `devman`'s `PYTHONPATH` in `postFixup`, the same way `dagu`/`watchexec`/
  `git` are already put on its `PATH`.
- `devman/devenv.nix`'s `devmanCli` and `flake.nix`'s `packages.devman`/
  `default` now pass all four new arguments through from their own
  `inputs.*`/flake inputs.
- Verified by hand: `nix build .#devman` succeeds end to end (`/nix/store/
  f4d9j6hz68d0h0qj8fwhr2q4vwbw416c-devman-0.6.0` at verification time), its
  `installCheckPhase` now also runs `import mancore` against the wrapped
  `PYTHONPATH` and passes, and running the built `devman --help` plus a
  direct `python3 -c "import mancore"` against the closure's own interpreter
  and `PYTHONPATH` both work. `devenv shell -- true` also still succeeds with
  the new inputs in `devenv.yaml`/`devenv.nix`.
- This is scoped narrowly to *making mancore importable in the closure*.
  **`wrap()` is not wired up by this change** — `cli.py`'s entry point and
  `[project.scripts]` are untouched, exactly as "defer it" below describes.
  `mancore` is also not added to `pyproject.toml`'s dependencies (base or
  `cutover`) — the Nix side gets it via `PYTHONPATH`, not via Python
  packaging metadata, so nothing there needed to change.

Given this, the two options originally posed below collapse: the Nix
packaging burden is paid (via the devenv-output + direct-uv2nix-build
approach above, not a hand-written `fetchFromGitHub` derivation), so wiring
`wrap()` next is no longer blocked on new Nix work. What is still a real,
open choice is only the ORIGINAL "land it or defer it" question for `wrap()`
itself:

1. Fix 1 (and the Fix 2 correction, which needs no code change) land on
   their own — they need no new dependency and carry no risk to the Nix
   build. (At the time of this update, Fix 1's code change is already present
   uncommitted in the working tree, from a prior session — re-verify it
   still matches the "Fix 1" section above before committing it.)
2. For `wrap()`: since `mancore` importable-in-the-closure is no longer the
   open question, whoever picks this up next can go ahead and wire
   `[project.scripts] devman = "devman.cli:run"` + the `run()` wrapper
   directly, test it with `devenv tasks run -v base:test` (rebuilds the real
   Nix closure) and `$out/bin/devman --help` (mirror `nix/devman-cli.nix`'s
   existing install check, now extended with the `import mancore` check
   above) — no need to stop and ask about the Nix fork first, since it is
   closed. The only remaining judgment call is cosmetic: `cli.py` still needs
   `from mancore.cli import wrap` for `run()`, and since `mancore` is not a
   declared Python dependency anywhere in `pyproject.toml` (see above), a
   plain `uv run`/dev-venv invocation of `devman` outside the Nix closure
   will not have `mancore` importable unless something adds it to a dev-only
   dependency group — decide that when wiring `wrap()`, not here.

If you want tests to exercise `wrap()` without relying on the Nix build above,
`mancore` still is not a declared Python dependency anywhere in
`pyproject.toml`. Do **not** add it to the `cutover` optional-dependencies
group as a half-measure — `cutover`'s whole design depends on the import
being lazy and flag-gated, which does not apply to a console-script entry
point that runs unconditionally. Add it under a *new*, separate optional
group instead (or reuse `cutover` only if `mancore` becomes genuinely optional
there too, e.g. gated on an environment variable at import time the same way)
and guard every new test with `pytest.importorskip("mancore")` at module
level, exactly like `tests/unit/test_linking.py:28` does for `linkman` — this
keeps `devenv tasks run -v base:unit`'s hermetic pytest (which has only
`pytest` and `pyyaml`, `devenv.nix:24`) skipping cleanly instead of failing to
import.

## Already correct — confirmed, do not touch

Four places the original plan worried about, all verified fine as of this
session. Don't waste time "fixing" what already works:

1. **`cli.py`'s `_central_verify`** (lines 452-532). Already returns `2` for
   both infra cases — no overlay directory (`:487-488`) and a
   `central.InfraError` (`:513-515`) — and `1 if findings else 0` (`:532`) for
   the finding case. `tests/unit/test_central.py` already exercises all three
   paths by calling `cli._central_verify(args, None)` directly. No change.
2. **`watch.py`'s watcher loop already returns `130` on interrupt.** Confirmed
   at `watch.py:466-467`, inside `supervise()`:
   ```python
   except KeyboardInterrupt:
       return 130
   ```
   This is a different code path from the entry-point question above — it is
   the long-running watcher daemon's own loop catching `SIGINT` and returning
   `130` as a plain value from `watch.main()`, which `cli.main()` then returns
   unchanged. It needs no `mancore` import and nothing about the open question
   above affects it. No change.
3. **`devman_link/cli.py`'s own `main()` already separates refusal from
   fault.** Confirmed at lines ~75-82:
   ```python
   except LinkAdapterError as exc:
       ...
       return 1
   except Exception as exc:  # noqa: BLE001 — an infrastructure fault is exit 2
       ...
       return 2
   ```
   No change — but note, without fixing it, that this function has no
   `KeyboardInterrupt` handler of its own, so a `Ctrl-C` during `devman-link`
   today likely does not exit `130`. That is the same class of gap `wrap()`
   exists to close, but `devman-link` ships from its own separate
   `packaging/devman-link/pyproject.toml` (a second, independent console
   script, `devman-link = "devman_link.cli:main"`, built by
   `nix/link-adapter.nix`), and is not named in this step's scope. Leave it;
   mention the gap in your summary as a finding, not a fix.
4. **`nix/link-adapter.nix`'s exit-code comment.** Confirmed at lines 121-124:
   ```
   # Exit 1 is the drift answer: nothing is linked yet. Exit 2 would mean the
   # component could not run at all, which is the failure this check is for.
   [ "$code" = 1 ] || { echo "expected exit 1, got $code" >&2; exit 1; }
   ```
   Already uses the correct numbers (unlike linkman's own `nix/linkman.nix`
   before its step 2 fix, which cited a stale `Exit 10`). No change.

## Verification

```bash
devenv tasks run -v base:check    # ruff check .
devenv tasks run -v base:unit     # the fast pytest loop
devenv tasks run -v base:test     # nix flake check — the authoritative gate,
                                    # minutes, run once near the end
```

If you added any `mancore`-dependent test behind `pytest.importorskip`, also
run it for real against a venv that has `mancore` installed (mirror
`tests/unit/test_linking.py`'s own instruction: `uv sync --extra cutover`-style,
adjusted for whichever extra you added it under) — don't rely on `base:unit`'s
skip to mean "passing".

Compare your test count against the Part 0 baseline: it should be the same
count plus the new `_link_reconcile_with_linkman` test(s) from Fix 1, with zero
failures, and no change at all if you deferred the entry-point question.

## What NOT to do in this step

- Do not touch `gitman`, `linkman`, `loci-core`, `testee`, `copyroom`,
  `docman`, or any other sibling repo, **including `mancore` itself** — not
  even to reconcile the §9a/§10.9/MIGRATION.md conflict this prompt flags.
  That reconciliation is real but it belongs to a human, in the `mancore`
  repo, not to this session.
- Do not push anything, to this repo or any other, without checking with the
  person running this session first. Commit locally; stop and report what you
  did before pushing.
- Do not migrate `doctor.py`'s `ok`/`..`/`!!`/`--` status vocabulary onto
  `mancore.Report`/`Row`, and do not change what counts toward `findings`
  (`doctor.py:122-138`). See "devman is NOT getting a full report-model
  migration" above — this is settled for this step regardless of what
  `mancore`'s own docs currently say.
- Do not touch `agent.py`'s `0/1/2/3` protocol with Agentman. That is
  `mancore/docs/MIGRATION.md` step 8, a separate project gated on changing
  `agentman` in step, not part of step 7 (confirmed in `mancore/CONCEPT.md`
  §9a: "`agent.py`'s `3` is not part of this migration").
- Do not touch the version/tag drift noted in Part 0 item 3 — that is step
  12's job.
- Do not touch the `"0"/"1"/"2"/"3"` phrasing in `doctor.py:127`'s docstring or
  any other prose reference to the retired four-code contract — that is
  `mancore/docs/MIGRATION.md` step 11's dedicated documentation sweep across
  the whole fleet, not this step. (If you happen to notice it while editing
  something else in the same function, it is fine to leave a one-line note
  about it in your summary, but do not edit it as part of this pass.)
- Do not change `UNIVERSAL_SKILLS` (`doctor.py:1824`) or any skill-pool
  mechanism — unrelated to this step.
- Do not rename `RegistryError`, `LinkError`, `LinkAdapterError`, `main`, or
  any other existing class or function.
- Do not add a `capability` command or manifest — that is
  `mancore/docs/MIGRATION.md` step 9, not gated on this step and not part of
  it.
- Do not add `mancore` to the `cutover` optional-dependencies group as a way
  to sidestep the Nix packaging question for the real entry-point wrapper —
  see the reasoning above for why that specific half-measure doesn't work.
- Do not tag or release `devman` yourself as part of this step unless asked.

When done, summarize exactly which exit codes changed for which situation
(expect: just the two stale linkman-numbering returns in
`_link_reconcile_with_linkman`, from `13`/`11` to `1`/`1`), state explicitly
that the `RegistryError`-as-fault idea from the original brief was
investigated and rejected (with the four pieces of evidence above), state
whether you landed, deferred, or escalated the entry-point `wrap()` question
and why, flag the unresolved `mancore`-docs conflict over devman's `..` status
one more time so it isn't lost, and confirm `devenv tasks run -v base:check`,
`base:unit`, and (once, at the end) `base:test` all pass clean with the
expected test count.
