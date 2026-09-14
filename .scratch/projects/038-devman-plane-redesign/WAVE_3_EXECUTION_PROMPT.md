# Project 038 Wave 3 — execution prompt

Copy the text below into a fresh session.

Written 2026-09-14, after the Wave 3 investigation
(`WAVE_3_INVESTIGATION_REPORT.md`). It supersedes Wave 3 of
`NEXT_SESSION_PROMPT.md`, which is stale in four measured ways.

---

You are executing Wave 3 of Project 038, the Devman machine-plane redesign.

**This is execution, not investigation.** The investigation is done and its
report is in the repository. Almost every question is already decided — some in
`IMPLEMENTATION_GUIDE.md`, some by the operator in Stage 37, some by the Wave 3
investigation. **Do not re-litigate a decided question.** The last session's
main error was rebuilding option matrices for choices the records had already
made. If you find yourself weighing an option, first grep the records to check
whether someone already weighed it.

## The one open decision, and the one repair

**Open decision — the seven orphan commits.** `gitman`, `image-gen-pipeline`,
`llgym`, `loci-core`, `nix-paseo`, `pydantree` and `pyjutsu` each sit on a
detached commit titled `chore: join the devman machine plane` with **zero
containing refs** and no copy on `origin`. The operator's decision is: **abandon
them and rely on the published Stage 37 branch** — gated on you first confirming
the branch carries the same manifest content. If it does not, stop and report.

**Repair with no alternative — the staged-empty manifests.** Nineteen
repositories carry `.devman/project.toml` staged as the empty blob
`e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`. A commit in any of them deletes the
manifest, which is the registration. **This is item 1 and it blocks every other
git operation.**

Everything else in this prompt is execution against decisions already recorded.

---

## Read first, in this order

1. `CLAUDE.md` — the ten properties. Rules 1, 2, 4 and 10 settle most arguments.
2. `.scratch/projects/038-devman-plane-redesign/WAVE_3_INVESTIGATION_REPORT.md`
   — the whole thing. It holds every measurement this prompt cites.
3. `IMPLEMENTATION_GUIDE.md` §5 — the reload boundary, and the nine VM
   assertions §5.2 requires.
4. `.scratch/projects/025-the-link-plane/CONCEPT.md` Stage 3 items 4 and 5 —
   **read them knowing item 4 is now false.** See R8 below.

Do **not** re-read `IMPLEMENTATION_LOG.md` end to end. Read the stage you are
about to amend.

---

## Five records that are wrong. Correct them before you rely on them.

| # | The false statement | Where | The truth |
|---|---|---|---|
| **R1** | "Dagu's own scheduled enqueues, **and the watcher's**, do not pass through `devman run`'s Python entry point" | `nix/nixos-module.nix:266-271`; `IMPLEMENTATION_LOG.md:379-381` | `src/devman/watch.py:612` calls `run.trigger`, whose first statement is the `reload.pending` refusal. **The watcher is gated.** Proven by experiment. `git log -S` dates the call to `373a8b6` (2026-09-04) and the comment denying it to `5f32817` (2026-09-12) |
| **R3** | Stage 37: "Published consumer commits are …" | `IMPLEMENTATION_LOG.md:1790-1793` | Published **to a branch**. For all ten repositories `git merge-base --is-ancestor <commit> origin/main` returns NO, and `origin/main:.devman/project.toml` is absent |
| **R7** | "`devman link status --all` reads the compatibility registry" | `NEXT_SESSION_PROMPT.md:199-210` (item H) | Removed in `976d14e`. Item H is closed |
| **R8** | "the mechanism for scheduled runs was never designed, only deferred" | `025/CONCEPT.md:876-888` (Stage 3 item 4) | The mechanism exists in Dagu 2.15.0. See "The `${DAG_NAME}` finding" below |
| **R10** | "Caught by the VM test once `reload.pending` made a stuck loop visible" | `nix/nixos-module.nix:324` | `grep -rn reload nix/tests/` returns nothing. **The VM test has no reload subtest.** Coverage is three unit tests that write markers by hand |

Also: `WAVE_3_INVESTIGATION_PROMPT.md:85-86` cites `LINK_PLANE_A_TO_C_GUIDE.md`
§13. That file ends at §11.

Rule 2 applies. A change that contradicts a charter changes that document in the
same commit.

---

## Ground truth, measured 2026-09-14 14:00–14:25 EDT

**Re-measure before you rely on any of it. Do not copy these numbers into a
report.**

```text
devman              main @ 394f13b, working tree clean
plane               generations/2, 45 projects, 143 DAG files
DAG digest          5a06aca3a93a8bd8030a8becc42dc57f0560452b04940518b31f8e7f696fe2b9
dagu ls             144 lines
dagu version        2.15.0, up 42 h, `dagu start-all`
reload markers      none — reload has never completed on this machine
manifests on disk   48 checkouts; 45 in the plane
doctor              exit 1, four known findings
```

The four known findings: `flora-037-part-e:devenv.local.nix: create`; dirty and
unpinned `vendomat`; dirty and unpinned `repoman`; the unpinned `git+file:`
advice. **Exit 1 is a finding result, not a failure.**

### The doctor command in older prompts inspects the wrong plane

Bare `devman doctor` uses `DEFAULT_REGISTRY` (`~/.local/share/devman`, the
compatibility registry) and reports `mode compatibility`. Always use:

```bash
cd /tmp
env -u PYTHONPATH -u PYTHONHOME devman \
  --registry "$HOME/.local/state/vendomat/devman/active" \
  --state "$HOME/.local/state/devman" \
  --dagu-home "$HOME/.local/share/dagu" doctor
```

**Even that sees only 4 of 45 projects**, because `doctor` enumerates from
`stateDir/projects/`. It validates 16 of 143 files. Item 5 below fixes this, and
until it lands, "doctor gained no new finding" is a weak gate.

---

## Measurements you do not need to repeat

| Fact | Value | How it was measured |
|---|---|---|
| Run durations | n=1306: p50 2 s, p90 22 s, p95 29 s, p99 61 s, **max 279 s**. Zero over 300 s | parsed `status.jsonl` under `~/.local/share/dagu/data/dag-runs/` |
| Scheduled runs (`triggerType=1`) | n=550, **max 20 s**; `maintain` max 5 s over 551 runs | same |
| Scheduled workload | 46 workflow files carry a schedule; **45 fire at 00:05 daily** | `grep -rl '^schedule:'` in the active generation |
| Scheduler bypasses the queue | 4 DAGs on a `max_concurrency: 1` queue all started within **15 ms** and ran concurrently for 10 s. The enqueued path serialised | isolated Dagu home, disposable |
| `${DAG_NAME}` expands in DAG-level `env:` | Yes, including `${DAG_NAME%.*}`. **No command substitution**, and no interpolation in `dotenv:` paths | isolated scheduler |
| Two links to one source | Give two distinct DAGs, named from the **link** basename | isolated Dagu home |
| Subdirectories do not namespace | `dags/a/check.yaml` and `dags/b/check.yaml` collide and Dagu refuses **both** | isolated Dagu home |
| Path convention | 45 of 45 active projects satisfy `<projectsRoot>/<project>` | compared each `metadata.json` `path` |

### Dagu 2.15.0 capability verdicts — closed, do not re-survey

No global pause. No drain verb. No runtime queue toggle. Per-DAG suspend exists
(`suspend_flags_dir`) but **drops** runs rather than deferring, and is API/UI
only. DAG-level `preconditions` also drop. `dagu ps` reads a heartbeat process
store with a 90 s stale threshold and **is not a lock**.

### The `${DAG_NAME}` finding — for the record correction, not for this wave

One shared source, linked as `projA.check` and `loci.nvim.check`, with:

```yaml
env:
  - DEVMAN_PROJECT_DIR: "/tmp/inv-dagu2/${DAG_NAME%.*}"
working_dir: ${DEVMAN_PROJECT_DIR}
```

produced two scheduled runs in two correct directories. **Use `%`, not `%%`**:
on `loci.nvim.check`, greedy `%%` gives `loci` (wrong) and lazy `%` gives
`loci.nvim` (right), mirroring `registry.py`'s `rsplit` rule.

**Render-to-link is NOT this wave's work.** Correct R8 in `025/CONCEPT.md`, and
leave the implementation to its own wave behind the VM prototype.

---

## The work, in order. One commit each. Do not batch.

### 1. Repair the nineteen staged-empty manifests — before any other git action

Affected: `argentic`, `eventic`, `flora-core`, `flora-qc`, `gitman`,
`image-gen-pipeline`, `llgym`, `loci-core`, `loci.nvim`, `nix-nvim`,
`nix-paseo`, `poddantic`, `pydantree`, `pyjutsu`, `pyllij`, `pytuin`,
`templateer_v2`, `testee`, `vendomat`.

Per repository, verify first, then repair, then verify again:

```bash
git -C <repo> ls-files -s .devman/project.toml        # expect the empty blob e69de29…
git -C <repo> diff --cached --stat -- .devman/project.toml
git -C <repo> restore --staged .devman/project.toml
git -C <repo> diff --cached --stat -- .devman/project.toml   # expect empty
git -C <repo> cat-file -p HEAD:.devman/project.toml          # expect four lines
test -s <repo>/.devman/project.toml                          # working tree intact
```

**Do not run a blind loop.** Check each repository's output. Seven of them sit
on orphan HEADs, so `restore --staged` restores from that orphan commit — which
is correct and safe, but confirm it rather than assuming.

`copyroom`, `docman` and `mypi-agent` are a **different** case: their manifest
is a staged add with no `HEAD` version. Leave them alone; item 9 resolves them.

Do not repair unrelated dirty state in any of these repositories.

### 2. Fix the investigation report

`WAVE_3_INVESTIGATION_REPORT.md` is untracked. Amend before committing it:

- **§6** — the queue row overstated the case. Dagu has a queue system, enabled
  here with six queues. The true statements are the two independent ones: a
  scheduled run never enters the queue, and there is no runtime way to close a
  queue. Add the measured bypass experiment.
- **§7.1 A3** — same correction.
- **§9** — recut from seven operator decisions to **one** (the orphan commits).
  Move O3, O4, O5, O6 and O7 into the implementation sequence, each citing the
  record that already decided it.

### 3. Correct the five records (R1, R3, R7, R8, R10)

Each in the file that holds it, with the measurement that disproves it. R1 also
means the Stage 10 log entry gains a correction note rather than an edit —
`REMOVAL_SEQUENCE_PROMPT.md:344-346` says record failed attempts rather than
erasing them.

### 4. Fix the two reload-script defects

Both in `nix/nixos-module.nix`.

- **The timeout branch never removes `reload.pending`** (`:328-334` versus
  `:340`). After a blocked reload, `run.trigger` refuses **every** manual and
  watcher-fired run on the machine, indefinitely — while `doctor`'s `!!` line
  says "the previous generation is still serving runs", which reads as healthy.
  On timeout, remove `pending` and keep `blocked`. The old generation is still
  serving, so refusing new work earns nothing.
- **The drain loop cannot terminate when Dagu is down.** `dagu ps 2>/dev/null ||
  true` yields an empty string, which is `!= "No running processes"`, so the
  loop runs the full timeout and then blocks — although there are definitionally
  no active runs. Treat a non-zero `dagu ps` exit **and** a stopped
  `dagu.service` as drained.

Also make `check_reload` in `src/devman/doctor.py:1360-1391` report both markers
rather than returning early on `blocked`.

### 5. Make `doctor` see the whole plane

In plane mode, enumerate projects from the active generation rather than from
`stateDir/projects/`. All 45 carry a `metadata.json` inside the generation.
Expect `check_load` to go from 16 to 143 `dagu validate` calls. **Measure the
cost**: `AGENTS_GUIDE.md` §3 records 87.6 ms per file, so budget about 12.5 s.
If it passes 30 s, the answer is a `--project` scope, not a heavier queue.

Every later gate depends on this landing.

### 6. Add the watcher unit test

`tests/unit/test_watch.py` currently has no reload coverage. Add a test proving
the dispatcher refuses under `reload.pending`. The investigation's experiment is
the specification: with the marker present, `watch.dispatch` prints `refusing to
enqueue …  a plane reload has been pending since …` and returns 1.

Also make a reload refusal distinguishable in `fired.jsonl`. Today both a reload
refusal and a resolution refusal record `refused (1)`, and `check_watcher` never
treats a refusal as a finding — so a machine with a stuck marker shows
`watcher ok` while every save is dropped.

### 7. Add the VM reload subtest

`nix/tests/dagu-service.nix` has none. `IMPLEMENTATION_GUIDE.md` §5.2 names nine
assertions; add them, plus:

- the timeout writes `reload.blocked`, does not restart Dagu, and **leaves the
  plane usable for manual runs** (item 4);
- a reload while `dagu.service` is stopped completes promptly (item 4);
- a failed `try-restart` is detected — today `set -eu` kills the script before
  `rm -f pending`, leaving a state indistinguishable from waiting.

### 8. Raise `reloadMaxWaitSec` to 600 s

`IMPLEMENTATION_GUIDE.md` §5.1 already instructs: "Choose the limit from
observed run durations and record the measurement." The measurement now exists —
max 279 s over 1306 runs. The current 300 s exceeds the observed maximum by 8 %.
Cite the measurement in the option description, and replace the "**a stated
bound, not a measurement**" sentence at `nix/nixos-module.nix:480-482`.

### 9. Close the scheduled-run race as an accepted limitation

**Do not build a gate.** `IMPLEMENTATION_GUIDE.md` §5.3 item 4 already sanctions
"remain covered by the accepted Dagu restart policy". What §5.3 demands and
nobody supplied is the second half: "state that limitation in the concept and
**measure the risk**."

Write the measurement into `CONCEPT.md`: scheduled runs max 20 s over 550
records, `maintain` max 5 s over 551, 45 DAGs firing simultaneously at 00:05
daily, and Dagu 2.15.0 offering no primitive that defers rather than drops. Flip
requirement 7 from `blocking gap` to `accepted limitation`.

Record the future option without building it: a scheduled parent whose single
step is `devman run <workflow>` inherits the existing marker gate for free,
because it passes `run.trigger`. `groups/agent/` already uses that shape and
says why.

### 10. Split the authored and generated roots

The overlay collision, re-verified in the current tree after Wave 2G moved it
out of `project.py`:

- **read** `overlay_root/projects/<p>/workflows/*.yaml` — `reconcile.py:283-292`
- **write** `registry/projects/<p>/workflows/<name>.yaml` — `:453-454`, `:486-489`
- **delete** any published file absent from the render — `:479-484`

At risk: five tracked, hand-authored files under
`~/.config/devman/projects/devman/workflows/` — `agent-review.yaml`,
`bench-entry.yaml`, `gitman-commit-message.yaml`, `plane-report.yaml`,
`stack-validate.yaml`. Only `devman` has such a directory.

`025/CONCEPT.md` gated the fix on §6.2a because render-to-link looked like the
only escape. **Splitting the roots was never considered — it is absent from the
record, not rejected by it.** It removes the collision without any new
mechanism.

Write the design into the log first, with the failure it avoids. Then change one
thing. `registryDir` does **not** move in this wave — `025/CONCEPT.md` Stage 3
item 5 fixes that order and it still holds.

### 11. Land the ten Stage 37 branches

First, the gate for the open decision:

```bash
# For each of the seven, compare the published branch against the orphan HEAD
git -C <repo> cat-file -p origin/038-devman-consumer-<name>:.devman/project.toml
git -C <repo> cat-file -p HEAD:.devman/project.toml
```

If the manifests match, abandon the orphan. If any differ, **stop and report**.

Then land all ten on `main`, one PR each: `copyroom`, `docman`, `mypi-agent`,
`gitman`, `image-gen-pipeline`, `llgym`, `loci-core`, `nix-paseo`, `pydantree`,
`pyjutsu`. The approved commits are named at `IMPLEMENTATION_LOG.md:1773-1793`.

`AGENTS.md` rule 10 is why this matters: today a fresh clone of `main` in any of
the ten carries no manifest, so it does not register.

**Never force-push. Never move a branch.** Several of these checkouts are dirty
with unrelated changes — do not stage them.

### 12. Archive `flora-037-part-e`, and review `fleetman`

`flora-037-part-e` is an orphaned git worktree at
`flora/.worktrees/037-part-e-flora` that `git -C flora worktree list` does not
know about. It is the sole cause of doctor finding 1. `fleetman` has moved to
`Documents/Projects/.archive/fleetman` and its share-registry entry still points
there.

`CONSUMER_MIGRATION_GUIDE.md` §6.3 says "These are separate cleanup work. Do not
delete them because the active plane has no matching project." Follow the
pattern Stage 41 used for `allium-env`: **move content into the repository
before removing the overlay.**

### 13. Answer the `.dag.index` question, then rebuild a generation

**Gate before any activation.** `~/.local/state/vendomat/devman/active/dags/.dag.index`
caches **fully resolved** paths, all pinned to `generations/2`. Whether
re-pointing `active → generations/N` invalidates that cache is unproven, and the
entire generation-swap design rests on it. Answer it in a VM or an isolated Dagu
home first.

Then rebuild and activate. The plane has not been rebuilt since 2026-09-12, so
it is two days behind the fleet: 48 manifest-backed checkouts on disk, 45 in the
generation. After items 11 and 12 the count should reach 48.

**`vendomat` and `repoman` are dirty and unpinned** (doctor findings 2 and 3).
An unpinned `git+file:` input resolves to the working tree, not a commit.
Consider whether to pin before activating.

### 14. Remove the literal identity fallback

`grep -rn 'devman\.project[[:space:]]*=' --include='*.nix'` over
`Documents/Projects` returns **zero hits**. The only live users of
`_legacy_identities()` are `forgelab` and `lodestar`, both in the archive set.

State the trade explicitly: `resolve_project_identity` calls
`_legacy_identities()` **unconditionally**, even when a manifest exists, because
the manifest/Nix drift refusal needs both (`identity.py:260-271`). Removing the
fallback removes that refusal too.

### 15. Documentation sweep

`AGENTS.md` property 6, `AGENTS_GUIDE.md` §3 and §4, `README.md`, `USER.md`, and
the `025/CONCEPT.md` amendments from item 3. Every new line cites its
measurement, in the stage-log shape.

---

## Explicitly deferred. Do not start these.

| Deferred | Why |
|---|---|
| Render-to-link (§6.2a) | The mechanism is proven but the safety property is not. A shared source resolving to a missing directory currently reports **`Succeeded`**. Needs its own wave, behind a VM prototype and a refusal |
| `registryDir` → `~/.config/devman` | `025/CONCEPT.md` Stage 3 item 5 gates it on a VM-verified Stage 4 |
| §11 item 5, compatibility mode | Still the documented rollback. `devman`'s own self-adoption must leave `project apply` first |
| A `<projectsRoot>/<project>` machine contract | Only needed under render-to-link |

---

## Verify, in layers, after every item

```sh
devenv tasks run -v base:check
devenv tasks run -v base:unit
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
devenv shell -- nix build .#packages.x86_64-linux.devman-link --no-link
```

Then the plane, from `/tmp`, with the full flag set shown above. `devman doctor`
must exit 0, or exit 1 with only the known findings, before a change to
`modules/`, `groups/`, `nix/` or `src/devman/` is committed.

A removal that drops the test count must say which tests went and why.

### The canary, after every removal

```sh
cd /tmp
VM_ROOT=/home/andrew/Documents/Projects/vendomat
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
  status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman \
  link status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
```

Both must return 0 with five `ok` states and the central configuration path.

### The fleet sweep, in the shape the hook actually calls

Use an explicit `--project`. Stage 16 swept without it, three repositories
refused, and that predicted nothing about shell entry.

```sh
cd /tmp
for d in "$HOME/.config/devman/projects"/*/; do
  p=$(basename "$d"); r="/home/andrew/Documents/Projects/$p"
  [ -d "$r" ] || continue
  env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
    status --project "$p" --root "$r" --overlay "$HOME/.config/devman" >/dev/null 2>&1
  printf '%s %s\n' "$?" "$p"
done | sort | uniq -c -w2
```

A new refusal is a regression. Diagnose it before removing anything.

---

## Traps, already measured. Do not re-learn them.

1. **`base:test` reads the git tree.** `nix flake check`'s `python-tests`
   fileset is `./src ./tests ./pyproject.toml ./groups ./nix/nixos-module.nix`.
   An unstaged new file fails hermetically while `base:unit` passes. Stage 17
   hit exactly this.
2. **`flake.nix`'s `shell-variable-unset`** requires every new `devman_*=`
   assignment in `modules/devenv.nix` to appear in the `unset` block, in the
   same commit. `hook-path-refusal` cuts a refusal block out by literal path.
3. **`tests/unit/test_cli.py`** asserts the parser and `handler()` name the same
   commands. Removing a command from one side must remove it from both.
4. **Check `git status --short` for `D `, `DA` or `AD` before committing
   anywhere.** Nineteen repositories carry this today; item 1 is the repair.
5. **Measure the live system from `/tmp`**, not from a repository shell, and
   clear both Python path variables.
6. **direnv can repair a link before your explicit shell entry runs**, which
   made Stage 16 misread a measurement.

---

## Stop conditions

Stop and ask when any of these is true.

1. A `git status` shows `D `, `DA` or `AD` for `.devman/project.toml` in a
   repository you are about to commit in.
2. A Stage 37 branch's manifest differs from its orphan HEAD's (item 11 gate).
3. `devman doctor` gains a finding outside the four known ones.
4. The active pointer, project count, DAG count or digest changes without an
   intended activation.
5. A change would make `overlayDir` and `registryDir` share a root before item
   10 lands.
6. An activation is proposed before the `.dag.index` question is answered.
7. Compatibility mode, compatibility registry writes or a consumer pin would be
   removed without its gate passing.
8. A migration commit has no clear destination branch.
9. A generated registry or plane file appears to need hand editing.

---

## How to work

- **Simplified Technical English.** Short sentences, active voice, one word for
  one meaning, no filler. `.agents/skills/writing/SKILL.md`.
- **Land each item on its own branch, then open a PR against `main`.** A direct
  push to `main` is refused. Merge with a merge commit; the project record cites
  commit SHAs, so do not squash.
- **No `Co-Authored-By` trailers**, and no agent attribution in PR bodies.
- **Record every item in `IMPLEMENTATION_LOG.md`** as its own stage section, in
  the fixed shape: the answer, the versions, the exact command, the evidence,
  the charter impact, and what the entry left on the machine. Put artifacts
  under `.scratch/projects/038-devman-plane-redesign/artifacts/<TS>-<slug>/`.
- **Record failed attempts rather than erasing them.** Stage 16's `lib` finding
  and Stage 17's three build failures are the model.
- **Prefer a loud refusal to a silent default.**

## Report at the end

Files changed per repository; tests and exact results; the live active
generation, DAG count and digest; every doctor finding; commits and pushed
branches; which items closed and which remain; and any blocker needing operator
input.

Do not mark Project 038 complete until every §11 item has its own recorded
evidence.
