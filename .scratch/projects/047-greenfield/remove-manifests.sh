#!/usr/bin/env bash
# Remove the tracked devman manifests from every repository (047 §14 item 2).
#
# For each jj repository under the projects root that tracks
# `.devman/project.toml` or `.devman/triggers.toml`:
#   1. fetch, then start a new change on trunk(), away from the working copy;
#   2. delete the manifest files, describe the change, move the trunk
#      bookmark to it, and push that bookmark;
#   3. return to the old working-copy change if it held work, else stay on
#      the new trunk.
# A working copy with uncommitted work is never edited. Archived
# repositories (038 archive set) are skipped.
#
# Usage: remove-manifests.sh [--dry-run] [projects-root]
set -u

dry=0
if [ "${1:-}" = "--dry-run" ]; then dry=1; shift; fi
root="${1:-$HOME/Documents/Projects}"
archived=" allium-env forgelab lodestar fleetman my-ai "
message="chore: remove the devman manifest (devman 047)

devman now reads one central projects.toml. The repository tracks nothing
devman-specific."

for dir in "$root"/*/; do
  repo="$(basename "$dir")"
  [ -d "$dir/.jj" ] || continue
  case "$archived" in *" $repo "*) echo "skip   $repo (archived)"; continue ;; esac
  files="$(git -C "$dir" ls-files .devman/project.toml .devman/triggers.toml)"
  [ -n "$files" ] || continue
  if [ "$dry" = 1 ]; then echo "would  $repo: $(echo $files)"; continue; fi

  (
    cd "$dir" || exit 1
    set -e
    old="$(jj log -r @ --no-graph -T 'change_id')"
    old_empty="$(jj log -r @ --no-graph -T 'if(empty, "yes", "no")')"
    jj git fetch --quiet 2>/dev/null || true
    trunk="$(jj log -r 'trunk()' --no-graph -T 'local_bookmarks.map(|b| b.name()).join(" ")' | awk '{print $1}')"
    [ -n "$trunk" ] || { echo "FAIL   $repo: trunk() has no local bookmark"; exit 1; }
    jj new --quiet "$trunk"
    rm -f $files
    rmdir .devman 2>/dev/null || true
    jj describe --quiet -m "$message"
    jj bookmark set --quiet "$trunk" -r @
    if jj git push --quiet --bookmark "$trunk" 2>/tmp/remove-manifests-push.err; then
      result="pushed $trunk"
    else
      result="NOT PUSHED: $(tr '\n' ' ' </tmp/remove-manifests-push.err)"
    fi
    if [ "$old_empty" = "no" ]; then
      jj edit --quiet "$old"
      result="$result; back on the working-copy change $old"
    else
      jj new --quiet "$trunk"
    fi
    echo "done   $repo: $result"
  ) || echo "FAIL   $repo"
done
