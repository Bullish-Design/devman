# Wave 3 item 6 — watcher reload refusal

Date: 2026-09-14

The watcher regression test feeds one matching filesystem event to
`watch.dispatch` while `reload.pending` exists. It proves:

- dispatch returns exit code 1;
- stderr includes the pending timestamp and refusal reason;
- `fired.jsonl` records `refused (1)` for the project and workflow.

Verification: `ruff check tests/unit/test_watch.py` passed. Full pytest and
devenv verification remain blocked by the host filesystem at 100% usage.
