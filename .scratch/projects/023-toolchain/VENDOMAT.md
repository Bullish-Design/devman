# Vendomat assessment

> **Superseded in part by `TARGET.md` (2026-09-06).** Measurement showed the
> vendomat wheelhouse is two mechanical steps from producing the published
> artifact, so "Face A was retired correctly" is too strong. Read `TARGET.md`
> before acting on the Face A / `[tool.uv.sources]` guidance here.


Read 2026-09-06 at `/home/andrew/Documents/Projects/vendomat`, working tree
clean, HEAD `20ff40e`.

## What it is

Vendomat has four faces. Three are built. The one that answers this
investigation's question is a proposal that was never implemented.

| Face | What it does | Built? | Consumers |
|---|---|---|---|
| **A — artifacts** | builds a native lib once into a content-addressed wheel in `/nix/store`; exports `UV_FIND_LINKS` + `UV_NO_BUILD_PACKAGE` | **yes, and it works** | `repoman` only |
| **B — knowledge** | per-dependency `SKILL.md` install, usage-gated | yes | `loci-core` only |
| **C — publish** | `vendomat.toml` + pre-push hook rewrites local `path:` sources to pinned `git+https://…@tag` in a disposable worktree | yes | **none — no `vendomat.toml` exists anywhere** |
| **D — toolchains** | build the whole RepoMan CLI family as Nix packages; deliver a roster closure on `PATH` | **no — `.scratch/projects/03-shared-repoman-toolchain/CONCEPT.md`, status "proposal", 2026-07-16** | — |

## Face A is ready, and it was deliberately retired for pyjutsu

```
$ nix build .#wheelhouse --print-out-paths
/nix/store/p5w78dj3fm0sbgk08xs3phahk96cl5bw-vendomat-wheelhouse
$ ls .../
pyjutsu-0.20.0-cp313-abi3-linux_x86_64.whl -> ...-pyjutsu-0.20.0/... (7.3 MB)
```

`flake.lock` pins the source properly — `rev 045cc030…` with a `narHash`, and
that rev is the commit tagged `Release 0.20.0`, four commits behind the
checkout's HEAD. This is **more** reproducible than I credited in `INVENTORY.md`
§4: the `git+file:` input is dirty-*sensitive*, but the lock records exactly
what was used.

It is nonetheless not what the machine runs. `gitman/pyproject.toml:66`:

```toml
[tool.uv.sources]
pyjutsu = { url = "https://github.com/.../v0.20.0/pyjutsu-0.20.0-cp313-abi3-manylinux_2_39_x86_64.whl" }
```

An explicit `[tool.uv.sources]` URL overrides `UV_FIND_LINKS`.

**This is not an accident, and it must not be reversed.** gitman project 35
(`OUTCOME.md`, 2026-08-28) decided it deliberately, closing project 32's G3:

> Pyjutsu is a maturin extension that is not on PyPI. It resolved only from
> vendomat's prebuilt wheelhouse via `UV_FIND_LINKS`, which works in gitman's own
> repo and nowhere else: a consumer had to import the same vendomat revision
> gitman was built against, or compile Rust. In loci-core that attempt broke the
> devenv shell outright.

Two further facts make the wheelhouse the *wrong* artifact for shipping, and
both are recorded in that outcome:

1. devenv exports `_PYTHON_HOST_PLATFORM=linux_x86_64`, which overrides
   `--compatibility` and stamps the bare `linux_x86_64` tag. That is exactly the
   tag on the wheel now sitting in the wheelhouse.
2. A nix-built maturin wheel carries a `RUNPATH` into `/nix/store`.
   `pyjutsu/scripts/relocate_wheel.py` strips it for the published artifact. The
   wheelhouse wheel is not relocated.

So the 7.3 MB `linux_x86_64` wheel in the store is the non-portable build, and
the 19.9 MB `manylinux_2_39` release asset is the portable one. The machine is
using the correct one. My first reading of this as "Face A is bypassed" was
wrong: Face A was **superseded on purpose**, and the research report predicted
it — *"vendomat can be removed from gitman's flake inputs when published pyjutsu
wheels become the authoritative artifact source."*

Corroborating that the wheelhouse is not load-bearing: the path recorded in
`~/.local/share/uv/tools/git-filter-repo/uv-receipt.toml`
(`qzm395kmcjj4…-vendomat-wheelhouse`) **no longer exists** — garbage collected,
and nothing noticed.

## Face C is the answer to P8, and nobody has switched it on

`repoman.lock` installs four managers as `--editable` installs of live working
trees, which is why the machine's toolchain cannot be rebuilt anywhere else
(P8, V6). Face C exists precisely for this: keep `path:` locally, rewrite to
`git+https://…@vX.Y.Z` on push, regenerate `uv.lock` in a disposable worktree,
and refuse the push if the resolved graph changes. No repository has a
`vendomat.toml`.

## Face D is the design this investigation independently arrived at

`03-shared-repoman-toolchain/CONCEPT.md` §9, written 2026-07-16:

> Build a **shared, pinned Nix command closure**, not a shared mutable
> virtualenv and not merely a global profile installation.

Project 12 then shipped the shared mutable virtualenv. Everything the concept
warned about is now measured on this machine:

| Concept 03 said | Measured 2026-09-06 |
|---|---|
| §3.4 "must not silently fall back to a venv installation" | the venv **is** the installation |
| §4.1 "use an absolute known path, not merely `command -v`, so a project's unrelated venv cannot shadow a selected shared tool" | `repoman` resolves to 0.7.0 in a login shell and 0.7.1 in a devenv (P3) |
| §8.3 "Vendomat targets Python 3.13 while RepoMan's standalone flake packages Python 3.12. The shared toolchain must choose and document one interpreter baseline" | Home Manager ships `repoman 0.7.0` on **3.12**; the toolchain venv runs **3.13.13**; devenvs run **3.13.14** |
| §7 "Their `.devenv` venvs contain neither the manager distributions nor their console-script wrappers" | `gitman/.devenv/state/venv` holds its own `pyjutsu` copy; 8 copies machine-wide |

Neither `repoman.toolchain.enable` nor `repoman.cliProvider` exists in the
repoman source today. Face D is a document, not code.

## Does Vendomat solve this issue?

**Not the way I first described.** Face A's flagship case is closed, not
pending.

- Native rebuild duplication for `pyjutsu` — **already solved, and not by
  Vendomat.** A published, relocated, hashed `manylinux_2_39` release asset,
  referenced from `[tool.uv.sources]`, is the authoritative source. It works in
  any repo, with or without Nix. Leave it alone.
- Unpinned local `path:` sources in `repoman.lock` — **Face C, built, unused.**
  This is Vendomat's clearest remaining win (P8, V6).
- CLI duplication and PATH-order ambiguity — **Face D, designed, not built.**
  Still the right answer to the other half.

**It does not solve P1, and no packaging tool can.** A store closure lends
console scripts through `PATH`. It cannot put `pyjutsu` on the `sys.path` of a
devenv's own interpreter. The answer to that half is not a distribution
mechanism at all — it is to stop importing across the boundary and call a
console script instead.

## What "Vendomat does its job correctly" now means

Its job is **not** the pyjutsu wheelhouse. The fleet already found a better
pattern for that, twice over, and wrote it down: *publish a portable, hashed
artifact and reference it by URL.* Vendomat's remaining jobs are:

1. **Face C** — turn every `path:` editable in `repoman.lock` into a pinned
   `git+https://…@vX.Y.Z` on push. This is the one thing nothing else does.
2. **Face D** — the shared Nix command closure, replacing the mutable venv.
3. **Face B** — knowledge skills; independent, already working.

Face A should be scoped down in Vendomat's own docs to what it is still good
for: a native library that has **no published release yet**, during local
iteration. Saying so is cheaper than letting a future reader re-derive G3.

## Two smaller observations

1. **Ten of thirteen importers enable nothing.** `nix-secrets`, `nix-nvim`,
   `loci.nvim`, `nix-paseo`, `nix-desktop`, `template-nix/golden/*` and others
   import `vendomat/modules` without setting `vendor.enable` or
   `knowledge.enable`. They pay a flake input's evaluation for no output.
   `vendor.publish.enable` defaults to `true`, so they also run a
   `vendomat install-hook` probe on every shell entry — cheap, but it is the
   "expensive shell-entry hook" anti-pattern in miniature.
2. **Vendomat vends exactly one library.** `flake.nix` has one native input
   (`pyjutsu`). `templateer` is pure Python and needs no maturin, but it needs
   the same *distribution*, and Face A's `mkArtifact` is already generalised
   (`builder = "maturinWheel"` is a parameter). A pure-Python builder would let
   the wheelhouse carry `templateer` too, which is exactly what R2 needs.
