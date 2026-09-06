Session root: ~/Documents/Projects/templateer_v2

# Phase 2b — publish templateer as a pinned artifact

Context: devman's changelog workflow currently reaches this library through
`PYTHONPATH=/home/andrew/Documents/Projects/templateer_v2/src` plus
`uv run --project <that same absolute path>`, inside a Dagu step. It also happens
to be importable in devman's devenv through a stray `.pth` file that no
repository declares, deleted in Phase 0. Neither is a dependency declaration.
This phase makes it one.

Read first:
- `~/Documents/Projects/devman/.scratch/projects/023-toolchain/PROBLEMS.md` (P2)
- `~/Documents/Projects/devman/.scratch/projects/022-templateer-changelog/KICKOFF.md`

## The job

1. Bump the version in `pyproject.toml` (currently 0.3.0).
2. Tag and publish the release through this repo's normal flow.

The dependency spelling consumers will then use:
```toml
[tool.uv.sources]
templateer = { git = "https://github.com/Bullish-Design/templateer_v2", tag = "vX.Y.Z" }
```

templateer is pure Python (`hatchling`, no native extension), so it needs
**neither** `relocate_wheel.py` **nor** the `_PYTHON_HOST_PLATFORM` unset that
pyjutsu's wheel task requires. A git tag is the smaller correct answer; uv
records a hash for it. Take the wheel-asset route (copying `pyjutsu/devenv.nix`'s
`pyjutsu:wheel` / `pyjutsu:publish` pair) only if the owner wants offline installs.

## Verification

```bash
devenv tasks run templateer_v2:lint
devenv tasks run templateer_v2:test
# then, from a scratch directory OUTSIDE this repo:
uv run --with 'templateer @ git+https://github.com/Bullish-Design/templateer_v2@vX.Y.Z' templateer --help
```
The last command is the one that matters: it proves the artifact resolves with no
sibling checkout and no PYTHONPATH.

## Rules

- Do not change the public API. The changelog integration uses the CLI
  (`templateer generate <template> --paths ... --request ... --model ... --json`,
  returning an object with an `artifact` key) and the documented
  `TemplateRegistry.from_paths` boundary. If either must change, stop and say so.
- Do not add devman, gitman or pyjutsu as dependencies here.
