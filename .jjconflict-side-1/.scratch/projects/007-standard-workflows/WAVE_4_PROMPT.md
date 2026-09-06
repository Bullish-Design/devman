# Wave 4 — adopt the remaining 43 repositories

Finish stage 7's rollout. Waves 0–3 are done; what remains is R-7's wave 4:
**43 repositories, in batches of ten.** The work per repository is one
`devenv.nix` task line, not a repair pass — that is measured, not assumed.

Work in the worktree at `/home/andrew/.paseo/worktrees/1n48r26y/special-dragon`
(branch `dagu-devenv-automation-eli5`, head `6115f89`, clean). The 007 documents
exist only on that branch and on `main`.

## Read these first, in this order

1. `.scratch/projects/007-standard-workflows/STAGE_7_LOG.md` — everything already
   measured. Read **I-4b** (the shell-entry survey) and **wave 2b** in full: they
   are what shaped this plan. Then **wave 2**, **wave 3** and **R-9**.
2. `.scratch/projects/007-standard-workflows/shell-entry-survey.tsv` — the raw
   58-row result. It is the reason wave 4 is 43 and not 46.
3. `.scratch/projects/007-standard-workflows/PROPOSAL.md` — §6 for the
   per-repository migration, §12 for the eight rules, **§12 rule 4 especially**.
4. `.scratch/projects/006-automation-plane/CONCEPT.md` — §5.2, §7.3, §7.4, §15.

## Where things stand — do not re-derive this

**The plane:** `devman doctor` clean, **11 projects, 40 workflows**. Dagu 2.15.0,
devenv 2.1.2, devman 0.3.0 **from the machine closure**.

**Branches.** `origin/main` is `f20a9c1` and carries R-3, R-4d, R-4f, R-6, R-8
and R-9. The working branch is **2 commits ahead and both are documentation**
(wave 3 and I-4b log entries), so **wave 4 needs no merge before it starts**.
Every repository in wave 4 pins `ref=main&rev=f20a9c11cd6b062aa6646e8b72b9767d7e90a522`.

**`nixos-rebuild switch` has NOT been run.** R-4d and R-4f are on `main` and not
in the installed `devman`. The nightly plane report is the proof: its `doctor`
output has no `trigger target` line. Say so again in the handover; do not run it.

**Already adopted (11).** Do not touch these:

| Repository | Commit |
|---|---|
| `devman` | `6115f89` (the worktree) |
| `siteman` | `541cf25` |
| `nix-paseo` | `65f564c` |
| `pyjutsu` | `8323e09` (head has since moved on unrelated work) |
| `pydantree` | `be150be` |
| `observantic` | `0f835d4` |
| `poddantic` | `a295423` |
| `nix-desktop` | `c775f2f` |
| `loci.nvim` | `7e6d984` |
| `webdantic` | `2486f27` |
| `parsedantic` | `e473af5` |

**Cannot be adopted (4).** Their shells do not enter, so §5.2 registration is
impossible. **Do not repair them and do not attempt them:**

| Repository | Cause |
|---|---|
| `PyGentic` | `git-hooks or pre-commit-hooks input required` — one input line away |
| `clinch` | `attribute 'configPath' missing` |
| `inferference` | `Refusing to evaluate package 'cuda12.9-cuda_nvcc-12.9.86'` |
| `fsdantic` | vendored agentfs Rust source absent |

**Known failing, already recorded, do not fix:** `pyjutsu` `test`,
`pydantree` `check` (256 ruff), `poddantic` `check` (20 ruff), `webdantic`
`check` (275 ruff), `parsedantic` `check` (78 ruff) and `parsedantic` `test`
(13 collection errors). Adoption and repair are separate passes.

## The two checks that are not optional

Both were bought with a wasted wave. Run them **per repository, before editing
any file**:

1. **`devenv shell -- true`.** I-4b says all 43 pass today, but it is a
   measurement with a date on it. A repository that has changed since is
   unadoptable, not slow.
2. **`command -v <the tool `base:test` would call>`, inside that shell.** Wave 2b
   found `pytest` absent from two venvs whose `pyproject.toml` declares it — it
   lives in `[project.optional-dependencies]`, which devenv's venv does not
   install. The fix there was `uv run --extra dev pytest`. A task naming a
   command the shell lacks fails **identically** to a failing suite.

## Rules

- **Measure, do not assume.** Every answer is a command, its output, and a
  verdict. An argument is not a measurement.
- **Trace the error before reporting the cause.** Wave 2 reported a
  five-for-five correlation as a mechanism and was wrong. Read the stack trace.
- **Continue `STAGE_7_LOG.md`** in the shape it already uses: the answer, the
  versions, the exact command, the evidence, the charter impact.
- **Commit and push each batch as you confirm it**, not once at the end. Each
  repository gets its own `chore(devman): adopt the stage-7 workflow set`
  commit, on its own default branch, pushed.
- **Name every repository you change, with its commit** (rule 7).
- **Report mistakes rather than tidying them away.** The log records a
  90-second outage, a bad synthetic record, two wrong causal guesses and an
  unpushed wave. Match that standard.
- **The charter changes in its own commit**, after the measurement that forces
  it — and wave 4 is not expected to force one.
- Leave the machine as you found it, and say what you left.

## The work, in order

### Batch 1 — the 15 `enterTest` repositories, first and in two batches

**These are the ones that can adopt a lie.** `PROPOSAL.md` §12 rule 4 rests on
`devenv test` exiting 0 having tested nothing in 30 of 58 repositories, and wave
2 hit it twice: `webdantic` and `parsedantic` both carried the devenv template's
default `enterTest`, which greps `git --version`. **Neither got `devenv test` as
its `base:test`.**

For each of these, **open `enterTest` and read it.** If it is the template
default, `base:test` is the real suite (`uv run --extra dev pytest`, `pytest`,
`nix flake check`, whatever the repository actually has) and **never**
`devenv test`. Record which ones carried the template default — that number is
the live half of §12 rule 4 and nothing has measured it directly.

```
batch 1: atuout, atuout-reconciler-test, boomtube, browsee, cairn,
         embeddy, fleetman, forgelab, fornix, grail
batch 2: knappy, nixbuild, templateer_v2, tyo3, zelligate,
         + loci-core (the one repository with an existing `<x>:test` task),
         + allium-env, argentic, copyroom, docman
```

### Batches 3–5 — the 27 with a suite and no task

```
batch 3: eventic, flora, flora-core, flora-qc, foreman,
         gitman, image-gen-pipeline, interplay, llgym, lodestar
batch 4: my-ai, mypi-agent, nix-nvim, nix-secrets, nixvim,
         pytuin, repoman, shellij, structured-agents-v2, talkee
batch 5: terminal-state, testee, vendomat
```

`nix-nvim`, `nix-secrets` and `nixvim` have no Python suite. Follow
`nix-desktop`'s pattern: `base:check` is `nix flake check --no-build` and
`base:test` is `nix flake check`. **A repository with no `tests/` still honours
the contract** — `siteman` is the precedent, and its `base:test` is an offline
end-to-end build.

### The adoption shape, per repository

`devenv.yaml` — add the input and the import:

```yaml
  devman:
    url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=f20a9c11cd6b062aa6646e8b72b9767d7e90a522"

imports:
  - devman/modules
```

`devenv.nix` — the block and the two names:

```nix
  devman = {
    enable = true;
    project = "<name>";
    groups = [ "base" ];
  };

  tasks = {
    "<name>:lint".exec = "<the repo's linter>";
    "<name>:test".exec = "<the repo's suite>";
    "base:check".after = [ "<name>:lint" ];
    "base:test".after = [ "<name>:test" ];
  };
```

Then `devenv shell -- true` to register, and `devman run check` / `devman run
test`.

### Each batch ends with proof before the next begins

- registry count and `devman doctor` clean
- `devman run check` and `devman run test` in each, with the status from
  `metadata.jsonl`
- **`git rev-list --count @{u}..HEAD` per repository** — wave 1's five adoption
  commits sat unpushed for a day and every other proof passed anyway. **The push
  is not observable from the plane.**
- **I-2b at each batch**: `devman doctor` timed five times. The curve is
  83.6 ms/file (I-2a), 87 at 6 projects, 78.9 at 34 workflows. It is still the
  closure's **serial** `check_load`; R-4f is merged and not installed.
- **I-1 at each batch**: the next morning's scheduled `maintain` runs and the
  single `plane-report`.

## Not in scope

- **Repairing the four unadoptable repositories**, or any recorded failure.
- **`nixos-rebuild switch`.** Say it is needed; do not run it.
- **The tail** — I-7, I-10, I-12, I-13. They gate nothing. I-10 feeds R-4c,
  which stays unbuilt.
- **R-4a** (refused), **R-4b** (not needed), **R-4c** and **R-4e** (held). Do not
  reopen without a new measurement.
- **Rewriting `watch.py`, `run.py`, `show.py` or `registry.py`.**
- **The empty directory** `${DEVMAN_PROJECT_DIR:-$DEVMAN_SELF_DIR}` in devman's
  root. Recorded in I-4b, deliberately left.

## Traps this environment already sprang

- **Landing on `main` is blocked by the permission classifier** — `gh pr merge`,
  `git branch -f main` and `git push <branch>:main` were all refused, as was
  editing `settings.json` to allow them. **Open a PR and let the owner merge.**
  Pushing a repository's own `main` when the commit is already on local `main`
  does work — that is how the adoptions land.
- `pkill -f 'dagu start-all'` kills **the user's real Dagu service** — the
  throwaway and the unit share a command line. Kill by recorded PID or by
  `DAGU_HOME=` match.
- A synthetic `metadata.jsonl` line must use compact JSON separators.
  `json.dumps` inserts a space after the colon and `grep -F` will not match it.
- Editing a `.devman/workflows/` file **does** re-project since R-8. Editing a
  file under `groups/` or `modules/` still needs `rm -f .devenv/nix-eval-cache.db*`
  before the shell entry.
- `nix flake check .#checks.x86_64-linux.<name>` is not valid. Use
  `nix build --no-link --print-build-logs .#checks.x86_64-linux.<name>`.
- **Nix caches a successful check.** Re-running `nix flake check` after a pass is
  a cache hit and proves nothing. Force with `nix build --rebuild`, or
  `nix store delete` the output first.
- In this shell `ls` and `cat` are aliased to eza and bat; use `find -printf` and
  `sed`/`head` for plain output. `EPOCHREALTIME` is unset — use `date +%s%N`.
- `systemctl --user` needs `XDG_RUNTIME_DIR=/run/user/$(id -u)` and
  `DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus` exported first.
- A cold `devenv shell` can take minutes — `terminal-state` took 568 s once and
  3 s immediately after. **A timeout measures the cache, not the repository.**
  Re-run before recording a failure.
