# Wave 3 item 7 — VM reload subtests

Date: 2026-09-14

The NixOS test now covers the reload failure modes that were absent from the
existing active-pointer test:

- a timeout writes `reload.blocked`, clears `reload.pending`, keeps Dagu's PID,
  and still permits a manual run;
- a stopped Dagu does not make reload wait for the full deadline;
- a failed restart leaves the reload service failed and its pending marker
  visible.

The existing active-run subtest continues to cover the nine guide assertions:
PID stability during the run, completion, restart, generation retention and
visibility, run metadata, and Dagu history.

Verification: `nix-instantiate --parse nix/tests/dagu-service.nix` passed.
The NixOS VM build is blocked by the host filesystem at 100% usage, so these
subtests still require a real VM run before item 7 is accepted.
