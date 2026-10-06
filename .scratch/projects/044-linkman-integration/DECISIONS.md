# Decisions — 044 Linkman integration

Every decision this session reached, with the rejected alternative and the
reason. Operator calls are marked and left undecided.

Written 2026-10-05 against devman trunk `f4a245f`, linkman `06de662` (`v0.1.0`).

Precedence followed, from Linkman's own contract: decisions override the
concept; the guide is followed except where judgment conflicts, and every
conflict is called out rather than silently resolved. The conflicts found are in
§D.

---

## A. Decisions

> **Architecture revised 2026-10-05, later the same day.** A step-back review
> asked whether the M14 lane docs' approach was the cleanest way to the goal.
> Four operator choices (D23-D26) changed it. **D1, D2, D3, D4, D5, D6 and D7
> below are superseded** — they describe wiring Linkman in as a Python library,
> which is no longer the plan. They are kept, marked, because their measurements
> stand and because a future session may need to know the library route was
> considered and why it was dropped. D8-D22 are unaffected. Read D23-D26 first.

### D23 — devman consumes the Linkman **CLI**, not the Python library

devman calls `linkman apply --repo-root X --overlay Y --name Z` from its
shell-entry hook. nix-meta installs the CLI on the system profile. devman takes
no flake input, no overlay and no Python dependency on Linkman.

**Verified before deciding**, not assumed: the CLI's
`--repo-root`/`--overlay`/`--name` reproduce
`devman-link reconcile --root/--overlay/--project` exactly
(`linkman/src/linkman/cli.py:36-41`, `repository.py:42-59`); `apply --json`
carries `applied[]`/`refused[]`/`failed[]` per link with messages and
`error_type` (`models/results.py:87-96`); and devman's exclude projection needs
only a binary target-inside-repo test computable from `links.yaml`
(`excludes.py:50-58` vs `linkman/topology.py:52-53`).

**Rejected: the Python library via a flake input**, which is what
`m14-lanes-8-10-refactoring-guide.md` assumes and what Linkman was deliberately
packaged as `buildPythonPackage` to allow. It is a coherent design and it would
work. It was dropped because it buys nothing devman needs and costs: a flake
input, an overlay, the `forAllSystems` rewrite off `legacyPackages`, interpreter
pinning across three derivations, darwin gating, and a private-repo credential
requirement on devman's own flake. Under the CLI route devman's `flake.nix` and
`nix/nixos-module.nix` need **no change at all**.

**Note the conflict, per the precedence rule.** `linkman/nix/linkman.nix:3-10`
states its reason for being a library: "devman's adapter must `import linkman`."
That is an assumption about devman's design, and this decision tests it and finds
it false — devman's residual job is three devman-only things (bootstrap content,
exclude projection, copyroom templates at zero live uses), none of which needs
the library. The `buildPythonPackage` choice remains correct for Linkman
regardless; it simply is not load-bearing for this consumer.

**The one capability with no CLI equivalent** is the `environ` override on
`api.*`, which lets a caller substitute a variable-resolution environment. It
matters only for sandboxed testing, not production. If devman ever needs it, that
is the trigger to revisit — `OPEN-QUESTIONS.md` O6.

### D24 — Switch engines by pin-bump and generation rollback; abandon `DEVMAN_LINK_ENGINE`

Verify the new engine read-only against all 60 projects with `linkman diff`
(lane 3), then one tag, one pin bump, one `nixos-rebuild switch`. Rollback is a
NixOS generation activation.

**Rejected: the env-flag migration** of lanes 9b-1/2/3 — make the flag reach
shell entry, flip the default, hold one release. Its justification is rollback
without a rebuild. But that rollback is **partly illusory**: once the default
flips, reverting machine-wide means setting an environment variable, either via
`environment.variables` (which needs a rebuild) or by hand-editing a shell rc
outside Nix's control. Meanwhile generation rollback is one atomic, already-tested
command. The flag would cost three lanes plus a dual-arm install-check fixture
and buy a weaker rollback than the pin already provides.

**What replaces the 7-day hold is stronger, not weaker.** `linkman diff` is a
complete read-only dry run for `apply` — same pipeline, stopping before
`apply_plan` (`linkman/src/linkman/api.py:183-207` vs `:210-230`). Exercising all
60 real configurations before switching is better evidence than a week of a flag
nobody sets. The readiness review's own finding was that the previous hold
measured nothing (`m14-lanes-8-10-readiness-review.md:326-335`).

`src/devman/cli.py:554-558` and `_link_reconcile_with_linkman` retire in lane 6.

### D25 — Stop this push after the engine swap; defer the 60 central files

**Enabled by a verified fact, not by appetite.** `links.yaml` is a **superset**
of the Nix declarations in all 60 overlay projects — 4 identical, 56 differing
only by the `devenv.local.nix` self-link that `links.yaml` carries extra. So the
engine can read `links.yaml` exclusively while `modules/link.nix` keeps its
option *declarations*, and the 60 `devman.link` attribute sets go **inert**
rather than away. Nix evaluation still succeeds in all 60 files, untouched.

**Rejected: the full 15-lane retirement in one push.** Its last two lanes were
the only hard-to-reverse ones, and both were operator-gated — rewriting 60 files
in `~/.config/devman`, whose `gitman land` the permission classifier correctly
denies to an agent (`041/DECISIONS.md:297-326`, D9), and deleting the adapter
from the system profile. Deferring them removes every hard-to-reverse step from
this push.

**Rejected: gate-green-only, then re-plan.** Considered, because a working gate
would make everything after it easier to judge. Dropped because the engine swap
is already fully specified and verified, so stopping at the gate would discard
finished design work for no safety gain.

### D26 — No decision needed on Linkman's repository visibility

**Dissolved rather than decided.** I had recorded this as operator question Q7,
on the grounds that a private `git+ssh` input would make devman's flake
unbuildable without credentials. Under D23 devman takes no input at all, and
nix-meta — where the input does go — already carries two private `git+ssh`
inputs (`silverbullet-server`, `inferference`) with root's SSH solved
declaratively at `machines/server.nix:435-448`, whose comment names this exact
problem and is exercised on every `sudo nixos-rebuild switch`.

So Linkman may stay private at no cost. Q7 is withdrawn, not answered.

### D27 — Central-overlay templating survives, but leaves the reconcile path. The `template` field does not move; it is replaced.

**Operator intent, 2026-10-05: central-overlay templates are wanted** — not just
for `agents/`, but for templated central content generally. So the capability is
not dead and must not be deleted. What must go is its current placement and its
current declaration site.

**Two parts, and they ship separately.**

*Now, inside the cutover:* remove the `copyroom new` branch
(`src/devman_link/reconcile.py:138-157`) from the shell-entry reconcile path,
together with the `template` field in `declarations.py:36,53-59`,
`config.py:102-112`, and the `modules/link.nix:50-53` Nix option. This is
required independent of the capability, for three measured reasons:

1. **It could never have worked.** It locates copyroom with
   `shutil.which("copyroom")`, and copyroom is never on `$PATH` by design.
   RepoMan invokes it by absolute path via `$REPOMAN_TOOLCHAIN_BIN`
   (`repoman/modules/managers/copyroom.nix:25`), and Vendomat states the reason:
   "The module invokes selected commands through their absolute store paths, so
   an unrelated executable in a consumer virtual environment cannot shadow
   them" (`vendomat/README.md:261-262`). devman's lookup is the exact
   anti-pattern that sentence exists to prevent.
2. **Its failure mode is silent.** A `LinkError` from `_create_canonical`
   propagates out of `reconcile()` and aborts the **whole** link reconcile for
   that project. `enterShell` runs without `errexit` (measured — see
   `OPEN-QUESTIONS.md` O9), so the non-zero exit is discarded. A declared
   template would have silently left every link in that project unmade.
3. **The successor schema cannot express it.** Linkman's `LinkConfig` has one
   field, `target: str`. After the cutover `links.yaml` is the sole declaration
   format, so there is no syntax in which to write `template:`.

*Later, as its own initiative:* build central-overlay templating in devman's
**CLI**, at adoption time, locating copyroom by absolute path.

**Rejected: port the call as Lane 8c scopes it.** It would move unreachable,
broken code into a smaller place and keep a once-per-project bootstrap action
inside a per-shell-entry loop.

**Rejected: delete the capability outright (the earlier recommendation in this
file's own §B).** It rested partly on a false premise — that copyroom was absent.
Copyroom is a maintained fleet pillar, described by RepoMan as "the repo
'genome'", and the operator wants the capability.

**Rejected: RepoMan owns it.** Tested and refuted. `repoman/AGENTS.md:10-11`
disclaims devman's domain in as many words — "Devman, vendomat, and shellij …
are not lifecycle managers" — and `:12-13` says "RepoMan writes exactly one
file, the router". `repoman new`/`adopt` are literal pass-throughs to copyroom
(`repoman/src/repoman/cli.py:190-217`). RepoMan has no model of
`~/.config/devman`, and giving it one would be the scope expansion its own
charter argues against.

**The design correction, and it is the point of this decision.** The `template`
field attached *how content is created* to *where a symlink points*. Those are
different lifecycles: creation happens once, at adoption; linking happens on
every shell entry. Conflating them is why a bootstrap concern sat in a reconcile
loop and went five years unexercised. So the replacement does **not** add a
`template` key to `links.yaml`. `links.yaml` declares links. Template intent
belongs in adoption input — the open design question recorded as
`OPEN-QUESTIONS.md` O3.

**Charter support for the new placement already exists**, and the current code
contradicts it. `024-personal-overlay/CONCEPT.md` §3.5: "put the logic in the
CLI, not in the hook … property 7 — Python for core logic." And §3.4 deferred
this same feature once, for want of a need: "Nothing is missing. What is missing
is the **need**." The need now exists, which is what makes building it right
worthwhile and what makes 025 §11.1's reconciler placement the part to amend.

**Charter amendment required, per CLAUDE.md property 2.** `025/CONCEPT.md` §11.1
says "The reconciler … renders any declared `template` with copyroom." Amend it
to say templating happens at adoption, through devman's CLI, by absolute path —
changing *where and how*, not *whether*. §11.1's core reasoning stands untouched:
auto-template is legitimate in the central config repo and only there, because
copyroom's managed ⇒ tracked ⇒ committed invariant holds in a tracked repo and
fails in a project repo.

### D28 — `devman-link reconcile` orchestrates in Python and shells out to `linkman`

Resolves `OPEN-QUESTIONS.md` O2. The hook keeps calling `devman-link reconcile`;
the engine substitution happens inside the binary.

**Rejected: the `enterShell` hook runs two or three commands.** There is no
`errexit` around the hook (O9), so nothing stops step 3 after step 2 fails
unless hand-written shell control flow is added — which AGENTS.md property 7
calls shell nobody can test. It also cannot do the 11-vs-13 distinction or gate
exclude-projection on `apply --json`'s `applied[]` without `jq` in shell. A
missing binary would give `command not found`, exit 127, no repair text, and the
shell would continue anyway.

**Rejected: the full `devman link reconcile` CLI.** Shell entry would need Dagu,
watchexec and the registry healthy to make a symlink — the dependency
`nix/link-adapter.nix:17-22` exists to prevent.

**Deferred, recorded as a follow-up:** moving exclude-projection out of shell
entry into `doctor`/`watch`. It would shrink the un-failable path to its two
load-bearing steps, at the cost of `.git/info/exclude` lagging a new link by up
to one cycle. Its only consumer is `git status`, not Nix evaluation, so the
staleness is not the same hazard class — but it needs its own lane and decision.

**Why this decision is cheap:** today's orchestration is already Python, already
in the right order — `src/devman_link/api.py:82-114` does identity → bootstrap →
validate → reconcile. This replaces **one call**. Locate `linkman` with
`shutil.which` and a typed error carrying a `repair:` line, per five house
precedents (`central.py:197-209`, `config.py:166-185`, `doctor.py:296-333`,
`reconcile.py:600-618`), all `check=False`, never `check=True`. The
`makeWrapper` route is unavailable because D23 forbids Linkman as a Nix build
input.

### D29 — Supply `git` in the CLI wrapper; keep the missing-`git` refusal unchanged

Decided 2026-10-06 for lane 2. This resolves O4 for the gate fix.

`check_link_drift` reads the central trunk with `git ls-tree`. The packaged CLI
must put `git` on its runtime PATH. The VM test first raised `InfraError` because
`git` was absent. After the wrapper change, doctor reached its universal-pool
check. The VM passed after its fixture supplied `writing/SKILL.md`. The package
fix removes the observed crash.

Doctor still exits 1 if somebody runs it without `git`. That refusal is loud,
but it prevents doctor from reporting other checks. Changing that behavior needs
a separate lane with a defined report status. This gate lane changes only the
runtime dependency.

---

### D1 — ~~Consume Linkman through `overlays.default`, with `inputs.nixpkgs.follows`~~ SUPERSEDED by D23

Add the input as
`git+ssh://git@github.com/Bullish-Design/linkman?ref=refs/tags/v0.1.0` with
`inputs.nixpkgs.follows = "nixpkgs"`, and apply `linkman.overlays.default`.

**Rejected:** taking `packages.${system}.linkman-lib` directly. It mixes Python
packages built from two nixpkgs revisions (devman's `ffb3c9b`, 2026-08-19;
linkman's `a7868a72`, 2026-10-03), which is how an ABI mismatch arrives.
Vendomat already handles `pyjutsu` this way for gitman — that is the precedent.

**Rejected:** the overlay without `follows`. The closure would then carry two
nixpkgs and the overlay's `linkman` would be built from one while devman's own
packages come from the other, defeating the point of using the overlay.

**Cost accepted and stated:** `follows` builds Linkman against a nixpkgs its own
`checks` have never exercised. Mitigated by D2.

### D2 — ~~Add a devman-side check that imports `linkman` through the overlay~~ SUPERSEDED by D23

Model it on `linkman/flake.nix:101-121`, which asserts a bare `import linkman`
succeeds and that neither `typer` nor `yaml` enters `sys.modules`.

**Rejected:** relying on Linkman's own `checks`. They run against Linkman's
nixpkgs, not devman's, so they cannot prove the combination D1 creates.

**Rejected:** relying on `pythonImportsCheck` in the consuming derivation alone.
It proves the package imports, not that it imports *through the overlay route*
devman uses.

### D3 — ~~`forAllSystems` moves to `import nixpkgs { … overlays = [ … ]; }`~~ SUPERSEDED by D23

**Rejected:** nothing. `flake.nix:31` passes `nixpkgs.legacyPackages.${system}`,
an already-instantiated set that cannot take an overlay in place. `pkgs.extend`
would re-instantiate nixpkgs per call site and hide the cost. This is forced, not
chosen.

### D4 — ~~Gate the linkman-dependent outputs with `optionalAttrs … isLinux`~~ SUPERSEDED by D23 (no linkman-dependent output exists)

Linkman ships `x86_64-linux` and `aarch64-linux` only; devman declares four
systems including two darwin.

**Rejected:** narrowing devman's `systems`. `nix/dagu.nix:36-43` deliberately
carries darwin release binaries and hashes; narrowing would silently drop support
somebody wrote on purpose.

**Rejected:** asking Linkman to widen. It costs an upstream change, and a
platform claim nobody can test, for zero present consumer — the plane has no
darwin machine.

**Reason for the choice:** `flake.nix:183` already uses exactly this idiom for
`module-assertions` and `dagu-service`, so the next reader needs no new concept,
and the adapter is installed by a NixOS module anyway.

### D5 — ~~`nix/devman-cli.nix:63` and `flake.nix:171` take the dependency~~ SUPERSEDED by D23 (no derivation takes it)

The adapter's fileset (`nix/link-adapter.nix:41-49`) excludes `src/devman`.
Nothing under `src/devman_link` imports Linkman — the only import is
`src/devman/linking.py:44`, which is in the CLI's fileset (`../src` wholesale)
and not the adapter's. The adapter needs Linkman only when Lane 9b-1 moves
engine selection into `src/devman_link/cli.py`.

**Rejected:** the guide's framing of 9c as "rewire the adapter"
(`m14-lanes-8-10-refactoring-guide.md:471-553`). It names the wrong derivation.
Adding the dependency to the adapter alone would leave the engine flag still
unable to work and `test_linking.py` still skipping.

**This is a conflict with the guide and is called out, per the precedence rule.**

### D6 — ~~Add `linkman` to the `python-tests` interpreter~~ SUPERSEDED by D23

`tests/unit/test_linking.py:28` is `pytest.importorskip("linkman")`. Today the
whole Linkman integration test **skips inside the gate** — it is the `1 skipped`
in the measured output.

**Rejected:** leaving it skipped until later. AGENTS.md's "Could it succeed while
doing nothing?" test applies directly, and the answer today is yes. A gate that
skips its only test of the new engine is the failure mode this plane exists to
prevent.

### D7 — ~~Pin the three linkman-touching derivations to `python313Packages`~~ SUPERSEDED by D23; the split it found survives as OPEN-QUESTIONS O5

Measured 2026-10-05: devman's nixpkgs `python3` is **3.14.7**; `python313` is
3.13.15. `nix/devman-cli.nix:43` and `nix/link-adapter.nix:36` take unpinned
`python3Packages` and therefore build on 3.14.7, while `flake.nix:137` and
`devenv.nix:24` pin `python313`. **devman already ships on 3.14.7 and tests on
3.13.15**, and nobody recorded it.

**Rejected:** `python314Packages`. Linkman has never been built or tested there
(`linkman/nix/linkman.nix:46` pins 3.13 precisely because its own nixpkgs rolled
to 3.14.7), and `pydantic` on 3.14 would be a second unverified variable.

**Rejected:** leaving them unpinned. That makes the shipped interpreter a
function of whenever nixpkgs last rolled, which is how this split arrived
unobserved. `pyproject.toml` requires `>=3.13`, so both satisfy it and the split
is silent.

### D8 — Leave `pyproject.toml:35-39` untouched until Lane 10.1

**Rejected:** switching `[tool.uv.sources]` to the published tag in 9c. It would
make the fast loop fetch over SSH on every lock refresh — slowing the loop whose
only purpose is speed — and it would not remove
`tools/cutover/gate.py`'s hard-coded
`~/Documents/Projects/linkman/.devenv/state/venv/bin/linkman`, which needs the
sibling checkout's built venv rather than an importable package.

**Rejected:** removing the `cutover` extra in 9c. `test_linking.py` still needs
Linkman importable in the dev venv.

The extra, the editable source and the hard-coded path all leave together with
their only consumer in Lane 10.1.

### D9 — `check_link_drift` is not ported. It is not a Linkman consumer.

`doctor.py:1582-1657` calls only `central.reverse_index`, `trunk_name`,
`check_c2_missing`, `check_c3_lane_only`, `check_c5_empty_surface` — all
present-tense filesystem plus `git ls-tree`. Its docstring (`:1607-1611`) records
that it was deliberately rewritten *off* any durable record. `doctor.py` makes
zero function calls into `devman_link`; four of its five remaining mentions are
prose.

**Rejected:** the prompt's premise that `check_link_drift` "rests on a concept
the replacement does not have". Verified false by reading the function. The
premise holds for `check_ledger_stale` alone.

### D10 — The ledger survives, with a smaller schema. Do not delete it.

`src/devman/linking.py:51` imports `read_state`/`write_state` and uses them at
`:138`, `:143`, `:146` to persist the exclude-projection baseline that
`ensure_local_gitignore` reads. D5 of the cutover keeps `.git/info/exclude`
projection as devman's. **devman therefore keeps a state file of its own, and
that is not a D2 violation — D2 binds Linkman, not its consumers.**

What dies is the promotion-hash half (`devman_link/reconcile.py:201-210`),
replaced by Linkman's present-tense `MigrationCollisionError`: "do both sides
hold conflicting real content *now*", which needs no history. Strictly weaker —
it cannot see "canonical changed while the view stayed a correct symlink" — but
that case is a no-op.

**Rejected:** deleting the ledger with `devman_link`, as the original guide
assumed. The readiness review's F2 already corrected this
(`m14-lanes-8-10-readiness-review.md:381-391`) and this session confirms it from
the code.

**Rejected, and not proposed:** re-adding durable state to Linkman. D2 is settled
and Trap 5 names this as the specific thing not to do.

**Consequence:** `check_ledger_stale` is not vacuous. It keeps checking a real
(smaller) record.

**Refinement, verified later in the session.** The schema does not change either.
`ensure_local_gitignore` reads *and* writes the identical `{canonical, hash}`
record (`src/devman_link/excludes.py:107-110`, `:139-142`), using the hash for
the same two-sided-edit refusal the promotion guard used. So only the **key set**
shrinks — from one entry per `project:view` to one exclude-projection entry per
project, about 345 rows down to about 59. Lane 7 is therefore a pruning and
ownership change, not a schema change. See `OPEN-QUESTIONS.md` O3.

### D11 — devman keeps computing dangling-link detection itself

`central.py:270-272` (`os.path.exists(v.target)`) over `central.py:173-184`'s
`_normalize_target`, which uses `os.readlink` + `normpath` and whose comment
(`:176-177`) explicitly refuses `.resolve()`: "resolving would follow a second
hop and report the wrong path if the target is itself a symlink." Already
Trap-6 compliant.

**This decision is not new.** `041/DECISIONS.md:329-358` (D10) already decided
it: "The check must not use `linkman check`; it is devman's own code", with the
gap filed as O7 for Linkman's owner and the standing rule that "this project is
forbidden from designing around a Linkman change." This session **confirms** it
from Linkman's code (`planning.py:20-32` reads only `actual.link.kind`;
`api.py:158` discards `actual_link.target`; `LinkStatusReport` has no target-kind
field) and records the consequence the prompt asked for: **the deferred
check-reporting gap does not become a Lane 9a dependency.**

### D12 — Porting `watch.py` onto `apply_plan` is a gain; split the handler

`devman_link` raises one `LinkError` for four deliberate refusals and two tool
failures; `watch.py:622-629` catches by type and flattens all of them to
`code = 1`, discarding `reconcile`'s return value at `:606-611`. Linkman
separates a safe refusal (11) from a real failure (13) and returns
`.applied`/`.refused`/`.failed` lists.

**Rejected:** a one-for-one port keeping the single handler. It would throw the
11/13 distinction away at the boundary, exactly as today, and leave the watcher
still unable to tell "nothing applied" from "three applied, one refused".

Copy the shape already correct at `src/devman/cli.py:411-449`.

### D13 — Only four source files import `devman_link`; classify accordingly

| File | Phase |
|---|---|
| `src/devman/linking.py:46-51` | D — move the feature out |
| `src/devman/cli.py:50` | E — port |
| `src/devman/watch.py:58` | E — port |
| `src/devman/doctor.py:63` | neither — follows the ledger schema change |

**Rejected:** the prompt's list of 17 files. `registry.py`, `central.py`,
`devman_contract/__init__.py`, `manifest.py` and `identity.py` do **not** import
`devman_link` — every hit in those five is a comment or docstring, verified by
reading each file.

### D14 — `devman_contract` survives untouched and is not a deletion candidate

It is 559 lines of identity grammar and manifest schema, consumed by three
parties (`devman`, `devman_link`, Vendomat). `devman_link/identity.py` imports
*from* it, never the reverse — it sits **under** the link engine, not over it.

**Rejected:** treating it as part of the `devman_link` closure to be moved or
deleted. The dependency direction forbids it.

### D15 — Two gate lanes, both before everything

`nix flake check` is red for two unrelated reasons. Lane 8.0 as scoped fixes one.

**Rejected:** one combined lane. The two failures have nothing to do with each
other — a fileset omission and a missing runtime dependency — and combining them
makes a revert all-or-nothing on unrelated changes.

**Rejected:** proceeding with a red gate. It is the `gitman.toml`
`[publish] verify` hook, so no lane in the milestone can land until it is green.

### D16 — Pull the Nix wiring forward to lane 3 of 15

**Rejected:** the guide's position for 9c-2, after 9b. That position exists
because Q1 was unanswered when the guide was written — there was no package to
wire. Q1 is now answered, and pulling the input forward un-skips
`test_linking.py` immediately, and supplies the dependency both 9b-1 and the
`watch.py` port need.

### D17 — Split Lane 9a

`doctor.py`'s change is a ledger-schema change needing no Linkman.
`watch.py`'s port **imports** Linkman and cannot precede the Nix wiring.

**Rejected:** the guide's single 9a before 9c. It would not build.

### D18 — Retain the guide's 9e-before-9d order

Confirmed on three measurements: both machine paths come from the one adapter
derivation (the live `link-module.nix` resolves into
`b9rrdnmy…-devman-link-0.6.0`, the same store path as the binary);
`nix/nixos-module.nix:697-700` and `:706-708` install both from one gated
package; and **59 of 60** central files import it (against the review's 77 of 78
— the absolute number fell with the project count, the proportion did not).

**Rejected:** the original guide's 9d-before-9e. It bricks shell entry with a Nix
trace nothing can intercept, because Nix reads `devenv.local.nix` before any hook
runs.

### D19 — Fold the `repo` kind removal into Lane 9d; give it no lane

Zero live uses, confirmed two ways: 180 `central`, 52 `external`, 0 `repo` across
`~/.config/devman/projects/`; and `links.yaml` schema v1 has no `kind` field at
all. Seven of its nine reference sites vanish with 9d's deletion of
`src/devman_link/` and `modules/link.nix`.

**Rejected:** an early standalone cleanup lane. It was considered because the
change is genuinely trivial, but it would edit an enum in files about to be
deleted and spend a `nixos-rebuild` cycle — `modules/link.nix` ships inside the
adapter derivation — to narrow a type nothing uses.

### D20 — Use **60** as the central project count, dated 2026-10-05

All 60 directories under `~/.config/devman/projects/` carry **both**
`links.yaml` and `devenv.local.nix`. None carries only one.

**Rejected:** 78. It is the instant of one bulk-conversion commit
(`268c0a37`, 2026-10-01, "the converted links.yaml for all 78 central
projects"), before 18 test fixtures and archived projects were pruned. It was
never a steady state.

**Rejected:** 68. A correct 2026-10-02 measurement
(`041/RESEARCH-cutover-interlock.md:55-56`) that has since moved.

### D21 — The residual duplication is structural, not drift

4 of 60 are full duplicates; 56 of 60 differ by exactly one key — `links.yaml`
declares the link that puts `devenv.local.nix` into the repository. On every
overlapping key, across all 60, the declared target is the same path.

That one key is **not** drift: Nix reads `devenv.local.nix` before any hook runs,
so a Nix file cannot bootstrap itself. The end state is therefore not "the two
files agree" but "`links.yaml` is the sole declaration, necessarily including the
link that makes the other file reachable." This strengthens B4 option 2 rather
than weakening it.

**Rejected:** reporting the 56 as partial drift to be reconciled. It would send a
lane chasing a difference that must exist.

### D22 — This session creates no gitman lane

It wrote five planning documents into `.scratch/projects/044-linkman-integration/`
and changed nothing else. Per the prompt's own process rule, no lane is needed.

---

## B. Operator decisions — not decided here

### Q1 — publish Linkman as a pinnable package. **ANSWERED.**

Tag `v0.1.0` at `06de662`, pushed, annotated, dereferencing to linkman HEAD.
The flake input URL resolves from this machine (`nix flake metadata` output in
`RESEARCH-integration-surface.md` B0). The engine swap is unblocked, and D26
withdrew the Q7 caveat that briefly replaced it.

### Q2 — the engine-flag release discipline. **OPEN.** Blocks lane 10.

Confirm the discipline: the flag reaches `enterShell` first, then one tag is held
at least seven days. This session adds evidence the operator should have: until
Lane 9b-1 lands, a hold measures nothing, because nothing in the held release
runs Linkman at shell entry (`RESEARCH-shell-entry.md` D1). Recommend requiring a
**recorded count** of real shell entries during the hold, since an unrecorded
hold is indistinguishable from no hold.

### Q3 / B4 — the reconcile hook's new home. **OPEN.** Blocks lanes 12-14.

Option 2 — a minimal central Nix file whose only job is the `enterShell` hook —
is recommended and twice endorsed, and this session's recount supports it (D21).
No formal decision record exists. Not decided here.

### Q6 — the one project of 60 that imports a different module. **OPEN.** Blocks lane 13.

59 of 60 `devenv.local.nix` import
`/run/current-system/sw/share/devman/link-module.nix`; one uses a different
combined module. Recorded in `041/RESEARCH-cutover-interlock.md:60-62` as the
mnemonix anomaly. It must be resolved before lane 13 rewrites all 60.

### Q7 — Linkman is private. **WITHDRAWN, not answered.** See D26.

Raised earlier in this session and dissolved the same day by D23 plus the nix-meta
precedent. Kept below, struck through, because the reasoning that retired it is
worth seeing.

#### ~~Q7 as originally raised~~

This is the session's most consequential new finding and it is an operator call.

- `nix-meta/flake.nix:238-239` pins devman over anonymous
  `git+https://github.com/Bullish-Design/devman?ref=refs/tags/v0.7.0`.
- Linkman is **private**, reachable only over `git+ssh`.
- Adding it as a devman input makes devman's flake unevaluable without SSH
  credentials for a second private repository. Every `nix flake check`, every
  `nix build .#devman`, and every `nixos-rebuild` importing
  `devman.nixosModules.default` acquires that requirement.
- `nix flake metadata` succeeded as user `andrew`, whose agent holds the key.
  `nixos-rebuild switch` evaluates as **root** under `sudo`, with a different and
  usually absent agent. **Untested** — the prompt forbids `nixos-rebuild` — so
  this is a hazard, not a measured failure.

Q1 asked for a fetchable, pinnable package and got a *private* one. That is a
different answer from the one Lane 9c was designed against, so the gate it
cleared has partly reappeared in a new form. Options, for the operator:

1. Make the Linkman repository public. Outward-facing, so it is the user's call.
2. Keep it private and accept that building devman requires credentials —
   including whatever `nixos-rebuild` needs as root.
3. Vendor Linkman into devman. Rejected on the plane's own grounds: it recreates
   the copy that `025/CONCEPT.md` P2 forbids.

**Not decided here.** Evidence that would settle it is in `OPEN-QUESTIONS.md` O1.

### H5 — landing lane 13 at all. **OPERATOR PREREQUISITE, OPEN.**

Lane 13 rewrites 60 files in `~/.config/devman`, a repository whose `gitman land`
the permission classifier denies to an agent at any lane size.
`041/DECISIONS.md:297-326` (D9) frames that denial as **correct** and the handoff
to the operator as deliberate. So whether lane 13 can land is an operator
question before it is a sequencing question.

---

## C. Settled — not re-litigated

Recorded as checked, with no argument made against any of them: **D2** (no
durable state in Linkman), **D5** (exclude projection, template rendering and
bootstrap content stay devman's), **D-b** / the seven-call pipeline as the whole
API, **Linkman never runs Nix**, **typer stays a hard runtime dependency**
(verified present at `linkman/nix/linkman.nix:59-63`), and **raw-target
classification** (verified at `linkman/src/linkman/planning.py:26`, and devman's
own side at `central.py:173-184`).

---

## D. Where documents and code disagree

Each verified by reading the code on 2026-10-05.

1. **The prompt's "known wrong" list is itself wrong on one item.** It says
   concept §15's `load_layers(repo)` is wrong and "the real signature takes the
   two resolved file paths." The **exported** `linkman.load_layers`
   (`linkman/src/linkman/__init__.py:38-41`) does take a single `Repository`, and
   `linkman/tests/test_api_surface.py:77` exercises exactly that. The two-path
   signature belongs to the private `linkman.config.load_layers`
   (`config.py:45-48`), which is not exported. **§15 is correct; the prompt's
   correction is not.**
2. **Confirmed wrong as the prompt says:** concept §14's
   `linkman.inspect(repo, config)` / `linkman.apply(repo, config)` do not exist.
   The real calls are `inspect_state(desired)` and `apply_plan(repository, plan)`.
3. **New, and it matters:** `linkman.api.check/diff/apply` exist and are what the
   CLI calls (`linkman/src/linkman/cli.py:132-180`), but **none is in `__all__`**,
   so by concept §15's own rule ("`__all__` is the contract") they are private. A
   devman port wanting one-call behaviour would be reaching past the contracted
   surface. Flagged, not decided.
4. **The guide names the wrong derivation for 9c.** See D5 above.
5. **Lane 8.0's scope is insufficient.** See D15.
6. **Line-number drift:** the readiness review cites `src/devman/cli.py:431` for
   the engine flag; it is `:556` today. The code moved; the finding did not.
7. **`AGENTS.md` property 6 is stale.** It records generation 3 since 2026-09-15
   with 48 projects and 152 DAG files. `readlink -f` on the active pointer gives
   **generation 4**, holding 44 projects, measured 2026-10-05. The architecture is
   unchanged — which is exactly how property 6 says to read its own counts.
8. **`src/devman/paths.py` does not exist.** The prompt names it for the `repo`
   kind; the file is `src/devman_link/paths.py`.
9. **Neither `devman` nor `devman-link` has a `--version` flag.** Both are
   argparse-based and treat it as a usage error. Any lane verifying which build
   is live must compare the store path.
