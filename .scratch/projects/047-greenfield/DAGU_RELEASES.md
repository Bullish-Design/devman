# Dagu releases since 2.15.0, and what they mean for G2

Research date: 2026-10-15. Research only. No code changed. The live Dagu was not touched.
Repository: github.com/dagucloud/dagu (the old name dagu-org/dagu redirects). Docs: docs.dagu.sh.

## Summary

**Newest release: v2.20.1 (2026-10-14).** v2.20.0 was tagged but never published. The machine runs 2.15.0 (2026-08-21). The gap is 19 tagged releases: 2.15.1 to 2.15.4, 2.16.0 to 2.16.6, 2.17.0, 2.17.2, 2.18.0 to 2.18.2, 2.19.0 to 2.19.2, 2.20.1. (There is no v2.17.1 tag in the list; 2.17.2 links to it in the changelog.)

The five most useful features for G2:

1. **v2.17.0: scheduled runs now go through the DAG's queue** (#2775), when the queue is defined in `config.yaml`. This fixes the "58 started at once" pain.
2. **Already in 2.15.0: per-project context without rendering.** A `workspace=<name>` label plus `dags/workspaces/<name>/base.yaml` sets `env`, `working_dir` and `log_dir` for every DAG with that label. Verified on 2.15.0. Risk: Dagu plans to remove workspaces in v3.0 (RFC 003).
3. **v2.16.6 and v2.19.1: base.yaml is now reliable.** The scheduler reloads inherited base defaults (schedule, queue, catchup) and watches base files (#2770). A base.yaml inside the DAG directory no longer shows as a phantom DAG (#3126). This carries the shared `actions:` plan.
4. **v2.17.2: the DAG index moves to `data_dir`** (#2858). A read-only `dags_dir` now works. This fixes the `.dag.index` pain.
5. **v2.17.0 and v2.17.2: human-task and harness hardening.** Human tasks gain run artifacts (2.17.0), push-back with rewind (2.17.2) and independent branches that keep running while a task waits (2.17.2). `harness.run` warns on an implicit working directory (2.17.0).

Also worth knowing: `dagu enqueue` and `dagu start` already accept `--name`, `--labels`, `--queue`, `--default-working-dir`, `--run-id` on 2.15.0. A router can set per-project context at enqueue time with these flags.

Report path: `/home/andrew/Documents/Projects/devman/.scratch/projects/047-greenfield/DAGU_RELEASES.md`

## Upgrade notes

**No breaking change between 2.15.0 and 2.20.1 breaks the G2 design.** The release notes list one "Upgrade notes" item (2.20.1). The behavior changes below still matter.

| Version | Change | Effect on devman |
|---|---|---|
| 2.20.1 | `GET /event-logs` omits `dag.run.updated` unless `type=dag.run.updated` is set (#3173). An old load-more cursor returns 400 once. | Only matters if devman reads the event log API. |
| 2.17.0 | Scheduled runs of DAGs on a configured queue wait for a slot (#2775). | Scheduled runs are now throttled by queue `max_concurrency`. Check that the six queue limits are right before upgrading. |
| 2.16.6 | The scheduler applies inherited base defaults, including `catchup_window`, `overlap_policy` and `queue` (#2770). Before this, the scheduler could ignore them. | If `base.yaml` sets `catchup_window`, every inheriting scheduled DAG now catches up. A DAG opts out with `catchup_window: ""`. |
| 2.17.0 | The default suspend-flags directory moves under `data_dir` (#2784). An explicit `suspend_flags_dir` keeps its place. | Check suspended DAGs after upgrade. |
| 2.17.2 | `.dag.index` moves to `<data_dir>/cache/dag-index/<hash>.index` (#2858). Dagu deletes the old file once, if it can. | None. This is good. |
| 2.18.0 | Scheduler runs load dotenv again (#2937). It was a regression since 2.13.0, so 2.15.0 is affected. | A project `.env` now reaches scheduled runs. Check that nothing relied on its absence. |
| 2.15.0 (observed) | `command:` steps print a deprecation warning: "use run". | Render `run:` in new templates. |
| v3.0 (planned) | RFC 003 removes workspaces. The `workspace` label stays as an ordinary label. Dagu refuses to start while workspace-scoped base config exists. | The per-project base config trick (below) has an end date. See "Features by design area". |

**Is upgrading worth it? Yes.** Three known pains go away (scheduled runs skip the queue, `.dag.index` on a read-only dir, base.yaml reload and phantom base DAG). Six months of fixes for distributed workers, queues and the scheduler come with it. The cost is a bump of the pin in `nix/dagu.nix` (version and hashes). No schema field that devman uses was removed: the DAG schema on 2.20.1 adds only `mail_accounts` at root level, and the config schema adds `browser`, `cloud` and `signal_handling`. Verified by diffing `dagu schema dag` and `dagu schema config` on 2.15.0 against a downloaded 2.20.1 binary (checksum verified, only `schema`, `validate`, `--help` run).

Plan the upgrade as its own spike. Re-run the symlink and reload spike on 2.20.1 first (see Pain points).

## Features by design area

"Verified" means a command on 2.15.0 or on the 2.20.1 binary showed it, or the source at tag v2.20.1 shows it. "Notes only" means release notes, PR text or docs only. I ran no scheduler or server from the downloaded binary.

### Per-project context

| Version | Feature | Effect on design | Evidence |
|---|---|---|---|
| 2.15.0 (and earlier) | **Workspace base config.** A DAG with label `workspace=<name>` merges `<dags_dir>/workspaces/<name>/base.yaml` after the global base. Order: global, workspace, DAG. | Replaces the rendered header (`env: DEVMAN_PROJECT_DIR`, `working_dir`, `log_dir`). The project file shrinks to `labels: [workspace=<project>]`, a schedule and a step. One `workspaces/<project>/base.yaml` per project holds the three values. Discovery skips the `workspaces/` directory, so it never loads as DAGs. Catch: each DAG file still needs the label, so devman still writes a line per file. Catch: Dagu plans to remove this in v3.0. | **Verified** on 2.15.0: a test DAG with the label ran with `DEVMAN_PROJECT_DIR`, `pwd` and `log_dir` from the workspace base. |
| 2.15.0 | `dagu start` and `dagu enqueue` accept `--name`, `--labels`, `--queue`, `--run-id`, `--default-working-dir`, `--profile`. | Event-driven runs can set the project context at enqueue time. `--name` can give a run a project-prefixed name. `--default-working-dir` covers DAGs that set no `working_dir`. | **Verified** (help text, 2.15.0). Behavior of `--default-working-dir` not run. |
| 2.15.0 | `working_dir` defaults to the directory of the DAG file. | A rendered file in a stable `dags_dir` gets the dags directory, not the project. A project still needs an explicit `working_dir`. | Schema text, verified. |
| 2.8.0 | `${context.*}` references: `dag.name`, `run.id`, `paths.work_dir`, `paths.log_file`, `trigger.type`, `profile.name` and more. | Steps can name their DAG and run without extra env. | Notes and spec 017. |
| 2.x | `consts`, `defaults` (per-step defaults), `params`, `dotenv`. `consts` from a base config are inherited. | `consts` in the workspace base can hold project facts. | Schema, verified. |
| 2.10.0, 2.18.2 | Runtime profiles (global, workspace, selected). A webhook can select a profile. | Possible home for project env and secrets. Heavier than a base file. Workspace layer is also on the v3.0 removal list. | Spec 070, notes only. |

Dropped: Dagu has **no** base-config layering by subdirectory. It has one global base plus the workspace layer. `paths.base_config` is a single file.

### DAG discovery and names

| Version | Feature | Effect on design | Evidence |
|---|---|---|---|
| 2.15.0 | `dag_discovery.recursive` and `dag_discovery.symlinks`. With `symlinks: true`, YAML file symlinks, including ones that point outside `dags_dir`, are discovered. Symlinked directories are never followed. Dagu cannot edit or delete external targets. | A central store can hold the files and the repository view can use symlinks. A symlink as `dags_dir` itself is also supported. | Docs and code, source identical at v2.15.0 and v2.20.1. |
| 2.15.0 and 2.20.1 | Names: **the DAG name is the file stem.** Spec 002 forbids `name:` in the entrypoint document. `dagu validate` rejects it on both versions ("entrypoint document must not define name"). The runtime on 2.15.0 still accepted `name:` in a dry run. | Do not put `name:` in rendered files. Encode the project in the file stem, such as `devman-<project>-check.yaml`. Stems and names must both be unique. Rejection by `validate` may become rejection at run time. | **Verified** on both. |
| 2.15.0 and 2.20.1 | Collision rule in recursive mode: file stems and effective names must be unique; conflicting files are excluded until the conflict ends. | Same as today. No release changes it. Devman's "two files claim one DAG name" refusal stays needed. | Code identical at both tags. |
| 2.19.1 | DAG listing skips the configured base config file (#3126). | A `base.yaml` inside `dags_dir` is safe. | Notes and PR. |
| 2.17.2 | `.dag.index` lives under `data_dir`. | `dags_dir` can be read-only. | Notes and PR. |
| 2.13.0 | Opt-in DAG file symlinks (#2548). | Same as `dag_discovery.symlinks`. | Notes. |
| 2.20.1 | Workflow list can pin DAGs (2.19.0), saved views, and one name for "workflow" in the UI. | None. | Notes. |

A second route exists: `dagu start` and `dagu enqueue` take a DAG definition path **outside** `dags_dir`, with `--name` and `--labels`. `POST /api/v1/dag-runs/enqueue` takes an **inline YAML spec** with `name`, `params`, `queue`, `singleton`, `labels` and `profile`. A router can enqueue a rendered spec without writing any file for event-driven runs. Schedules still need a file in `dags_dir`. Read from the API schema, not run.

### Reuse: actions, import, sub-DAGs

| Version | Feature | Effect on design | Evidence |
|---|---|---|---|
| 2.7.1 and later | **Custom `actions:`** with `input_schema` and a `template` that holds exactly one of `run` or `action`. Dotted names such as `devman.check` are valid. Defined in `base.yaml` or in the DAG. Base and DAG actions merge; duplicate names across scopes are rejected. | Fits the `action: devman.check` plan for single-step workflows. A template is one step. It is not a multi-step workflow. | **Verified**: a base.yaml with `devman.check` and a DAG using it validate on 2.15.0 and 2.20.1. |
| 2.19.1 | Fix: custom actions in `base.yaml` raised "duplicate action" when base.yaml sat in the DAG directory (#3122, #3126). | Safe to keep base.yaml next to the DAGs. | Notes and PR. |
| 2.18.0 | Parse errors in base.yaml actions now surface on run records (#2890). | Better diagnosis of a bad shared action. | Notes. |
| 2.11.0 and later | **Action packages.** `dagu-action.yaml` plus a DAG entrypoint. Callers write `action: owner/repo@version`, `name@version` or `source:target@version` (a local path or `file://` path). Versioned. Inputs and outputs have JSON Schema. | A multi-step shared workflow, such as check, test or release, can be one package in the devman flake, called by `source:target@version`. Catch: the action DAG runs in a materialized action workspace and must not set `working_dir`. The project directory must arrive as a parameter. Caller `tools` are not inherited. | Present at v2.15.0 and v2.20.1 in docs; notes and docs only. Not run. |
| 2.x | Multi-document YAML: later documents are local sub-DAGs in the same file. `call`, `dag.run`, `dag.parallel`, `dag.enqueue` start children. | A project file can hold small local sub-DAGs. | Spec 002, docs. |
| 2.17.0 | `pass_env` on sub-DAG steps (#2783). Never passes secrets. Rejected on `dag.enqueue`. | A parent can hand `DEVMAN_PROJECT_DIR` to a child that runs on another host. Local children already see the parent scope. | Notes and PR. |
| 2.17.0 | `retry --bypass-preconditions`, `start --only`, `--output`, `--outputs-from` (2.17.2). | Re-run one step of a past run. Useful to retry a failed check only. | Verified in `--help` on 2.20.1. |

Dagu has no `import:` key and no template include for DAG files. Reuse is `actions`, action packages, sub-DAGs and the base config.

### Triggers and events

| Version | Feature | Effect on design | Evidence |
|---|---|---|---|
| 2.15.0 | `schedule` with `catchup_window`, `overlap_policy` (`skip`, `all`, `latest`) and `skip_if_successful`. | Already there. Use `catchup_window` to replay missed nightly runs after sleep. | Schema, verified. |
| 2.16.3, 2.18.0 | Cron descriptors such as `@daily`, `@hourly` (#2642, #2876). | Shorter schedule lines in project files. | Notes. |
| 2.16.4 | Catchup recovers after scheduler pauses (#2742). | Fewer lost runs after a restart. | Notes. |
| 2.16.5 | Global scheduler pause switch (#2762); `GET/POST /services/scheduler/pause`. | A one-call "pause the plane". | Notes and API file. |
| 2.7.1 and later | Per-DAG webhook: `POST /api/v1/webhooks/{fileName}` with a token; optional HMAC; `webhook.forward_headers`. Payload reaches the run as `WEBHOOK_PAYLOAD`. | A webhook source for `devman emit` can call a Dagu webhook directly, or devman can enqueue through `POST /dags/{file}/enqueue`. | Schema and API file. |
| 2.20.1 | Per-DAG webhooks can get a public URL through Dagu Cloud (#3164). | Not useful: needs a Dagu Cloud account. | Notes. |
| 2.13.0, 2.16.6 | **Notification channels and rules**: providers email, webhook (custom payload), Slack, Telegram, Teams. Events: `dag.run.waiting`, `succeeded`, `partially_succeeded`, `failed`, `aborted`, `rejected`. Rules are global, per workspace, and per DAG (`/dags/{file}/notifications`). | A webhook rule on `dag.run.failed` or `dag.run.succeeded` posts to an HTTP endpoint. That makes "workflow outcome" an event source for `devman emit` without polling. Needs a devman HTTP listener. | Notes and API file. Not run. |
| 2.x | `handler_on` (`success`, `failure`, `exit`) steps. | Alternative outcome hook: a handler step runs `devman emit`. No server setting needed. | Schema. |
| 2.x | Event store and `GET /event-logs` (`kind`, `type`, `dagName`, `dagRunId`, time range, cursor). | Poll for outcomes, if a push is not wanted. | API file. |
| **proposed, not shipped** | **RFC 004 "Triggers".** A `triggers:` field with sources `github`, `stripe`, `slack`, `webhook`, `file` (directory plus glob, by polling) and `dag` (another DAG's status). Status: Proposed. Only the public-webhook part is in 2.20.1. | If it ships, it replaces the router for file and outcome events. The shipped schema at 2.20.1 has no `triggers` key. Do not design around it. Watch the RFC. | RFC read in the repository at v2.20.1; schema diff **verified** absence. |

Dagu still has no native file-watch trigger and no "run when DAG X ends" trigger. The router stays.

### Queues

| Version | Feature | Effect on design | Evidence |
|---|---|---|---|
| 2.15.0 | Global `queues.config` list with `max_concurrency`; per-DAG `queue:` and `max_active_runs`. | Already used for the six names. | Schema. |
| **2.17.0** | **Scheduled runs enter the queue** when the DAG's queue (own YAML or base.yaml) is a queue defined in `config.yaml` (#2775). A DAG with no configured queue keeps its own local queue and starts directly. The same PR fixes dropped queued retries. | Fixes the pain "a scheduled run does not pass through its queue". Condition: every project DAG must name one of the six configured queues (set `queue:` in base.yaml, so it needs no per-file line). | Notes and PR. Not run. |
| 2.18.0 | Queue identity kept for distributed starts (#2895). Scheduler logs scheduled slots skipped while a DAG is busy (2.18.2, #2980). | Less guessing about skipped schedules. | Notes. |
| 2.16.1 | Large queues stay fast (#2673, #2678). | None for 33 repositories. | Notes. |
| 2.20.1 | UI shows stuck queues, queue fill, wait time of the next run, a stopped scheduler and a 90% full disk on the Overview (#3162, #3179). | Free monitoring of the plane. | Notes. |
| 2.15.0 | Enqueue API and CLI take a `queue` override and `singleton` (409 if the DAG already runs or waits). | `devman emit` can choose the queue per event, and `singleton` gives a free "debounce". | API file and CLI help, verified (CLI). |

### Agents

| Version | Feature | Effect on design | Evidence |
|---|---|---|---|
| 2.8.0 | `harness.run` can run in containers. | Optional isolation. | Notes. |
| 2.11.0 | `git.worktree.add` and `git.worktree.remove`; `human.task` steps; controller DAGs (renamed `type: agent` in 2.14.0, with `tasks:`). | Matches the spike: harness plus worktree plus human review. | Notes; schema lists `tasks`, `harness`, `harnesses`. |
| 2.15.0 | More built-in harness providers; agent actions run in parallel (#2584, #2585). | A fan-out of agent runs without extra wiring. | Notes. |
| 2.17.0 | Warning on implicit harness working directories (#2790). Kilo Code provider (#2823). `human-task` can attach run artifacts (#2824). | Always set `working_dir` on `harness.run`, or the run warns. Attach a diff or report for review. | Notes. |
| 2.17.2 | **Human-task push-back and rewind** (`with.push_back`, `rewind_to`, optional feedback form). Feedback reaches the rewound `harness.run` prompt as `DAG_PUSHBACK` env and prompt text. Independent branches resume while a task waits (#2838). | Gives a reject-with-feedback loop for agent review with no custom code. | Notes and PR. Not run. |
| 2.19.1 | Thinking effort mapped per provider for chat and agent steps (#3124). | None for `harness.run` with the `claude` CLI. | Notes. |
| 2.7.1 and later | Extra flags in `with:` pass to the CLI, such as `max-budget-usd` for claude. | Cost cap comes from the CLI flag, not from Dagu. | `llms.txt` example. |
| ? | **No cost or token budget reporting for `harness.run`.** The event store has `llm.usage.recorded` (`kind=llm_usage`, filter by `model`, `sessionId`). I found it only tied to Dagu's own chat and agent sessions, not to external CLIs. | Devman must read cost from the harness output or the CLI itself. | API file; code read. Not run. |

### Operations

| Version | Feature | Effect on design | Evidence |
|---|---|---|---|
| 2.16.6 | Live reload of base config (global and workspace) by the scheduler, with a debounce (#2770). | Editing a shared base takes effect without restart. | Notes and PR. Not run. |
| 2.16.2 | DAG list refresh after scheduler changes (#2689). Idempotent history cleanup (#2694). | None. | Notes. |
| 2.15.0 | `hist_retention_days` and `hist_retention_runs` per DAG; `dagu rm --history`. | Retention per DAG, set once in base.yaml. | Schema, verified. |
| 2.16.0 | **Git sync** (`dagu sync`) now covers scripts and configs next to a workflow (#2662). | Drop: devman files are machine-local. | Notes. |
| 2.16.5, 2.17.0 | `dagu ps --json`, local process info in the API, step-log ZIP download, `retry --bypass-preconditions`. | Cleaner status in `devman status`. | Notes. |
| 2.17.0 | Saved views for runs and artifacts; Artifacts page (#2774, #2788). | Per-project views in the UI. | Notes. |
| 2.20.1 | UI redesign, Activity view: "Needs attention" (failed latest run with the failed step, waiting approvals, slow runs), "In progress", "Up next". | Replaces a custom dashboard. Grouping still uses `group:` and labels. | Notes. |
| 2.18.2 | `--params-stdin` on `start` and `enqueue` (up to 1 MiB). | An event payload can pass as params without shell quoting. | **Verified** in `--help` (2.20.1); absent on 2.15.0. |
| 2.18.2 | Optional signal propagation to running DAG processes on shutdown (`signal_handling.enable_propagation`). | A scheduler restart can stop children cleanly. Off by default. | Config schema (new key on 2.20.1). |
| 2.15.0 | REST API under `/api/v1`: `/dags/{file}/enqueue`, `/dag-runs/enqueue`, `/dag-runs/{name}/{id}/…`, `/queues`, `/event-logs`, `/services/scheduler/pause`, `/webhooks`, `/sync/*`. MCP server for agents (2.7.1). | `devman emit` can enqueue by REST or by CLI. | API file. |

## Pain points

| Pain | Fixed? | Version and detail |
|---|---|---|
| Scheduled run bypasses the queue | **Yes** | 2.17.0 (#2775). Only for DAGs whose queue is defined in `config.yaml`. |
| `dag.enqueue` hides a child's failure | No | No release note addresses it. 2.17.0 adds outputs from parallel sub-DAGs, but not failure propagation from `dag.enqueue`. |
| `dag.run` bypasses the queue | No | No release note addresses it. (2.17.0 changes scheduled runs only.) |
| Dagu reads `$SHELL` from the enqueuing process | No | No release note addresses it. Set `shell` (and `shell_args`) in base.yaml, or `with.shell` per step. 2.18.0 adds a dry-run warning for a missing shell. |
| Duplicate basename in two subdirectories gives "No DAGs found" | No | Discovery code is identical at v2.15.0 and v2.20.1. Rule: stems and names unique; conflicting files excluded. Keep devman's refusal. |
| `.dag.index` cannot be written into a read-only dags dir | **Yes** | 2.17.2 (#2858). Index goes to `<data_dir>/cache/dag-index/`. |
| No native file-watch trigger | No | RFC 004 proposes `source: file` (polling). Not shipped; no `triggers` key in the 2.20.1 schema. |
| `dags_dir` symlink repoint is not followed | Unknown | No note claims a fix. 2.16.6 reworked watching (new `entryreader.go`) but watches the resolved target and refreshes only on events inside it. Events from a repointed link are not obviously handled. Re-spike on 2.20.1 before relying on it. Per-file atomic rename (current G2 plan) stays the safe route. |
| Base-config schedule, catchup and queue ignored by the scheduler | **Yes** | 2.16.6 (#2770). |
| Dotenv missing in scheduled runs | **Yes** | 2.18.0 (#2937). |

## Not useful

- Git sync (`dagu sync`): devman files are machine-local, not a shared repository.
- Dagu Cloud relay, public webhook URLs, Dagu Console and licensing changes (2.19, 2.20): needs an account.
- Browser, computer, xlsx, mailbox, `js.run`, `decision.evaluate`, Gemini and Kilo providers (2.17 to 2.19): no bearing on repository automation.
- Distributed workers and coordinator fixes (2.15.4, 2.16.0, 2.16.1): the plane runs on one machine.
- Helm chart and Windows installer tags: not for this machine.
- Runtime profiles: a base file does the same job with less machinery, and the workspace layer is on the removal list.
- Web UI localisation and layout changes: no design effect.
- Workspace feature as a long-term base: planned removal in v3.0 (RFC 003). Use it only as a bridge.
- Controller and agent DAG type (`type: agent`, `tasks:`): the spike chose `harness.run` plus human review.
- RFC 004 triggers: proposed only.

## Recommendations

1. Upgrade the pin to 2.20.1 in a separate lane. Re-run the reload spike on it, including the repointed `dags_dir` symlink.
2. Set `queue:` (one of the six names), `shell`, retention and, if wanted, `catchup_window` in the global base.yaml. On 2.17.0 and later this base now reaches the scheduler and the queue.
3. Choose the per-project context route before the redesign locks in. Option A: keep a rendered header (works on any version). Option B: a `workspace=<project>` label with `workspaces/<project>/base.yaml` (less rendering, verified on 2.15.0, ends at v3.0). Option C: set context at enqueue time with `--default-working-dir`, `--labels` and `--name` for events, plus a header for scheduled runs. I suggest C with a thin header, because B ends at v3.0.
4. Use `action: devman.check` templates for one-step workflows. Use an action package (`source:target@version`) for multi-step ones, and pass the project directory as a parameter.
5. Use notification-channel webhook rules or `handler_on` steps for the "workflow outcome" event source.

## Sources

Release tags read (notes via `gh release view`): v2.15.1, v2.15.2, v2.15.3, v2.15.4, v2.16.0, v2.16.1, v2.16.2, v2.16.3, v2.16.4, v2.16.5, v2.16.6, v2.17.0, v2.17.2, v2.18.0, v2.18.1, v2.18.2, v2.19.0, v2.19.1, v2.19.2, v2.20.1. Earlier tags skimmed for feature origin: v2.7.1, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.14.0, v2.15.0.

Pull requests read: #2775 (queue pacing), #2770 (base reload), #3126 (base config skip), #2858 (index under data_dir), #2937 (dotenv), #2783 (`pass_env`), #2885 (signal propagation), #2840 (human-task push-back).

Files read at tag v2.20.1 (shallow clone into a temp directory): `llms.txt`, `specs/002-yaml-schema.md`, `specs/017-built-in-run-context.md`, `specs/067-harness.md`, `specs/070-runtime-profiles.md`, `rfcs/003-remove-workspaces.md`, `rfcs/004-triggers.md`, `api/v1/api.yaml`, `internal/persis/file/dag/discovery.go`, `internal/persis/file/dag/entryreader.go`, `internal/workspace/workspace.go`, `internal/cmd/validate.go`, `README.md`, `LICENSING.md`.

Docs: https://docs.dagu.sh (linked from release notes), https://github.com/dagucloud/dagu/releases, https://github.com/dagucloud/dagu/tree/v2.20.1/specs

Checks run: `dagu schema dag` and `dagu schema config` on 2.15.0 and on a downloaded 2.20.1 binary (SHA-256 matched `checksums.txt`; temp `DAGU_HOME`); `dagu validate` on both; `--help` diffs for `start`, `enqueue` and the root command. On 2.15.0 only, with a temp `DAGU_HOME`: one `dagu dry` and one `dagu start` of an `echo` DAG to test the workspace base config. I started no scheduler or server, and ran no DAG with the downloaded binary.
