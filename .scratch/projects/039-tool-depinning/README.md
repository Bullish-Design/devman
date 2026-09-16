# 039 — Remove repoman and vendomat from per-repo pins

Date: 2026-09-15
Status: **both halves built and deployed; the repoman half migrated 12 of 23
consumers, the vendomat half migrated none.** Read `IMPLEMENTATION_LOG.md`
§"Stage 2" for the audited state, dated 2026-09-16. The repoman half keeps its
own log in `repoman/.scratch/projects/039-repoman-depin/`.

Project 038 removed devman from consumer repositories' version pins. It replaced
a per-repo flake input with two machine-delivered channels and one stable
in-repo manifest. The result: a devman release costs one plane build and one
system switch, not 48 lock bumps.

This project applies the same pattern to the two tools that still carry a
per-repo pin: **vendomat** and **repoman**.

## The measurement that justifies it

Dated 2026-09-15, measured across 72 live directories under
`~/Documents/Projects/` (61 with `devenv.yaml`).

| Tool | Declarers | Module importers | Distinct pinned revs | Unpinned `file://` | Repos at HEAD | Worst staleness |
|---|---:|---:|---:|---:|---:|---|
| repoman | 25 | 23 | 3 | 11 | **0** | 38 commits / 21 days |
| vendomat | 16 | 14 | 2 | 6 | **0** | 24 commits / 5 days |

Two findings sharpen the case:

1. **Ten repositories bind repoman twice at different revisions** — `57473ad4`
   directly, and `cd34bfd4` transitively through vendomat's flake. That diamond
   is the sharpest edge in the current graph, and removing the direct pin
   collapses it.
2. **Most of the pinned option surface is unused.** Five of vendomat's eight
   options and four of repoman's seven are set by zero repositories. The fleet
   pays a lock bump per release for an interface almost nobody calls.

   **But the options that are set are load-bearing, and an earlier revision of
   these prompts got their values backwards.** Ten repositories set
   `vendor.toolchain.enable = false` **and** `repoman.cliProvider = "venv"` —
   one coherent opt-out from the store toolchain, against both defaults.
   Deleting either line silently flips those ten repositories. Both prompts now
   carry the correction; read it before deleting any option line.

## The order

**Vendomat first, then repoman.** Two reasons, both hard:

1. Vendomat's plane code is **unreleased**. `v0.3.9` points at `511e70f`, which
   has no `plane` subcommand, no `devman-plane` output, and no
   `VENDOMAT_DEVMAN_PLANE_MANIFEST` wrapper. `nix-meta` locks that tag. The
   running plane was driven from a working tree. Cut `v0.4.0` before anything
   else.
2. Vendomat's module sets `repoman.cliProvider = "store"` and exports
   `REPOMAN_TOOLCHAIN_BIN`. Repoman's module reads that variable and fails loudly
   without it. Move the supplier before the consumer.

## The prompts

- [`VENDOMAT_PROMPT.md`](VENDOMAT_PROMPT.md) — run in
  `~/Documents/Projects/vendomat`. Do this one first.
- [`REPOMAN_PROMPT.md`](REPOMAN_PROMPT.md) — run in
  `~/Documents/Projects/repoman`. Do this one second.

Each prompt is self-contained. Each names the 038 documents to read, the target
state with literal snippets, the traps the 038 log already paid for, the per-repo
runbook, and the verification gate.

## What this project does not do

It does not start a pinning campaign. `CLEANUP_INVESTIGATION_PROMPT.md` in 038
records that 91 of 93 local inputs on this machine are unpinned and rules that
campaign out of scope. This project **deletes** inputs; the eleven unpinned
repoman consumers and six unpinned vendomat consumers are fixed as a side effect,
because the input disappears.

It does not touch `forgelab` or `lodestar`. Both still declare devman and both
are in the archive set. Leave them.
