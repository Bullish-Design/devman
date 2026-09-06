# Project 009 — deep code review

## Objective

Review the devman library against its charter, public contract, measured stage
evidence, implementation, and tests. Record confirmed findings with a focused
reproduction and a practical fix direction.

## Scope

- `src/devman/`
- `modules/devenv.nix`
- `nix/`, including the NixOS module and virtual-machine test
- `flake.nix`, packaging, and the repository task graph
- `tests/` and the public documentation that defines expected behavior
- Governing design in projects 006 and 007

## Method

1. Read the governing documents and stage evidence for non-obvious mechanisms.
2. Trace each public operation across the Nix, shell, Python, Dagu, and test boundaries.
3. Run the repository checks before adding review artifacts.
4. Reproduce each high-impact candidate in a disposable directory.
5. Separate confirmed defects, risks, test gaps, and strengths.
6. Rank findings by user impact and likelihood.

## Status

1. Governing documents and stage evidence: complete.
2. Code, configuration, workflows, and tests: complete.
3. Baseline and live-plane checks: complete.
4. Focused reproductions: complete.
5. Final report: complete.
6. Repository verification: complete. Publication: in progress.

## Deliverables

- `NOTES.md`: review map, evidence, candidate findings, and disposition.
- `REPORT.md`: final prioritized code review.
- `reproductions.py`: focused, disposable reproductions for Python-layer findings.
- `EVIDENCE.md`: command results and environmental evidence.
