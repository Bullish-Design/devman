# 041 — Personal-layer retirement: baseline survey and scope

**Date:** 2026-10-03
**Purpose:** preserve the useful findings from the original fleet survey while
recording the newer retirement scope. This is not the final machine inventory;
use the current REMAINING.md report for current counts and blockers.

## Scope and decisions

The operator authorized removal of deployed skills, template enrollment
markers, active configuration references, and text mentions in working files.
The source repository stays in its dated archive. Git history, conversation
logs, caches, worktrees, and archives stay outside text cleanup. The later
instruction excludes all content under Notes/1_Projects.

Review text by hand. Keep useful measurements and research conclusions. Update
instructions, code, tests, and examples so they remain correct. Do not make a
blind name replacement or remove surrounding facts.

## Fresh scan before editing

The 2026-10-03 scan found 14 deployed skill directories, 14 enrollment files,
one retired central overlay, five paths needing review, and 229 files with
1,275 exact text matches. After excluding Notes/1_Projects, the text baseline
was 197 files and 1,223 matches. Most paths requiring ownership review were in
vendor, template, generated, or historical-output trees. They needed their
owner to classify them before editing.

The path-review set included the central overlay, two research filenames in the
041 project, a historical run output in Interplay, and two CopyRoom research
paths. The CopyRoom owner retained the research under a neutral topic name and
removed the obsolete deployment helper.

## Findings retained from the earlier survey

- The writing rules had already moved to a separate shared writing skill.
  That skill contains writing rules only; it is not a replacement for unrelated
  project, build, or manager instructions.
- A prior citation survey counted 35 repository instruction files that named
  the removed skill. It found that 7 also had the writing skill linked and 28
  did not. The count is historical, not a current inventory.
- A separate link-plane audit found 64 populated agent surfaces among 65
  central project entries: 542 relative pool links, 161 real directories,
  10 real files, and no absolute links among 559 checked symlinks.
- The earlier survey found one tracked leftover skill in llama-infernal and one
  top-level live enrollment in pytuin. The current cleanup lanes handle those
  repositories; consult their current Gitman status, not the old survey state.
- Four enrollment markers in template-nix were template or golden-output
  material. The template owner must preserve the template's own behavior while
  removing the retired enrollment from any active generated result.
- The central project's archived personal-layer directory was already absent
  from the current trunk. Its stale default workspace required a separate
  review before switching to trunk. The source archive remains unchanged.

## How to read old measurements

The old survey saw 39 sampled repositories with central agent-surface links,
then found one real, uncrossed local surface in llama-infernal. It also found
four repositories with no agent surface. These counts describe that survey
moment and do not prove that every generated or vendor path is safe to edit.

The earlier research rejected a path-only change from the retired skill to the
writing skill. The old citation often claimed four topics, while the writing
skill covered only writing. Each surviving sentence therefore needs a content
rewrite, not a pointer swap.

## Current source of truth

The user’s fresh scan and the final per-repository Gitman status checks take
precedence over all counts and lane states in this historical record. Update
REMAINING.md from the last verified scan. List unresolved generated outputs,
local-only lanes, and missing remotes there. Do not claim full retirement while
any in-scope active path or text match remains.
