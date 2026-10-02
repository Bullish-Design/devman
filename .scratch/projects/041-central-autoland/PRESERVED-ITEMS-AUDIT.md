# Preserved-items audit — O8, items 2 and 13

Date: 2026-10-01

Scope: `.scratch/projects/025-the-link-plane/CONCEPT.md` §10 items 2 and 13,
both of which cite `devman/modules/devenv.nix`, a file deleted by commit
`37050e9` ("refactor: delete the compatibility plane module", 2026-09-19
14:51:39 -0400, 553 lines removed). This closes devman project 041, open
question O8.

Mode: read-only audit of code and git history. Nothing was mutated. Only raw
`git log`/`show`/`grep` were used; no `gitman` or `jj` command ran.

Extends: `.scratch/projects/035-config-repo-cleanup/README.md` and
`036-lane-and-charter-audit/README.md`, which previously closed adjacent
link-plane questions. Supersedes nothing; item 13's finding corrects §10's own
citation, which already pointed at stale line numbers before the deletion.

## Executive result

- **Item 2 (duplicate-registration refusal): LOST.** No code path in today's
  tree compares a project name's previously-registered root against the
  current one before writing a registry entry. The only thing that even looks
  for two checkouts sharing a project name is a manual, opt-in sweep
  (`devman link status --all --projects-root <dir>`) that no automatic
  process — not shell entry, not `doctor` — ever runs.
- **Item 13 (exclude writer's worktree awareness): PRESERVED by construction,
  with a direct test.** The mechanism moved out of `modules/devenv.nix` eight
  days *before* the deletion (commit `35efaa3`, 2026-09-10) into
  `src/devman_link/excludes.py`, where it is stronger than the original: it
  also follows a worktree's `commondir` indirection, which the cited revision
  did not need to.

## Item 2 — the duplicate-registration refusal

### What the old mechanism did

The cited line range (`:778-786`) is from a revision before `37050e9^`; by
content, the refusal in the file as it stood at deletion is the `elif` branch
near the end of the `enterShell` script:

```
elif [ -n "$devman_recorded" ] && [ "$devman_recorded" != "$devman_root" ] \
     && [ -d "$devman_recorded" ]; then
  echo "devman: refusing to register '${projectName}'" >&2
  echo "devman:   already registered at $devman_recorded, which still exists" >&2
  echo "devman:   this repo is        $devman_root" >&2
  echo "devman:   set a different devman.project in one of them" >&2
```
(recovered text, `git show 37050e9^:modules/devenv.nix`, lines ~524-531 of 553)

Three properties, confirmed by reading the block:

1. **Refused at shell entry**, synchronously, before any projection write —
   not a post-hoc report.
2. **The condition it detected:** a project name whose registry-recorded path
   differs from the current checkout's path, when the recorded path still
   exists on disk. A recorded path that is *gone* is treated as a move, not a
   collision (the entry is replaced, which the comment ties to "criterion
   11"/C5).
3. **"Unique by construction" described the registry layout** (one
   `metadata.json`/workflow set per project name), not an unenforceable
   filesystem guarantee. The refusal is what made that layout actually mean
   one physical repository per name — without it, a second checkout using the
   same name would simply overwrite the first's entry on its own next write.

This is the mechanism §6.4 of the same CONCEPT.md calls *"the only defence"*
against a duplicate DAG name — the hazard where `dagu ls` prints a name once,
exit 0, while the manual run path and the scheduler quietly pick different
files (§6.4's worked example: `dags/flora.nightly.yaml -> repoA`,
`dags/flora.nightly.yml -> repoB`).

### Where the equivalent was sought, and what was found instead

| Candidate location | What it actually does | Does it compare root paths across checkouts for one project name? |
|---|---|---|
| `src/devman/reconcile.py:384-517` (`compatibility_apply` → `_publish_compatibility_bundle`) | Writes `projects/<name>/workflows/*.yaml`, `metadata.json`, and the `dags/` symlinks, keyed purely by `manifest.project` | No — no read of any prior root before writing |
| `src/devman_link/identity.py:80-121` (`resolve_project_identity`) | Validates the manifest's `project` field grammar, and that `--project` agrees with the manifest when both are given | No — single-repository, single-call scope only |
| `src/devman/registry.py:479-518` (`Registry.project_for` → `_checkout_between`) | Refuses when a checkout is a `.git`-bearing directory physically *nested inside* another registered checkout's own path tree | No — this is a different hazard (parent/child nesting of one developer's own checkouts), not two disjoint checkouts sharing a name. Confirmed by its test, `tests/unit/test_registry.py:112` (`test_a_checkout_inside_a_registered_one_is_refused`) |
| `src/devman/doctor.py` — all 23 checks run by `main()` (`:1593-1644`) | `check_dag_names` (`:530`) checks name-grammar validity; `check_projection` (`:489`) checks that an existing `dags/` link still points at *that project's own* projected file | No check reads two different on-disk roots and asks whether they declare the same project name |
| `src/devman/cli.py:286-333` (`_manifest_candidates`) via `devman link status --all` (`:368-`) | Walks an explicit `--projects-root` directory, reads every child's `.devman/project.toml`, and reports `"duplicate manifest identity"` for two children sharing a name | **Yes, but** — manual only, requires an explicit flag naming the directory to scan, and is reachable from nowhere else in the codebase (confirmed: the only references to `_manifest_candidates`/`_link_all` are their own definitions and the `link status --all` dispatch, `cli.py:531-533`) |

`src/devman/cli.py:9-15` states the design intent directly: *"there is no
`list`, no `status`, no `register` and no `unregister`, because registration
is automatic and has no manual path (§5.2)"* — but that statement describes
the *developer-facing* three-command surface; `link status --all` exists
precisely as the escape hatch for the case the automatic path cannot see, and
nothing wires it into that automatic path.

### Classification and the §6.4 window

**LOST**, not degraded. A "degraded" reading would require some automatic
process — even a slow one, like nightly `doctor` — to still catch a duplicate
registration eventually. No such process exists: `devman doctor`'s 23 checks
(enumerated at `src/devman/doctor.py:1618-1639`) do not include one. The
`link status --all` sweep is real and can fail (`cli.py:296-310`,
`"duplicate manifest identity"`), but it is invoked by a person who already
suspects the problem and knows to pass `--projects-root`; it is not part of
`repoman doctor`/`devman doctor`'s routine verification.

**§6.4's window therefore does not close on a schedule — it does not close at
all** unless a person runs the manual sweep. Between a second checkout
registering under an in-use project name and that sweep (which nothing
schedules), §6.4's hazard is live: `dagu ls` would show the name once,
`dagu enqueue` would pick whichever file is on disk, and the registry
would silently point at whichever checkout's shell entered most recently.

Caveat, unverified: this audit covers the devman repository only. A separate
tool, Vendomat, now assembles "generations" by calling `devman project
render`/`inspect` across checkouts and activating them atomically
(`nix/nixos-module.nix:294-299`, `GenerationStore._activate_number`
referenced there). If Vendomat's generation-build step enumerates checkouts
from its own inventory and refuses a name collision there, that would be a
different — and possibly adequate — replacement for this refusal. Settling
this requires reading Vendomat's generation-assembly code, which lives in a
different repository (`/home/andrew/Documents/Projects/vendomat`) and was out
of scope for this audit.

## Item 13 — the exclude writer's worktree awareness

### What the old mechanism did, and when it actually left `devenv.nix`

The 553-line revision at deletion (`37050e9^`) contains **no** exclude-writing
logic at all — no `.git/info/exclude`, no `gitdir:`, no `commondir` handling.
`git log --follow -- modules/devenv.nix` and `git show 35efaa3 --
modules/devenv.nix` show why: commit `35efaa3` ("fix: centralize per-project
git exclusions", 2026-09-10 13:10:23 -0400 — nine days before the deletion)
replaced the module's own exclude-writing with a six-line call to
`${linkScript}`, moving ownership into `src/devman/link.py`:

```
-      # reconciler owns both the view and its .git/info/exclude entry. The
+      # reconciler owns the view, the central .local.gitignore file, and the
+      # .git/info/exclude symlink.
```
(`git show 35efaa3 -- modules/devenv.nix`)

So **§10 item 13's citation (`devenv.nix:798-827`) was already stale when 025
was written** against the pre-`35efaa3` revision — the mechanism it names had
moved nine days before the module that line range refers to was itself
deleted. The deletion commit `37050e9` is not where item 13's property
changed hands.

### Where it lives today, and what it does

`src/devman/link.py` was itself superseded; `git log --follow` on it stops at
`35efaa3`, and the current implementation is `src/devman_link/excludes.py`
(reached from `src/devman/linking.py:130-141`,
`_project_local_gitignore` → `devman_link.excludes.ensure_local_gitignore`).
The worktree-aware function is `git_exclude_path`:

```python
def git_exclude_path(root: Path) -> Path | None:
    marker = root / ".git"
    if marker.is_dir():
        return marker / "info" / "exclude"
    if not marker.is_file():
        return None
    lines = marker.read_text().splitlines()
    if not lines or not lines[0].startswith("gitdir:"):
        raise LinkError(f"cannot read linked-worktree metadata from {marker}")
    git_dir = Path(lines[0].partition(":")[2].strip())
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    git_dir = git_dir.resolve()
    commondir = git_dir / "commondir"
    if commondir.is_file():
        common = Path(commondir.read_text().strip())
        if not common.is_absolute():
            common = git_dir / common
        git_dir = common.resolve()
    return git_dir / "info" / "exclude"
```
(`src/devman_link/excludes.py:22-47`)

This is the exact property §10 names: a linked worktree has `.git` as a file
naming its own git directory, and that directory's `commondir` file names the
*real* shared one — the function follows both hops, so the exclude projection
always lands on the one `info/exclude` every clone of the repository actually
reads, never a second, orphaned one inside the worktree's private git
directory. The module docstring states the same reasoning
(`src/devman_link/excludes.py:1-10`).

### Classification

**PRESERVED by construction**, and strengthened. The mechanism is a pure
function of the filesystem shape (`.git` file vs. directory, plus the
`commondir` indirection) — there is nothing to refuse or report; a worktree
cannot get a second, un-read exclude file because the function always resolves
to the common one. This is a stronger form of the original: the recovered
`37050e9^` revision of `devenv.nix` had no exclude logic to compare against
(it had already been delegated), and the pre-`35efaa3` shell version this
audit could not recover did not need to follow `commondir`, since nothing in
the available history shows it doing so.

It has a direct test, not just incidental coverage:
`tests/unit/test_link_adapter.py:789` —
`test_a_linked_worktree_uses_its_common_git_directory` — builds exactly the
shape the function exists for (`main/.git/worktrees/feature/commondir`
pointing back at `main/.git`, a worktree's `.git` as a `gitdir:` file) and
asserts the symlink lands on `main/.git/info/exclude`, not a second file under
the worktree. A second test,
`tests/unit/test_link_adapter.py:810` —
`test_a_repository_without_a_git_marker_gets_no_exclude_link` — covers the
`None` case (gitman/jj workspace, no `.git` at all) so a non-Git repository
never gets a spurious link.

## What this audit could not determine

- **Whether Vendomat's generation-assembly step (not in this repository)
  independently refuses two checkouts sharing a project name.** Unverified.
  Settling it needs the generation-build code referenced at
  `nix/nixos-module.nix:294-299` in `/home/andrew/Documents/Projects/vendomat`.
- **The exact shell-hook text that `devenv.nix:798-827` referred to in 025's
  own revision.** Not recovered — `git log --follow` does not expose a
  revision where that exact line range held exclude logic within the window
  searched (`37050e9^` back through `35efaa3`); the property was already
  Python-owned by the oldest revision this audit read in full. Settling this
  further would mean bisecting further back than `35efaa3^` purely to confirm
  025's original citation, which does not change item 13's current
  classification.

## Other items in §10 worth checking later (not audited here)

Spot-checking line citations against the *current* files (in scope, since
they are in this repository) found drift similar to items 2 and 13:

- **Item 4** cites `AGENTS.md:67` for *"the plane holds no project fact"* —
  line 67 today reads *"prefer a check that can fail to one that cannot"*
  (a different law, not the one cited).
- **Item 5** cites `AGENTS.md:106` for the `devenv test` 30-of-58 story — that
  text is now at `AGENTS.md:146-148`; line 106 today holds the secrets-masking
  text item 6 cites.
- **Item 6** cites `AGENTS.md:75-81` for secrets — those lines now hold the
  "three roots, each with a different owner" registry table.
- **Item 3** cites `AGENTS.md:120-131` for "the tier table" — those lines now
  hold the "verify before you save" command block.

All four look like simple line-shift from edits to `AGENTS.md` (171 lines
today) rather than lost content — the cited prose exists somewhere in the
file, just not at the cited line. Not verified further; this audit only
confirms the citations are stale, not whether the properties themselves
survived.

Items 1, 7, 8, 9, 10, 12 cite sibling repositories (`gitman`, `agentman`,
`copyroom`, `vendomat`, `repoman`) and were not opened — out of scope for an
audit of `devman/modules/devenv.nix`'s deletion.

## What this audit did not do

- Did not run `devman doctor`, `devman link status --all`, or any other live
  command against the real registry or overlay — this was a static read of
  source and git history only.
- Did not open or audit any sibling repository (`gitman`, `agentman`,
  `copyroom`, `vendomat`, `repoman`) beyond the single `grep` confirming they
  exist on disk.
- Did not re-audit the already-confirmed link-drift finding in the task
  prompt (`check_link_drift` / `0`-of-`48` entries) — that was given, not
  re-derived.
- Did not audit §10 items 1, 3-12 beyond the line-citation spot-check above.
- Did not modify `modules/link.nix`, any `.py`/`.nix`/`.toml`/`.yaml` file, or
  anything under `.scratch/projects/041-central-autoland/CONCEPT.md`,
  `DECISIONS.md`, or `artifacts/`.
