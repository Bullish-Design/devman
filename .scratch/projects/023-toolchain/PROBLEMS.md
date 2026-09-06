# Current problems, ranked by what they can cost

## P1 — `import pyjutsu` fails in every adopter's devenv (correctness)

Measured M3. `groups/changelog/workflows/changelog.yaml` steps `gate` and
`write` cannot run as written. The shared toolchain venv lends `gitman` through
`PATH` and cannot lend `pyjutsu` through `sys.path`.

Failure mode: the run fails loudly, which is the good half. The bad half is
that both `repoman doctor` and `gitman doctor` report `pyjutsu` green (M6),
because each asks its own interpreter and neither asks the step's.

## P2 — `templateer` reaches devman through residue

`_agent_factory_spike_siblings.pth` inside `.devenv/state/venv/` injects four
sibling repositories into `sys.path`. No file in any repository writes it; it is
left over from project 005. It is inside a gitignored directory, so nothing sees
it. `import templateer`, `import pydantic` and `import yaml` in devman's devenv
all resolve through it today.

This is a rule-4 hazard in the charter's own sense: the plane can succeed while
depending on a file that exists on exactly one machine and that a
`devenv gc` or a `rm -rf .devenv` would delete without warning.

## P3 — two `repoman`s, and PATH order picks between them

Home Manager installs `repoman 0.7.0` on python 3.12. The toolchain venv holds
`repoman 0.7.1` on python 3.13, editable. In a login shell you get 0.7.0; inside
any devenv you get 0.7.1. `rlist` / `rstatus` / `rsync` in `.zshrc` all run
0.7.0.

## P4 — `devenv` installed imperatively, shadowing the declared one

`nix profile` holds `devenv 2.1.2` and `~/.nix-profile/bin` sits ahead of
`/etc/profiles/per-user/andrew/bin` on `PATH`. The Home Manager `devenv` is
never used. `nix-meta/flake.nix` also pins `devenv v2.2` as a flake input with a
comment describing it as the toolchain pin, but `profiles/developer.nix` puts
`pkgs.devenv` in `home.packages`, so the pin does not reach the binary anyone
runs. Three declarations, one imperative install, and the imperative one wins.

## P5 — `git+file:` inputs read dirty working trees

`shellij`, `repoman`, `atuout`, `nix-paseo`, `nix-terminal` are consumed as
`git+file:///home/andrew/Documents/Projects/...`. Measured: entering devman's
devenv prints `warning: Git tree '.../repoman' is dirty`, and a cold evaluation
takes 6.05 s against 0.755 s warm (M2). Nothing records what was used. The
nix-meta flake already documents two inputs disabled for exactly this reason
(shellij, zelligate, both 2026-08-01).

## P6 — the serving stack is declared in Nix but not built by it (weak)

**Corrected 2026-09-06 after re-checking.** The router is **up and correct**:

```
$ systemctl --user status inferference-router.service
   Active: active (running)   Main PID: 2852392 (llama-server)
$ curl -s http://127.0.0.1:8100/v1/models
{"data":[{"id":"gemma", ... "status":{"value":"loaded"} ...
```

It **is** configured through nix-meta: `machines/server.nix` imports
`inputs.inferference + "/nix/nixos-module.nix"` from the pinned flake input and
sets `services.inferference-router = { enable; user; repoDir; }`, plus an
explicit `systemd.user.services.inferference-router.environment.PATH`. My first
reading caught a transient `activating (auto-restart)` during a model load and
drew the wrong conclusion from it.

What remains is a documented owner trade-off, not a defect: `repoDir` points at
the checkout, so the `llama-server` build under `ci/modea/server/` and the
launch script are not store paths, and the resident set lives in
`~/.config/inferference/{placement.yaml,models/*.yaml}`. The module states the
reason — changing the resident set must be an edit plus
`inferference-reconcile.py apply`, never a rebuild — and the unit is
fail-closed if those files disappear. The only cost is that the serving stack
is not rebuildable from the flake alone. That is inferference's call, and it is
recorded there.

**Note for the changelog workflow, measured on the live endpoint:** gemma
returns `reasoning_content` alongside `content`. At `max_tokens: 16` it
returned `finish_reason: "length"` and `content: ""` — a successful HTTP 200
carrying an empty artifact. At `max_tokens: 300` it returned
`finish_reason: "stop"` and `content: "ROUTER OK"`. A generation step that
reads `content` without checking `finish_reason` will write an empty changelog
section and exit 0. That is precisely the rule-4 hazard the workflow's own
comment names.

## P7 — a dormant third `gitman`

`uv tool install --editable ~/Documents/Projects/gitman` created
`~/.local/bin/gitman` (dated today). `~/.local/bin` is not on `PATH`, so it does
nothing. It becomes a silent third source the day anything adds that directory —
and `~/.local/bin` is a directory many tools add by default.

## P8 — `repoman.lock` pins a floor, not a version

`source = "wheel:pyjutsu>=0.20.0"` with `--upgrade`. The installed wheel is in
fact the hashed GitHub release (`direct_url.json` confirms
`.../v0.20.0/pyjutsu-0.20.0-cp313-abi3-manylinux_2_39_x86_64.whl`), but nothing
records that. The next `repoman-sync --machine` takes whatever the wheelhouse
holds. By contrast `gitman/uv.lock` pins the exact URL **and** a sha256. The
authoritative pin already exists — the machine lock just does not use it.

Also: `repoman-sync --machine` refuses when `UV_FIND_LINKS` is unset, and only
repoman's own devenv sets it. The machine's toolchain can therefore be rebuilt
from exactly one directory on exactly one machine.

## P9 — no tool reaches an interactive shell

Measured: a login shell has no `gitman`, no `uv`, no `jj`, no `templateer`.
Every use requires `cd` into a repository and `devenv shell`, at 0.755 s warm
and 6 s cold. This is the ergonomics complaint behind the whole question.

## P10 — mutable state not represented in configuration

- `~/.local/share/repoman/venv` — the whole shared toolchain. Not rebuildable
  offline, not rollback-able, four `--editable` entries.
- `~/.cache/uv`, 43 GB.
- `~/Documents/Projects/pyjutsu/target`, 6.9 GB.
- `~/.local/share/uv/python/cpython-3.12` and `cpython-3.14` — two uv-downloaded
  interpreters that Nix does not know about.
- `/home/andrew/$h`, root-owned, from a `%h` that did not expand.
