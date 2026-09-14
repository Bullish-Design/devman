# 038 — Devman plane redesign

Date: 2026-09-12
Status: proposed concept

This project redesigns Devman as a machine-level automation plane.

The target design has four rules:

1. Vendomat builds, installs, updates, and rolls back the machine plane.
2. Devman owns the automation contract, resolver, renderer, and reconciler.
3. Repositories carry a stable project manifest and their own task definitions.
4. RepoMan handles repository-specific changes and migrations.

The design removes routine Devman version updates from consumer repositories.
It replaces shell-entry projection with central generation reconciliation.

[`CONCEPT.md`](CONCEPT.md) records the proposed architecture, trade-offs,
invariants, migration path, and open decisions.

[`IMPLEMENTATION_GUIDE.md`](IMPLEMENTATION_GUIDE.md) is the step-by-step
runbook for the remaining package, migration, canary, cutover, and removal
work.

[`LINK_PLANE_A_TO_C_GUIDE.md`](LINK_PLANE_A_TO_C_GUIDE.md) is the focused
runbook for the agreed link-plane transition: keep Devman as the adapter now,
make the central configuration contract stable, and defer extraction until the
bridge is proven.

[`LINK_ADAPTER_B_GUIDE.md`](LINK_ADAPTER_B_GUIDE.md) is the next-phase runbook
for extracting the link adapter into a stable package without changing the
central configuration interface.

[`LINK_ADAPTER_B_PROMPT.md`](LINK_ADAPTER_B_PROMPT.md) is a copy-ready prompt
for starting the B implementation in a clean session.

[`FULL_REFACTOR_PROMPT.md`](FULL_REFACTOR_PROMPT.md) is a copy-ready prompt
for a clean implementation session. It defines the work across Devman,
Vendomat, and RepoMan.

[CONSUMER_MIGRATION_GUIDE.md](CONSUMER_MIGRATION_GUIDE.md) is the detailed
clean-session runbook for the remaining consumer migrations.

This project is a design document. It does not implement the redesign.
