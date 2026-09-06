# Kickoff — Investigation A, the Dagu capability audit

## Your task

Run Investigation A from `KICKOFF_PROMPT.md` §1. Answer A1 through A5 with
evidence, and write the answers to `FINDINGS.md` in this directory.

**You are answering questions, not building the plane.** Every deliverable is a
measurement or a written answer. Nothing you produce needs to survive into the
implementation. Use `/tmp` and throwaway DAGs.

---

## 1. Read these first

Read in this order. Do not skip the first two.

1. `.scratch/projects/006-automation-plane/CONCEPT.md` — the charter. It is a
   proposal, not a specification.
2. `.scratch/projects/006-automation-plane/KICKOFF_PROMPT.md` — §0 for the
   rules, §1 for A1–A5, §5 for the reporting shape, §7 for the stop rule.
3. `.scratch/projects/006-automation-plane/FINDINGS.md` — if it exists, append.
   If it does not, create it.

---

## 2. The environment is already built — do not rebuild it

A previous session packaged Dagu and wired it into this repo. Use it as it
stands.

| Fact | Value |
|---|---|
| Dagu version under test | **2.15.0** |
| Upstream | `https://github.com/dagucloud/dagu` (`dagu-org/dagu` redirects here) |
| Package expression | `nix/dagu.nix` — the release tarball, pinned to tag `v2.15.0` |
| Flake outputs | `packages.<system>.dagu`, `.default`, `overlays.default` |
| devenv wiring | `devenv.nix` — Dagu on `PATH`, plus `processes.dagu` |
| `DAGU_HOME` | `<repo>/.devenv/state/dagu` (set by `devenv.nix`) |
| DAG directory | `<repo>/.devenv/state/dagu/dags/` |
| Web UI | `http://127.0.0.1:8080` |

`DAGU_HOME` is the single knob. Dagu derives `dags/`, `logs/`, `data/`, and
`suspend/` from it. Upstream's own example DAGs are already in `dags/` and are
useful references.

### Driving it

```bash
devenv up -d                       # start the Dagu process
devenv processes list              # confirm it is ready
devenv shell -- dagu start <name>  # run one DAG, print the result tree
devenv shell -- dagu --help        # the full command set
```

`dagu start-all` runs the scheduler, the coordinator, and the web UI in one
process. Restart it after a config change.

**Commit and push at regular intervals.** Work on the current branch. Commit
each finding as you confirm it, rather than saving one commit for the end — an
investigation that loses a day's evidence to a bad shell command has to run
twice. Push after each commit.

`.devenv*` is git-ignored, so DAGs you drop in `dags/` never dirty the tree.
Keep throwaway experiments in `/tmp` so they stay out of the history.

---

## 3. Where the answers probably live

Read the source before you guess. Clone it fresh — `/tmp/dagu-src` may be gone:

```bash
git clone --depth 1 --branch v2.15.0 https://github.com/dagu-org/dagu.git /tmp/dagu-src
```

High-value files, in the order they will help:

| Path | Why |
|---|---|
| `internal/cmn/schema/dag.schema.json` | 270k of DAG schema. Every legal field, with descriptions. Answers much of A1, A2, A4, A5 by reading. |
| `internal/cmn/schema/config.schema.json` | 49k of instance config. Queue definitions, `log_dir`, `artifact_dir`, `data_dir`, `dag_discovery`. Answers A1, A3, A5. |
| `skills/dagu/SKILL.md` + `skills/dagu/references/*.md` | Upstream ships an agent skill. `cli.md`, `steptypes.md`, `file-dependencies.md`, `build.md`, `context.md`. |
| `llms.txt` | 86k of documentation in one file. |
| `internal/cmd/*.go` | Command behaviour when the schema is ambiguous. |

**Read the schema, then prove it by running a DAG.** A schema field is a claim;
a run is evidence. §5 of `KICKOFF_PROMPT.md` asks for the command and its
output, so every answer needs both.

For A2 and A3, make two throwaway project directories under `/tmp` and point
one DAG at both. That is exactly the §12.1 measurement.

---

## 4. What to answer

Restated from `KICKOFF_PROMPT.md` §1. Go there for the full framing and the
"why it matters" for each.

**A1 — per-DAG queues.** Can a DAG name a queue? Where is the queue's
concurrency limit set — global config or per DAG? What happens when a DAG names
a queue that does not exist: error, warn, or silent default? Does a
concurrency-1 queue really serialize?

**A2 — `workingDir` interpolation.** Does Dagu interpolate environment
variables in `workingDir`? In which other fields? Where can the variable be set
per project? **Does it resolve at load time or at run time?** Load time is a
different design — one variable per Dagu instance, not per project.

**A3 — per-run log destination.** Is the log directory configurable per DAG, or
only per instance? Does it accept an interpolated path? What does Dagu write,
and what would a workflow have to write itself? Is run history separable from
logs?

**A4 — DAG-to-DAG triggering.** Can one DAG trigger another by name and wait?
Does the child run with its own `workingDir` and queue, or inherit the parent's?
**Inheriting breaks §11 entirely.** Does failure propagate? Can the parent read
the child's result?

**A5 — two smaller questions.** Does Dagu reject unknown top-level keys? How
does Dagu discover DAGs — directory scan, config list, or API call — and can
registration add a project's workflows without restarting the service?

**Deliverable:** a capability table — assumption, supported yes/no, version, the
command that proved it, and what the charter must change if no.

---

## 5. Findings already established — carry these into `FINDINGS.md`

Record these as sections. They are measured, not assumed.

**Dagu is absent from nixpkgs at every version.** Verified against the machine's
pinned nixpkgs and `github:NixOS/nixpkgs/nixos-unstable` on 2026-08-21:

```
$ nix eval --raw github:NixOS/nixpkgs/nixos-unstable#dagu.version
error: flake '...' does not provide attribute '...dagu.version'
```

*Charter impact:* changes §4. The plane must carry its own Dagu package. It now
does — `nix/dagu.nix`, one expression that both the devenv module and the
future NixOS module call, which is §3.1 applied to the one package both
interfaces need.

**Dagu 2.15.0 cannot be built from source on this machine today.** Two
independent blockers: `go.mod` declares `go 1.27.0` and nixpkgs ships 1.26.4;
and the web UI is a pnpm/webpack build whose output is not committed
(`internal/service/frontend/assets/` holds only a `.gitkeep` at the tag). The
package installs the upstream release tarball instead, pinned to the tag with
sha256 sums taken from the release's own `checksums.txt`.

*Charter impact:* none yet. No feature is lost — `.goreleaser.yaml` builds
`./cmd` with `CGO_ENABLED=0`, no build tags, and no edition gating, and the
release binary serves the full 1 MB web UI bundle. Note the constraint so a
later pass can revisit when nixpkgs has Go 1.27.

---

## 6. How to report

Write `FINDINGS.md` in this directory. One section per ID:

```markdown
## A2 — workingDir interpolation

**Answer:** yes, at run time, from the DAG's own env block.
**Tested:** dagu 2.15.0, on <date>.
**Command:** <the exact thing you ran>
**Evidence:** <output, trimmed to the part that proves it>
**Charter impact:** none. §7.2 stands as written.
```

`Charter impact` is the field that matters. Use one of:

- **none** — the charter stands
- **changes §N** — name the section, state the change in one sentence
- **kills §N** — the design must be rethought; say what you would do instead

End the file with one list of every `changes §N` and `kills §N`, so the
reconciliation pass has a single place to look.

---

## 7. Rules

1. **Report what happened, not what should have happened.** An absent
   capability is a useful result. Record the version and the exact command.
2. **Throwaway is fine.** `/tmp`, scratch DAGs, two dummy project directories.
   Do not build toward the real thing.
3. **Timebox each investigation.** If A1 takes more than a day, stop and report
   what you learned. The charter would rather change than wait.
4. **Do not edit `CONCEPT.md`.** Record what a finding contradicts and leave the
   edit to a later pass, so one person reconciles everything at once.
5. **Stop at the end of A.** Do not start Investigation B, C, or D. A1–A4 decide
   the shape of the workflow file, the layout on disk, and whether devman parses
   workflows at all. Every later answer is conditional on them.

**If any of A1–A4 returns a no, stop and report immediately.** Do not work
around it. A "no" is the most valuable result this investigation can produce,
because it is cheaper to change the charter now than to plan around something
Dagu does not do.
