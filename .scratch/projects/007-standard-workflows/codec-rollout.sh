#!/usr/bin/env bash
# Migrate one repository to devman's DAG identity codec (devman S-12).
#
#   devenv.yaml pins devman by an explicit rev= in the URL, so the bump is a
#   text edit plus `devenv update devman`. Entering the shell is what performs
#   the projection: the enterShell guard tests the new link shape, finds it
#   missing, re-projects, and sweeps the old link.
#
# DRY=1 reports what it would do and changes nothing.
# Any failure reverts devenv.yaml, so the repository stays on its old pin and
# keeps working through the CLI's unmigrated() fallback.

set -uo pipefail
NEW_REV="${NEW_REV:-50c4c2e841136496b05fc1bf1037c9eba0133db7}"
DRY="${DRY:-0}"
REG="$HOME/.local/share/devman"

say() { printf '%s\n' "$*"; }

migrate() {
  local proj="$1" path rev before after
  path=$(python3 -c "import json,sys;print(json.load(open('$REG/projects/$proj/metadata.json'))['path'])") || {
    say "SKIP  $proj — no registry entry"; return 1; }
  cd "$path" 2>/dev/null || { say "SKIP  $proj — $path is not a directory"; return 1; }

  [ -f devenv.yaml ] || { say "SKIP  $proj — no devenv.yaml"; return 1; }
  rev=$(grep -oE 'devman\?ref=[^&"]*&rev=[0-9a-f]{40}' devenv.yaml | grep -oE '[0-9a-f]{40}' | head -1)
  if [ -z "$rev" ]; then
    say "SKIP  $proj — no pinned devman rev= in devenv.yaml"; return 1
  fi
  if [ "$rev" = "$NEW_REV" ]; then
    say "OK    $proj — already on the new pin"; return 0
  fi

  # A DETACHED HEAD IS LEFT ALONE, and it is not a tidiness rule. The
  # devenv.yaml edit has to persist, or the next shell entry re-projects under
  # the old codec and undoes the migration — so the edit must be committed. A
  # commit on a detached HEAD is a dangling commit nothing points at. These
  # repositories keep working through the fallback and are reported instead.
  local branch; branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [ "$branch" = "HEAD" ]; then
    say "HOLD  $proj — detached HEAD, left on ${rev:0:7} and on the fallback"; return 1
  fi

  before=$(ls "$REG/dags/" | grep -c "^$proj-" || true)
  if [ "$DRY" = 1 ]; then
    say "DRY   $proj — ${rev:0:7} -> ${NEW_REV:0:7}, $before old-shape links, branch $branch"
    return 0
  fi

  cp devenv.yaml /tmp/devenv.yaml.revert
  sed -i "s|rev=$rev|rev=$NEW_REV|" devenv.yaml

  if ! timeout 600 devenv update devman >/tmp/wave-$proj.log 2>&1; then
    cp /tmp/devenv.yaml.revert devenv.yaml
    say "FAIL  $proj — devenv update: $(tail -2 /tmp/wave-$proj.log | tr '\n' ' ' | cut -c1-140)"; return 1
  fi
  if ! timeout 900 devenv shell -- true >>/tmp/wave-$proj.log 2>&1; then
    cp /tmp/devenv.yaml.revert devenv.yaml
    timeout 900 devenv update devman >/dev/null 2>&1
    say "FAIL  $proj — shell entry: $(tail -2 /tmp/wave-$proj.log | tr '\n' ' ' | cut -c1-140)"; return 1
  fi

  after=$(ls "$REG/dags/" | grep -c "^$proj\." || true)
  local leftover
  leftover=$(ls "$REG/dags/" | grep -c "^$proj-" || true)
  if [ "$after" = 0 ]; then
    say "FAIL  $proj — shell entered but nothing projected under the codec"; return 1
  fi

  # Only the two files this touched. A repository may be dirty for its own
  # reasons, and that is not this wave's business.
  git add devenv.yaml 2>/dev/null
  git add devenv.lock 2>/dev/null   # ignored in most repos; harmless where it is
  if git diff --cached --quiet; then
    say "OK    $proj — $after links, nothing to commit"
    return 0
  fi
  git commit -q -F - <<'MSG'
chore(devman): bump to 50c4c2e for the DAG identity codec

devman #137 makes the DAG name injective: <project>-<workflow> became
<project>.<workflow>. Entering the shell after this re-projects this
repository under the new name and sweeps the old dags/ link.

Until this lands a repository keeps working through the CLI's unmigrated()
fallback, which enqueues the old name and says so on stderr.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
  if ! git push -q origin "$branch" 2>>/tmp/wave-$proj.log; then
    say "WARN  $proj — migrated and committed on $branch, push failed"
    return 0
  fi
  say "OK    $proj — ${rev:0:7} -> ${NEW_REV:0:7}, $after links, $leftover old left, pushed $branch"
}

for p in "$@"; do migrate "$p"; done
