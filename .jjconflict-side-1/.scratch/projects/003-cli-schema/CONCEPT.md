# `--schema` — a family CLI publishes its own facts

> **STATUS: PROPOSED (2026-08-19). Follows 001, does not block it.**
> A family-contract change, not a devman feature. devman v1 ships the walker
> (`001` §9) and needs nothing from anyone. This proposal retires the walker once
> v1 has shown which facts are worth exporting.

---

## 1. The proposal

Every family Typer CLI gains one command:

```bash
copyroom --schema        # JSON: the command tree, on stdout, exit 0
```

Output is the same shape devman's walker already produces:

```json
{"tool": "copyroom", "version": "0.6.3",
 "commands": {
   "layer":  {"kind": "leaf",  "positional": ["action", "template"],
              "options": ["--as", "--force", "--json", "--ref"]},
   "remote": {"kind": "group", "children": ["add"]}}}
```

One shared helper implements it for all five CLIs. Each tool calls
`typer.main.get_command()` on **its own** app — in its own process, under its own
typer — and prints the result.

---

## 2. Why the walker is not the end state

devman v1's walker works and is verified. It carries two costs that no amount of
engineering removes, both measured in `.scratch/spikes/SPIKES.md` §B.2:

| Cost | Measurement |
|---|---|
| **It imports the tool** | `import copyroom.cli` takes 222ms and executes `release.check`, `session.dispatcher`, `workshop.golden`. devman runs another tool's import-time code to read a command list. |
| **It couples devman to typer internals** | across interpreters devman does not control; skew is already present (toolchain 0.27.1, testee's venv 0.26.8) |

Import side effects are the sharper of the two. Today they are harmless. Nothing
guarantees that stays true, and the failure mode is bad: a tool adds a
module-level side effect, and `devman doctor` starts triggering it in every repo.

**The import-free alternative does not work.** Parsing `--help` was tested:
copyroom reads correctly, and gitman, docman, and repoman return **0 nodes**,
because they render help in rich panels rather than a plain `Commands:` section.
Two incompatible help formats already exist inside one family. Script:
`.scratch/spikes/helpwalk.py`.

That leaves one clean option: the tool reports its own facts.

---

## 3. The argument this proposal actually rests on

Not convenience. **Correctness has an owner.**

`001` §9 records a reversal worth repeating here. A click-free walker was built to
avoid depending on click internals. `parity.py` scored it against the click route
and it failed three rounds — 43 discrepancies, then 13, then 6 — and the final 6
were all cases where it disagreed with the CLI's real `--help`:

| Command | click-free walker | real `--help` |
|---|---|---|
| `gitman save` | `--message` | `--message`, `-m` |
| `gitman release` | `--set-version` | `--version` |
| `docman doctor` | `--json-output` | `--json` |

The lesson generalises past click. **A tool's facts live inside its own
resolution logic.** Any third party reading them either calls that logic
(`get_command`, which means importing the tool) or approximates it (which means
being quietly wrong). There is no third option from the outside.

`--schema` is the inside. Each tool runs its own resolution and prints the
answer. It cannot drift from itself, and devman stops guessing.

---

## 4. What it costs

| Cost | Size |
|---|---|
| a shared helper | ~20 lines, written once |
| wiring per tool | one import and one command, 5 tools |
| a release per tool | can ride an existing release; nothing is urgent |
| a contract line in `repoman/docs/` | one row |

Nothing here is reversible-hard. A tool that has not shipped `--schema` yet falls
back to the walker, so adoption is incremental and no coordination window exists.

---

## 5. Why this is a family-contract change, not a devman feature

The family already shares `init`, `doctor`, `status`, the `0/1/2/3` exit codes,
and distribution as a devenv module. `repoman/src/repoman/registry.py` already
records per-tool capabilities (`doctor=[...]`, `status=[...]`), so the roster has
somewhere to record `schema=True`.

The first draft of the devman concept dismissed `--schema` as "a new surface to
negotiate". That was wrong twice over: the family negotiates surfaces routinely,
and the alternative turned out to be devman importing five other tools.

---

## 6. Entry criteria

1. `001` step 2 has shipped and `devman doctor --refs` runs on real repos.
2. The walker's output schema has been stable for one release — that schema is
   this proposal's contract, and v1 is what proves which fields matter.
3. `repoman/src/repoman/registry.py` gains a `schema` capability flag, so devman
   can pick per tool rather than probing.

Criterion 2 is the reason this follows 001 rather than replacing it. Freezing a
contract before knowing which facts the checks need would freeze the wrong one.

---

## 7. Open questions

- **`--schema` or `schema`?** A flag on the root app, or a hidden sub-command?
  Lean: `--schema` on the root, so it cannot collide with a domain command.
- **Does the schema carry more than the command tree?** Exit-code meanings would
  serve `001` §5's `exit:` blocks, and domain prose would serve `001` §5.2's
  three-material split. Lean: start with the command tree only. Add fields when a
  check needs them, not before.
- **Non-family CLIs.** An asset may reference `jj`, `uv`, or `nix`. Those will
  never ship `--schema`. Does the reference check skip them, or does devman keep
  a small curated fact set? Lean: skip and say so in the report — a silent skip
  reads as a pass.
- **Versioning.** When the schema shape changes, how do a new devman and an old
  tool agree? Lean: a `schema_version` integer, and devman accepts N and N-1.
