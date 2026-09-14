# Wave 3 item 8 — reload deadline

Date: 2026-09-14

The production default for `reloadMaxWaitSec` is now 600 seconds. The option
description records the observed maximum of 279 seconds over 1306 runs and p99
of 61 seconds. The new limit gives a two-times margin over the observed
maximum. The VM test keeps its explicit 15-second override so it can exercise
the timeout path.

Verification: `git diff --check` passed. Full Nix evaluation remains blocked by
the host filesystem at 100% usage.
