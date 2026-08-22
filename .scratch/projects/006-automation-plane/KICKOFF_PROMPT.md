# Kickoff — investigations before planning devman

Read `CONCEPT.md` in this directory first. It is the charter. This document
lists what must be known before anyone plans or writes code, and how to find it
out.

**Your job is to answer questions, not to build the plane.** Every deliverable
here is a measurement, a scrap of throwaway configuration, or a written answer.
Nothing you produce needs to survive into the implementation.

---

## 0. Rules for this work

1. **Report what happened, not what should have happened.** A capability that is
   absent is a useful result. Write down the version you tested and the exact
   command you ran.
2. **Throwaway is fine.** Use `/tmp`, a scratch flake, two dummy repos. Do not
   build toward the real thing.
3. **Timebox each investigation.** If A1 takes more than a day, stop and report
   what you learned; the charter would rather change than wait.
4. **Do not fix the charter as you go.** Record what a finding contradicts and
   leave the edit to a later pass, so one person reconciles everything at once.
5. **Write results into `FINDINGS.md`** in this directory, one section per
   investigation ID, using the template in §5 below.

---

## 1. Investigation A — Dagu capability audit

**This is the highest-value work here, and it runs first.** The charter assumes
a Dagu feature set and never checked any of it. Four assumptions are
load-bearing; if any fails, the design changes shape before planning starts.

Establish the Dagu version under test and record it. If a capability exists only
in a newer version than nixpkgs ships, that is itself a finding.

### A1 — Per-DAG queues

**Claim (§7.1):** a DAG can name a queue, and the queue's concurrency is
configured centrally rather than in the DAG.

- Can a DAG declare a queue by name?
- Where is a queue's concurrency limit set — global config, or per DAG?
- What happens when a DAG names a queue that does not exist? Error, warn, or
  silent default?
- Is there a real serialization guarantee for a concurrency-1 queue?

**Why it matters:** queue names are devman's *only* global vocabulary. If they
cannot be bound this way, §7.1 has nothing left in it and the machine module has
no lever on concurrency.

### A2 — `workingDir` interpolation

**Claim (§7.2):** `workingDir: ${DEVMAN_PROJECT_DIR}` resolves at run time from
the environment, so one group file serves every repo that takes the group.

- Does Dagu interpolate environment variables in `workingDir`?
- In which fields generally — `workingDir`, `run`, `env`, elsewhere?
- Where can the variable be set per project: the DAG's own `env`, the projection,
  Dagu's service environment, a per-DAG parameter?
- Does the variable resolve at load time or at run time? **Load time is a
  different design** — one variable per Dagu instance, not per project.

**Why it matters:** this is what makes a workflow file portable and lets devman
avoid parsing workflows at all. If it fails, registration must rewrite each
projection, and §7.2's "devman never parses a workflow" becomes false. Report
what the minimum rewrite would be.

### A3 — Per-run log destination

**Claim (§9.2):** a run's logs, artifacts, and metadata can be written under the
triggering project's `.devman/.runs/`.

- Is the log directory configurable per DAG, or only per Dagu instance?
- Does it accept an interpolated path?
- What exactly does Dagu write, and what would a workflow have to write itself?
- Where does Dagu keep run history and status, and is that separable from logs?

**Why it matters:** if the log path is fixed machine-wide, §9.2's two-location
layout collapses and run output moves back beside the registry.

### A4 — DAG-to-DAG triggering

**Claim (§11):** a cross-repo workflow's steps trigger other projects' DAGs
rather than running commands.

- Can one DAG trigger another by name, and wait for it?
- Does the child run with its own `workingDir` and queue, or inherit the
  parent's? **Inheriting would break §11 entirely.**
- Does failure propagate to the parent?
- Can the parent read the child's result?

**Why it matters:** §11 is the whole reason for one central instance.

### A5 — Two questions worth asking while you are in there

- **Unknown top-level keys.** Does Dagu reject them? The charter removed
  `x-devman`, so nothing depends on this today, but knowing the answer tells us
  whether a sidecar would ever be needed.
- **Discovery.** How does Dagu find DAGs — a directory scan, a config list,
  an API call? §5.2 assumes registration can add a project's workflows without
  restarting the service. Verify that.

**Deliverable:** a capability table — assumption, supported yes/no, version,
the command that proved it, and what the charter must change if no.

---

## 2. Investigation B — one flake, two module interfaces

**Claim (§3.1, §12.3):** a NixOS module and a devenv module can live in one
flake at one version, without either constraining the other's nixpkgs.

Build the smallest honest pair:

- `nixosModules.default` that starts a Dagu service with one queue
- `modules/` that a repo imports through `devenv.yaml` and that writes a
  registry entry on shell entry
- both from **one** flake, imported into this machine and one test repo

Answer:

- Does the devenv module evaluate cleanly under the repo's
  `devenv-nixpkgs/rolling` while the NixOS module evaluates under the machine's
  nixpkgs?
- Does the devman package resolve in both, or does it need its own pin?
- What breaks first when the two disagree on a shared input?
- Is `modules/` the right import path? Confirm the `<input>/<subdir>` form
  against this repo's existing `imports: - shellij/modules`.

**Deliverable:** the scratch flake, plus a yes/no on whether the module must pin
its own nixpkgs. If yes, the plane ships two flakes and §3.1's anti-drift
argument weakens to a convention — say so plainly.

---

## 3. Investigation C — registration mechanics

**Claim (§5.2, §15.1):** registration runs in `enterShell`, guarded by a content
hash, and it is the *only* way into the registry (criterion 17).

- Does devenv's `enterShell` run on every entry, including `devenv shell -- cmd`
  and direnv-driven entry? Anything that skips it means a repo silently misses
  registration.
- How long does a hash comparison plus a no-op add to shell entry? It must not
  spoil Spike A's 0.16s (criterion 7).
- Is `$DEVENV_STATE` — or any devenv-provided state path — available in
  `enterShell`? Not needed for the token any more, but it tells us what devenv
  exposes.
- Can the module add `.devman/.runs/` to the repo's ignore rules without
  clobbering a hand-maintained `.gitignore`?
- **Identity collisions:** two repos declaring `project = "test"`. What should
  registration do — refuse the second, or replace? Recommend one.
- **Stale entries:** a repo is deleted from disk without unregistering. There is
  no `devman unregister`. How does the registry notice, and is that `doctor`'s
  job?

**Deliverable:** written answers, plus a timing number for the guarded no-op.

---

## 4. Investigation D — the smaller open questions

Each of these has a lean recorded in `CONCEPT.md` §16. Confirm or overturn it;
a one-paragraph answer each is enough.

| ID | Question | Recorded lean |
|---|---|---|
| D1 | Does anything else claim `~/.local/share/devman/`? | nothing does |
| D2 | Do ecosystem groups ship in this flake or separately? | in-repo until a third party wants to publish one |
| D3 | Should the machine module manage a Dagu it did not install? | no — own the service, document the conflict |
| D4 | Which ecosystem groups first? | Python and Nix |
| D5 | Retention for `.devman/.runs/`? | 7 days for logs and artifacts, keep `metadata.json` |

Two more that the charter has not written down, and should:

- **D6 — the `.devman/` collision.** §15.2 says registration must detect a
  `.devman/` of an older shape and refuse it. Survey the repos you actually have:
  how many carry one, what shape is it, and what is the minimum test that
  distinguishes old from new?
- **D7 — watchexec wiring.** §8 assumes a watcher triggers a workflow. What
  actually invokes Dagu — a CLI call, an HTTP endpoint, a file drop? Is one
  watcher per repo, or one watching many? This decides whether triggers are
  plane machinery or group content, which §8 currently leaves open.

---

## 5. Reporting

Write `FINDINGS.md` in this directory. One section per ID, in this shape:

```markdown
## A2 — workingDir interpolation

**Answer:** yes, at run time, from the DAG's own env block.
**Tested:** dagu 1.x.y, nixpkgs <rev>, on <date>.
**Command:** <the exact thing you ran>
**Evidence:** <output, trimmed to the part that proves it>
**Charter impact:** none. §7.2 stands as written.
```

`Charter impact` is the field that matters. Use one of:

- **none** — the charter stands
- **changes §N** — name the section and state the change in one sentence
- **kills §N** — the design must be rethought; say what you would do instead

---

## 6. What "done" looks like

Planning may start when:

1. Every A-series assumption has a yes/no with evidence.
2. Investigation B has a yes/no on the single-flake premise.
3. Investigation C has answers, and a timing number for the registration no-op.
4. D1–D7 have leans confirmed or overturned.
5. `FINDINGS.md` lists every `changes §N` and `kills §N` in one place.

**One investigation is deliberately absent.** §12.4 — whether whole-file
shadowing is coarse enough to live with — cannot be answered before there are
real workflows to override. It is measured at stage 2, across five repos, and it
is not a blocker for planning.

---

## 7. The single most important instruction

If Investigation A returns a no, **stop and report before doing B, C, or D.**
A1 through A4 decide the shape of the workflow file, the layout on disk, and
whether devman parses workflows at all. Every later answer is conditional on
them.

The charter is a proposal, not a specification. It is cheaper to change it now
than to plan around something Dagu does not do.
