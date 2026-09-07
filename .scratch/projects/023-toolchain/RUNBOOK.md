# Runbook: fixing the toolchain, step by step

> **Superseded in part by `TARGET.md` (2026-09-06).** Measurement showed the
> vendomat wheelhouse is two mechanical steps from producing the published
> artifact, so "Face A was retired correctly" is too strong. Read `TARGET.md`
> before acting on the Face A / `[tool.uv.sources]` guidance here.


Read `RECOMMENDATION.md`, `VENDOMAT.md` and `FLEET.md` first. This file is the
executable form.

**The governing rule:** a console script is a property of the machine; an import
is a property of the repository that imports it. Every step below either moves
something to the correct side of that line, or removes a second owner of a name.

**Version control.** For devman, route every mutation through gitman — start a
lane, save, publish, open a PR to `main`. Never raw `git`/`jj`. Other repos:
follow their own rules. Do not batch unrelated phases into one lane.

**How to use this.** Each step has: goal, commands, verification, rollback.
Verification must pass before you move on. Stop at the end of any phase and the
machine is consistent.

---

# Phase 0 — stop the bleeding

Zero risk. Nothing depends on any of it. Do it in one sitting.

## Step 0.1 — delete the spike `.pth`

**Goal:** remove the undeclared `sys.path` injection (P2) so the real dependency
gap becomes visible instead of masked.

```bash
rm /home/andrew/Documents/Projects/devman/.devenv/state/venv/lib/python3.13/site-packages/_agent_factory_spike_siblings.pth
```

**Verify** — this must now FAIL, and that is the success condition:

```bash
cd ~/Documents/Projects/devman
devenv shell -- python3 -c 'import templateer'   # expect ModuleNotFoundError
```

**Rollback:** recreate the file with the single line recorded in
`INVENTORY.md` §3. You will not want to.

## Step 0.2 — remove the dormant third gitman

**Goal:** P7. `~/.local/bin` is not on `PATH` today; the day anything adds it,
this shadows the toolchain.

```bash
uv tool uninstall gitman     # from inside any devenv, uv is not on the login PATH yet
ls -la ~/.local/bin/gitman   # expect: No such file
```

**Rollback:** `uv tool install --editable ~/Documents/Projects/gitman`.

## Step 0.3 — remove the imperative devenv

**Goal:** P4. `~/.nix-profile/bin` precedes `/etc/profiles/per-user`, so this
imperative copy wins over the declared one. Both are 2.1.2 today, by luck.

```bash
nix profile list                       # confirm: act, devenv
nix profile remove devenv
command -v devenv                      # expect /etc/profiles/per-user/andrew/bin/devenv
devenv --version
```

**Verify:** enter one devenv and confirm it still works.

```bash
cd ~/Documents/Projects/devman && devenv shell -- true
```

**Rollback:** `nix profile install nixpkgs#devenv`.

> Decide separately whether Home Manager should install `pkgs.devenv` (2.1.2) or
> the `devenv v2.2` your `nix-meta/flake.nix` already pins and nothing uses.
> That is open question 7; it is not blocking, and moving ~60 devenvs onto a new
> devenv is its own change.

---

# Phase 1 — one owner per name

Low risk, one NixOS rebuild, fully reversible with `--rollback`.

## Step 1.1 — put `uv` and the toolchain venv in the login shell

**Goal:** P9. Today a login shell has no `gitman`, no `uv`, no `jj`.

Edit `nix-meta/profiles/developer.nix`. In the `nix-meta.developer.packages`
default list add `uv`:

```nix
default = with pkgs; [
  gh
  nodejs
  python3
  uv          # ad-hoc `uv run --with ...` without entering a devenv
  devenv
];
```

In the same file's `users.${username}` block add:

```nix
# The RepoMan shared toolchain's console scripts, for interactive use.
# LAST on sessionPath, so it can never shadow a Nix-managed binary.
# It is the same venv repoman/modules/devenv.nix already prepends inside a
# devenv; this adds no second copy of anything.
home.sessionPath = [ "${homeDir}/.local/share/repoman/venv/bin" ];
```

**Apply and verify:**

```bash
cd ~/Documents/Projects/nix-meta
sudo nixos-rebuild test --flake .#server      # test first: not persisted across reboot
zsh -lic 'command -v uv gitman repoman; gitman --version'
```

Expected: `uv` from `/etc/profiles/per-user/...`, `gitman` from the toolchain
venv. Then `sudo nixos-rebuild switch --flake .#server`.

**Rollback:** `sudo nixos-rebuild --rollback`, or revert the two edits.

## Step 1.2 — remove the second `repoman`

**Goal:** P3. Home Manager ships `repoman 0.7.0` on **python 3.12**; the
toolchain venv has `0.7.1` on 3.13. PATH order decides, and your `rlist` /
`rstatus` / `rsync` aliases get 0.7.0.

Do this **after** 1.1, so a login shell still has a `repoman` when the Home
Manager one goes away.

In `nix-meta/profiles/developer.nix`, set:

```nix
programs.repoman.enable = false;
```

Keep the aliases. `nix-terminal/modules/repoman.nix` defines
`rsync`/`rlist`/`rstatus` alongside the package, so if disabling the module
takes the aliases with it, re-declare the three in the terminal profile.

> Checked: `grep -rn 'repoman.toml\|repoman.yaml\|\.config' repoman/src/`
> returns nothing. The `xdg.configFile."repoman/repoman.toml"` that module
> writes is not read by repoman 0.7.1. Losing it costs nothing. Re-verify
> before you delete it.

**Verify:**

```bash
zsh -lic 'type -a repoman'      # expect exactly ONE line, the toolchain venv
zsh -lic 'repoman --version'    # expect 0.7.1
cd ~/Documents/Projects/devman && devenv shell -- repoman doctor
```

**Rollback:** `sudo nixos-rebuild --rollback`.

## Step 1.3 — record the interpreter baseline

**Goal:** make the decision explicit before anything depends on it.

Write into `nix-meta/profiles/developer.nix` as a comment, and into
`repoman`'s `AGENTS.md`:

> **Python baseline: 3.13.** Every first-party CLI, the shared toolchain, and
> every devenv target CPython 3.13. `pyjutsu` ships `cp313-abi3`, which loads on
> 3.13 and forward and **cannot** load on 3.12 — measured:
> `ImportError: _pyjutsu.abi3.so: undefined symbol: Py_GetConstantBorrowed`.

`repoman/flake.nix:21` still builds `packages.default` with
`python312Packages`. After 1.2 nothing installs it, so it is no longer a live
hazard — but it must be moved to `python313Packages` before Face D packages
anything from that flake. Do it now while it is cheap:

```bash
cd ~/Documents/Projects/repoman
# flake.nix: python312Packages -> python313Packages (3 sites: lines ~21, ~28, ~34; plus the devShell at ~87)
nix build .#default --no-link
```

**Verify:** `nix build` succeeds and the wrapper references `python3-3.13.*`.

**Rollback:** revert the file; nothing consumes this output after 1.2.

---

# Phase 2 — make the changelog workflow correct

Medium risk, contained to two repositories. This is the phase that fixes P1.

## Step 2.1 — add `gitman log` to gitman

**Goal:** close the API gap that forces a workflow to `import pyjutsu`.
Confirmed: `gitman log` does not exist; the CLI is all lane-lifecycle verbs.

In `~/Documents/Projects/gitman`, on a gitman lane, add:

```
gitman log --revset '<a>..<b>' --json
```

emitting one object per change with at least `change_id` and `description`.
That is exactly what `changelog.yaml` reads today through
`pyjutsu.Workspace.load(".").log(...)` and `ws.resolve(cid).description`.

Requirements:
- JSON to stdout, nothing else. Diagnostics to stderr.
- Non-zero exit on a bad revset, with the revset in the message.
- Tests for: empty range, single change, a revset that does not parse.

**Verify:**

```bash
cd ~/Documents/Projects/gitman
devenv shell -- gitman log --revset 'main~5..main' --json | python3 -m json.tool | head
devenv tasks run test          # gitman's own suite
```

**Rollback:** abandon the lane. Nothing consumes it yet.

## Step 2.2 — publish templateer as a pinned artifact

**Goal:** R2 / P2. Replace `PYTHONPATH=$TEMPLATEER_PATH/src` plus
`uv run --project <sibling>` with a versioned dependency.

`templateer` is pure Python (`hatchling`, no native code), so it does **not**
need the pyjutsu machinery. A git tag is enough and uv records a hash for it:

```bash
cd ~/Documents/Projects/templateer_v2
# bump version in pyproject.toml, then tag and push through gitman
devenv shell -- gitman start release-0-3-1
# ... version bump ...
devenv shell -- gitman save -m "release 0.3.1"
devenv shell -- gitman publish
```

Then the dependency spelling anywhere that needs it:

```toml
[tool.uv.sources]
templateer = { git = "https://github.com/Bullish-Design/templateer_v2", tag = "v0.3.1" }
```

> If you would rather have a wheel asset like pyjutsu's, copy
> `pyjutsu/devenv.nix`'s `pyjutsu:wheel` / `pyjutsu:publish` task pair. For a
> pure-Python project you need neither `relocate_wheel.py` nor the
> `_PYTHON_HOST_PLATFORM` unset — both exist only because of the native
> extension. A git tag is the smaller correct answer; take the wheel route only
> if you want offline installs.

**Verify:** in a scratch directory,

```bash
uv run --with 'templateer @ git+https://github.com/Bullish-Design/templateer_v2@v0.3.1' \
  templateer --help
```

## Step 2.3 — put `templateer` on the machine's CLI shelf

**Goal:** the workflow calls a console script, so devman needs no venv.

Add to `repoman/repoman.lock`:

```toml
# templateer: typed artifact generation. A CLI on the shared shelf, not a
# library any repo imports — the changelog workflow calls `templateer generate`.
[managers.template]
package = "templateer"
source = "git+https://github.com/Bullish-Design/templateer_v2@v0.3.1"
```

Then re-sync the machine toolchain:

```bash
cd ~/Documents/Projects/repoman
devenv shell -- repoman-sync --machine
```

**Verify:**

```bash
zsh -lic 'command -v templateer && templateer --help | head -3'
~/.local/share/repoman/venv/bin/python -c 'import templateer, pyjutsu, gitman; print("shelf ok")'
cd ~/Documents/Projects/devman && devenv shell -- repoman doctor
```

`repoman doctor` verifies the whole venv is mutually compatible — this is the
check for open question 5 (does templateer's `pydantic-ai-slim[openai]` +
`minijinja` tree coexist with gitman's). **If it refuses, stop here** and decide
whether templateer belongs on the shared shelf or stays group-scoped.

**Rollback:** remove the lock entry, re-run `repoman-sync --machine`.

## Step 2.4 — rewrite `changelog.yaml`

**Goal:** P1. Both `import pyjutsu` blocks and the `PYTHONPATH` /
`uv run --project` line go away.

In `groups/changelog/workflows/changelog.yaml`:

- `gate`: replace the heredoc with `devenv shell -- gitman log --revset
  "$last..$trunk" --json`, filtered by "an entry file exists" as today.
- `write`: same, for the subject lookup.
- `summarize`: drop `PYTHONPATH=` and `uv run --project "$TEMPLATEER_PATH"`.
  Call `templateer` directly — it is on `PATH` from 2.3.
- `params`: delete `TEMPLATEER_PATH`. Change `TEMPLATEER_TEMPLATE_PATH` to
  resolve through `$DEVMAN_SELF_DIR`, since the templates are group assets.
- **Add a `finish_reason` check.** Measured: gemma returns `content: ""` with
  `finish_reason: "length"` on a short budget — an HTTP 200 carrying nothing.
  Fail the step on anything but `stop`.

**Verify:**

```bash
cd ~/Documents/Projects/devman
grep -n 'TEMPLATEER_PATH\|PYTHONPATH\|import pyjutsu' groups/changelog/workflows/changelog.yaml
# expect: no matches
devenv shell -- dagu validate groups/changelog/workflows/changelog.yaml
devenv tasks run -v base:check
devenv tasks run -v base:test
devman doctor
```

Then the real end-to-end, as the 022 kickoff already requires: a disposable
adopter, real `gitman start` / `save` / `land`, the real post-hook enqueue, the
chained run reaching generation, and a person reading the lane diff. Plus both
refusals: empty batch, and a second unreviewed lane.

**Rollback:** revert the workflow file. It cannot regress anything — the current
form does not work.

## Step 2.5 — make the gap checkable

**Goal:** M6. Both doctors report `pyjutsu` green while a step fails, because
each asks its own interpreter.

Add to the `changelog` group's gate, or to `devman doctor`:

```bash
devenv shell -- gitman log --revset 'x..x' --json >/dev/null
devenv shell -- templateer --help >/dev/null
```

Run it the way a **step** runs it. A check that cannot fail proved nothing;
before Phase 2 this one fails.

---

# Phase 3 — make the machine reproducible elsewhere

Medium risk. This is Vendomat Face C, which is built and has zero users.

## Step 3.1 — one `vendomat.toml` per editable manager

**Goal:** P8. Four entries in `repoman.lock` are `--editable` installs of live
working trees, so the toolchain cannot be rebuilt on another machine (V6).

For each of `gitman`, `repoman`, `copyroom`, `docman`, at the repo root:

```toml
[[replacement]]
files = ["repoman.lock"]
local = "path:/home/andrew/Documents/Projects/gitman"
github = "git+https://github.com/Bullish-Design/gitman.git@v0.6.0"
```

The consuming devenv must import `vendomat/modules`; `vendor.publish.enable`
defaults to `true`, and the pre-push hook installs itself on shell entry when a
`vendomat.toml` is present. It refuses to overwrite an existing `pre-push` hook.

**Verify, before pushing anything:**

```bash
cd ~/Documents/Projects/gitman
devenv shell -- vendomat publish --dry-run
```

Read the manifest and lock diff it prints. Vendomat rejects the push if
regenerating `uv.lock` adds, removes, or changes a resolved version — review
that separately if it fires.

> Expect the first push to print a nonzero status: the hook deliberately aborts
> the outer push after pushing the rewritten commits. The
> `published GitHub-source commit(s)` line above it is the success signal. This
> is documented in vendomat's README and it looks like a failure the first time.

**Rollback:** delete `vendomat.toml`; the hook becomes a no-op.

## Step 3.2 — pin the machine lock's pyjutsu entry

**Goal:** P8. `wheel:pyjutsu>=0.20.0` is a floor resolved with `--upgrade`.
The authoritative pin already exists in `gitman/pyproject.toml`.

```toml
[managers.git-pyjutsu]
package = "pyjutsu"
# The published, relocated manylinux asset — the same URL gitman's own
# [tool.uv.sources] names. Not vendomat's wheelhouse: that wheel carries the
# bare linux_x86_64 tag and a RUNPATH into /nix/store (gitman project 35).
source = "wheel:pyjutsu @ https://github.com/Bullish-Design/Pyjutsu/releases/download/v0.20.0/pyjutsu-0.20.0-cp313-abi3-manylinux_2_39_x86_64.whl"
```

Check that `repoman-sync`'s source-form parser accepts this spelling
(`repoman/modules/scripts/repoman-sync.sh`, the `"wheel:"` lambda passes the
rest through to uv verbatim, so a PEP 508 direct reference should work). If it
does not, add a `url:` source form rather than bending `wheel:`.

**Verify:**

```bash
cd ~/Documents/Projects/repoman && devenv shell -- repoman-sync --machine
cat ~/.local/share/repoman/venv/lib/python3.13/site-packages/pyjutsu-0.20.0.dist-info/direct_url.json
# expect the GitHub release URL, unchanged
```

This also removes the `UV_FIND_LINKS` precondition from the machine bootstrap,
which is what currently makes the toolchain rebuildable from exactly one
directory on one machine.

## Step 3.3 — scope Vendomat Face A down in its own docs

**Goal:** stop a future reader re-deriving G3.

In `vendomat/README.md`, state that the wheelhouse is for a native library with
**no published release yet**, during local iteration — and that a published,
relocated, hashed release asset is the shipping path. Cite gitman project 35.

Also: ten of thirteen repos import `vendomat/modules` and enable no face.
Remove the import from those that need nothing
(`nix-secrets`, `nix-nvim`, `loci.nvim`, `nix-paseo`, `nix-desktop`,
`template-nix/golden/*`). They pay a flake input's evaluation and an
`install-hook` probe per shell entry for no output.

---

# Phase 4 — the shared command closure (Vendomat Face D)

Large. Do not start before Phases 0-3 are done and stable. The full design is
`vendomat/.scratch/projects/03-shared-repoman-toolchain/CONCEPT.md`; follow its
§6 phasing, which is already correct. The sketch:

1. **Phase 0 of that concept** — inventory every manager's console script,
   dependencies, and venv-path call sites; add `repoman.cliProvider = "venv"` as
   an unchanged default with regression tests.
2. **Phase 1** — package `copyroom` and `repoman` as Nix Python applications at
   **3.13**. Prove one fixture has no manager in its venv.
3. **Phase 2** — add `testee`, `docman`, one at a time.
4. **Phase 3** — `gitman`, built against the published pyjutsu wheel. Prove a
   `git` consumer pulls no Rust.
5. **Phase 4** — make store mode the default; keep `editable` for tool authors.
6. **Phase 5** — expose the closure through Home Manager, replacing the
   `home.sessionPath` line from step 1.1.

Decide concept §8.2 before writing code: is Vendomat's flake lock authoritative
in store mode, or does `repoman.lock` gain a `toolchain:` source kind? Either
needs a mismatch check, not implicit precedence.

---

# Phase 5 — housekeeping

Not blocking. Do when convenient.

```bash
# 43 GB of uv cache, 6.9 GB of cargo target
uv cache prune
du -sh ~/.cache/uv ~/Documents/Projects/pyjutsu/target

# stale devenv venvs holding old pyjutsu copies
ls ~/Documents/Projects/gitman/.devenv/test-state
ls ~/Documents/Projects/gitman/.worktrees/loci-adoption-fixes

# the root-owned file from a %h that did not expand
sudo rm '/home/andrew/$h'
```

Also open, separately (P5): the `git+file:` inputs across nix-meta and every
devenv. Measured cost is 6.05 s cold evaluation against 0.755 s warm, on every
dependent devenv, after any edit anywhere in the source repo. nix-meta has
already disabled two such inputs for exactly this reason. Vendomat's own
`flake.lock` shows the mitigation works: it pins `pyjutsu` by rev and narHash,
so the lock records what was used even though the input is a local path.

---

# Verification ladder

Run after each phase.

```bash
# 1. one name, one binary
for c in python3 repoman devenv gitman uv templateer; do type -a $c; done
#    ...in a login shell AND inside a devenv. Exactly one line each.

# 2. the environment matrix
zsh -lic 'bash .scratch/projects/023-toolchain/evidence/probe.sh'
devenv shell -- bash .scratch/projects/023-toolchain/evidence/probe.sh
#    Compare to INVENTORY.md §3. Every row: one interpreter, one path per package.

# 3. the plane's own gates
devenv tasks run -v base:check
devenv tasks run -v base:test
devman doctor
devenv shell -- repoman doctor

# 4. a real Dagu step, not a shell
#    Enqueue the real changelog workflow in a disposable adopter and read the
#    step log. A devenv is not a step; the step re-derives its environment from
#    /etc/profile (GRAPH.md §2).
```

# What success looks like

- `zsh -lic 'gitman status'` works, from any directory, in ~1.1 s.
- `type -a repoman` prints one line.
- `changelog.yaml` contains no `import pyjutsu`, no `PYTHONPATH`, no absolute
  sibling path, and runs end to end against the local model.
- `devman`'s devenv venv stays empty and it still has no `uv.lock` — because
  nothing imports across a repository boundary any more.
- `repoman.lock` names four pinned releases, not four working trees, and
  `repoman-sync --machine` needs no `UV_FIND_LINKS`.
- One Python: 3.13, everywhere, stated in writing.
