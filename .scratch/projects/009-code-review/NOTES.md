# Review notes

## Baseline

- Repository lint: passed.
- Python and Dagu conformance suite: 236 tests passed.
- Governing sources read: `AGENTS.md`, `AGENTS_GUIDE.md`, project 006 charter,
  project 007 proposal, `README.md`, `USER.md`, and `tests/README.md`.

## Review map

| Boundary | Main implementation | Main proof |
|---|---|---|
| registration and projection | `modules/devenv.nix` | shell-entry stage logs |
| identity and registry | `src/devman/registry.py` | unit tests and codec conformance |
| workflow reader | `src/devman/workflow.py` | Dagu conformance fixtures |
| trigger | `src/devman/run.py` | refusal unit tests and NixOS run |
| reactivity | `src/devman/watch.py` | unit tests and NixOS watcher run |
| whole-plane diagnosis | `src/devman/doctor.py` | unit tests and live plane checks |
| machine service | `nix/nixos-module.nix` | NixOS virtual-machine test |

## Final disposition

The prioritized explanations and fixes are in `REPORT.md`.

| Finding | Priority | Disposition |
|---|---:|---|
| projection uses grep instead of parsed YAML semantics | P1 | confirmed with actual projection script |
| reserved directory parameter can retarget a run | P1 | confirmed in disposable registry |
| scheduled workflows inherit the daemon's zsh | P1 | confirmed from live service environment and source |
| nested registered projects double-dispatch | P1 | confirmed in disposable registry |
| identity codec accepts Dagu-invalid and path-active names | P1 | confirmed against the pinned Dagu rule |
| non-loopback bind is allowed while authentication is forced off | P1 | static configuration defect |
| paths are interpolated without YAML or JSON encoding | P2 | confirmed with colon-space path |
| trigger accepts a file Dagu's schema rejects | P2 | confirmed with pinned conformance fixture |
| malformed registry shapes crash readers; invalid JSON disappears | P2 | confirmed for a JSON list |
| the generated projection and scheduler path lack an integration test | P2 | confirmed test-boundary gap |
| source comments make false runtime claims | P2 | confirmed against current implementation |
| undeclared parameters are accepted | P2 | confirmed in disposable registry |
| `defaultQueue` need not name a declared queue | P3 | static configuration defect |
| `--print` does not shell-quote values | P3 | static CLI defect |
| this repository's format trigger includes files its task excludes | P3 | observed during review |

## Architectural strengths

- The charter is unusually precise about failure modes and ownership.
- The registry-to-DAG collision check refuses wrong-file execution on the normal
  CLI path.
- The bounded workflow reader is backed by a pinned Dagu conformance table.
- `child_env()` correctly removes ambient project variables and `$SHELL` on
  every path that reaches `devman run`.
- Watcher state, stale path handling, and the supervisor restart design are
  careful and evidence-based.
- `doctor` combines file checks with live-plane checks and keeps diagnosis
  useful when the daemon is unavailable.

## Cross-cutting conclusion

Most Python algorithms are small and readable. The highest-risk code is the
generated shell in `modules/devenv.nix`. It implements a YAML transformation, a
JSON renderer, an identity codec, and an incremental projection cache with grep,
printf, and Bash substitution. The tests exercise the Python consumers and the
source YAML, but not this producer's exact output. That is why several defects
share one boundary and still coexist with a green suite and a green doctor.
