#!@bash@
# devman checkout guard (PLAN §A.8, MEASUREMENTS M2). Do not edit the installed copy.
# Dagu creates a missing working_dir and the run then succeeds in an empty
# directory. So a step fails here unless the checkout holds .git or .jj.
if [ -n "${DEVMAN_PROJECT_DIR:-}" ] \
   && [ ! -e "$DEVMAN_PROJECT_DIR/.git" ] && [ ! -e "$DEVMAN_PROJECT_DIR/.jj" ]; then
  echo "devman: checkout $DEVMAN_PROJECT_DIR is gone (no .git, no .jj); refusing to run" >&2
  exit 1
fi
exec "@bash@" "$@"
