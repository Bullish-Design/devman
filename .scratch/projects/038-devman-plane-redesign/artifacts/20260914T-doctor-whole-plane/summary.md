# Wave 3 item 5 — doctor whole-plane enumeration

Date: 2026-09-14

## Changes

- `Registry` now supports a read-only active-generation project view.
- Plane-mode `doctor` selects that view when `generation.json` exists at the
  active root.
- Compatibility mode and all non-doctor callers keep reading the stable state
  root.
- A unit test proves that active-generation metadata wins over stale state
  metadata.

## Verification

- `ruff check src/devman/registry.py src/devman/doctor.py
  tests/unit/test_doctor.py`: passed.
- Expected plane count after deployment: 45 projects and 143 projected
  workflows, instead of the partial state-root count.
- Full `devenv` and pytest verification is blocked by the host filesystem at
  100% usage (`416M` free); Nix evaluation fails with `No space left on
  device`.
