# Unresolved questions and evidence gaps

## Not measured

1. **NixOS rebuild time** for each candidate architecture. Not measured — a
   rebuild changes the active system and the brief was read-only. Architecture A
   is ruled out on iteration-loop grounds, not on rebuild cost, so the number
   would not change the recommendation.
2. **`uv sync` time** per repository, and whether uv hardlinks the 20 MB
   `pyjutsu` extension from `~/.cache/uv` or copies it. This decides whether
   "N copies" in the architecture table costs 8 x 20 MB or nothing. Test:
   `stat -c %h` on two copies' inodes.
3. ~~**A real LLM generation.**~~ **CLOSED 2026-09-06.** The router is up and
   configured through nix-meta. A real completion succeeded against
   `http://127.0.0.1:8100/v1/chat/completions` with model `gemma`
   (`b10267-ecc0cb0d3`, Vulkan0, 32768 ctx). Remaining sub-gap: a real
   *Templateer* generation through that endpoint is still unproven — only a raw
   OpenAI-compatible call was made. And see P6 on `finish_reason`.
4. **Dagu enqueue-to-step-start latency.** The probe runs measured 2 s and 45 s
   wall clock, but the second included a `light` queue wait behind other work,
   so neither is a clean number. 012 already holds the measured 1.44 s figure.
5. **Whether `templateer`'s dependency tree can share one venv with `gitman` and
   `pyjutsu`.** `templateer` needs `pydantic-ai-slim[openai]` and `minijinja`.
   `repoman doctor` verifies mutual compatibility for the current 33 packages;
   it has not been asked about these. Test before step 6:
   `uv pip install --dry-run` into a copy of the toolchain venv.
6. **Multi-user and CI behaviour.** Judged from the design (`$HOME`-scoped venv,
   absolute paths), not measured. There is one user on this machine.

## Genuine open decisions

7. **`pkgs.devenv` or the flake's pinned `devenv v2.2`?** `nix-meta/flake.nix`
   pins v2.2 with a comment describing it as the developer-toolchain pin, but
   `profiles/developer.nix` installs `pkgs.devenv` (2.1.2). One of the two is
   wrong and the comment says which — but adopting v2.2 across ~60 devenvs is
   its own change with its own blast radius.
8. **Does `gitman log --json` belong in gitman?** It is a read verb in a tool
   whose CLI is otherwise entirely lane lifecycle verbs. The alternative is that
   the changelog group declares `pyjutsu` directly and accepts the coupling.
   Recommendation is R1a, but the argument against is real.
9. **Should the wheelhouse move off a Nix store path?** `UV_FIND_LINKS` pointing
   at `/nix/store/...-vendomat-wheelhouse` is what makes the toolchain
   non-rebuildable from anywhere except repoman's own devenv.
10. **Should `templateer` be a `changelog`-group cost, or a shared toolchain
    entry?** The 022 kickoff says do not make it a dependency of every devman
    adopter. Keeping it group-scoped honours that; putting it in the toolchain
    venv would not, and would also not help, since the toolchain venv cannot
    lend imports.

## Assumption re-verified, and one that failed

- Verified: `pyjutsu` is a native PyO3 extension; `gitman` depends on and imports
  it; the `[managers.git-pyjutsu]` entry is as described; `repoman-sync
  --machine` installs into `~/.local/share/repoman/venv`; the Dagu daemon does
  not inherit the interactive shell environment.
- **Failed:** the assumption that installing `gitman` into the shared venv makes
  `pyjutsu` available to devman workflows. It makes the `gitman` **command**
  available. It makes no import available to any other interpreter. This is the
  finding the whole investigation turns on.
