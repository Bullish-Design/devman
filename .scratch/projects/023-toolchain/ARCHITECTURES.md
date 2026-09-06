# Candidate architectures

## The six models

- **A — Nix owns everything.** `pyjutsu`, `gitman`, `templateer` become nixpkgs
  derivations in `nix-meta`, installed through Home Manager.
- **B — one shared user venv.** Extend today's RepoMan toolchain venv to hold
  every cross-repository Python tool, including `templateer`.
- **C — every repository owns a complete environment.** Each `devenv` declares
  `gitman`, `pyjutsu`, `templateer` as its own uv dependencies.
- **D — shared toolchain *module*, per-repository installation.** RepoMan keeps
  the lock and the wiring, but the packages install into each repository's own
  uv venv rather than a machine venv.
- **E — hybrid.** Nix owns system binaries and native build tools; a shared user
  environment owns cross-repository CLIs; each project devenv owns its own
  libraries; a workflow uses the environment of the repository that owns it.
- **F — devenv inputs from sibling checkouts.** Expose `templateer` and
  `pyjutsu` as devenv/flake inputs pointing at local repositories.

## Comparison

| Criterion | A Nix | B shared venv | C per-repo | D shared module | E hybrid | F sibling inputs |
|---|---|---|---|---|---|---|
| Correct interpreter for `import` | yes | **no** — measured M3 | **yes** | yes | yes | yes |
| Console script on PATH everywhere | yes | inside devenv only | inside devenv only | inside devenv only | yes | inside devenv only |
| Reproducible | high | **low** — editable `path:` sources | high — `uv.lock` hashes | high | high | **low** — dirty tree, M2 |
| Native extension supported | needs a maturin derivation | yes, wheel | yes, wheel | yes, wheel | yes | needs a build |
| Works for non-interactive Dagu | yes, no wrapper needed | only via `devenv shell --` | only via `devenv shell --` | only via `devenv shell --` | CLI yes, import via wrapper | via wrapper |
| Cold start | ~0 | ~0.6 s | 6 s eval (M2) | 0.75 s | 0.75 s | 6 s when dirty |
| Warm start | ~0 | ~0.6 s | 0.75 s | 0.75 s | 0.75 s | 0.75 s |
| Rebuild on upgrade | full NixOS rebuild (min) | `repoman-sync --machine` (s) | `uv lock` per repo (s) | `uv lock` per repo | mixed | re-eval every dependent devenv |
| Duplicate disk | one copy | one copy | **N copies** (measured: 8) | N copies | 2-3 copies | N copies |
| Cache behaviour | binary cache | uv cache (43 GB today) | uv cache, shared | uv cache, shared | both | poor — dirty tree defeats eval cache |
| Upgrade propagation | atomic, all at once | one command, all repos at once | per repository, staged | per repository | staged where it matters | implicit, invisible |
| Rollback | `nixos-rebuild --rollback` | **none** — venv is mutable | `git checkout uv.lock` | same | mixed | none |
| CI / fresh machine | best | needs the bootstrap + a wheelhouse | best | good | good | **impossible** — absolute paths |
| Works without sudo | no (needs a rebuild) | yes | yes | yes | mostly | yes |
| Works when source is dirty | no | yes (editable — that is the point) | no | no | yes for the CLI | yes, and silently |
| Diagnose a wrong interpreter | easy — one python | **hard** — measured M6 | easy — `VIRTUAL_ENV` names it | easy | medium | hard |
| Add a new tool | write a derivation (hours) | one line in `repoman.lock` (minutes) | one line per repo | one line + roster | depends on category | edit two repos |
| Multi-user | yes | no — `$HOME`-scoped | no | no | partly | no |
| Trust boundary | Nix hashes | wheelhouse + editable local code | `uv.lock` hashes | hashes | mixed | none |

## Reading of the table

**A is right for a stable CLI and wrong for tools under daily development.**
`pyjutsu` is a 6.9 GB Rust build tree that changes weekly. A NixOS rebuild per
iteration is the wrong loop. But `dagu`, `devman`, `git`, `devenv`, `uv` are
exactly the A case, and three of the four are already there.

**B is what exists, and the measurement says it cannot carry a library.** A
shared venv on `PATH` lends console scripts and never lends imports. The
failure in M3 is not a bug in RepoMan; it is the boundary of what `PATH` means.
B also has no rollback and no reproducibility: three of its four entries are
`--editable` installs of live working trees.

**C is the most correct and the most expensive.** It gives every consumer the
right interpreter and a hashed lock, at the cost of 8 copies of a 20 MB
extension and one `uv lock` per repository per upgrade. The copies are cheap;
uv hardlinks from a shared cache where the filesystem allows it. The real cost
is upgrade fan-out across ~60 repositories.

**F is disqualified by measurement.** `git+file:` inputs read the dirty working
tree (M2), so an unrelated edit in `repoman` costs every dependent devenv a 6 s
re-evaluation, and no lock records what was actually used. It also cannot leave
this machine.

**D and E are the same shape at different scopes.** Both keep RepoMan as the
declaration point and move installation to where the interpreter is.
