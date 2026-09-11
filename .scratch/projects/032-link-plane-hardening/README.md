# Link-plane hardening

Date: 2026-09-10

This note records the implementation of the link-plane hardening work against
the authoritative design in
`.scratch/projects/025-the-link-plane/CONCEPT.md`. It does not implement the
deferred Stage 3 state separation or Stage 4 direct workflow links.

## Closure decision

The per-project `.local.gitignore` is tracked in the central config repository
at `projects/<project>/.local.gitignore`. It is authored configuration, not
generated state. The config repository's `.gitignore` therefore does not ignore
this path. The repository-side `.git/info/exclude` remains a symlinked view of
the tracked file.

The reconciler also resolves all declarations before creating missing canonical
paths. If one canonical path is an ancestor of another, it is created as a
directory even when its view name has no slash. This covers the bootstrap pair
`.agents` and `.claude/skills`.

## Before this change

- The reconciler implemented the five link states, promotion, recorded
  canonical hashes, and the no-silent-clobber refusal, but it accepted
  templates for repository and external canonical owners.
- The shell entry point wrote `.git/info/exclude`, while the Python reconciler
  did not. Linked worktrees required the common Git directory.
- The watcher dispatched registered workflows without reconciling their
  declared views.
- Link identity parsing accepted only a direct literal assignment. A valid
  `projectName = "devman"; devman = { project = projectName; };` declaration
  therefore failed from the devman repository root.

## Rules enforced

- Templates are valid only for central canonical owners.
- Canonical paths and views must remain inside their declared boundaries.
  External canonical paths must remain outside the project and overlay.
- A matching symlink is healthy only while its canonical target exists.
  Missing canonical content is created deterministically before linking.
- The Python reconciler is the single owner of link creation, promotion, and
  `.git/info/exclude` updates. It supports ordinary repositories and linked
  worktrees and never writes `.gitignore`.
- The watcher reconciles each registered project immediately before triggering
  its workflow. It continues other registered entries, records link refusals,
  and returns failure when any refusal occurs. It does not scan arbitrary
  directories.
- CLI identity remains explicit. It accepts literal and supported local
  variable forms, refuses missing or ambiguous declarations, and never uses a
  directory basename as identity.

## Bootstrap decision

The generated bootstrap declaration continues to include only `.envrc`,
`.loci`, `.agents`, and `.claude/skills`. The concept makes each link an
explicit declaration choice; it does not require every repository to receive a
`.devman/workflows` view. The omission is therefore intentional. A repository
that needs that view declares it, as the live devman project does.

## Implementation

- `src/devman/link.py`: owner validation, boundary checks, deterministic
  missing-target handling, Git exclusion reconciliation, linked-worktree
  support, and explicit Nix identity parsing.
- `src/devman/watch.py`: shared link reconciliation before workflow dispatch
  and surfaced per-project failures.
- `modules/devenv.nix`: removal of the duplicate shell exclusion writer and
  documentation of the Python ownership boundary.
- `tests/unit/test_link.py`: owner, boundary, missing-target, exclusion,
  linked-worktree, and identity regressions.
- `tests/unit/test_watch.py`: watcher reconciliation and failure propagation.

## Verification

`devenv tasks run base:unit` passed all 516 tests. `devenv tasks run -v
base:check` passed. The first `devenv tasks run -v base:test` invocation
returned 1 because Nix treated the nested lane as an untracked path below the
canonical Git root. The correct explicit workspace invocation,
`nix flake check path:/home/andrew/Documents/Projects/devman/.worktrees/032-link-plane-hardening`,
returned 0 and ran all checks, including the hermetic Python suite and the
Dagu service VM test. Its no-build counterpart also returned 0.

The built lane CLI returned 0 for `devman --help`, `devman link --help`,
`devman link status --all`, and `devman link status` from the devman repository
root. The built `devman doctor` returned 1 with eight existing live local-source
findings; those findings were not caused by this lane and were not changed.

The live checks were read-only. They inspected `~/.config/devman`, the
generated registry under `~/.local/share/devman`, and representative project
views. No central configuration, registry projection, nix-meta checkout, or
other repository was modified. `devman doctor --prune` and a system rebuild
were intentionally skipped.

The live registry still has five adopted projects with 21 declared links, and
`~/.local/state/devman` is absent. The devman repository has the declared
`.devman/workflows` view; sampled pydantree and flora checkouts retain real
`.agents` directories and do not have that view. Those are adoption state
observations, not automatic migration failures.

There are no unresolved design questions for this scoped implementation. The
bootstrap workflow view remains an explicit declaration choice, and direct CLI
reconciliation writes exclusions because the concept defines exclusions as a
projection of the same declaration.

## Remaining work

- Stage 3 state separation remains deferred. The generated registry remains
  under `~/.local/share/devman`; `~/.local/state/devman` is not introduced.
- Stage 4 direct Dagu workflow links remains deferred. Registry workflow files
  remain generated projections.
- Live adoption is not completed by this lane. Repositories with real
  `.agents` directories or no workflow view require separate migration or may
  be intentional opt-outs; this implementation does not rewrite them.
