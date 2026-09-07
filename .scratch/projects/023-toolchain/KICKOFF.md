# Kickoff: where development tooling lives

Date: 2026-09-06
Status: investigation complete, no configuration changed.

## Objective

Decide where `gitman`, `pyjutsu`, `templateer`, `repoman` and the rest of the
Python and native-extension tooling must live, so that one installation serves
three consumers: an interactive shell, a repository `devenv`, and a Dagu
workflow step.

## Why now

The `changelog` group (021, 022) is the first workflow that needs a Python
*import* (`pyjutsu`) and a third-party library (`templateer`) inside a step.
Every earlier workflow needed only a console script on `PATH`. The import is
what exposed the layering, because a console script and an `import` resolve
through different mechanisms.

## Constraint the investigation had to respect

Read-only. No layer was changed. One disposable Dagu DAG was created in the
projection directory to capture a real step environment, and was deleted after
the capture. `.scratch/` is the only directory written.

## Question in one sentence

`gitman` runs inside `devenv shell`; `import pyjutsu` does not. Why, and what
is the smallest correct fix?

## Answer in one sentence

`repoman` puts the shared toolchain venv on `PATH`, and `PATH` carries console
scripts but never `sys.path`; so the shared venv can lend a CLI to any
repository and cannot lend a library to any repository.

See `FINDINGS.md`.
