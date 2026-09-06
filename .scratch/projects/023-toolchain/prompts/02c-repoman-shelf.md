Session root: ~/Documents/Projects/repoman

# Phase 2c — put templateer on the shared CLI shelf

Context: the shared toolchain venv (`~/.local/share/repoman/venv`) is the
machine's console-script shelf. devman's changelog workflow needs `templateer` as
a command, not as an import — that is the whole point of the refactor, because
the shelf lends console scripts through PATH and cannot lend imports.

Prerequisite: Phase 2b tagged a templateer release.

Read first:
- `~/Documents/Projects/devman/.scratch/projects/023-toolchain/RECOMMENDATION.md`
- this repo's `repoman.lock` header, which documents the source forms.

## The job

Add to `repoman.lock`:
```toml
# templateer: typed artifact generation. A CLI on the shared shelf, not a library
# any repo imports — devman's changelog workflow calls `templateer generate`.
[managers.template]
package = "templateer"
source = "git+https://github.com/Bullish-Design/templateer_v2@vX.Y.Z"
```
Then `devenv shell -- repoman-sync --machine`.

## Verification

```bash
devenv shell -- repoman doctor
zsh -lic 'command -v templateer && templateer --help | head -3'
~/.local/share/repoman/venv/bin/python -c 'import templateer, pyjutsu, gitman; print("shelf ok")'
```

`repoman doctor`'s `deps:toolchain` row verifies the whole venv is mutually
compatible. It currently reports 33 packages compatible.

## STOP CONDITION — read this before starting

templateer depends on `pydantic-ai-slim[openai]` and `minijinja`. **If
`repoman doctor` refuses after the sync, stop and write a note.** That answers an
open question — whether templateer can share one venv with gitman and pyjutsu —
and the answer would be no. Do not weaken the check, do not force the install.
The fallback is that templateer stays scoped to devman's `changelog` group, and
devman's 022 kickoff explicitly says not to make it a dependency of every adopter.

## Rules

- Do not convert any existing `path:` entry in `repoman.lock` in this phase.
  That is Phase 3, and it needs vendomat's publish hook first.
- If `repoman-sync`'s source parser rejects the `git+https://...@tag` spelling,
  fix the parser or add a source form; do not overload `wheel:`.
