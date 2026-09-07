Session root: ~/Documents/Projects/vendomat

# Phase 3 — make the wheelhouse emit the published artifact

Context: this repository builds pyjutsu into a wheel in the Nix store, and the
fleet also builds pyjutsu with maturin in a devenv and publishes that to a GitHub
release. **Two builds, two different files, one version number.** Every downstream
symptom follows from that. gitman project 35 resolved it by abandoning the
wheelhouse; measurement shows the wheelhouse is two mechanical steps from
producing the correct artifact.

Note: this repo carries no `gitman` skill and no session memory. Read
`~/Documents/Projects/gitman/.agents/skills/gitman/SKILL.md` before any version
control operation.

Read first, in order:
1. `~/Documents/Projects/devman/.scratch/projects/023-toolchain/TARGET.md` — authoritative
2. `~/Documents/Projects/gitman/.scratch/projects/32-loci-core-adoption-issues/ISSUES.md` §G3
3. `~/Documents/Projects/gitman/.scratch/projects/35-wheel-distribution/OUTCOME.md`
4. `~/Documents/Projects/pyjutsu/scripts/relocate_wheel.py`

## Measured facts. Do not re-derive.

The nix-built wheel differs from the published one in exactly two ways:

| | vendomat (nix) | published |
|---|---|---|
| tag | `cp313-abi3-linux_x86_64` | `cp313-abi3-manylinux_2_39_x86_64` |
| RUNPATH | three `/nix/store` entries | `''` |
| extension size | 19,762,792 | 19,964,296 |

Running pyjutsu's own `relocate_wheel.py` on the nix wheel removed the RUNPATH;
the result installed into a clean venv, imported, and needed only `libgcc_s`,
`libm`, `libc`, `ld-linux` — the four libraries project 35 lists as permitted by
manylinux. **Nothing about Nix prevents a portable wheel.**

## The job

1. `lib/mkMaturinWheel.nix`: pass `--compatibility manylinux_2_39` to
   `maturin build`, and run the relocate step in `postBuild`. **Reuse
   `pyjutsu/scripts/relocate_wheel.py`; do not reimplement it.**
2. `vendomat publish <lib>` uploads **that exact store file** to the GitHub
   release, so hash equality with `[tool.uv.sources]` is by construction.
3. **Invert `UV_NO_BUILD_PACKAGE`.** Today a missing or mismatched store wheel
   fails loudly, which is what took down loci-core's devenv shell. The store is
   an accelerator; a missing store wheel must fall back to the declared URL. That
   is not a silent fallback — the URL is the declaration.
4. Rule to enforce somewhere checkable: an iteration build gets its own version
   (`0.21.0.dev0+<rev>`), never the same version as a published release. One
   version, one artifact.
5. Scope Face A down in `README.md`: the wheelhouse is for a native library with
   no published release yet, and for local iteration. Cite project 35.
6. Remove the `vendomat/modules` import from the repos that enable no face:
   `nix-secrets`, `nix-nvim`, `loci.nvim`, `nix-paseo`, `nix-desktop`,
   `template-nix/golden/*`. They pay a flake input's evaluation and an
   `install-hook` probe per shell entry for no output.

## Verification

```bash
nix build .#pyjutsu-wheel --print-out-paths
# then, on the produced wheel:
python3 -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); print([n for n in z.namelist() if n.endswith('WHEEL')])" <whl>
patchelf --print-rpath <extracted .so>     # must be ''
uv venv --python 3.13 /tmp/smoke && uv pip install --python /tmp/smoke/bin/python <whl>
/tmp/smoke/bin/python -c 'import pyjutsu; print("ok")'
patchelf --print-needed /tmp/smoke/.../pyjutsu/_pyjutsu.abi3.so   # only the four permitted libs
devenv tasks run vendomat:lint && devenv tasks run vendomat:test
```

## Do not reverse

**`gitman/pyproject.toml`'s `[tool.uv.sources]` pyjutsu URL stays.** It is the
fix for G3 and is what makes gitman adoptable in a repo with no Nix. This phase
makes the store wheel emit the same bytes; it never replaces the URL.

## Stop if

A relocated nix-built wheel fails its smoke test. That would contradict
`TARGET.md`'s central measurement, and the design must be revisited rather than
patched around.
