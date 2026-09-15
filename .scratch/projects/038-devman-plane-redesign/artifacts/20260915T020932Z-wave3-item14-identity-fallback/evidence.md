# Wave 3 item 14 — remove the literal identity fallback

Date: 2026-09-15 UTC

## Scope

The link adapter now resolves identity from `.devman/project.toml`, or from an
explicit `--project` value for a manifest-free compatibility checkout. It no
longer reads `devenv.nix` or `devenv.local.nix` for `devman.project` values.

The parser, compatibility identity field, manifest/Nix drift refusal, and
manifest-free literal fallback tests were removed. Four tests left with that
old behavior. The unit count changed from 594 to 590 for this reason.

The measured trade-off is explicit: a repository with both a manifest and an
old Nix identity no longer gets a manifest/Nix drift refusal. That check was
the reason the fallback ran even when a manifest existed. The current fleet has
zero literal `devman.project =` assignments, so no live repository uses the
removed path. `forgelab` and `lodestar` also have no such assignment.

## Exact checks

The search returned zero:

```
rg -n 'devman\\.project[[:space:]]*=' --include='*.nix' /home/andrew/Documents/Projects
literal_assignment_hits=0
```

The repository gates passed:

- `devenv tasks run -v base:check`
- `devenv tasks run -v base:unit` — 590 passed in 10.50s
- `devenv tasks run -v base:test` — all checks passed in 137s
- `nix build .#checks.x86_64-linux.dagu-service --no-link`
- `nix build .#packages.x86_64-linux.devman-link --no-link`

The Vendomat canary returned exit 0 for both `devman-link status` and
`devman link status`, with five `ok` states and the central configuration path.
The fleet sweep returned 47 clean repositories and one known exit-1
`image-gen-pipeline` promote drift. It returned no new refusal.

## Machine state

The active Devman plane remains generation 3 with 48 projects and 152 DAG
files. The change did not rebuild or alter the generated plane. Dagu remains
2.15.0. No generated registry, overlay, or consumer repository was changed.
