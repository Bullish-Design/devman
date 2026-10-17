# 048 state validation — evidence

Baseline: devman `main` at `921cb87` (guide note), worked in the
`048-state-validation` gitman lane opened from `15c1424` (guide commit, no
code change against `921cb87` in `src/devman/`).

## Initial failing run

`initial-failures.txt`: 14 of 16 cases in `tests/test_state_validation.py`
failed on the baseline (run of 2026-10-17, lane working copy).

The failures, by intended reason:

1. Green health for malformed data (`global_health` dropped a string
   `global.reasons`; missing `global.at` and an integer digest also stayed
   green). Tests: `test_string_global_reasons_cannot_report_green`,
   `test_malformed_global_fields_are_named`,
   `test_boolean_version_is_not_a_valid_state_version`,
   `test_a_green_project_needs_a_real_path` (in part).
2. Uncaught exceptions on truthy non-mappings and null records:
   `show` raised `TypeError` on `[1]`, `42`, `"x"`; `emit` and `run` did the
   same; `doctor` raised `AttributeError` on `[1]` in `check_compile`; the
   watcher's `save_projects` raised `AttributeError` on truthy
   non-mappings. Tests: `test_truthy_non_mapping_state_refuses_cleanly`,
   `test_null_project_record_does_not_raise_anywhere`,
   `test_null_workflow_record_does_not_raise_anywhere`,
   `test_nested_project_record_fields_are_validated`.
3. Green-for-empty-lists and missing-state wording:
   `[]` produced no guard failure on the baseline doctor path
   (`compile_doc` turned it into `{}`), and neither missing nor malformed
   state named a field path. Tests:
   `test_missing_state_is_an_initial_condition`,
   `test_broken_json_refuses_every_command_and_changes_nothing`,
   part of the truthy non-mapping matrix.

The two passing cases on the baseline are stable regression tests, not
reproductions: `test_valid_version_one_state_upgrades_through_a_full_compile`
and `test_a_refused_full_compile_recovery_cycle`.

## Fix

`src/devman/state.py` holds the one validated reader. Consumers:
`compile` (`_read_compile_doc`), `status`, `show`, `doctor`
(`check_compile`, `check_dags`, `check_checkouts`), `router.emit` (so
`emit` and `run`), `watch` (`save_projects`, so `targets` and `classify`).
`Paths.compile_doc` and `Paths.records` are gone; no other JSON read of
`compile.json` remains in `src/devman/`.

## Final run

`final-results.txt`: 16 passed. Whole-suite gate results are in the lane's
commit message and the main checkout's verify log: `base:check`,
`base:unit` (191 passed), `base:e2e` (10 passed), `base:test`,
`nix build .#devman --no-link`, installed `devman doctor`.
