# Wave 3 item 4 — reload defects

Date: 2026-09-14

## Changes

- The reload timeout now removes `reload.pending` after writing
  `reload.blocked`. The old generation remains active, and manual and watcher
  runs are not left refused forever.
- The drain loop treats an inactive `dagu.service` as drained.
- The drain loop treats a failed `dagu ps` call as drained while Dagu is
  stopping or unavailable.
- `doctor` reports `blocked` first and includes `pending` when both markers
  exist.
- The doctor unit test now checks both marker lines.

## Verification

- `ruff check src/devman/doctor.py tests/unit/test_doctor.py`: passed.
- `git diff --cached --check`: passed before commit.
- Full `devenv` verification is blocked by the host filesystem reaching 100%
  usage (`416M` free). Nix evaluation fails with `No space left on device`.
- The VM reload proof remains item 7.
