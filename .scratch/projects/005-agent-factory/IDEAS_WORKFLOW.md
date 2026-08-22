# Factory workflow

This repository is an idea-to-output factory. Its job is to preserve a raw
thought with almost no friction, then progressively turn selected ideas into a
useful, inspectable result: a project, article, research brief, experiment, or
decision record.

`devenv.sh` is the stable human and agent interface. Jujutsu (JJ) is the local
work model. Git is the publishing and interoperability layer.

## Principles

- Capture first; structure later. An incomplete idea is valid input.
- Interrogate before building. Never start planning or coding an idea until it
  has been challenged and shared understanding is confirmed (see below).
- Keep the source context. A resulting brief should link to or include the
  relevant Paseo conversation, notes, prompts, and assumptions.
- Prefer small, independently understandable changes over long-lived agent
  branches.
- Automation may recommend and prepare work; it must not silently publish,
  discard, or rewrite a user's work.
- Fast, objective checks may block a change. Agent judgment should normally
  create a review artifact or a clear recommendation instead.

## Lifecycle

An idea moves through these states. State is recorded in its front matter or
metadata, never inferred only from a commit message.

```text
inbox -> triaged -> developing -> ready -> published
                  \-> parked
                  \-> archived
```

| State | Meaning | Minimum record |
| --- | --- | --- |
| `inbox` | Raw captured thought; no judgment yet. | Title, source, captured date |
| `triaged` | Worth revisiting and given a proposed destination. | Problem, outcome type, next action |
| `developing` | Active work has an owner and a JJ change. | Brief, decisions, active change ID |
| `ready` | Meets the output type's acceptance criteria. | Deliverable and verification evidence |
| `published` | Shared externally or merged into the appropriate repository. | Destination URL or revision |
| `parked` | Potentially useful but intentionally inactive. | Reason and revisit trigger |
| `archived` | No further action is intended. | Reason, if useful |

## Roles

### Intake and triage agent

Turns a pasted chat, note, or URL into an idea record. It preserves the raw
input and produces a short brief:

- the idea in one sentence;
- the problem or opportunity;
- intended audience;
- proposed output type: `project`, `article`, `research`, `experiment`, or
  `decision`;
- assumptions, open questions, and risks;
- the smallest useful next action.

It may label an item `archived` or `parked`, but it must explain why. It does
not create a publishable project or claim research conclusions.

Before any idea moves toward `developing`, the agent must **interrogate the idea
itself** and confirm shared understanding before building:

1. Interrogate — surface hidden assumptions, internal contradictions, undefined
   or overloaded terms, scope boundaries and non-goals, dependency/naming
   collisions, and the single riskiest unknown. Argue with the idea, do not just
   restate it.
2. Ask — put the minimum set of concrete, decision-shaping clarifying questions
   to the user.
3. Confirm, then proceed — only after those are resolved is a plan or code
   written. New ambiguity mid-work sends you back to step 1.

### Workflow agent

Owns the JJ work plan and repository hygiene. Before directing substantive
work, it checks the idea brief, current JJ log, working-copy diff, and any
unrelated outstanding changes. It then chooses one of these actions:

| Situation | JJ action |
| --- | --- |
| Work advances the same deliverable and remains reviewable together. | Continue the current change. |
| Work has a distinct purpose or can be reviewed and landed separately. | Create a child change. |
| Two tracks can proceed independently, such as research and a prototype. | Create sibling changes. |
| A change contains separable purposes. | Split it before review or landing. |
| Several dependent changes are one inseparable deliverable. | Squash only after preserving useful descriptions and decisions. |

The workflow agent writes and maintains change descriptions. A description
states intent, notable decisions, verification performed, and known limits. It
never uses destructive JJ operations without explicit user authorization.

### Specialist agents

Specialists work within the scope assigned by the workflow agent and return
artifacts rather than vague status reports.

| Specialist | Expected artifact |
| --- | --- |
| Research | Sourced brief, confidence level, unanswered questions |
| Writing | Thesis, outline or draft, audience and editorial notes |
| Product/spec | Problem statement, acceptance criteria, non-goals |
| Engineering | Runnable implementation, tests, setup and limitations |
| Review | Findings ordered by severity, evidence, suggested follow-ups |

## JJ and Git policy

- Use JJ locally for changes, descriptions, rebasing, splitting, and recovery.
- Treat Git branches, pushes, and pull requests as explicit publication steps.
- One concrete deliverable normally maps to one named JJ change; a chat session
  does not automatically deserve its own change.
- Before a push or PR, the workflow agent ensures the change has a description,
  a clean intended diff, and recorded verification.
- Preserve provenance in repository files. JJ descriptions aid review but are
  not the sole record of the idea's rationale.
- Sync with remotes deliberately. A hook may report divergence but must not
  auto-push, auto-bookmark, or auto-land changes.

## Hook contract

Hooks are a thin, deterministic event router. They collect changed paths and
JJ/Git context, execute cheap checks, and optionally enqueue specialist work.
They do not embed prompts or make workflow decisions.

### Synchronous checks

These must be fast, deterministic, and safe to run repeatedly. Target a total
latency of two seconds for ordinary changes.

- formatting and generated-file freshness where applicable;
- syntax, lint, or type checks scoped to changed files;
- secret and credential detection;
- required idea metadata validation;
- basic link or reference validation when cheap.

Only objective failures block completion. Every failure identifies the command
to reproduce it locally.

### Asynchronous checks

These produce an artifact linked to the change and never alter it themselves.

- source and citation review for research;
- architecture or security review for software;
- editorial review for writing;
- broader test suites and integration checks;
- metadata or taxonomy suggestions.

The workflow agent decides whether an asynchronous finding becomes a follow-up
change, a revision to the current change, or an accepted risk.

### Events

Initial event names may map to Git hooks for compatibility, but their input is
repository state rather than Git-only assumptions.

| Event | Purpose |
| --- | --- |
| `change:validate` | Run synchronous checks against the intended JJ change. |
| `change:review` | Queue relevant specialist review. |
| `publish:validate` | Run full required checks before push or PR creation. |
| `idea:triaged` | Queue the next recommended development action. |

## `devenv.sh` interface

Start with a small command surface and retain stable machine-readable output
where agents need it.

```sh
./devenv.sh idea capture <source>
./devenv.sh idea triage <idea-id>
./devenv.sh idea develop <idea-id>
./devenv.sh change status
./devenv.sh change validate
./devenv.sh change review
./devenv.sh publish validate
```

The scripts should provide `--json` for agents, clear human output by default,
and `--dry-run` for actions that would create files, changes, or queued jobs.
The initial implementation may be simple shell plus checked-in templates;
external agent calls should sit behind one adapter so providers can change.

## Output acceptance criteria

Every output type has a small definition of done:

- **Research:** question, sources, synthesis, confidence, and open questions.
- **Article:** audience, thesis, outline or draft, source/claim review.
- **Software:** problem/spec, runnable setup, tests appropriate to risk, and
  documented limitations.
- **Experiment:** hypothesis, method, observations, conclusion, and follow-up.
- **Decision:** context, options, decision, consequences, and revisit trigger.

## First implementation milestone

Build only the vertical slice needed to prove the workflow:

1. Define the on-disk idea template and create `idea capture`.
2. Add `idea triage` to produce a brief and state transition.
3. Add `change status` and `change validate` with JJ-aware context and metadata
   checks.
4. Add one asynchronous review adapter that writes a review artifact.
5. Use the workflow on three real ideas, then revise states, templates, and
   branching rules based on friction observed.

Do not add background workers, a database, or a large hook framework until
this slice has demonstrated a genuine need for them.
