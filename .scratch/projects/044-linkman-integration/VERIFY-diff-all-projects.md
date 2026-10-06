# Verification — Linkman `check`/`diff` against all 60 overlay projects

Date: 2026-10-05.

## Commands used

Binary: `/home/andrew/Documents/Projects/linkman/.devenv/state/venv/bin/linkman`
(the linkman repo's own editable venv — "the sibling checkout's binary" per
`PLAN-lanes.md` lane 3). `which linkman` found nothing on `PATH`. The devman
repo carries a second copy at
`/home/andrew/Documents/Projects/devman/.devenv/state/venv/bin/linkman`; both
`dist-info/direct_url.json` files show the same editable install
(`file:///home/andrew/Documents/Projects/linkman`, `editable: true`), and
`--help` output is byte-identical, so the two binaries are the same code. This
report used the linkman-repo one.

Linkman source at commit `06de662dc8c09714a2663166e9fef1a97fec07b0`
(2026-10-05T13:15:24-04:00, "m14 l9c: package Linkman as a pinnable Nix
flake"). Package version `linkman-0.1.0.dist-info`.

`--help` confirms six subcommands: `config`, `check`, `diff`, `apply`, `prune`,
`migrate`. This report ran only `config`, `check`, `diff`, each with:

```
linkman <config|check|diff> --repo-root ~/Documents/Projects/<name> \
  --overlay ~/.config/devman --name <name> --json
```

No `apply`, `migrate`, or `prune` ran. No `devman link reconcile` or
`devman-link reconcile` ran. No devenv shell entered.

## Executive verdict

**Safe to proceed to lane 4, with one fix first.**

- 60 overlay project directories under `~/.config/devman/projects/`. 59 have a
  live checkout under `~/Documents/Projects/<name>`. 1 does not: `foreman`.
- All 59 checked projects: `check` exit 0, `clean: true`, 0 of 283 declared
  links non-correct, 0 refusals.
- All 59 checked projects: `diff` exit 0. Every one of 283 planned actions is
  `noop`. **The cutover is a no-op for every live project.** No migration, no
  repoint, no refusal, anywhere.
- Disjoint-namespace risk: **0 of 60 would refuse.** Only one repository
  (`linkman` itself) carries its own `links.yaml`, and it declares zero links
  and zero vars, so no overlap with the overlay layer is possible anywhere.
- Exclude-set equality: **58 of 59 identical** once one unrelated hand-written
  line is correctly classified as not-owned. **1 project has a real gap:**
  `linkman`'s own overlay declaration is missing a `.loci` link that every
  comparable project declares, and the repository holds a real (non-symlink)
  `.loci` directory that depends on today's legacy exclude line to stay out of
  `git status`. Fix this before lane 4 (see the closing list).
- No dangling targets, no `special` paths, no unresolved `${env.*}` or
  `${vars.*}` tokens, no YAML parse failures, anywhere in the 59 checked
  projects.

Findings count: **1 project with a finding that blocks lane 4/5** (`linkman`),
**0 projects with findings that block the engine-swap itself** (lane 5's `diff`
output is clean everywhere).

## Per-project results (60 rows)

`checkout` = live checkout present. `check_exit`/`diff_exit` = process exit
code (0 everywhere a checkout exists). `clean` = `check` JSON's `clean` field.
`links_total` = `check` JSON's `summary.total`. `noncorrect` =
`total - correct` (0 everywhere). `diff_mutates` = any plan action other than
`noop` (none, anywhere). `exclude_match` = owned exclude-entry set identical to
`.local.gitignore` today (see §5).

| project | checkout | check exit | clean | links total | non-correct | diff mutates | exclude match |
|---|---|---|---|---|---|---|---|
| agentman | yes | 0 | true | 5 | 0 | no | yes |
| argentic | yes | 0 | true | 5 | 0 | no | yes |
| atuout | yes | 0 | true | 5 | 0 | no | yes |
| browsee | yes | 0 | true | 5 | 0 | no | yes |
| cairn | yes | 0 | true | 5 | 0 | no | yes |
| clinch | yes | 0 | true | 5 | 0 | no | yes |
| copyroom | yes | 0 | true | 5 | 0 | no | yes |
| devman | yes | 0 | true | 5 | 0 | no | yes |
| docman | yes | 0 | true | 5 | 0 | no | yes |
| embeddy | yes | 0 | true | 5 | 0 | no | yes |
| eventic | yes | 0 | true | 5 | 0 | no | yes |
| flora | yes | 0 | true | 6 | 0 | no | **no** (see §5 — not-owned line) |
| flora-core | yes | 0 | true | 5 | 0 | no | yes |
| flora-qc | yes | 0 | true | 5 | 0 | no | yes |
| foreman | **no** | N/A | N/A | N/A | N/A | N/A | N/A |
| forgelab | yes | 0 | true | 5 | 0 | no | yes |
| fornix | yes | 0 | true | 5 | 0 | no | yes |
| fsdantic | yes | 0 | true | 5 | 0 | no | yes |
| gitman | yes | 0 | true | 5 | 0 | no | yes |
| grail | yes | 0 | true | 5 | 0 | no | yes |
| inferference | yes | 0 | true | 5 | 0 | no | yes |
| interplay | yes | 0 | true | 5 | 0 | no | yes |
| knappy | yes | 0 | true | 5 | 0 | no | yes |
| linkman | yes | 0 | true | 4 | 0 | no | **no** (see §5 — real gap) |
| llgym | yes | 0 | true | 5 | 0 | no | yes |
| loci-core | yes | 0 | true | 5 | 0 | no | yes |
| loci.nvim | yes | 0 | true | 5 | 0 | no | yes |
| mnemonix | yes | 0 | true | 3 | 0 | no | yes |
| nixbuild | yes | 0 | true | 5 | 0 | no | yes |
| nix-desktop | yes | 0 | true | 5 | 0 | no | yes |
| nix-meta | yes | 0 | true | 3 | 0 | no | yes |
| nix-nvim | yes | 0 | true | 5 | 0 | no | yes |
| nixos-core | yes | 0 | true | 3 | 0 | no | yes |
| nix-paseo | yes | 0 | true | 5 | 0 | no | yes |
| nix-secrets | yes | 0 | true | 6 | 0 | no | yes |
| nix-terminal | yes | 0 | true | 3 | 0 | no | yes |
| nixvim | yes | 0 | true | 5 | 0 | no | yes |
| observantic | yes | 0 | true | 5 | 0 | no | yes |
| parsedantic | yes | 0 | true | 5 | 0 | no | yes |
| poddantic | yes | 0 | true | 5 | 0 | no | yes |
| pydantree | yes | 0 | true | 5 | 0 | no | yes |
| PyGentic | yes | 0 | true | 5 | 0 | no | yes |
| pyjutsu | yes | 0 | true | 5 | 0 | no | yes |
| pyllij | yes | 0 | true | 5 | 0 | no | yes |
| pytuin | yes | 0 | true | 5 | 0 | no | yes |
| repoman | yes | 0 | true | 5 | 0 | no | yes |
| scopeman | yes | 0 | true | 4 | 0 | no | yes |
| shellij | yes | 0 | true | 5 | 0 | no | yes |
| silverbullet-server | yes | 0 | true | 3 | 0 | no | yes |
| siteman | yes | 0 | true | 5 | 0 | no | yes |
| structured-agents-v2 | yes | 0 | true | 5 | 0 | no | yes |
| talkee | yes | 0 | true | 5 | 0 | no | yes |
| templateer_v2 | yes | 0 | true | 5 | 0 | no | yes |
| template-py | yes | 0 | true | 3 | 0 | no | yes |
| terminal-state | yes | 0 | true | 5 | 0 | no | yes |
| testee | yes | 0 | true | 5 | 0 | no | yes |
| tyo3 | yes | 0 | true | 5 | 0 | no | yes |
| vendomat | yes | 0 | true | 5 | 0 | no | yes |
| webdantic | yes | 0 | true | 5 | 0 | no | yes |
| zelligate | yes | 0 | true | 5 | 0 | no | yes |

Total declared links checked across the 59 live projects: 283. All 283: status
`correct`, action `noop`.

## 1. Enumeration

60 overlay project directories under `~/.config/devman/projects/`.
59 have a checkout at `~/Documents/Projects/<name>`. 1 does not:

- `foreman` — no directory at `~/Documents/Projects/foreman`.

No other project is missing its checkout.

## 2. `linkman check --json` — status of every declared link

Ran against all 59 checked-out projects. Every run: exit 0.

Aggregate:

| metric | value |
|---|---|
| projects checked | 59 |
| projects with `clean: true` | 59 / 59 |
| total declared links (sum of `summary.total`) | 283 |
| total `correct` | 283 |
| total `changes_required` | 0 |
| total `refusals` | 0 |

Per-project `links_total` ranges from 3 (`mnemonix`, `nix-meta`, `nixos-core`,
`nix-terminal`, `silverbullet-server`, `template-py` — these projects do not
declare `.loci`) to 6 (`flora`, `nix-secrets` — these declare an extra
`.claude/settings.local.json` link). No project has a non-`correct` link, so
there is nothing to list under "every link that is NOT `status: correct`" —
the list is empty for all 59.

Sample raw evidence (`agentman`, representative of all 283 links):

```json
{
  "link_rel": ".agents",
  "status": "correct",
  "expected_target": "/home/andrew/.config/devman/projects/agentman/agents",
  "observed_kind": "symlink",
  "observed_raw_target": "/home/andrew/.config/devman/projects/agentman/agents",
  "refusal_reason": null,
  "source": "/home/andrew/.config/devman/projects/agentman/links.yaml",
  "message": "link matches its declaration",
  "safe_next_step": null
}
```

```json
{"total": 5, "correct": 5, "changes_required": 0, "refusals": 0}
```

## 3. `linkman diff --json` — the plan for every project

Ran against all 59 checked-out projects. Every run: exit 0 (no `DRIFT`, no
`REFUSAL`).

Action-kind census across all 59 plans, 283 planned links:

```
283 noop
```

No `create_target_file`, `create_target_dir`, `create_link`, `repoint_link`, or
`refuse` action occurs anywhere. **Every one of the 59 projects would be a
complete no-op under `linkman apply`.** None would mutate the filesystem.

Sample raw evidence (`agentman`, `.agents` link):

```json
{
  "link_rel": ".agents",
  "desired": {
    "target_abs": "/home/andrew/.config/devman/projects/agentman/agents",
    "raw_symlink_target": "/home/andrew/.config/devman/projects/agentman/agents",
    "target_scope": "external",
    "declared_kind": "dir",
    "source": "/home/andrew/.config/devman/projects/agentman/links.yaml"
  },
  "actual": {
    "link": {"kind": "symlink", "raw_link_target": "/home/andrew/.config/devman/projects/agentman/agents"},
    "target": {"kind": "dir"}
  },
  "status": "correct",
  "actions": [{"kind": "noop", "link_rel": ".agents", "reason": null}]
}
```

## 4. The disjoint-namespace risk

`load_layers` (`linkman/src/linkman/config.py:44-76`) raises `ConfigError`
(exit 10) the moment the same link path, or the same variable name, is
declared in both the repo layer and the overlay layer. It does not merge or
override; it refuses.

**Cheap check — which repos carry their own `links.yaml`?**

```
$ ls ~/Documents/Projects/*/links.yaml
/home/andrew/Documents/Projects/linkman/links.yaml
```

Exactly one of the 60 projects: `linkman` itself. Its full content:

```yaml
version: 1
links: {}
```

It declares zero links and (no `vars:` key, so) zero variables. No overlap
with the overlay layer is possible for this or any other project, because no
other project has a repo-level `links.yaml` at all.

**Exit-code check across all 59 live projects.** `exit_codes.tsv` (captured
during this run) shows `check_exit`, `diff_exit`, `config_exit` all equal to
`0` for every one of the 59 projects — no project exited 10, 11, 12, or 13 on
any of the three read-only commands. Every `.err` capture file was empty
(0 bytes) for all 59 × 3 = 177 invocations.

**Definitive count: 0 of 60 projects would refuse on the disjoint-namespace
ground.** 59 have no repo-level `links.yaml` at all (nothing to collide with
the overlay). The 60th (`linkman`) has one, but it is empty, so it cannot
collide either. `foreman` was not run (no checkout) but also carries no
repo-level `links.yaml` to create this risk, moot regardless.

## 5. Exclude-set equality

Rule used, exactly as specified: for each declared link, resolve its target
with `linkman config --json` (field `target_abs`), test
`target_abs.is_relative_to(repo_root) and target_abs != repo_root` — true means
inside the repo (skip), false means include. Owned entry set =
`[".devman/.runs/"]` plus every link whose target is outside the repo.

**First finding: every single resolved link, across all 283, has
`target_scope: "external"`.** Zero are `internal`. So for every project, the
computed owned set is simply `{".devman/.runs/"} ∪ {all declared link_rel
keys}` — nothing gets excluded from the owned set by the inside/outside test in
practice today.

**Classification of current `.local.gitignore` lines not owned by the
projection.** Comments (`#...`), blank lines, `/.jj/` (the jj-workspace
marker), and the `**/.claude/...` block that follows the
`# claude-code-runtime` comment in several files — these are hand-authored,
not produced by any link declaration, and are excluded from the comparison per
the task's own example.

**Mechanical result, before judgment:** comparing the owned set to the
remaining (non-excluded) lines gives 57 of 59 identical. Two differ:

```
flora   ADD: []  DROP: ['.scratch/projects/063-warm-sglang-sweep/smoke_prompts.json']
linkman ADD: []  DROP: ['.loci']
```

**`flora`'s extra line is also hand-authored, unrelated content — not owned.**
`~/Documents/Projects/flora/.scratch/projects/063-warm-sglang-sweep/smoke_prompts.json`
is a real, untracked file; the line is a one-off scratch-output exclusion, not
a projected link view (it is deeply nested, project-specific, and no other
project's exclude file has anything like it; `flora`'s `links.yaml` has no key
resembling it). Classified "not owned, ignore," the same as `/.jj/` and the
`claude-code-runtime` block. **Not a bug.**

**`linkman`'s `.loci` line is a real gap.** `~/Documents/Projects/linkman/.loci`
exists as a genuine directory (not a symlink):

```
$ ls -la ~/Documents/Projects/linkman/.loci
drwxr-xr-x - andrew 30 Sep 17:09 .loci
$ git -C ~/Documents/Projects/linkman ls-files | grep '^\.loci'
(nothing — not tracked)
$ git -C ~/Documents/Projects/linkman check-ignore -v .loci
.git/info/exclude:11:.loci	.loci
```

It is real, untracked, local content that stays out of `git status` **only**
because today's `.local.gitignore` carries a `.loci` line. But the overlay
declaration that governs this project —
`~/.config/devman/projects/linkman/links.yaml` — declares only `.agents`,
`.claude/skills`, `.envrc`, `devenv.local.nix`. **No `.loci` key.** Every other
project in this plane that has a `.loci` directory declares it as a managed
link (49 of the other 58 do). `linkman` is the one project where `.loci` is
real content, not a link, and its exclusion depends on a line the new,
links.yaml-derived rule would not produce.

**Definitive verdict: 58 of 59 checked projects have an IDENTICAL owned
exclude-entry set once the one unrelated hand-written line (`flora`) is
correctly classified as not-owned.** The sole project where it differs for a
real reason is **`linkman`**, and the diff is:

```
linkman: current owns {".devman/.runs/", ".agents", ".claude/skills", ".envrc", "devenv.local.nix", ".loci"}
         new rule computes {".devman/.runs/", ".agents", ".claude/skills", ".envrc", "devenv.local.nix"}
         DROP: .loci
```

Whether this is a regression depends on how lane 4 implements the projection:
`append_entries` in today's engine (`src/devman_link/excludes.py:64-73`) only
*appends* missing entries and never deletes a line, so if lane 4 keeps that
append-only behavior, the stale `.loci` line stays and nothing breaks today.
But the *computed owned set* the new rule reports for `linkman` is wrong
regardless — it is missing a key every comparable project has for a directory
that demonstrably exists and needs it. If lane 4's gate ever moves to a
full-regenerate model instead of append-only, this gap becomes a live
regression (an untracked directory suddenly visible in `git status`). Treat it
as a data gap to close now, not a projection bug to chase later.

`foreman` excluded from this section (no checkout).

## 6. Anomalies

Checked across all 59 live projects, all 283 declared links, all 59
`config --json` runs:

| anomaly class | found | evidence |
|---|---|---|
| unresolved `${env.*}` / `${vars.*}` tokens | **0** | all 59 `config` runs exited 0; a `ResolutionError` would exit 10 and none did |
| dangling targets (`actual.target.kind == "missing"`) | **0** | target-kind census across all 283 diff entries: `168 dir`, `115 file`, `0 missing` |
| `real_file` / `real_dir` refusals | **0** | `check` summary `refusals` totals 0 across all 59; `changes_required` totals 0 |
| `special` path kind (link or target) | **0** | link-kind census across all 283: `283 symlink`, 0 of any other kind |
| `links.yaml` parse/validation failure | **0** | all 59 `config`/`check`/`diff` runs exited 0 with empty stderr; the one repo-level `links.yaml` (`linkman`) also parses cleanly |
| non-empty stderr on any of the 177 read-only invocations | **0** | every `.err` capture file is 0 bytes |

No other anomaly class surfaced. The plane's 59 live projects are, as of
2026-10-05, in exactly the state their `links.yaml` declares.

## What must be fixed before lane 4 (then lane 5)

1. **`linkman`'s overlay `links.yaml` is missing a `.loci` declaration.** The
   repository holds a real, untracked `.loci` directory that depends on a
   legacy exclude line the new links.yaml-derived rule will not reproduce.
   Add the `.loci` key to
   `~/.config/devman/projects/linkman/links.yaml` (matching the pattern every
   comparable project uses), or decide explicitly that `linkman` keeps `.loci`
   as unmanaged real content and document that choice — before lane 4 computes
   exclude sets from `links.yaml` alone.

Nothing else blocks the cutover. The disjoint-namespace refusal that lane 3 was
built to catch does not occur anywhere in the 60 projects. `diff` is a no-op in
every one of the 59 live projects. `foreman` has no checkout to verify against
and was not run; it carries no repo-level `links.yaml`, so it carries none of
the risks checked here, but its `check`/`diff` behavior remains unmeasured
until it exists on disk.
