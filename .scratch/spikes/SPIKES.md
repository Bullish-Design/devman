# devman re-charter — spike results

> **Run 2026-08-19** against the live machine and the sibling repos in
> `~/Documents/Projects/`. Every number here is measured, not estimated.
> These results decide four questions the 2026-08-13 concept left open, and
> correct two claims it made. Scripts live beside this file.

Environment: devenv 2.1.2, nix 2.34.7, atuin 18.18.1, toolchain venv at
`~/.local/share/repoman/venv` (typer 0.27.1).

---

## Spike A — does a regenerated `devman.nix` defeat devenv's eval cache?

**Question.** §8 names `devenv-script` the primary emitter. §15 asked whether a
nix file that changes on every build makes shell entry too slow to keep it.

**Method.** A minimal devenv project imports `gen/devman.nix`, which declares
N `scripts.*.exec` entries. Time `devenv shell -- true` across regenerations.
Script: `devenv-eval-cache/run.py`.

| Step | Time |
|---|---|
| 1. cold (first eval) | 5.46s |
| 2. warm, no change | 0.19s |
| 3. warm, no change | 0.21s |
| 4. **rewrite identical bytes** (new mtime) | **0.17s** |
| 5. regen, content changed | 1.44s |
| 6. warm after regen | 0.16s |
| 7. regen, script added (20 → 21) | 1.43s |
| 8. warm after regen | 0.16s |

**Verdict: `devenv-script` stays the primary emitter.** A content change costs
about **1.3s once**, then returns to the 0.16s warm path. That is well inside
the cost of entering a shell.

**Two findings that change the design:**

1. **devenv hashes content, not mtime.** Step 4 rewrote the file with identical
   bytes and paid nothing. So `devman build` may run unconditionally — on every
   save, in a hook, in CI — with no eval cost when the catalog has not changed.
2. **Therefore emitter output must be byte-deterministic.** Sort every key. Emit
   no build timestamp, no hostname, no random ordering. This **constrains §6's
   provenance rule**: a provenance header may name devman, the asset id, and the
   pack version, but must not carry a timestamp. A timestamp would turn every
   build into a 1.4s re-eval and forfeit finding 1.

---

## Spike B — how are CLI facts introspected?

**Question.** §15 leaned toward "walk the Typer app, because every family member
is a Typer CLI in the same machine venv." §14 step 2 depends on the answer.

**Method.** Import each tool and walk its Typer app. Scripts: `walker.py`
(final), `walker_typer_only.py` (abandoned), `parity.py` (the test that decided
between them).

**The lean was wrong on its premise.** Not every family member is in the machine
venv:

| Tool | In toolchain venv? | Commands found |
|---|---|---|
| copyroom | yes | 19 |
| gitman | yes | 25 (incl. group `remote`) |
| docman | yes | 10 |
| repoman | yes | 4 |
| **testee** | **no — `ModuleNotFoundError`** | — |

`repoman/src/repoman/registry.py` sets `install="uv"` for testee, with the
reason in a comment: testee's tools import the consumer's code. testee is a
per-repo dependency and is not importable from the shared venv. It is also the
tool the old §14 step 5 named as the first conversion target.

**The fix: an out-of-process walker.** devman ships one small script and runs it
under whichever interpreter can import the tool. Confirmed working:

```
~/.local/share/repoman/venv/bin/python  walker.py copyroom.cli app   → 19 nodes
<repo>/.devenv/state/venv/bin/python    walker.py testee.cli   app   →  8 nodes
```

One mechanism covers both install models, and needs nothing from any tool.

### B.1 The walker must go through `typer.main.get_command()`

This was re-opened by a good question — *why are we caring about click at all?* —
and the answer reversed on measurement. It is recorded in full because the first
answer was wrong.

`typer.main.get_command()` converts a Typer app into a click object graph. That
is what drags click in. It looks avoidable: typer exposes `registered_commands`
and `registered_groups` directly, and a walker built on those imports no click.
That walker was built (`walker_typer_only.py`) and matched on command *names*
immediately.

`parity.py` compares the two walkers fact for fact. The click-free version failed
three rounds:

| Round | Discrepancies | What was missing |
|---|---|---|
| 1 | **43** | `Annotated[str, typer.Option()]` style — its params live in type metadata, not in the default. copyroom and repoman use the legacy style and matched; gitman, docman and testee use `Annotated` and lost every parameter. |
| 2 | **13** | typer's name derivation — `all_` → `--all`, not `--all-`; bare `path: str` is a positional |
| 3 | **6** | short-only decls gaining a long form |

The last 6 never closed. Checked against the CLIs' real `--help`, **the click
route is right and the click-free walker is wrong in every one**:

| Command | click-free | via click | real `--help` |
|---|---|---|---|
| `gitman save` | `--message` | `--message`, `-m` | `--message`, `-m` |
| `gitman release` | `--set-version` | `--version` | `--version` |
| `docman doctor` | `--json-output`, `--repo-root` | `--json`, `--repo-root` | `--json`, `--repo-root` |

**Conclusion: `get_command()` is typer's own resolution, so it is ground truth by
construction.** Any other route reimplements that resolution, and an
approximation of it is exactly as wrong as its gaps. Three rounds of patching
reduced the error without eliminating it, and each round's gaps were invisible
until parity was run.

So devman does care about click — not by choice, but as the price of reading
facts correctly. The price is about ten lines, listed next.

**Three traps that price brings, all handled in `walker.py`:**

1. **typer vendors click.** typer 0.27.1 ships click privately as `typer._click`
   and there is **no top-level `click`** in the toolchain venv. Code that does
   `import click` fails outright.
2. **`typer._click` is not a drop-in.** It exposes `Command` and `Parameter` but
   not `Group`, `Argument`, or `Option` at the top level.
3. **`isinstance` against click is unreliable — this is the dangerous one.** In
   testee's venv, a real `click` *is* installed, and
   `isinstance(typer.main.get_command(app), click.Group)` returns **False** for a
   genuine `TyperGroup`, because typer built it from its own vendored click. The
   check fails silently and every group looks like a leaf.

**Conclusion: duck-type, never `isinstance`.** A node is a group when
`.commands` is a dict. A parameter's kind comes from `.param_type_name`
(`"argument"` / `"option"`). This works across typer 0.26.8 and 0.27.1, and
across both click layouts.

**Version skew is already present**: toolchain typer 0.27.1, testee's repo venv
typer 0.26.8. The walker must tolerate it, because devman cannot pin the
interpreter it borrows.

### B.2 Two costs the walker cannot remove

1. **It imports the tool.** `import copyroom.cli` takes 222ms and executes the
   module tree beneath it — `release.check`, `session.dispatcher`,
   `workshop.golden`. devman runs another tool's import-time code to learn
   command names.
2. **It couples devman to typer's internals** across interpreters it does not
   control.

The import-free alternative was tested and rejected. Parsing `--help` works on
copyroom (19 nodes, correct) and returns **0 nodes** for gitman, docman, and
repoman, which render help in rich panels (`╭─ Commands ─╮`) rather than a plain
`Commands:` section. Two incompatible help formats already exist inside one
family. Script: `helpwalk.py`.

Both costs point the same way: the only party that can report a tool's facts
without approximating typer's resolution is **the tool itself**. That is
`003-cli-schema`, proposed as a family-contract change rather than a devman
feature. The walker ships first because it needs agreement from nobody.

---

## Spike C — is the stale-reference check real, or does it drown in noise?

**Question.** §5.1 promises devman turns skill/CLI drift from a risk into a
check. §15 leaned "names and sub-commands in step 2; flags later, behind
`--strict`". Nothing had measured the error rates.

### v1: names only — 100% false positives

The naive check (`refcheck.py`) extracted 41 references from real skills and
flagged 6 as stale. **All 6 were wrong:**

| Flagged | Reality |
|---|---|
| `copyroom layer add`, `copyroom layer list` | `layer` is a **leaf** command with a positional `action` argument ("add or list") |
| `gitman version bump` | `version` is a **leaf** with positional `action` ('bump') and `level` |

Family CLIs use positional pseudo-subcommands. A names-only check cannot tell
`gitman remote add` (a real group) from `gitman version bump` (a leaf plus a
value). It reports every one of them.

**This corrects §15's lean.** Flags can wait. **Arity and command kind cannot** —
they are required in step 2 just to make the *names* check usable.

### v2: parameter-aware — 0 false positives, all true positives caught

`refcheck2.py` adds three things: group-vs-leaf from spike B, positional arity,
and prefix handling (testee's skill writes every command as
`devenv shell testee verify`, which the v1 extractor missed entirely — its
reference count went 0 → 10).

**Part 1 — real skills. Every finding would be a false positive:**

| Tool | Skill files | References | Findings |
|---|---|---|---|
| copyroom | 3 | 18 | 0 |
| gitman | 1 | 43 | 0 |
| docman | 4 | 8 | 0 |
| testee | 1 | 10 | 0 |
| **total** | **9** | **79** | **0** |

**Part 2 — injected synthetic skill with known-bad references:**

| Injected | Detected | Class |
|---|---|---|
| `copyroom frobnicate` | yes | stale-command |
| `copyroom update --nonexistent-flag` | yes | unknown-option |
| `gitman remote nope` | yes | stale-subcommand |
| 4 valid lines mixed in | correctly ignored | — |

**Verdict: §5.1 is buildable, and it is the strongest idea in the charter.**
Build it parameter-aware from day one.

**Note on today's state:** the family is currently in sync — 79 references, zero
real drift. The check is a regression detector, not a cleanup tool. It has no
backlog to prove itself against, so its value shows up the first time a rename
lands.

---

## Spike D — can a whole-repo view detect trigger collisions?

**Question.** `repoman/docs/SKILLS.md` lists trigger-collision linting as an open
question, and must: no single component sees every skill at once.

**Method.** Parse `auto_trigger.keywords` from every `SKILL.md` in eight repos;
report any keyword claimed by two skills. Script: `triggers.py`.

**Result: 33 colliding keywords, present today, undetected.**

| Colliding keyword | Skills | Where |
|---|---|---|
| `adopt a repo` | `copyroom`, `copyroom-adopt` | all 8 repos |
| `personal layer` | `copyroom`, `copyroom-adopt` | all 8 repos |
| `templatize` | `copyroom`, `copyroom-adopt` | all 8 repos |
| `my-ai` | `copyroom`, `my-ai` | all 8 repos |
| `command not found` | `devenv-run-commands`, `devenv-troubleshoot` | shellij |

Every repo carrying the copyroom skill set inherits four collisions. shellij
adds a fifth from the devenv literacy pair.

**Verdict: the capability is real and cheap.** It needs a whole-set view. It
does **not** need ownership of the skills — reading them is enough.

---

## Spike E — does the mirror anchor survive ordinary work?

> **Run 2026-08-20** for `004-unified-charter`, not the re-charter. Script:
> `anchors.py`. Runs under pydantree's `devenv shell`; `src/` resolves through
> the `pydantree:venv-src-pth` task, so there is no `PYTHONPATH` to set.

**Question.** 004 §6.2 keys authored prose to `<relpath>::<dotted.symbol>`.
§15 step 1 made the orphan rate a gate on the whole mirror half, and §16
criterion 10 set the bar at "≥ 90% of prose re-attaches per commit, 0 lost".
Is the anchor stable enough to build on?

**Method.** Replay each repo's first-parent history. Extract every anchor at
every commit with pydantree-sitter (`M("module", ..., "function_definition")`
and the `class_definition` twin, dotted paths built by span containment). For
each consecutive pair, split the orphans by whether the code is still in the
tree, using a body hash. Merge commits are excluded from the rates: a
first-parent diff across a merge is a whole branch of work, not one step.

Scope: **public symbols under `src/`** — no tests, no `_private`. That is
where prose actually goes. Annotating everything measures churn in private
helpers nobody documents.

| Repo | Churn pairs | Orphans | Code deleted | **Anchor failures** | Recovered by `git -M` |
|---|---|---|---|---|---|
| pydantree | 13 | 926 | 584 | **342** | 334 |
| fsdantic | 1 | 1 | 1 | **0** | — |
| templateer_v2 | 1 | 20 | 20 | **0** | — |
| devman | 2 | 5 | 5 | **0** | — |

**Three of four repos produced zero anchor failures.** Every orphan was prose
on code that was genuinely deleted, which is correct behaviour, not breakage.
pydantree — three rewrites and three reverts in 162 commits — is the family's
worst case, and `git -M` recovers 334 of its 342 real failures.

### E.1 Criterion 10 measures the wrong thing

The raw per-pair rate looks alarming (pydantree: mean 66.1%, median 77.2%,
8/13 pairs under the bar) because it counts prose on **deleted** code as a
re-attachment failure. It cannot re-attach; the subject is gone.

Measured as *"of orphans whose code still exists, how many re-attach"*, the
bar clears at **~98%**.

### E.2 Quarantine does not heal

004 §6.3 quarantines orphaned prose instead of deleting it. The obvious hope
is that a revert or a re-landed branch re-attaches it later. It does not:

| Repo | Detach events | Ever re-attached |
|---|---|---|
| pydantree | 971 | 91 (9.4%) |
| fsdantic | 10 | 1 (10.0%) |
| templateer_v2 | 20 | 1 (5.0%) |
| devman | 58 | 0 (0.0%) |

Quarantine is a safety net for the user, not a recovery mechanism. Do not
claim otherwise.

### E.3 The name-only bridge is unambiguous where prose lives

Matching a quarantined anchor by its dotted symbol alone, ignoring the path:

| Scope | Cleared | **Ambiguous** |
|---|---|---|
| pydantree, public `src/` | 360 | **0** |
| pydantree, whole repo incl. tests | 688 | **978** |

Test functions share names across files (`test_reparse_incremental` lives in
two); public source symbols do not. The bridge works exactly where prose lives
and collapses exactly where it does not.

### E.4 Two predictions that were wrong

1. **Narrowing to public `src/` would improve the rate.** It made it worse.
   pydantree's 014 refactor renamed the public surface deliberately, so the
   prose target absorbed the full blast while private helpers stayed put.
2. **Reverts would re-attach quarantined prose.** See E.2 — 4–9%.

**Verdict: the anchor is sound; the criterion was not.** Build the rename
bridge in step 4 rather than deferring it to §17 — `git -M` for the file
case, name-only for the residue. A deliberate reorganization still detaches
most prose, and no bridge fixes that, because the subject was renamed on
purpose. That is a bulk re-attachment chore, not data loss.

---

## Spike F — can model-owned Python survive ordinary editing?

> **Run 2026-08-20** for `005-agent-factory`. Prototype and full evidence:
> `agent-factory-round-trip/`.

**Question.** Can nested typed units ingest and deterministically render a real
Python module, then preserve ordinary source edits and a cross-file move?

**Method.** Pydantree-sitter supplied declaration byte spans. Python's Abstract
Syntax Tree supplied qualified ownership. Pydantic records formed the disposable
unit store. Templateer rendered ordered typed sections. Ruff was the final
render step. A deterministic promotion test double exercised the convergence
guard.

| Measure | Result |
|---|---|
| Initial ingest to render | **100% byte identity** |
| Body, signature, docstring edits | **Pass**; one unit changed in each case |
| Add and delete | **Pass**; stable new unit and recoverable tombstone |
| Same-file method rename | **Pass**; durable identifier retained |
| Cross-file function move | **Pass**; one moved function, one added module, zero unrelated changed units |
| Unsupported import edit | **Pass**; rejected with the correct owner |
| Failed promotion | **Pass**; source and accepted store preserved; proposal written |
| Ruff stability | **Pass**; no post-render drift |

**Verdict: investigate one blocker.** The round-trip premise survived the
fixture, so do not retreat to skeleton-only generation yet. Templateer cannot
interpolate raw Python source under `language: python`; it escapes strings for
quoted positions. The spike used `language: text`, then Ruff. Define or reject
a validated raw-source-fragment contract before production work. The promotion
test double also does not prove semantic model promotion.

---

## What the spikes decide

| Question | Was | Now |
|---|---|---|
| devenv eval cache vs generated nix | open, "measure early" | **measured — not a blocker**; forces byte-deterministic emitters |
| how facts are introspected | open, leaned Typer-import | **out-of-process walker through `get_command()`**, duck-typed |
| testee reachable from the machine venv | assumed yes | **no** — the walker handles it |
| can the walker avoid click? | assumed yes, then built | **no** — proved by `parity.py`; `get_command()` is ground truth |
| is `--schema` needed? | dismissed as "a surface to negotiate" | **it is the right end state** — `003-cli-schema`, after the walker |
| reference-check depth | leaned names first, flags later | **arity is mandatory in step 2**; names alone are unusable |
| trigger-collision linting | open question | **works, and finds 33 real collisions** |
| is the mirror anchor stable enough? | gated the whole mirror half | **yes** — 0 failures in 3 of 4 repos; ~98% of live-code orphans recovered |
| does the anchor need a rename bridge? | 004 §17 open, "do not build before the measurement" | **yes, build it in step 4** — `git -M`, then name-only for the residue |

## What the spikes correct

| Claim | Corrected |
|---|---|
| §4.1/§4.2: "the `devenv-*` skills (11)" | there are **8**; 11 is the whole skill dir, including copyroom's 3 |
| §15: "every family member is a Typer CLI in the same machine venv" | testee is not, by deliberate design |
| §6: provenance on every emitted file | provenance must carry **no timestamp**, or spike A's free-rebuild property is lost |
| 004 §16 criterion 10: "≥ 90% re-attaches per commit" | the metric counts prose on **deleted** code as failure. Replaced by 10a/10b/10c — see 004 §16 |
| 004 §6.3: quarantined prose can re-attach later | it almost never does (4–9%). Quarantine prevents loss; it does not recover |

## What the spikes change about the plan

Spikes C and D both deliver value **without owning a single skill**. devman can
read skills it does not write, and report drift and collisions in them. That
turns the family-wide authorship takeover from a precondition into a conclusion
it can earn. See `../projects/002-agent-surface/CONCEPT.md`.
