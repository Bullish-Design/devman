# 048-base lane results

Workspace: `.gitman/workspaces/048-base`.

The lane packages the required base template. Compile stages the filled template,
checks `handler_on.exit`, `devman.task`, the seven-day retention value, and no
base queue. Real Dagu validates the candidate and every changed DAG before base
publication. The Home Manager module no longer has `defaultQueue`.

The wheel contains `devman/base.yaml`. The Nix install check reads it through
`importlib.resources`. The fixture no longer copies a base file into the overlay.
The overlay base cannot change required behavior.

## Verification

- Focused base tests: 64 passed.
- `base:check`: passed.
- `base:unit`: 167 passed, 8 deselected.
- `base:e2e`: 8 passed, 167 deselected. Real Dagu emitted `done` and `failed`.
- `base:test`: passed. Nix checked 11 flake checks on x86_64-linux.
- `nix build .#devman --no-link`: passed.
- `git diff --check`: passed.

The first focused run found four test expectation errors. I fixed them and reran
the suite. The first Nix install check used a path search that missed the wheel
resource. The importlib resource check now passes.

The rebase had one conflict in `tests/test_doctor.py`. I kept the new explicit
queue fixture and removed the test's overlay base write. The conflict is clear.
