# The fleet-level answer

> **Superseded in part by `TARGET.md` (2026-09-06).** Measurement showed the
> vendomat wheelhouse is two mechanical steps from producing the published
> artifact, so "Face A was retired correctly" is too strong. Read `TARGET.md`
> before acting on the Face A / `[tool.uv.sources]` guidance here.


## Scale, measured

```
62  repositories with a devenv.yaml under ~/Documents/Projects
29  import repoman/modules
13  import vendomat/modules  (only 3 enable a face)
 4  declare templateer in pyproject.toml
 3  declare pyjutsu
```

Eight first-party libraries circulate: `pyjutsu`, `gitman`, `repoman`,
`copyroom`, `docman`, `templateer`, `testee`, `knappy`.

## The one sentence

You have three distribution mechanisms competing for one job, and **each is
correct for a different category** — the problem is that none of them was given
a category and told to stay in it.

| Mechanism | Correct for | Wrong for | Why |
|---|---|---|---|
| Nix / Home Manager | stable binaries you do not edit | anything you edit daily | a rebuild per iteration is the wrong loop |
| shared venv on `PATH` | console scripts | **libraries** | `PATH` is not `sys.path` (M3, M4) |
| per-repository `uv.lock` | libraries, including native ones | fleet-wide CLIs | 62 upgrade sites |

The failure is not that any one is bad. It is that `pyjutsu` was placed by
mechanism 2, which cannot deliver a library, and `templateer` was placed by a
fourth mechanism nobody chose — a stray `.pth` file (P2).

## Best practice for a personal fleet of this shape

The literature answer and the answer already written in
`vendomat/.scratch/projects/03-shared-repoman-toolchain/CONCEPT.md` are the same
one. Stated as three rules:

### Rule 1 — a CLI is a Nix package, delivered as an immutable closure

Not a shared mutable virtualenv. One derivation per exact source revision,
Python version and dependency graph; every shell points at the same store path.
You get rollback, provenance, atomic upgrade, and no PATH-order ambiguity. This
is Vendomat Face D. It is designed and not built.

Cost, honestly: §8.1 of that concept names package materialization as the
principal expense, and it is real — every `pyproject.toml` must be made to build
under Nix, one tool at a time.

### Rule 2 — a library is a declared dependency of the repository that imports it

There is no shared-library mechanism in Python that works across interpreters,
and no packaging tool will invent one. If a repository writes `import pyjutsu`,
it declares `pyjutsu`. The fleet cost of that rule is the build, not the
declaration — and Vendomat Face A already removes the build.

### Rule 3 — local development is a mode, not a source format

`path:` editable installs are correct while you are editing a tool and wrong in
anything that ships. Vendomat Face C is exactly this: keep `path:` locally,
rewrite to `git+https://…@vX.Y.Z` on push, and refuse if the resolved graph
moves. It is built and has zero users.

## What that means concretely, in dependency order

**Corrected after reading gitman projects 32 and 35.** My first draft told you
to delete gitman's `[tool.uv.sources]` so `UV_FIND_LINKS` would decide. That
would reverse a decision made on 2026-08-28 with evidence and reintroduce issue
G3 — gitman becoming un-adoptable in any repo not wired to the exact vendomat
revision it was built against. Do not do it.

The corrected order:

1. **Nothing to do for `pyjutsu` distribution.** The published, relocated,
   hashed `manylinux_2_39` release asset is correct. It is the pattern to copy,
   not the thing to fix.
2. **Give `templateer` the same treatment** — a pinned, hashed artifact
   referenced by URL or `git+https://…@tag`, instead of `PYTHONPATH` at a
   sibling checkout.
3. **Stop crossing the import boundary at all.** Reach both `pyjutsu` and
   `templateer` from a workflow as *console scripts*, never as imports. This is
   what lets `devman` keep an empty venv and no `uv.lock`, which its own
   `devenv.nix` comment already argues for.
4. **Adopt Face C** in the four editable managers, so the machine's toolchain is
   rebuildable somewhere else.
5. **Then** Face D, phased as concept 03 §6 specifies.

## The interpreter baseline, first

Concept 03 §8.3 flagged one decision as blocking, and it has since gone wrong in
production. Four interpreters are in play:

```
Home Manager repoman 0.7.0   -> python 3.12.13   (nix-terminal/modules/repoman.nix,
                                                  overriding with python312Packages)
toolchain venv               -> python 3.13.13
every devenv                 -> python 3.13.14
vendomat wheelhouse          -> cp313-abi3
```

Two distinct problems live in that list, and they need separating.

### The 3.13.13 / 3.13.14 split is not an ABI problem

Both are CPython 3.13, so both take the same `cp313` ABI tag. The wheel loads on
either, and it would load on either even if it were an ordinary `cp313-cp313`
wheel — a CPython ABI tag is per *minor* version, and patch releases do not
break it. `abi3` is not what rescues this pair.

What that split does break is `sys.path`: two interpreters means two
`site-packages` trees, which is P1, and it is a packaging-layout problem rather
than a binary-compatibility one.

### The 3.12 / 3.13 split is a hard ABI wall, and it is measured

```
$ ~/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12 -c \
    "import sys; sys.path.insert(0, '<toolchain venv site-packages>'); import pyjutsu"
ImportError: .../pyjutsu/_pyjutsu.abi3.so: undefined symbol: Py_GetConstantBorrowed
```

`Py_GetConstantBorrowed` entered the stable ABI in CPython 3.13. `abi3` gives
*forward* compatibility (this wheel will load on 3.14), never backward. So the
Home Manager `repoman` on 3.12 could not host `gitman` or `pyjutsu` even if
someone asked it to.

### Why this blocks Face D specifically

Face D builds each manager CLI as a Nix Python application. That build must
choose an interpreter. Vendomat targets `python313`; repoman's own flake
packages 3.12. Pick 3.12 and `gitman` cannot load the wheelhouse's `pyjutsu` —
measured above. Pick 3.13 and the 3.12 `repoman` in Home Manager remains
installed alongside it, so `command -v repoman` still resolves by PATH order
(P3) — which is the exact ambiguity Face D exists to remove.

So the order is: state one baseline (3.13), rebuild or drop the 3.12 `repoman`,
**then** build the closure. Doing it the other way round produces a shared
toolchain that still has to be disambiguated by PATH, which is no toolchain.
