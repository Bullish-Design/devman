# Cutover log — devman 047 Stage 10

Date: 2026-10-16.

## Phase A — release and content

- devman v0.9.0 released.
- The overlay `~/.config/devman` got the library, `projects.toml` (33 projects),
  `workflows/devman/` and the `links.yaml` declarations for
  `.devman/workflows` and `.devman/runs`.

## Phase B — machine switch

- The old plane stopped. The old state was deleted (R12).
- `sudo nixos-rebuild switch` ran from the nix-meta workspace `devman-047`.
- `systemctl --user list-unit-files 'dagu*' 'devman*'` shows only
  `devman-dagu.service` and `devman-watch.service`. Both are enabled and active.
- `~/.local/state/devman/` holds `base.yaml compile.json compile.lock dags runs
  tmp watch`.

## Phase C — links, proofs, landing

### Compile and doctor

- `devman compile --all`: exit 0. `compile.json` holds 33 projects, all `ok`,
  0 refused.
- `devman doctor`: exit 0.

```
ok   Dagu answers
ok   Dagu version
ok   watcher runs
ok   watch budget
ok   compile clean
ok   dags match compile
ok   checkouts
ok   library actions
```

### Links

For all 33 projects, `linkman diff` showed only two creates: `.devman/runs ->
~/.local/state/devman/runs/<p>` and `.devman/workflows ->
~/.local/state/devman/dags/<p>`. (66 create lines in total.) `linkman apply`
succeeded (exit 0) for all 33. None was skipped. In each project both links
resolve, and `git status --short` shows neither. The `testee` repository has
many staged `.scratch/` and `docs/` files. They were there before and have no
link to this work.

### Proofs (in the devman repository)

1. `devman status` lists check, test, format, release and the
   `workflows/devman/` ones (agent-review, bench-entry, gitman-commit-message,
   upkeep).
2. `devman run check` enqueued run `8a8b369d-bd5a-4ac7-9844-2a3077c9e6de` and it
   succeeded. The log is under
   `.devman/runs/devman_check/dag-run_20261016_134216Z_8a8b369d-.../`.
3. The `done` event for that run:
   `{"at": "2026-10-16T13:42:26.853+00:00", "event": "done", "project": "devman",
   "source": "dagu", "subjects": ["check"], ...}`.
4. A no-op rewrite of `src/devman/__init__.py` gave one `save` line with the
   match `format` (run `c93d3fe6-c6f4-4e2a-9e9d-b4a07090dd9a`, enqueued) and a
   `done` line for `format` at 13:43:30. No tracked file changed (`jj st` empty).
5. A save of `.scratch/zz_probe.py` (created, then deleted) gave a `save` line
   that **did** match `format` (run `2c972f74-94f6-4cca-8ad8-dcc85783827f`).
   The plan expected no match. See "Open".
6. Dagu REST `/api/v1/dags`: 72 DAGs in 33 groups, one group per project. The
   devman group holds agent-review, bench-entry, check, format,
   gitman-commit-message, release, test and upkeep.
7. `devman.upkeep` has schedule `20 0 * * *` (cron) in Dagu.

### nix-meta landing

Trunk was already `c88b8efe`; the rebase changed nothing, so no rebuild-check
was needed. `main` moved to `d6645b2a337d` ("devman 047: move the machine to the
Home Manager module at v0.9.0") and was pushed to origin. `jj new main` ran in the
main checkout. `gitman done devman-047` removed the workspace.

## Open

- The `[[devman.on]]` save entry in `~/.config/devman/projects.toml` has no
  `exclude`. A save under `.scratch/` runs `format`. The code supports
  `exclude` (`manifest.py`, `router.py`), so the comment in `projects.toml` is
  stale. Fix: add `exclude = [".scratch/**", ".worktrees/**", ".gitman/**"]`
  to that entry. This log did not change the overlay.
- nix-meta has other old workspaces under `.worktrees/`. They are not part of
  this cutover.
