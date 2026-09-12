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

This project is a design document. It does not implement the redesign.
