# Argentic consumer gate investigation

Date: 2026-09-13

## Target and acceptance condition

The target is the `argentic` consumer transition to the machine-owned Devman
link module. The consumer change must pass `devenv shell -- true`,
`devenv tasks run -v base:check`, and `devenv tasks run -v base:test`. The
plane must also pass both link canaries and keep the active generation and DAG
tree unchanged.

The Devman change must not alter argentic source or test code. The only
consumer edits are `devenv.yaml`, `devenv.nix`, and the direct Devman removal
from `devenv.lock`.

## First complete gate

Repository: `/home/andrew/Documents/Projects/argentic`

Consumer revision before the uncommitted change: `4edc111`.

Command:

```text
devenv tasks run -v base:test
```

Result: 11 failed, 677 passed in 395.22 seconds.

Every failure is in one of the two live suites:

- `tests/test_loop_live.py`: 3 failures;
- `tests/test_overlay_live.py`: 8 failures.

The failures are semantic live-client assertions. They are not Nix evaluation,
lock validation, lint, or deterministic unit failures.

## Isolated deterministic gate

Command:

```text
devenv shell -- pytest --ignore=tests/test_loop_live.py --ignore=tests/test_overlay_live.py
```

Result: 666 passed in 256.14 seconds.

This result proves that the changed devenv boundary does not break argentic's
deterministic Python and consumer tests. It does not prove the live SilverBullet
client behavior.

## Runtime boundary

The host services were reachable during the investigation:

- SilverBullet process: `silverbullet-2.10.0`;
- headless Chromium: `150.0.7871.46`;
- SilverBullet `/.ping`: HTTP 200;
- SilverBullet `/.runtime/lua` with `1+1`: HTTP 200, `{"result":2}`;
- argentic bridge `/health`: HTTP 200, version `0.1.0`, eight expected tools.

The failing tests then reached deeper client behavior and failed on:

- owned-region payload spans including the closing fence or disappearing from
  the live index;
- the expected modal backdrop not appearing;
- editing keys being cancelled by the host client;
- multi-touch opening SilverBullet pickers from inside the panel;
- the agent answering without a tool event;
- the saved transcript missing the assistant section;
- the write-path test receiving no diff card.

The SilverBullet journal recorded runtime warnings during the same period:

```text
runtime call sbRuntime.evalLua failed: unexpected symbol near 'i'
runtime call sbRuntime.evalLuaScript failed: runtime request timed out
runtime call sbRuntime.evalLua failed: unexpected symbol near '['
```

The runtime state and API captures are retained in:

- `/tmp/argentic-devman-removal-X4vzZm/`;
- `/tmp/argentic-devman-removal-static-*/`;
- `/tmp/argentic-devman-removal-canary-*/`;
- `/tmp/argentic-devman-removal-probes-*/`.

## Upstream evidence

- [SilverBullet 2.10.0 release](https://github.com/silverbulletmd/silverbullet/releases/tag/2.10.0)
  calls the Runtime API experimental and describes it as a full headless-Chrome
  client. This makes the live gate dependent on a separate browser runtime,
  not only the HTTP server.
- [SilverBullet issue #2078](https://github.com/silverbulletmd/silverbullet/issues/2078)
  reports Runtime API crashes in 2.10.0, headless-Chrome restarts, and an
  `attempt to index a nil value` error. This overlaps the observed runtime
  warnings and the failing live-client assertions.

## Classification

The failure boundary is **after the server is listening and after a basic
Runtime API request succeeds, but during validated client/index/overlay
behavior**.

Hypothesis that Devman removal changed argentic's application behavior: not
supported by the evidence. The deterministic suite passes, the changed files
contain no application or test code, and both link canaries pass.

Hypothesis that the external SilverBullet/Chromium client or the current
argentic live environment is unhealthy: supported by the journal warnings,
the host process versions, and the matching upstream 2.10.0 report.

A pre-existing argentic live-test or application regression is not ruled out.
No application fix is justified by this Devman migration, so this remains an
external gate blocker rather than a scope expansion.

## Decision

Do not commit the `argentic` consumer transition yet. Preserve the three
uncommitted consumer edits and the minimal lock diff. Repair or baseline the
SilverBullet/bridge live environment, then rerun the exact full test command
with a new evidence directory. Commit only after the complete gate passes or
the operator explicitly accepts a documented live-gate waiver.

The canary proof already passed without changing the machine plane:

```text
active=generations/2
projects=46
dags=146
digest=5acf4cc3be671f7118643e33eb01f37d708ed780ee228027956dce0dcee6022b
dagu_ls_lines=147
```
