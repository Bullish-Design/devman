# Kickoff — Investigation E, the Dagu capability sweep

## Your task

Find out what else Dagu 2.15.0 can do, and report which of it the plane should
use. Write the answers to `FINDINGS.md` in this directory, appending.

**Investigation A asked whether Dagu does what the charter assumed. This asks
the opposite question: what does Dagu already do that the charter is planning to
build itself?**

E is not in `KICKOFF_PROMPT.md`. It is an addition, and it does not replace
Investigations B, C, or D.

---

## 1. The one rule that keeps this session useful

A capability sweep fails in a predictable way: it finds interesting features and
invents work. Guard against that with a single filter.

> **A capability earns a section only if it lets the charter delete something,
> or answers a question the charter left open. Everything else is one line in a
> catalogue.**

Three buckets, and put every finding in one:

| Bucket | Means | Length |
|---|---|---|
| **Replaces** | the plane can stop building this; Dagu already has it | a full section, with evidence |
| **Answers** | it settles an open question or a `lean` in §16 | a full section, with evidence |
| **Catalogue** | real, possibly useful later, nothing to decide now | one line in a table |

**Do not design devman.** Do not propose new charter sections, new CLI commands,
or new contract keys. If a capability suggests one, say so in a sentence and
stop. Reconciliation is a later pass, by one person, over everything at once.

**Bias toward deletion.** The best result this session can produce is
"§8.1 is unnecessary, Dagu does it" — a section the charter can drop. The second
best is "Dagu does not do this, keep building it." Both are wins. A long list of
features nobody will use is not.

---

## 2. Read these first

1. `.scratch/projects/006-automation-plane/CONCEPT.md` — the charter. A
   proposal, not a specification. §16 lists the open questions.
2. `.scratch/projects/006-automation-plane/FINDINGS.md` — Investigation A, in
   full. It tells you how Dagu actually behaves, and it will stop you
   re-measuring things.
3. `.devman/context/README.md` — where the vendored upstream source lives.

---

## 3. The environment is already built

A previous session packaged Dagu, wired it into this repo, and ran Investigation
A against it. Use it as it stands.

| Fact | Value |
|---|---|
| Version under test | **2.15.0** |
| Package | `nix/dagu.nix` — the release tarball, pinned to tag `v2.15.0` |
| devenv wiring | `devenv.nix` — Dagu on `PATH`, plus `processes.dagu` |
| `DAGU_HOME` | `<repo>/.devenv/state/dagu` |
| DAG directory | `<repo>/.devenv/state/dagu/dags/` |
| Instance config | `<repo>/.devenv/state/dagu/config.yaml` |
| Web UI | `http://127.0.0.1:8080` |
| **Upstream source** | **`.devman/context/.vend/dagu`** — a full clone at the tag |

```bash
devenv up -d                       # start the Dagu process
devenv processes list              # confirm it is ready
devenv shell -- dagu start <name>  # run one DAG, print the result tree
devenv shell -- dagu --help        # the full command set
```

The source is already cloned. **Do not clone it again to `/tmp`.** If it is
missing, `.devman/context/README.md` has the refetch command. `.vend/` is
git-ignored, so nothing you read there dirties the tree.

Investigation A left `config.yaml` holding two queues (`light` at 4,
`exclusive` at 1), a `DEVMAN_` passthrough allowlist, and
`dag_discovery.recursive/symlinks`. Its throwaway DAGs are still in `dags/`,
prefixed `a1_` through `a5_`. Leave them or delete them; they are disposable.

---

## 4. What Investigation A already established

Do not re-measure any of this. It is in `FINDINGS.md` with commands and output.

**Behaviour:**

- The schema is **snake_case** throughout, and `additionalProperties: false` —
  unknown top-level keys are a hard load failure.
- A DAG's identity is its **file name**. `dagu validate` rejects a top-level
  `name:` key. Step `id:` may not contain a hyphen; step `name:` may.
- **`dagu start` ignores queues. `dagu enqueue` honours them.** Only enqueued
  runs are governed.
- **`log_dir` and `artifacts.dir` are resolved by the process that enqueues.**
  `working_dir` is resolved by the process that executes. They read different
  sources, and no instance arrangement changes that.
- An unresolved `${VAR}` in a path is **not an error**. Dagu creates a directory
  named literally `${VAR}` and carries on.
- An undefined queue name is accepted **silently**, with no limit applied.
- Sub-DAG runs nest under the parent's run record. A parent's parameters shadow
  a child's own values when the names collide, including over `with.params`.

**Documentation that is wrong.** Three places where the schema or the shipped
`base.yaml` disagrees with the binary. Expect more, and trust the run:

- `working_dir` relative paths resolve against the **process CWD**, not the DAG
  file location.
- Symlinked DAG files take the **link's** directory, not the target's.
- `with.params` is documented as authoritative for sub-DAGs. It is not, when the
  name collides.

---

## 5. Where to look, in priority order

Every field named below **exists** in 2.15.0 — that was checked before this
prompt was written. What none of them has is a measurement.

### Tier 1 — could let the charter delete something

Spend most of the session here.

**E1 — Does Dagu already break the write-loop? (§8.1)**
§8.1 makes the plane own a `generation.json` content-hash token, so a workflow
that writes files a watcher watches does not chase itself. Dagu may already have
this.
Look at: `preconditions`, `skip_if_successful`, step-level `dependencies`
(`references/file-dependencies.md`), and `type: build` with declared `outputs:`
(`references/build.md`) — the build path verifies "input snapshots" and
atomically replaces outputs, which is content-hashing by another name.
*Answer:* can a workflow skip itself when its inputs are unchanged, using only
Dagu? Does it survive `enqueue`? **If yes, §8.1 stops being plane machinery.**

**E2 — What actually invokes Dagu? (§8, and D7)**
§8 says a watcher or a hook triggers a workflow, and leaves the mechanism open.
D7 asks the same question.
Look at: the DAG-level `webhook` field, the `webhooks` instance config, the HTTP
API (`api_base_path`, `public_url`, `sse`), and the **MCP endpoint** — the
server logs `MCP route configured path=/mcp` at startup.
*Answer:* what are the trigger surfaces, do they accept params, and does a
webhook-triggered run go through the queue? Recall that `dagu start` does not.
**This decides whether triggers are plane machinery or group content.**

**E3 — Whose job are secrets? (§9.4)**
§9.4 has the NixOS module read secrets from the machine's secret manager and
inject them into Dagu's environment.
Look at: the DAG-level `secrets` field and the instance-level `secrets` config.
The schema documents providers `env`, `file`, and `vault`.
*Answer:* can a DAG name a secret and have Dagu resolve it, and how does that
interact with the `env_passthrough` allowlist A2 found? **If Dagu resolves
secrets itself, §9.4's injection path shortens or disappears.**

**E4 — How much can the machine set once? (§7.1)**
§7.1 wants the smallest possible shared vocabulary, and group workflow files
that stay thin.
Look at: `base_config` and the generated `base.yaml` — "values defined here are
inherited by ALL DAGs" — plus DAG-level `defaults:` for step settings.
*Answer:* which of `queue`, `log_dir`, `env`, retention, and `working_dir` can
be set once in `base.yaml` instead of in every group file? **Every field that
can move out of a workflow makes §7.2's portability claim cheaper.**

### Tier 2 — answers an open question

**E5 — Can Dagu diagnose a wedged plane? (§10, §15.3)**
§15.3 accepts a shared-availability failure on one condition: `devman doctor`
must diagnose it. §10 defers the CLI.
Look at: `dagu ps`, `history`, `status`, `dequeue`, `stop`, `dry`, and the
`audit`, `event_store`, `monitoring`, `metrics`, and `otel` config blocks.
*Answer:* what can `doctor` read rather than reimplement? Specifically, how does
one see a stuck queue, a zombie run, and a DAG that failed to load?

**E6 — Could `git_sync` replace the projection? (§9.2, §5.2)**
§9.2 projects each project's workflows into `~/.local/share/devman/`. §5.2 makes
registration write it at shell entry.
Look at: the `git_sync` config block and the `dagu sync` command.
*Answer:* can Dagu pull DAG definitions from a repository itself? **If so, the
projection and part of registration may be unnecessary.** Note the tension with
§5.1's "the repo supplies its own location".

**E7 — Does Dagu already have a registry concept? (§5, §7.2)**
Look at: DAG-level `labels`, `tags`, and `group`, plus `dag_discovery`.
*Answer:* is devman's group-and-project model duplicating something Dagu has?
Can a workflow be selected or filtered by label from the CLI and the API?

**E8 — Is there a cleaner per-project mechanism than A2 and A3 found? (§7.2)**
A2 and A3 landed on "the trigger exports a variable **and** passes a param".
That is forced given queues — A6 proved it — but only for the mechanisms tested.
Look at: `dagu profile` and `run_config`, `consts`, and `dotenv`.
*Answer:* does a runtime profile carry per-run values into **both** `log_dir` and
`working_dir`? This is the one Tier 2 item that could still simplify §7.2.

### Tier 3 — catalogue only, one line each

Real capability, nothing to decide now. **Do not spike these.** One table, one
line per item, saying what it is and which stage it would belong to.

- `harness`, `harnesses`, `llm`, `type: agent` with `tasks:`, the `opencode`
  config block, `action: chat.completion`, and the MCP endpoint — §13 stage 4's
  "agent workflows". This repo already ships `claude-code` and `codex-cli`.
- `worker`, `coordinator`, `worker_selector`, `remote_nodes`, `dagu context` —
  §9.1 claims identity makes "a future remote worker" work. Does it?
- `human-task` — §13 stage 4's "policy gating".
- `container`, `kubernetes`, `registry_auths` — isolation.
- `retry_policy`, `repeat_policy`, `continue_on`, `handler_on`, `otel` —
  reliability and lifecycle hooks.
- `smtp`, `error_mail`, `mail_on` — notification.
- `permissions`, `auth`, `ip_access`, `tls`, `tunnel` — exposure.

---

## 6. How to report

Append to `FINDINGS.md` in this directory. Continue the `E` numbering. One
section per ID, in the shape Investigation A used:

```markdown
## E1 — Does Dagu already break the write-loop?

**Bucket:** replaces / answers / catalogue
**Answer:** <one sentence, first>
**Tested:** dagu 2.15.0, on <date>.
**Command:** <the exact thing you ran>
**Evidence:** <output, trimmed to the part that proves it>
**Charter impact:** <one of the three below>
```

`Charter impact` is the field that matters:

- **none** — the charter stands
- **changes §N** — name the section, state the change in one sentence
- **deletes §N** — Dagu already does this; say what the charter should drop
- **kills §N** — the design must be rethought; say what you would do instead

End your work by extending the existing summary list at the bottom of
`FINDINGS.md`, so every `changes`, `deletes`, and `kills` stays in one place.

Finish with the Tier 3 catalogue as a single table.

---

## 7. Rules

1. **Report what happened, not what should have happened.** An absent capability
   is a useful result. Record the version and the exact command.
2. **Read the schema, then prove it by running a DAG.** Investigation A found
   three places where the documentation is wrong. Assume there are more.
3. **Throwaway is fine.** `/tmp`, scratch DAGs, dummy project directories. Do
   not build toward the real thing.
4. **Timebox.** Tier 1 is the session. If E1 through E4 take all of it, stop and
   report — Tier 2 and Tier 3 are worth less than a rushed Tier 1.
5. **Do not edit `CONCEPT.md`.** Record what a finding contradicts and leave the
   edit to a later pass.
6. **Do not start Investigations B, C, or D.**
7. **Commit and push at regular intervals.** Commit each finding as you confirm
   it, rather than saving one commit for the end. Work on the current branch.

**If a Tier 1 answer would delete a charter section, stop and say so plainly
before moving on.** A section the charter can drop is worth more than three more
capabilities it might one day use.
