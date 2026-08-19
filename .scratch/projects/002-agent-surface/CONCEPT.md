# devman — one author for the family's agent surface

> **STATUS: PROPOSED (2026-08-19). BLOCKED ON 001.** Do not start this before
> `001-recharter` step 4 ships. See §5 for the entry criteria.
>
> This proposal was §12.1 of the 2026-08-13 devman concept, where it sat as
> **step 1 of the build order** — a cross-repo governance change gating every
> line of code. It is split out here because it is a separate project with a
> separate risk profile, and because devman v1 can collect the evidence that
> decides it.

---

## 1. The proposal

devman authors **every** agent skill in the family, and is the only writer under
`.agents/skills/`.

This does not add devman as one more owner. It replaces the ownership protocol
outright.

`repoman/docs/AGENT-FILES.md` fixes one owner per file and names five classes:
tool-shipped (copyroom's canonical set), genome, personal (my-ai), repoman's
generated router, and repo overlay. It needs a "two-writer rule" to keep those
classes from fighting, and `repoman doctor` needs an ownership lint
(`skill_ownership_checks`, wired at `repoman/src/repoman/cli.py:219`) to police
them.

All of it would collapse to two rows:

| Owner | What |
|---|---|
| **devman** | every skill — authored here, built from packs, facts introspected |
| **the repo** | declared overlays (`.devman/devman.toml`), for permanent divergence |

The two-writer rule, the five ownership classes, and `skill_ownership_checks`
retire together. A design that deletes a coordination protocol is usually the
right one.

---

## 2. What each tool would keep

| Tool | Keeps | Loses |
|---|---|---|
| **copyroom** | its CLI facts; its **domain prose** (001 §5.2); seeding `.devman/devman.toml`; `AGENTS.md` + the `CLAUDE.md` symlink | `src/copyroom/agent/assets/skills/` — the 3 canonical skills; `agent-files export` shrinks to the two convention files |
| **repoman** | `registry.py` — the roster, `SPINE`, `route_when`. **repoman still decides lifecycle order.** | the Jinja template and `install_entrypoint`; `install-skills` becomes `skills render` or retires |
| **my-ai** | the standing law as prose, authored as a devman skill asset in its pack | nothing structural — it was already a layer |
| **testee, gitman, docman** | their CLI facts and their domain prose | their hand-written skills |

The boundary that must hold: repoman owns the **facts of ordering** (`SPINE`,
`route_when`). devman owns the **prose that renders them**. devman never decides
what comes before what — it reads that from the registry. Two conductors would be
worse than none.

---

## 3. The argument, corrected by measurement

The original draft gave five reasons. **Two of them no longer support this
proposal**, because 001's spikes showed a *reader* can deliver them. Stating that
plainly is the point of this section: the case is narrower than it was, and it
should be argued on what actually remains.

| # | Original argument | Status after the spikes |
|---|---|---|
| 1 | Version drift between a skill and its CLI is unchecked today; one author fixes it | **Withdrawn.** 001 §10.1 delivers the check by *reading* skills. Measured: 0 false positives on 79 references, all 3 synthetic defect classes caught. Ownership is not required. |
| 4 | Trigger-collision linting is impossible because no component sees every skill | **Withdrawn.** 001 §10.2 delivers it by reading. It found 33 real collisions across 8 repos. Ownership is not required. |
| 2 | Uniform shape becomes generation, not a lint | **Stands.** `repoman/docs/SKILLS.md` asks every manager skill to carry three disciplines and hopes `repoman doctor` can enforce them. A generator emits them by construction. This is the difference between a style guide and a formatter. |
| 3 | A convention change costs one edit, not six repos and six releases | **Stands, and is the strongest remaining reason.** Change the deferral-footer format today and it is six repos, six reviews, six releases. |
| 5 | Skills generate from the assets they document | **Stands.** A script asset already carries `summary`, `requires`, and `exit` (001 §5). The section documenting it writes itself. The catalog and its documentation stop being two things that drift. |

**What this means.** The case for the takeover is now about **authoring cost and
uniformity**, not about **detection**. Detection is solved more cheaply. That is
a weaker case than the original draft made, and it may still be a sufficient one
— but it must be argued on those terms.

There is also a cheaper alternative that did not exist before, and it deserves a
fair comparison rather than dismissal:

> **The lint-only option.** devman reports drift, collisions, and missing
> disciplines. Each tool keeps authoring its own skill and fixes what devman
> reports. This keeps release coupling tight, keeps domain prose next to the
> domain, and needs no cross-repo protocol change. It does not fix argument 3.

Decide between full authorship and lint-only **after** 001 step 4, with a year of
`devman doctor` output to look at.

---

## 4. The cost, stated plainly

**Release-order coupling.** copyroom ships a renamed command; until the devman
pack is rebuilt, every repo carries a skill naming the old one. That window does
not exist today, because the skill and the binary ship together.

This is a real regression. It is acceptable for one reason: the window is
**detected**. 001 §10.1's check fails with exit `1` and names the stale command;
the fix is one `devman sync --machine && devman build`.

Note the asymmetry, though — the detector is delivered by 001 regardless. So the
mitigation for this cost exists whether or not this proposal lands, while the
cost only exists if it does.

**Domain prose leaves the domain.** 001 §5.2 splits skill material three ways and
assigns domain prose to the tool. This proposal must honour that split, or a
tool's maintainer loses the ability to explain their own boundary. The open
question in 001 §18 — how a tool publishes its domain prose — must be answered
**before** this project starts, not during it.

---

## 5. Entry criteria

Do not open this project until all five hold:

1. `001-recharter` step 4 has shipped: packs, `lock.toml`, and `sync --machine`
   work, and the `devenv-literacy` pack is the proof.
2. devman has authored **one** manager's skill end-to-end and it is in use. Pick
   **gitman**, not testee — gitman has 25 commands, a real sub-group (`remote`),
   and 43 references in its skill, so it exercises the generator. testee is
   smaller but its per-repo install makes it the awkward case, not the
   representative one.
3. 001 §18's question "how does a tool publish its domain prose?" is answered and
   implemented.
4. `devman doctor --refs` has caught at least one **real** drift in the wild. The
   family is currently in sync (0 findings across 79 references), so this
   proposal's core premise — that drift happens and goes unnoticed — is so far
   unevidenced. Wait for the evidence.
5. The lint-only alternative (§3) has been compared against full authorship on
   the record, not skipped.

Criterion 4 is the important one. The original draft assumed drift was a live
problem. Measurement says it is a *possible* problem that has not yet occurred.
Rebuilding six repos' agent surface to prevent an unobserved failure is the kind
of decision worth delaying until it is observed.

---

## 6. Bootstrap — the contradiction, resolved

The original draft's bootstrap paragraph contradicted its own ownership table:

> "Each tool keeps a minimal export path, and `copyroom new` still seeds a
> starting set."

But the same section deleted `src/copyroom/agent/assets/skills/`. Deleted assets
cannot seed. Worse, the moment a second component may write under
`.agents/skills/`, the two-writer rule this proposal claims to retire is back —
now undocumented, which is worse than the rule it replaced.

**Resolution: one writer, one seeder, and they write different things.**

| Component | Writes | When |
|---|---|---|
| **copyroom** | `.devman/devman.toml` and the `devman` devenv import line. **Nothing under `.agents/skills/`.** | `copyroom new`, `copyroom adopt` |
| **devman** | every file under `.agents/skills/` | `devman build` |

A fresh repo has no skills until `devman build` runs once. That is acceptable
because the devenv import line makes it run on first shell entry — the same hook
shellij already uses (`shellij/modules/devenv.nix:55`). The gap is one shell
entry, not a missing capability.

The rule to state in `repoman/docs/AGENT-FILES.md`, replacing the ownership
split: **copyroom seeds the pointer; devman writes the content; nothing else
writes under `.agents/skills/`.**

---

## 7. Migration, if it proceeds

Each step is reversible on its own. Do not batch them.

1. `repoman/docs/AGENT-FILES.md` loses the five ownership classes and the
   two-writer rule, and gains §1's two-row table plus §6's seeding rule.
2. `skill_ownership_checks` retires — the classes it lints no longer exist.
3. gitman's skill is authored in devman's pack; the copy in `gitman/` is deleted.
   Run for one release cycle before continuing.
4. testee, docman: same, one at a time.
5. copyroom's 3 canonical skills move; `src/copyroom/agent/assets/skills/` is
   deleted; `agent-files export` shrinks to `AGENTS.md` + the symlink.
6. The router skill moves. repoman keeps `registry.py` and loses the Jinja
   template. This is last, because the router is the one skill whose facts come
   from a live registry rather than a CLI walk.
7. my-ai's law becomes a pack asset — or stays a hand-edited overlay. See §8.

Step 3 is the pilot. If it does not clearly improve on gitman's hand-written
skill, stop and take the lint-only option.

---

## 8. Open questions

- **Does the my-ai law stay a hand-written file?** It is prose, so devman would
  author it. It is also the one skill the user edits directly and most often.
  Lean: permanent overlay. A generator between a user and their own standing
  instructions is friction with no payoff.
- **What happens to a repo that wants a skill devman does not ship?** The overlay
  path in `.devman/devman.toml` covers permanent divergence. Is there a
  lighter-weight local-only skill, or does everything become an asset?
- **Trigger ownership.** If devman authors every skill, it also assigns every
  `auto_trigger` keyword. That makes collisions impossible by construction — but
  it also means a tool can no longer choose the words users reach it by. Is that
  a gain or a loss?
- **What is the rollback?** If the takeover proves wrong two repos in, what
  restores per-tool authorship? An emitter that writes each skill back into its
  home repo would make this cheap, and is worth building **before** step 3.
