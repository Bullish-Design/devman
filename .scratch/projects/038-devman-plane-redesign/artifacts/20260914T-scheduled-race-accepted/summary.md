# Wave 3 item 9 — scheduled-run race accepted

Date: 2026-09-14

The charter now records the accepted Dagu limitation instead of requiring an
unavailable scheduler gate:

- scheduled runs maxed at 20 seconds over 550 records;
- `maintain` maxed at 5 seconds over 551 records;
- 45 DAGs fire together at 00:05 daily;
- Dagu 2.15.0 has no primitive that defers scheduled runs.

Requirement 7 is now an accepted limitation. A future strict option is a
scheduled parent with one `devman run <workflow>` step, which would inherit the
marker gate through `run.trigger`. No scheduled gate was built in this item.

Verification: `git diff --check` passed. Full Nix verification remains blocked
by the host filesystem at 100% usage.
