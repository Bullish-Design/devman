# Wave 3 item 10 — authored/generated root split

Date: 2026-09-14

The compatibility publisher now refuses when the resolved authored overlay
root and generated registry root are the same directory. The refusal happens
before rendering or writing. The default roots remain separate, and
`registryDir` does not move.

The unit test proves the refusal and verifies that no generated project tree is
created. The implementation log records the five protected Devman workflow
files and the delete path that made this guard necessary.

Verification: Ruff and `git diff --check` passed. Full Nix and pytest
verification remain blocked by the host filesystem at 100% usage.
