# The clean target: one build, one artifact, two indexes

**This supersedes the "leave Face A retired" reading in `VENDOMAT.md` and step 1
of `FLEET.md`.** Both were written from gitman project 35's outcome document.
That document records a real failure and a fix that worked, but the fix removed
the approach instead of repairing it. Measured below: the repair is two
mechanical steps.

## The experiment

Vendomat's nix-built wheel differs from the published wheel in exactly two ways:

| | vendomat, nix-built | published (devenv maturin + relocate) |
|---|---|---|
| platform tag | `cp313-abi3-linux_x86_64` | `cp313-abi3-manylinux_2_39_x86_64` |
| `RUNPATH` | `/nix/store/…-pyjutsu-0.20.0/lib:/nix/store/…-glibc-2.42-61/lib:/nix/store/…-gcc-15.2.0-lib/lib` | `''` |
| extension size | 19,762,792 | 19,964,296 |

> Correction to `VENDOMAT.md`: I earlier contrasted "7.3 MB" with "19.9 MB".
> That compared a *compressed wheel* against an *installed `.so`*. The two
> extensions are 19.76 MB and 19.96 MB. They are the same artifact, built twice.

Applying pyjutsu's own `scripts/relocate_wheel.py` to vendomat's wheel:

```
$ python3 pyjutsu/scripts/relocate_wheel.py <vendomat wheel, renamed to manylinux tag>
relocated pyjutsu-0.20.0-cp313-abi3-manylinux_2_39_x86_64.whl: removed RUNPATH from 1 extension module(s)

$ patchelf --print-rpath <extracted .so>
''
```

Then installing it into a clean throwaway venv:

```
$ uv venv --python 3.13 $V && uv pip install --python $V/bin/python <relocated wheel>
$ $V/bin/python -c 'import pyjutsu'
import OK 0.20.0

$ patchelf --print-needed $V/.../pyjutsu/_pyjutsu.abi3.so
libgcc_s.so.1
libm.so.6
libc.so.6
ld-linux-x86-64.so.2
```

Those are exactly the four libraries project 35's own outcome lists as *"all
permitted by manylinux"*. **A nix-built vendomat wheel, relocated, is a portable
manylinux artifact.** Nothing about Nix prevents it.

## What G3 actually was

Three causes, conflated in one issue:

| Cause | Intrinsic? | Repair |
|---|---|---|
| bare `linux_x86_64` tag | **no** | `mkMaturinWheel` never passes `--compatibility`. Add it. |
| `RUNPATH` into `/nix/store` | **no** | run the relocate step in `postBuild`. Proven above. |
| consumer needs the *same vendomat revision*, else compiles Rust | **partly** | a store path is only available where the store has it — see below |

Only the third is a real property of Nix, and it has two independent answers.

## The actual defect, stated once

**There are two builds producing two different files carrying the same version
number.** Every downstream symptom follows from that: which one wins,
`[tool.uv.sources]` versus `UV_FIND_LINKS`, "the wheelhouse is bypassed",
"the wheelhouse only works at the matching revision".

If one version means one artifact, the question of which source wins stops
existing, because both sources name the same bytes.

## The design

> **Vendomat is the release engine. It performs the single hermetic build and
> emits the artifact into two indexes — the Nix store and a published release —
> from the same derivation, so the two cannot disagree.**

1. `mkMaturinWheel` gains `--compatibility manylinux_2_39` and the relocate
   step. Its output becomes the artifact, not a second opinion about it.
2. `vendomat publish <lib>` uploads **that exact store file** to the GitHub
   release. Hash equality is by construction, not by luck.
3. Consumers keep `[tool.uv.sources]` with the release URL. Portable, works in
   CI, on a fresh machine, in a repo that has never heard of Nix. **Unchanged
   from today, so nothing regresses.**
4. Nix-native consumers may additionally take `UV_FIND_LINKS` at the store
   wheelhouse. Because the bytes are identical, the `uv.lock` hash is valid
   through either route.
5. **`UV_NO_BUILD_PACKAGE` inverts in meaning.** Today a missing or mismatched
   store wheel fails loudly — which is what took down loci-core's shell. Under
   this design the store is an *accelerator*, not the source of truth, so a
   missing store wheel falls back to the declared URL. That is not a silent
   fallback; the URL is the declaration.
6. Optionally push the wheel derivation to cachix — already on your devenv PATH
   — so a consumer at a different vendomat revision substitutes instead of
   compiling.

What the store index buys, once it can never disagree with the URL: **iteration
ahead of a release.** Edit pyjutsu, one `nix build`, every Nix consumer sees it
without cutting a tag. That is the one thing a URL cannot do, and it is why the
two-index design earns its keep.

One rule keeps the invariant intact: **an iteration build gets its own version**
(`0.21.0.dev0+<rev>`), never the same version as a published release. One
version, one artifact — always.

## Where this lands, with Face D

The design above is worth doing on its own. But it becomes much smaller once the
shared command closure exists, because **pyjutsu stops being a distributed
package at all**:

```
pyjutsu  — native library
   built once by vendomat: hermetic, relocated, manylinux-tagged
   consumed by exactly one thing — the gitman package derivation
   published to a GitHub release for outside adopters, no longer load-bearing

gitman · repoman · copyroom · docman · templateer  — CLIs
   built once by vendomat as Nix Python applications, all at 3.13
   composed into one roster closure
   on PATH in every devenv, the login shell, and every Dagu step

your 62 repos
   declare zero first-party Python dependencies
   call console scripts
   their venvs hold only their own application dependencies
```

The single rule underneath: **no repository imports across a repository
boundary.** That one rule retires P1, P2, P3, P7, P8 and G3 together, because
each of them is a different symptom of a cross-boundary import.

Under it, G3's scenario cannot even be expressed: loci-core never runs
`uv add gitman`, because gitman is not a library it depends on — it is a command
on its PATH.

### What it removes, counted

| | now | after |
|---|---|---|
| `pyjutsu` extension copies | 8, in 3 distinct builds | 1 |
| `repoman` installs | 2, at two Python versions | 1 |
| resolution decided by PATH order | `repoman`, `python3`, `devenv` | none — store paths, absolute |
| `--editable` live working trees in the machine lock | 4 | 0 |
| rollback for the shared toolchain | none | `nixos-rebuild --rollback` |
| Pythons in play | 3.12, 3.13.13, 3.13.14 | 3.13 |

### What it costs, honestly

- Packaging each CLI as a Nix Python application. Concept 03 §8.1 names this as
  the principal cost and it is right: every `pyproject.toml` has to be made to
  build under Nix, one tool at a time.
- Editable mode must stay first-class, or tool authors cannot work. Concept 03
  §3.1 already specifies `store` and `editable` as explicit modes.
- One more thing that can break `nix build` and therefore block a shell. The
  loci-core incident is the warning: a broken `vendor-status` took the whole
  devenv down. Nothing in the closure may be on the shell-entry critical path
  without a degrade.

## Was project 35 wrong?

No — it was **right about the symptom and short about the cause.** Publishing a
portable, hashed wheel and referencing it by URL is genuinely more portable than
a store path, and that value survives here unchanged: step 3 of the design keeps
`[tool.uv.sources]` exactly as project 35 left it.

What that decision did not do is repair the builder. It concluded "the
wheelhouse produces a non-portable artifact" and moved on, when the artifact was
two mechanical steps from portable — steps pyjutsu had already written, in a
script sitting in the same fleet. The wheelhouse was then left in the tree,
still built, still referenced by `repoman/devenv.nix`, producing a wheel with
the wrong tag that nothing uses. That is the state I measured.
