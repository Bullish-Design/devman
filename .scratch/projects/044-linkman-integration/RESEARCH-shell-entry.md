# Research — shell entry, the engine flag, and the central attribute set

Answers sections D and E of `INVESTIGATION_PROMPT.md`, including the recount.

Measured 2026-10-05. Every count carries that date. The 78→60 drift is explained
in E1 and the figure a downstream plan should use is named there.

---

## D. Reaching real shell entry — blocker B5

### D1. The flag has never governed a real reconcile. Confirmed, with stronger evidence than the review had.

**The shell-entry path, end to end.**

`modules/link.nix:70-75` is the only shell-entry invocation anywhere:

```nix
70      enterShell = ''
71        /run/current-system/sw/bin/devman-link reconcile \
72          --root "$DEVENV_ROOT" \
73          --overlay "${overlayDir}" \
74          --project "${projectName}"
75      '';
```

No environment variable is set, exported or referenced in that file.

**Two different binaries, two different packages.** This is the crux:

| Console script | Entry point | Store path (live) |
|---|---|---|
| `devman` | `devman.cli:main` (`pyproject.toml:42`) | `/nix/store/jvyh5s2ijqm5jnphd7n1b8k7jfawbp77-devman-0.6.0` |
| `devman-link` | `devman_link.cli:main` (`packaging/devman-link/pyproject.toml:28`) | `/nix/store/b9rrdnmy6gbqixyvs4rz76x7qkcr76yv-devman-link-0.6.0` |

Different store hashes, different derivations. Shell entry calls the second.

**`DEVMAN_LINK_ENGINE` — every hit in the repository:**

```
src/devman/cli.py:412    """`DEVMAN_LINK_ENGINE=linkman`: reconcile through concept §14 (Lane 7).
src/devman/cli.py:556        and os.environ.get("DEVMAN_LINK_ENGINE") == "linkman"
tests/unit/test_linking.py:8  `DEVMAN_LINK_ENGINE=linkman devman link reconcile` was also run against a
```

All three are in the `devman` package or its test. **Nothing in
`src/devman_link/`, `modules/`, `nix/`, `groups/` or `.devman/` mentions it.**

`src/devman_link/cli.py` (93 lines) does not import `os`. It defines two
subcommands, `status` and `reconcile`, reads only `--project`, `--root`,
`--overlay`, `--json`, and explicitly refuses the retired `--registry`/`--state`
flags. It reads no environment variable of any kind.

The flag's one read site, `src/devman/cli.py:554-558`:

```python
554      if (
555          args.link_command == "reconcile"
556          and os.environ.get("DEVMAN_LINK_ENGINE") == "linkman"
557      ):
558          return _link_reconcile_with_linkman(args)
```

This sits inside `_link_command`, which backs `devman link reconcile` — a
subcommand of the `devman` console script. Shell entry never calls it.

**Finding, stated as the prompt asked: `DEVMAN_LINK_ENGINE` has never governed a
real shell-entry reconcile.** Lane 7's gate was met by an explicit
`devman link reconcile` invocation, not by a shell entry. The flag is dead code
with respect to the only path that runs 59 times a day.

**Corroboration the readiness review did not cite.** `nix/nixos-module.nix:414-416`,
in the `installLinkAdapter` option's own description:

```
414        The option is machine-level because the component is machine-local.
415        §7.1's shared environment contract stays closed: no `DEVMAN_*` name is
416        added for it.
```

The module documents that no `DEVMAN_*` name was added for the adapter. The flag
was never *intended* to reach this path. That makes B5 not an oversight but a
consequence of a recorded contract decision — which matters, because closing it
touches the shared-contract question in AGENTS.md property 3.

Note also a line-number correction: the readiness review cites
`src/devman/cli.py:431` for the flag (`m14-lanes-8-10-readiness-review.md:322`).
It is `:556` today (and `:412` for the docstring). The code moved; the finding
did not.

### D2. The minimum change that makes the engine selectable at shell entry

> **RECOMMENDATION WITHDRAWN, 2026-10-05, later the same day.** This section
> recommends option B — teach `devman_link/cli.py` to read `DEVMAN_LINK_ENGINE`
> and delegate. `DECISIONS.md` D24 **abandons the flag entirely** in favour of
> verify-then-pin with NixOS generation rollback, on the finding that the flag's
> rollback is partly illusory: once the default flips, reverting machine-wide
> needs `environment.variables` (a rebuild) or a hand-edited shell rc outside
> Nix's control.
>
> **The analysis below stands and is why D24 could be made.** D1's finding — the
> flag never reached shell entry — is what showed the flag bought nothing yet,
> and so could be dropped rather than fixed. The chosen path is closest to
> **option A** (change the hook at `modules/link.nix:71`), but calling `linkman`
> rather than `devman link`, which answers option A's stated objection: the hook
> still never depends on the workflow plane.
>
> Read the four options as the record of what was considered.

Four options. Recommending option B.

**Option A — change `modules/link.nix:71` to call `devman link reconcile`.**
Minimum diff, one line. Rejected: it makes shell entry depend on the full
`devman` package, which carries Dagu, watchexec and the registry. The adapter
exists precisely so shell entry does not need any of that
(`nix/link-adapter.nix:17-22`). It also inverts the dependency the no-registry
fixture was written to prove. Rollback: revert one line, one `nixos-rebuild`.

**Option B — teach `src/devman_link/cli.py` to read `DEVMAN_LINK_ENGINE` and
delegate to Linkman. RECOMMENDED.** This is Lane 9b-1 as the refactoring guide
scopes it. The adapter gains `linkman` in `nix/link-adapter.nix:71` and an
engine branch in its own `cli.py`. Both binaries then honour one flag, and the
flag finally governs the path that actually runs. Costs: the adapter takes a
third-party dependency (shown acceptable in `RESEARCH-integration-surface.md`
B4) and the no-registry fixture needs a second arm (B4 again). Rollback: unset
the variable — instant, no rebuild, because default-off means anything other
than `"linkman"` takes the legacy branch. Full rollback: pin the previous devman
tag in `nix-meta` and rebuild.

**Option C — add a `devman.link.engine` option to `modules/link.nix` and pass
`--engine` on the command line.** Rejected: it puts engine selection in 60
central Nix files at the exact moment Lane 9e is trying to empty them, and it
adds a per-project knob for a machine-wide migration. It also makes rollback a
60-file edit instead of one variable. Rollback: revert the module, rebuild, and
re-edit every file that set it.

**Option D — flip the default inside `devman_link` with no flag at all.**
Rejected: it removes the ability to roll back without a rebuild, which is the
one property worth keeping during a cutover that touches shell entry in 59
projects. AGENTS.md property 4's preference for a loud refusal over a silent
default argues the same way.

**Recommendation: option B**, and it must land *before* any default flip. The
readiness review's phrasing is right — "the flip is necessary and insufficient"
(`m14-lanes-8-10-readiness-review.md:333`). Until B lands, a release held for
seven days measures nothing, because nothing in the held release ran Linkman.

### D3. The live binary and the real cost of a flip

Measured 2026-10-05:

```
$ readlink -f /run/current-system/sw/bin/devman-link
/nix/store/b9rrdnmy6gbqixyvs4rz76x7qkcr76yv-devman-link-0.6.0/bin/devman-link

$ nix-store -q --deriver $(readlink -f /run/current-system/sw/bin/devman-link)
/nix/store/cgv6wgvxacvqjdd92mm2ikrrxgbhv67a-devman-link-0.6.0.drv

$ /run/current-system/sw/bin/devman-link --help
usage: devman-link [-h] {status,reconcile} ...
Reconcile one repository's link plane.
```

**Confirmed: `devman-link-0.6.0`**, store path as above. Note there is no
`--version` flag on either binary — both are argparse-based and treat
`--version` as a usage error. Any lane that wants to verify which version is
live must compare the store path, not ask the binary.

**The chain from a devman tag to that binary.**

`/etc/nixos/` holds only `configuration.nix` and `hardware-configuration.nix`,
with no devman reference. The pin lives in `nix-meta`:

```
nix-meta/flake.nix:238    devman = {
nix-meta/flake.nix:239      url = "git+https://github.com/Bullish-Design/devman?ref=refs/tags/v0.7.0";
nix-meta/profiles/devman.nix:19   imports = [ inputs.devman.nixosModules.default ];
nix-meta/profiles/devman.nix:40   services.devman-dagu.registryDir = "$HOME/.local/state/vendomat/devman/active";
```

`nix-meta/flake.lock` locks devman at:

```
311      "lastModified": 1789478635,                                    # 2026-09-15
313      "ref": "refs/tags/v0.7.0",
314      "rev": "4c9927ada27a5c12a5ee2acdf8ad85648f7aafa1",
```

`installLinkAdapter` is left at its default of `true` (`nix/nixos-module.nix:400-402`).

The ordered chain:

1. A commit lands on devman `main`.
2. A tag is cut and pushed.
3. `nix-meta/flake.nix:239`'s ref is edited, **if** the tag name changes. The ref
   is `refs/tags/v0.7.0`, so moving that tag forward instead would skip this step.
4. `nix flake update devman` in `nix-meta` bumps the lock's `rev`/`narHash`.
5. `nixos-rebuild switch` builds `devman-link-<version>` from the new rev and
   re-links `/run/current-system/sw/bin/devman-link`.
6. Any devenv shell opened *after* that rebuild runs the new binary at
   `enterShell`.

**How many `nixos-rebuild` cycles a flip costs: one — but only after option B
has shipped in a tag.** Two findings qualify this:

- **The machine is five-plus commits behind.** Locked rev `4c9927a` is `v0.7.0`
  (2026-09-15). devman trunk is `f4a245f`, with `5c64dfd`, `6278e08`, `c8684ca`,
  `6be8869` in between. So the live binary does not contain anything from Lanes
  1-7. Any claim about what shell entry does today must be read against `v0.7.0`,
  not trunk.
- **Today, no number of rebuilds would make shell entry read the flag**, because
  the flag lives in the wrong package (D1). The real cost is: one tag containing
  option B → one lock bump → one rebuild to make the flag *live*; then zero
  further rebuilds to flip it, since flipping is setting an environment variable.
  A second rebuild is needed only to change the *default*.

**New hazard, interacting with `RESEARCH-integration-surface.md` B1a.** `nix-meta`
fetches devman over anonymous `git+https://`. If devman's flake gains a private
`git+ssh` input, then step 4 and step 5 both acquire a credential requirement,
and step 5 evaluates as root under `sudo`. I did not test this — the prompt
forbids `nixos-rebuild`. It is an untested hazard and it is recorded as an
operator question, not a finding.

---

## E. The reconcile trigger and the Nix attribute set — blocker B4

### E1. The recount, and the duplication verified against the live tree

**The root.** `~/.config/devman` is the overlay root (`devman.overlayDir`), a git
repository holding `projects/`, `dags/`, `agents/`, `common/`, `skills/`,
`devenv.nix`. It is the only root carrying hand-authored `links.yaml` /
`devenv.local.nix` pairs. The other three roots hold run metadata, DAG
projections and the Dagu-facing generation — no link declarations.

**The counts, 2026-10-05:**

```
$ ls -1 ~/.config/devman/projects/ | wc -l                                  → 60
$ find ~/.config/devman/projects -maxdepth 2 -name links.yaml | wc -l       → 60
$ find ~/.config/devman/projects -maxdepth 2 -name devenv.local.nix | wc -l → 60
```

**All 60 project directories carry both files. None carries only one.** That is
one step beyond what the prompt reported ("60, and all 60 carried `links.yaml`"):
all 60 also carry `devenv.local.nix`, so the b4 endorsement's 10-project gap of
`links.yaml`-without-`devenv.local.nix` no longer exists.

**Why 78 drifted to 60.** The 78 was never a steady state — it is the instant of
one bulk-conversion commit in the overlay repository:

```
$ git -C ~/.config/devman log -1 --format="%H %ad %s" --date=short 268c0a37
268c0a37 2026-10-01 m14 phase A: the converted links.yaml for all 78 central projects
$ git -C ~/.config/devman show --name-status 268c0a37 -- 'projects/*/links.yaml' | grep -c '^A'
78
```

The 18 since removed: `allium-env`, `boomtube`, `docman-consumer-sitestest`,
`docman-debug`, `docman-debug2`, `docman-existing-repo-after`, `docman-migrate`,
`docman-new-repo-after`, `docman-roundtrip`, `docman-showcase-after`,
`docman-showcase-sitestest`, `image-gen-pipeline`, `lodestar`, `my-ai`,
`mypi-agent`, `paloma-text-pipeline`, `pytuin-desktop`, `roundtrip-debug`.

Two groups: test and scratch fixtures (the `docman-*` set, `roundtrip-debug`,
`pytuin-desktop`, `image-gen-pipeline`, `paloma-text-pipeline`, `mypi-agent`),
and the archive set (`allium-env`, `boomtube`, `lodestar`, `my-ai`). Later
overlay commits pruned them: "m14: retire foreman and my-ai into
projects/.archive/", "chore: archive inactive project overlays", "*: remove the
declarations for the archive set".

**Use 60.** It is the directly measured, current count of overlay project
directories, each carrying both files. 78 was a snapshot of a bulk commit before
fixtures and archived projects were pruned, and the readiness review's "77 of 78"
was already a drifted citation of it — `041/RESEARCH-cutover-interlock.md:55-56`
re-measured it as 68 on 2026-10-02 and said so.

**The duplication claim, verified rather than asserted.** Full `cat` comparison
of nine pairs (`agentman`, `flora`, `gitman`, `nixvim`, `repoman`, `PyGentic`,
`clinch`, `fsdantic`, `inferference`), then a read-only key-diff across all 60:

| Verdict | Count | Shape |
|---|---|---|
| FULL DUPLICATE | **4** | `PyGentic`, `clinch`, `fsdantic`, `inferference` — identical key sets and targets; `devenv.local.nix` even self-declares its own `"devenv.local.nix"` entry |
| PARTIAL OVERLAP | **56** | every key `devenv.local.nix` declares is in `links.yaml` with the same resolved target; `links.yaml` carries exactly one extra key — `devenv.local.nix` itself |
| DISJOINT | **0** | — |

The recurring keys are `.envrc`, `.loci`, `.agents`, `.claude/skills`, plus
`.claude/settings.local.json` in `flora` and `nix-secrets`, and `.devman/workflows`
in `devman`'s own entry.

**On every overlapping key, across all 60 projects, the declared target is the
same path.** So the b4 endorsement's argument stands, with one refinement worth
carrying into the lane: the 56 are not full duplicates, and the difference is
**not drift — it is structural.** `links.yaml` must declare the link that puts
`devenv.local.nix` into the repository, because Nix reads that file before any
hook can run. A Nix file cannot bootstrap itself. So the end state is not "the
two files agree"; it is "`links.yaml` is the sole declaration, and it necessarily
includes the one link that makes the other file reachable."

That strengthens option 2 rather than weakening it: the duplication is real
(`AGENTS.md` P2, "source or projection, never a copy"), and the one key that is
not duplicated is precisely the key proving `links.yaml` has to be the source.

**Where the `enterShell` hook actually lives — not in the overlay.**

```
$ grep -rn "devman-link\|devman link" ~/.config/devman
→ 1 hit, a .gitignore entry naming the state file
$ grep -rl "devman/link-module.nix" ~/.config/devman/projects | wc -l
→ 59
```

No overlay file carries the hook. It lives in the Nix-store module that each
`devenv.local.nix` imports:
`/run/current-system/sw/share/devman/link-module.nix` →
`/nix/store/b9rrdnmy6gbqixyvs4rz76x7qkcr76yv-devman-link-0.6.0/share/devman/link-module.nix`.
Delivered by `nix/nixos-module.nix:706-708` (`environment.pathsToLink = [ "/share/devman" ]`),
from the **same derivation** as the `devman-link` binary. **59 of 60 import it.**
The one exception uses a different combined module — this is the mnemonix anomaly
the interlock research records as Q6 (`041/RESEARCH-cutover-interlock.md:60-62, 293`).

**Live plane health.** `devman doctor` exits **0**, "Nothing to report."
Relevant lines: `ledger 345 entries, 59 projects`;
`duplicate name 58 checkouts under /home/andrew/Documents/Projects`.

**Four counts that look contradictory and are not** — each measures a different
layer, all 2026-10-05:

| Count | What it measures |
|---|---|
| **60** | overlay project directories under `~/.config/devman/projects/` |
| **59** | projects named in the link ledger `.devman-link-state.json` |
| **58** | live git checkouts under `~/Documents/Projects` (doctor's duplicate-name check) |
| **44** | projects in the active vendomat generation's DAG-projection registry |

**Two loose ends found while counting**, neither in scope here:

1. **`foreman`** is the one overlay directory absent from the ledger. It has no
   live checkout (`~/Documents/Projects/foreman` does not exist) and was never
   reconciled — its files are dated 2026-10-01 19:49, about 17 minutes after the
   bulk M14 commit. This matches the archive-set memory and the refactoring
   guide's Lane 10.2 `foreman` item.
2. **`AGENTS.md` property 6 is stale.** It records "generation 3 since
   2026-09-15" with 48 projects and 152 DAG files.
   `readlink -f ~/.local/state/vendomat/devman/active` →
   `.../generations/4`, holding **44** projects. The architecture is unchanged;
   the dated evidence has moved, which is exactly what property 6 says to read
   it as. Worth a one-line correction in whichever lane next touches that file.

### E2. Does 9e-before-9d still hold? Yes, and the recount strengthens it.

The reasoning (`m14-lanes-8-10-readiness-review.md:270-282`): both machine paths
— the `devman-link` binary and `link-module.nix` — come from one derivation,
`nix/link-adapter.nix`, through its `postInstall`. Deleting the adapter (9d)
before the central files stop importing it (9e) means every central
`devenv.local.nix` imports a store path that no longer exists. Nix reads
`devenv.local.nix` before any shell hook runs, so shell entry fails with a trace
nothing can intercept.

**Confirmed on three independent measurements:**

1. Both paths do come from one derivation. The live
   `/run/current-system/sw/share/devman/link-module.nix` resolves into
   `b9rrdnmy…-devman-link-0.6.0`, the same store path as the binary (D3).
2. `nix/nixos-module.nix:697-700` and `:706-708` install both from the single
   `linkAdapter` package, gated by one option.
3. **59 of 60 central files import it** (E1), against the review's 77 of 78 —
   the absolute number fell with the project count, but the proportion rose from
   98.7% to 98.3%, materially unchanged. The hazard is undiminished.

So the corrected order holds: **9e before 9d.**

**Other ordering hazards found.** These were written against the fifteen-lane
plan. **H2, H3 and H4 no longer apply** under the architecture in
`DECISIONS.md` D23-D26: H2's derivation question is moot (no derivation takes a
Linkman dependency), H3's flag sequencing is moot (the flag is abandoned), and
H4's private-input gate dissolved via the nix-meta precedent. **H1 and H5 stand
unchanged**, and H5 is now off the critical path rather than on it.

- **H1 — Lane 8.0 does not make the gate green.** A second, unrelated failure
  (`checks.dagu-service`, `git` not on devman's PATH) must be fixed too, or every
  later lane's `gitman land` verify hook fails. See
  `RESEARCH-integration-surface.md` A1. This moves to the front of the order.
- **H2 — 9c as scoped names the wrong derivation.** `nix/link-adapter.nix:71`
  does not need `linkman` until 9b-1; `nix/devman-cli.nix:63` and
  `flake.nix:171` do. If 9c adds the dependency only to the adapter, the engine
  flag still cannot work and `test_linking.py` still skips. See
  `RESEARCH-integration-surface.md` B3.
- **H3 — 9b-1 must precede any default flip**, because until it lands the flag
  does not reach shell entry (D1). The readiness review already says this; it is
  restated because the lane order in the guide places 9b-2 immediately after
  9b-1 with only a time gap between them, and the gap is what must be measured.
- **H4 — the private-input decision gates 9c, and transitively 9d/9e.** If the
  operator declines to make Linkman public, 9c's output is a devman flake that
  cannot be fetched anonymously, which changes `nix-meta`'s pin
  (`RESEARCH-integration-surface.md` B1a). This is a *new* gate on 9c that did
  not exist when Q1 was framed, because Q1 asked only for a pinnable package and
  got a private one.
- **H5 — an operator prerequisite sits outside devman.**
  `041/RESEARCH-cutover-interlock.md:16-20` and `041/DECISIONS.md:297-326` (D9)
  record that `m14-central-residue` in `~/.config/devman` is stalled on a
  `gitman land` the permission classifier denies to an agent at any lane size,
  and frames that denial as correct. Lane 9e rewrites 60 files in that same
  repository. Whether 9e can land at all is therefore an operator question
  before it is a sequencing question.

### E3. The `repo` kind — which lane removes it, and what else references it

**Live uses: zero. Confirmed two ways, 2026-10-05.**

```
$ grep -rho 'canonical = "[a-z]*"' ~/.config/devman/projects | sort | uniq -c
    180 canonical = "central"
     52 canonical = "external"
      0 canonical = "repo"

$ grep -rl "kind:" ~/.config/devman --include=links.yaml | wc -l
0
```

A detail worth recording: `links.yaml` schema version 1 has **no `kind` field at
all** — each link carries only `target:`. So the kind concept exists solely in
devman's `devman.link` Nix attribute set, and disappears with it rather than
needing migration. Linkman decision 16 drops `canonical = "repo"` on the same
evidence (its own census: 231 central, 68 external, 0 repo, across 76 projects —
the larger numbers reflect the pre-prune 78-project tree).

**Everything that references it:**

| Reference | What it is | Effect of removal |
|---|---|---|
| `modules/link.nix:43` | `types.enum [ "central" "repo" "external" ]` | the type contract every central file validates against; safe to narrow at 0 live uses |
| `src/devman_link/declarations.py:17` | `CANONICAL_KINDS = ("central", "repo", "external")` | the Python enum; changes the refusal message at `:49` |
| `src/devman_link/config.py:94` | error-repair text listing `repo` as valid | text only |
| `src/devman_link/paths.py:93, 119-121` | `resolve()`'s `repo` branch, which **inverts** view and canonical | deleting it reduces `resolve()` to a two-way switch |
| `tests/unit/test_link_adapter.py:549, 553` | parametrize `["repo", "external"]` on the template restriction | needs rewriting to drop the `repo` case |
| `tests/unit/test_link_adapter.py:686-701` | `test_a_repo_canonical_exposes_the_repository_through_the_overlay` | the only functional test of the inverted sides; deleted outright, not rewritten |
| `tools/cutover/convert.py:9-12` | the Phase-A converter **refuses** `canonical="repo"` | already treats it as dead |
| `tools/cutover/snapshot.py:98-101` | raises `RuntimeError` on `canonical="repo"` in a live sweep | a second independent refusal |
| `src/devman/linking.py:112-115` | docstring: the converter "already refuses that kind at cutover" | the Linkman path never represents it |

A correction to the prompt: it names `paths.py` and `test_link_adapter.py`. The
full set is nine sites across six files, and `src/devman/paths.py` does not
exist — the file is `src/devman_link/paths.py`. The readiness review's F8
measured five sites plus a comment against the guide's four
(`m14-lanes-8-10-readiness-review.md:532-546`); the count is higher again
because the two cutover-tool refusals and the `linking.py` docstring are also
references.

**Which lane removes it.** Lane 9d, where `src/devman_link/` and
`modules/link.nix` are deleted wholesale. Seven of the nine sites vanish with
those two deletions and need no separate work. The two test sites are the only
edits, and both are inside `test_link_adapter.py`, which 9d retires anyway.

**Recommendation: do not give `repo` its own lane.** A standalone lane would
edit the `modules/link.nix` enum and the `declarations.py` tuple in a tree where
both files are about to be deleted, costing a `nixos-rebuild` (because
`modules/link.nix` ships in the adapter derivation) to narrow a type nothing
uses. Fold it into 9d. Rejected alternative: an early cleanup lane — it was
considered because the change is genuinely trivial, but it buys no safety and
spends a rebuild cycle on 0 live uses.
