# Phase 5 implementation note — devman side — 2026-09-08

## Status

**The devman half of the Agentman boundary is implemented, not only
documented.** `groups/agent/` ships, the `llm` queue is declared, the secret
allowlist and masking behave as measured, the receipt is verified, the retry
policy is stated and tested, and 60 tests drive a real subprocess through the
whole path.

**What is not claimed: a live Claude run.** Every test uses
`tests/fixtures/fake_agentman.py` — a real executable with no network, no
credential and no model. The path through a real `agentman` binary, a real Dagu
service and a real key has not been run.

Agentman's v1 contract is **adopted unchanged**. No version bump was needed, and
none was made.

## What landed

| | |
|---|---|
| `src/devman/agent.py` | the adapter — §10's fourth command |
| `src/devman/cli.py` | `devman agent`, and the closed-list test that names it |
| `groups/agent/` | the workflow, its README, its `writes.toml` |
| `nix/nixos-module.nix` | the `llm` queue, concurrency 2 |
| `tests/unit/test_agent.py` | 60 tests |
| `tests/fixtures/fake_agentman.py` | the double |
| `tests/fixtures/dagu/secrets-env.yaml`, `secrets-dagu-prefix.yaml`, `queue-llm.yaml` | three conformance fixtures |
| `flake.nix` | the hermetic suite may now read `groups/` and `nix/nixos-module.nix` |
| charter §7.1, §9.4, §10 | three amendments, each with its measurement |
| `020/RESULT.md`, `022/EVIDENCE.md` | the decisions and the evidence |

## The three charter amendments, and why each was unavoidable

**§7.1 — a sixth queue name.** `llm`, because a scheduled run bypasses its queue
(020) and the only gated arrow is `devman run`, so the gate there needs a limit
set by a vendor's quota rather than by this machine's cores. Every repository
inherits the name; that is the cost, and §7.1 says to weigh it that way.

**§9.4 — masking covers the exact value only.** The section claimed masking
without stating its limit, and the limit is the part a workflow author has to
know. Measured: five characters of a token log in clear.

**§10 — a fourth command.** `devman agent` runs *inside* a workflow rather than
being typed at one. The alternative was a devenv task in every adopter, which
would put the secret allowlist, the process bound, the receipt check and the
exit-code mapping in 54 files that drift.

## The one measurement that changed the design

**Dagu never escalates to `SIGKILL`.** It re-sends `SIGTERM` every 5 s,
indefinitely, and a step that ignores it runs unbounded with the DAG never
finishing — measured over 75 s (022 M3). Its own schema documents an escalation
that does not happen.

Before that measurement, `--timeout-s` looked like a declaration for Agentman to
validate and the orchestrator to enforce. **It is the only bound that exists**,
and `agent.invoke()` implements the escalation the daemon lacks. This is also the
first entry in `AGENTS_GUIDE.md`'s trap table that is about the orchestrator
doing less than its documentation says.

## Verification

```
devenv tasks run -v base:check     ok
devenv tasks run -v base:unit      483 passed
devenv tasks run -v base:test      all checks passed (87 s, incl. the NixOS VM test)
devman doctor (from source)        1 finding, and it is not this change
```

**The `doctor` finding is `local sources`: `repoman` has uncommitted changes and
`pytuin` pins a stale `atuout`.** Both are other repositories' git state and
pre-date this work. Every check that could see this change — `queue names`,
`validate`, `writes`, `handlers`, `fan-out`, `projection` — is `ok`.

`queue names` reports the machine's five queues, not six, and that is correct:
the running `config.yaml` is the installed build, and `llm` arrives at the next
machine rebuild. Nothing projects a workflow naming it yet.

**`base:test` failed twice before it passed, both times for the same reason, and
it is worth recording.** `checks.python-tests` builds from a `fileset`, and the
fast loop reads the working tree — so five tests asserting things about
`groups/` and `nix/nixos-module.nix` were green locally and absent in the
sandbox. `tests/README.md` already warns that a coverage row is a claim; the
`fileset` is that claim, and `flake.nix` now says so where the list is.

## devman does not take its own `agent` group, and that is deliberate

Criterion 16 has devman adopt its own workflows, and this is the exception. The
group's own README lists what taking it costs: a credential on the Dagu service,
`agentman` on the step's PATH, and an `agent:capsule` task. **devman has none of
the three**, so adopting it would project a workflow that fails before its first
step on every run — which is `groups/README.md`'s "a workflow whose output
nobody reads", with a failure attached.

Adopt it in the first repository that has an Agentman capsule worth running.
That is also the first honest test of the live path.

## What the next project inherits

- **A live proof is not done.** Nothing here has spent a token.
- **`human-task` is still unexamined** (020 §8). Look at it before assuming the
  gitman lane is the only review shape the plane has.
- **Option B's dispatcher is chosen and unbuilt** (020 §3). Its unsolved problem
  is deriving a fan-out from the registry rather than stating 54 project names.
- **Cost has no ceiling.** The queue bounds concurrency; nothing bounds spend,
  and the capsule's `[budget]` is per run rather than per day. Stated in the
  group README under what taking it costs, and enforced nowhere.
