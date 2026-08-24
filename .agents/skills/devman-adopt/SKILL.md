---
name: devman-adopt
description: Bring a repository into the devman automation plane — the two devenv.yaml lines, the three devenv.nix keys, the two task names, and the proof. Holds the per-ecosystem task recipes and the adoption failures measured across the 53-repository rollout.
auto_trigger:
  keywords: ["adopt devman", "join the plane", "register a repository", "devman.enable", "devman project groups", "devman input pin", "base:check base:test", "devenv.yaml devman", "repository not registered", "no such task base:test", "devman doctor stale"]
---

# devman-adopt — bringing a repository into the plane

Read the `devman` skill first for the model. This one is the procedure and the
recipes.

**Adoption is four edits in two files, plus one shell entry.** The rollout across
53 repositories measured the per-repository cost at **one `devenv.nix` task
line** plus the input line. What went wrong was never the plane — it was the
repository's own environment.

---

## 0. Pre-check first, before editing anything

```bash
cd <repo>
devenv shell -- true            # MUST pass before any edit
```

**A repository that cannot enter its own devenv shell cannot be adopted.** Shell
entry is the only registration path there is. Two repositories in wave 2 were
pinned to the plane and could never register, which is worse than not being
pinned: the pin is config that does nothing and goes stale.

If the shell fails, fix that first and **revert any devman edits** rather than
committing them.

The measured example: `error: git-hooks or pre-commit-hooks input required`,
thrown by devenv's own integration module while evaluating `config.shell`. The
fix is one input:

```yaml
pre-commit-hooks:
  url: github:cachix/pre-commit-hooks.nix
```

> **A correlation is not a mechanism.** Wave 2 matched a perfect five-for-five
> correlation between this failure and one unrelated input's `flake:` setting,
> "fixed" it, and nothing changed. Trace the error to the throwing line.

Then check the tools the tasks will call — **in the task environment, not the
interactive shell**:

```bash
devenv shell -- command -v pytest ruff     # necessary, NOT sufficient
```

**The task runner's PATH is not the interactive shell's PATH.** Both directions
were measured:

- `fleetman`'s venv has `pytest` and the interactive shell finds it;
  `devenv tasks run base:test` failed with `pytest: command not found`. The task
  environment does not put the venv bin on PATH. The answer is `uv run pytest`.
- `forgelab` inverted it: the interactive shell failed with 45
  `ModuleNotFoundError`, and the plane's own run passed — 85 tests, OK, three
  times. The task environment reached a machine venv the shell did not.

**The task environment is the one that matters.** Prove the task, not the shell.

---

## 1. `devenv.yaml` — the input and the import

```yaml
inputs:
  devman:
    url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>"

imports:
  - devman/modules
```

| Rule | Why |
|---|---|
| **`git+https` with an explicit `rev`** | that form records `rev` **and** `narHash` in `devenv.lock`. `git+file` records neither and silently follows the branch head, so a local checkout is never pinned |
| **`devman/modules`, not `devman/modules/devenv.nix`** | devenv resolves `<input>/<subdir>` and then looks for `devenv.nix` inside it. A `default.nix` is never consulted, and the error names a file you did not write |
| **the rev must be on `main` and pushed** | every consumer resolves the URL from the remote. A commit that exists only locally cannot be pinned |

For local iteration on the plane itself, use a fixed `path:` copy — never
`git+file`.

---

## 2. `devenv.nix` — three keys

```nix
devman = {
  enable  = true;
  project = "myproject";
  groups  = [ "base" ];
};
```

| Key | Rule |
|---|---|
| `enable` | required |
| `project` | **required, no default.** Identity is stated, never inferred from the directory name — otherwise a rename re-registers the repository as new and loses its run history |
| `groups` | defaults to `[ "base" ]`. `[ ]` is legal: the repository then has only its own `.devman/workflows/` |

Two more exist: `registryDir` (must match the machine's) and `installClient`
(puts the Dagu client on this shell's PATH, default true).

**Take `format` or `release` only if the repository wants what they cost:**

```nix
groups = [ "base" "format" ];    # a .py save now rewrites your source
groups = [ "base" "release" ];   # one workflow nothing fires on its own
```

A repository still naming `python` or `python-format` keeps working — both are
tombstones — but rename `python-format` to `format` and drop `python` when you
next edit the file.

---

## 3. The two task names

```nix
tasks."base:check".exec = "ruff check .";
tasks."base:test".exec  = "pytest";
```

| Task | Means | Budget |
|---|---|---|
| `base:check` | the fast check that needs no build and runs no test | ≤ 5 s warm |
| `base:test` | the test suite | ≤ 5 min |

**The `base:` prefix is not decoration — devenv requires `namespace:name`.** An
un-namespaced name is an evaluation error.

### If the repository already has its own task graph, alias

One line each, no duplicated command body. A task with only `after` runs its
dependencies and then does nothing itself, and a failure in a dependency still
fails the run.

```nix
tasks."base:check".after = [ "python:lint" "python:typecheck" ];
tasks."base:test".after  = [ "python:test" ];
```

### If the repository cannot honour a name

**Do not define it.** `devman run check` then fails loudly with devenv's own
`no such task`. **Never write `base:check = true`** — a workflow that reports
success having checked nothing is the one failure the whole design exists to
prevent.

---

## 4. The recipes, by what the repository is

These are the shapes the 53-repository rollout actually used.

### Python, tools in the venv

```nix
tasks."base:check".exec = "ruff check .";
tasks."base:test".exec  = "pytest";
```

### Python, tools in an extra or a group the venv does not install

The most common case in the rollout. `pytest` in
`[project.optional-dependencies].dev` is not in devenv's venv, which installs
only base dependencies.

```nix
tasks."base:test".exec = "uv run --extra dev pytest";
tasks."base:test".exec = "uv run --group dev pytest";     # PEP 735 groups
tasks."base:test".exec = "uv run --extra dev --extra scrape pytest";
```

### Python, the venv bin is not on the task runner's PATH

```nix
tasks."base:test".exec = "uv run pytest -q";
```

### Python, no ruff configured

```nix
tasks."base:check".exec = "python -m compileall -q src";
```

### Python, `unittest` rather than pytest

```nix
tasks."base:test".exec = "PYTHONPATH=src python -m unittest discover -s tests";
```

### Python, the devenv's `PYTHONPATH` shadows the venv

Symptom: `No module named 'pydantic_core._pydantic_core'` at collection, while
the correct `.so` for the venv's Python version is present. A chain of Nix
site-packages for a **different** Python version is prepended to `PYTHONPATH`.
State the environment the task needs:

```nix
tasks."base:test".exec = "env -u PYTHONPATH uv run --extra dev pytest";
```

The devenv's `PYTHONPATH` stays the repository's own misconfiguration — reported,
not changed by the adoption.

### A Nix flake

The Nix case was never the hard one. `nix flake check` splits cleanly:

```nix
tasks."base:check".exec = "nix flake check --no-build";
tasks."base:test".exec  = "nix flake check";
```

One builds nothing and one builds everything, which is exactly the two rungs.
Used by every Nix repository in the plane.

### A Neovim plugin, or Lua

Either the flake answer above, or `luacheck` plus a headless `nvim` run. A Lua
repository takes `base` and nothing else — there is no `lua` group and there will
not be one.

### A repository with no language files

`siteman` is the hardest case in the inventory and honours the contract with two
ordinary lines calling its own devenv shell functions:

```nix
tasks."base:check".exec = "fmt-check && lint";
tasks."base:test".exec  = "ci";
```

### A repository with genuinely nothing to test

4 of 58 were in this class. **This is a decision, not a line.** Options, in
order of preference:

1. Point `base:test` at whatever proves the repository still works — an offline
   end-to-end build, a flake check, a schema validation.
2. Take `groups = [ ]` and write the repository's own `.devman/workflows/`.
3. Do not adopt it yet.

**Never** point it at something that exits 0 having done nothing.

### `enterTest` is not a `base:test`

19 of 58 repositories had an `enterTest` and nothing else, and **7 of the 15
examined carried the devenv template default** — which exits 0 having tested
nothing. `devenv test` was measured at 5.6 s in `copyroom` and 15.2 s in
`nix-paseo`, both testing nothing. That is why `full-test` was deleted.

Read the `enterTest` before aliasing to it. If it is the template default, point
`base:test` at the real suite instead.

---

## 5. Register and prove it

```bash
devenv shell -- true                 # registers; there is no `devman register`
devman show                          # groups, and where each workflow came from
devman run check
devman run test
devman doctor                        # must exit 0
tail -2 .devman/.runs/metadata.jsonl
```

The proof for one repository:

- `devman show` lists `check`, `test` and `maintain` from group `base`.
- `devman run check` and `devman run test` both reach `metadata.jsonl`.
- `devman doctor` exits 0, and the project count went up by one.
- The next night leaves one `maintain-<run id>.md` under
  `.devman/.runs/reports/`.

### Record a pre-existing failure; do not repair it

**Adoption and repair are separate passes.** A `check` that fails on 83 ruff
findings, or a suite with a pre-existing failing test, is recorded as adopted with
a known failure. Prove it is pre-existing with a control:

```bash
git stash push -- devenv.yaml devenv.nix
devenv shell -- ruff check .          # same failure => not a migration regression
git stash pop
```

---

## 6. Commit and push — and push is not optional

```bash
git add devenv.yaml devenv.nix devenv.lock
git commit -m "chore(devman): adopt the stage-7 workflow set"
git push
git rev-list --count @{u}..HEAD       # MUST be 0
```

> **The push is not observable from the plane.** A projection reads the working
> tree, not the remote, so every proof above passes identically whether or not
> the commit was pushed. Wave 1's five repositories were committed and not pushed
> for a day, and nothing on the machine noticed. **Check `@{u}..HEAD` per
> repository.**

---

## 7. What registration creates and touches

```
<repo>/.devman/workflows/            your own workflow files — TRACKED
<repo>/.devman/.runs/logs/           each step's stdout and stderr
<repo>/.devman/.runs/reports/        what a run leaves for a person
<repo>/.devman/.runs/artifacts/      what a run builds — never auto-pruned
<repo>/.devman/.runs/metadata.jsonl  one line per run
```

Plus one line in `.git/info/exclude` — never in `.gitignore`, which may be a
read-only store symlink and which is tracked, so writing to it would dirty the
tree the rule exists to keep clean.

Machine side:

```
~/.local/share/devman/projects/<project>/metadata.json
~/.local/share/devman/projects/<project>/workflows/<workflow>.yaml   (generated)
~/.local/share/devman/dags/<project>-<workflow>.yaml -> the line above
```

**`.devman/` belongs to the repository.** devman reserves `workflows/` and
`.runs/` inside it and never reads, writes or inspects anything else there. A
whitelist that refused unknown entries was removed at stage 7.

**The registry is derived.** Everything under `~/.local/share/devman/` is
reconstructable by re-entering every registered repository's shell, which is what
makes `devman doctor --prune` safe.

---

## 8. Adoption failures, and what each one means

| Symptom | Cause | Fix |
|---|---|---|
| shell entry fails before any devman edit | the repository's own devenv | fix it first; revert the devman edits meanwhile |
| `devman: group 'X' does not exist` | a group that was deleted without a tombstone | rename the group. `python` and `python-format` are tombstones and do **not** throw |
| `× Invalid task name: check` | devenv requires `namespace:name` | `base:check` |
| `no such task base:test` | the group was taken, the name was not defined | define it, or drop the group |
| `pytest: command not found` in a task, but present in the shell | the task runner's PATH is not the shell's | `uv run pytest` |
| `ModuleNotFoundError` for the project's own package | the venv's editable install, or a shadowing `PYTHONPATH` | `env -u PYTHONPATH uv run …`, or fix the venv |
| the shell entry says nothing at all | **by design.** devenv runs the hook twice, and the firing that performs the write has its output discarded. There is no `devman: registered` line and there cannot be one | `devman show` to confirm |
| `refusing to resolve 'X' from this directory` | a git worktree or submodule **inside** a registered checkout. It never registers, so a run typed there would target the outer project | give it a distinct `devman.project`, or pass `--project` |
| two projects claim one DAG name | `<project>-<workflow>` is not injective: `devman-b` + `check` and `devman` + `b-check` collide | rename one project or one workflow, then re-enter both shells |
| a registry entry for a repository that is gone | a deleted checkout. It does not expire on its own | `devman doctor --prune`; it restores itself if the checkout returns |

---

## 9. Leaving the plane

Remove the three keys, the input and the import. Then:

```bash
devman doctor --prune
```

The `.devman/.runs/` tree stays with the checkout. Nothing on the machine
outlives the prune.
