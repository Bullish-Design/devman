Session root: ~/Documents/Projects/devman

# Phase 2d — rewrite the changelog workflow to cross no import boundary

Context: `groups/changelog/workflows/changelog.yaml` cannot run today. Two of its
steps do `devenv shell -- python3 - <<PYEOF ... import pyjutsu`, and that import
fails in every adopter's devenv. A third step reaches `templateer` through
`PYTHONPATH` at an absolute sibling checkout. Phases 2a-2c replaced both with
console scripts.

Prerequisites: `gitman log --json` exists (2a); templateer is tagged (2b) and on
the shared shelf (2c).

Read first:
- `.scratch/projects/023-toolchain/PROBLEMS.md` (P1, P2, P6)
- `.scratch/projects/023-toolchain/GRAPH.md` §2 — environment propagation
- `.scratch/projects/021-changelog/DESIGN.md` and
  `.scratch/projects/022-templateer-changelog/KICKOFF.md`
- `AGENTS.md`, and `.agents/skills/devman-workflow/SKILL.md`

## Measured facts. Do not re-derive.

- `devenv shell -- python3 -c 'import pyjutsu'` fails; `devenv shell -- gitman` works.
- A Dagu step does **not** inherit the daemon environment — it re-derives from
  `/etc/profile` plus Home Manager session vars. `env_passthrough_prefixes` is
  `[DEVMAN_]`, so `GPU_LLM_*` reach a step only as DAG `params:`.
- The local endpoint is up. gemma returns `content: ""` with
  `finish_reason: "length"` on a short token budget — an HTTP 200 carrying nothing.
- A warm `devenv shell --` costs ~0.755 s. This workflow pays it four times.

## The job

1. `gate` and `write`: replace both heredocs with
   `devenv shell -- gitman log --revset "$last..$trunk" --json`, keeping the
   existing "an entry file exists for this change" filter.
2. `summarize`: drop `PYTHONPATH=` and `uv run --project "$TEMPLATEER_PATH"`.
   Call `templateer` directly; it is on PATH from Phase 2c.
3. `params`: delete `TEMPLATEER_PATH`. Resolve `TEMPLATEER_TEMPLATE_PATH` through
   `$DEVMAN_SELF_DIR` — the templates are group assets, not machine paths.
4. **Add a `finish_reason` check.** Fail the step on anything but `stop`. A
   successful run must never write an empty or truncated section.
5. Add an interpreter probe that runs the way a *step* runs it, in the group's
   gate or in `devman doctor`. Both `repoman doctor` and `gitman doctor` report
   pyjutsu green while a step fails, because each asks its own interpreter.

## Verification

```bash
grep -n 'TEMPLATEER_PATH\|PYTHONPATH\|import pyjutsu' groups/changelog/workflows/changelog.yaml   # no matches
devenv shell -- dagu validate groups/changelog/workflows/changelog.yaml
devenv tasks run -v base:check
devenv tasks run -v base:test
devman doctor
```
All three gates must exit 0 before committing anything under `groups/`.

Then end to end, as 022's kickoff requires: a disposable adopter, real
`gitman start` / `save` / `land`, the real post-hook enqueue, the chained run
reaching generation, and a person reading the lane diff. Plus both refusals —
empty batch, and a second unreviewed lane.

Disposable-DAG traps, already paid for: `dir:` is now `working_dir:`; `env` is a
reserved step id; and `DEVMAN_PROJECT_DIR` must be **exported in the enqueuing
shell**, because `base.yaml`'s `log_dir` reads the variable and DAG `params:` do
not reach it.

## Do not reverse

- The loud failure on an unset `${DEVMAN_PROJECT_DIR}`. A run must record `Failed`.
- `GPU_LLM_BASE_URL` / `GPU_LLM_MODEL` stay as DAG `params:`. Nothing about the
  endpoint belongs in Nix.
- **devman gets no `uv.lock` and no populated venv.** The point of this phase is
  that the workflow calls console scripts, so devman needs no Python dependencies.
- The fixed-lane collision refusal and the empty-batch refusal.

## Rules

Route version control through gitman — lane, save, publish, PR to main. Never raw
git or jj. Preserve unrelated worktree changes; this tree has many.

## Stop if

Making it work needs an absolute sibling path, or weakens either refusal.
