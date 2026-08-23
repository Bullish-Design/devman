# STAGE 6 — what was measured while putting the schedule in the file

`STAGE_1_LOG.md` holds what stage 1 found while building the two modules,
`STAGE_2_LOG.md` what stage 2 found while turning the plane on, `STAGE_3_LOG.md`
what stage 3 found while making it react, `STAGE_4_LOG.md` what stage 4 found
while giving it work worth doing, and `STAGE_5_LOG.md` what stage 5 found while
moving the repositories underneath it. This holds stage 6, in the same shape:
the answer, the versions, the exact command, the evidence, and the charter
impact.

**Environment for every entry below**, unless it says otherwise:

| Fact | Value |
|---|---|
| Host | NixOS 26.11.20260705, hostname `server`, Nix 2.34.7 |
| Dagu | 2.15.0, `systemd --user` unit `dagu` |
| devenv | 2.1.2 |
| devman | 0.3.0, `/run/current-system/sw/bin/devman` — the installed build predates stage 5's fixes |
| watchexec | 2.5.1, `systemd --user` unit `devman-watch` |
| Registry | `~/.local/share/devman/` — 6 projects, 36 workflows, 36 DAG links |
| Timer | `devman-maintain.timer`, enabled, daily, five hand-written `ExecStart` lines |
| Date | 2026-08-22 |
| devman rev | branch `dagu-devenv-automation-eli5`, at `d215e12` |

---

## S1 — What "done" means for stage 6, written before anything was built

**Why this entry exists.** §13's rollout ended at stage 4 and stage 5 wrote its
own definition of done. This is the second stage to do that, and the first whose
subject was set by the owner rather than by a shortlist: **a developer must not
have to remember to change anything outside the repository for automation to
work as declared.**

**What made it possible** is `STAGE_5_LOG.md` S12, measured at the owner's
prompting: Dagu's own scheduler resolves everything correctly when the
**projected file carries the values**. Stage 4's S2 had concluded that Dagu's
scheduler "cannot trigger anything this plane projects", and that conclusion was
true of the projection shape devman chose — a symlink to one shared group file
whose `working_dir` and `log_dir` interpolate from whoever enqueues — rather
than of Dagu.

### What stage 6 is, in one sentence

> **Stage 6 moves the schedule into the workflow file.** The projection stops
> being a symlink and becomes a small generated file that states the project's
> own `working_dir`, `log_dir` and directory parameter, so `schedule:` — Dagu's
> own key, in the workflow's own YAML — is fired by Dagu's own scheduler, and
> `devman-maintain.timer` is retired.

**And what it is not.** It is not a new trigger mechanism: `devman run`, the
watcher and VCS hooks are unchanged, and no new command, global name, queue or
registry field appears. The schedule is content, exactly as the queue name is.

### The ten conditions

**D1 — The projection materialises, and every workflow still loads and still
runs.** All 36 projected files pass `dagu validate` through `devman doctor`, and
at least one workflow per **home** (§7.3's three: a group everyone takes, a
group taken by name, a repository's own `.devman/workflows/`) is run through the
plane afterwards, with its `metadata.jsonl` line quoted.

**D2 — One real scheduled run, fired by Dagu, in a real repository.** Not a
throwaway instance and not `systemd-run`: the installed `dagu` daemon, a
registered repository, a `schedule:` line in a group file, and the evidence is
the daemon's own dispatch log plus the project's `metadata.jsonl` line plus the
log tree under that project. **A schedule that has not fired is not delivered.**

**D3 — The generated header is auditable, and it is the smallest thing that
works.** It states only what a trigger states today — the directory parameter,
`working_dir` and `log_dir` — and it never edits a workflow's steps. Two rules
it must keep, both measured before the projection is changed:

1. **A cross-repo workflow (§11) must not gain `DEVMAN_PROJECT_DIR`.** The
   header supplies `DEVMAN_SELF_DIR` there instead, and `doctor`'s §11 check is
   what proves it.
2. **A body that already states a field keeps its own.** The header adds, it
   does not overwrite.

**D4 — The timer is retired only after the schedule is proved**, and retiring it
is the developer's own act on their own file (§8). This log states the exact
command and the order.

**D5 — Every criterion that holds must still hold, measured rather than
asserted.** A criterion-by-criterion table against §14. **Six are re-run by
command**, because materialising the projection pressures them hardest:

| # | Why stage 6 pressures it |
|---|---|
| 5 | shadowing is exact — a generated file must still be diffable against the group version it shadows |
| 6 | a workflow is portable Dagu — the header is per project, so the *body* must stay unedited |
| 7 | the hook now **writes files** where it wrote symlinks. The added cost is measured, with a spread |
| 10 | no workflow contains an absolute path — the source files must stay clean while the projection holds one by construction |
| 13 | the watchers do not chase each other — a scheduled run writes into a watched tree while nobody is at the keyboard |
| 17 | there is one way in — a projection that generates files must still be derived from repositories and nothing else |

**D6 — What this costs is stated, not discovered later.** `STAGE_5_LOG.md` S12
names the loss in advance: a repository's own `.devman/workflows/x.yaml` stops
being live-edited, because Dagu reads a generated copy rather than a symlink to
it. This log states the remedy (`devenv shell -- true`), measures how long it
takes, and says plainly whether it is acceptable.

**D7 — Whatever a schedule inherits, a repository can refuse.** A `schedule:` in
a group file reaches every repository that takes the group. That is the same
promotion rule §16 already applies to the file itself, and the escape hatches are
§7.3's — do not take the group, or shadow the file whole. The entry that adds the
first schedule states which repositories it starts running work in, by name.

**D8 — Nothing gives the registry a second entry path.** Unchanged since stage 1
and the rule that outranks the rest. A generated projection is derived state,
like the symlinks it replaces; if generating it appears to need a fact no
repository stated, this log says so before the code is written.

**D9 — The charter changes only in its own commit, and the log entry comes
first.** Stage 6 is expected to move **three** sections — §7.2's "devman never
parses a workflow", §8's third trigger arrow, and §9.2's projection layout — and
each one waits for the measurement that forces it.

**D10 — The machine is left as it was found, and every touched repository is
named.** `devman doctor` back to `Nothing to report`, no throwaway in the
registry, every repository at a stated commit, and a machine change proposed and
handed over rather than activated.

### What this deliberately does not promise

- **Not a schedule for every repository.** The first one is `maintain`, because
  it is what the retired timer already ran and because its work is bounded and
  its output is a report. A scheduled workflow that rewrites source files is the
  case §8 warns about for reactivity, and stage 6 does not ship one.
- **Not catch-up after downtime.** Dagu's scheduler fires on a cron expression;
  a machine that was asleep at the appointed minute missed that minute. Whether
  the plane should notice is a question this stage records rather than answers.
- **Not a change to how anything else is triggered.** The watcher, the hook and
  `devman run` are untouched, and the refusals in `src/devman/run.py` still
  govern every path a person or a service takes.
- **Not §9.4's first use.** Nothing here publishes or needs a value outside
  `$HOME`, so stage 4's S7 decision stands for a third stage.

**Charter impact:** **none.** This entry is stage 6's own definition of done.
