#!/usr/bin/env bash
# 012 Part A — the dispatch half, one process at a time.
#
# Every figure here is hyperfine with `--warmup 3 --runs 30`, which is the
# KICKOFF's "n >= 20, its p50 AND its max" made the default. Run it from the
# repository's devenv shell: `hyperfine` and `watchexec` are in `devenv.nix`.
#
# NOTHING HERE ENQUEUES. The dispatch batch names README.md, which resolves to
# the devman project and matches no glob, so `match()` does its full work over
# the registry and returns nothing. `run --print` stops before `dagu enqueue`.
# `dagu enqueue` itself is measured by enqueue.sh, separately and on purpose.
set -euo pipefail
DEVMAN=${DEVMAN:-/tmp/012/devman-src/bin/devman}
PY=$(grep -o '/nix/store/[^/]*python3[^/]*/bin/python[0-9.]*' "$(dirname "$DEVMAN")/.devman-wrapped" | head -1)
REG=$HOME/.local/share/devman
DAGU_H=$HOME/.local/share/dagu
OUT=${1:-/tmp/012/micro.json}

echo "devman     : $DEVMAN"
echo "interpreter: $PY"
echo "load        : $(cut -d' ' -f1-3 /proc/loadavg)"

# stdin redirection needs a shell, so the two dispatch cases get one wrapper
# script each and hyperfine still runs them with -N.
cat > /tmp/012/w-dispatch <<W
#!/bin/sh
exec $DEVMAN --registry $REG --dagu-home $DAGU_H watch --dispatch < /tmp/012/batch-nomatch.json
W
chmod +x /tmp/012/w-dispatch

hyperfine --warmup 3 --runs 30 -N --export-json "$OUT" \
  -n "py-floor            interpreter start, nothing else" \
      "$PY -c pass" \
  -n "devman-help         + console script + devman imports" \
      "$DEVMAN --help" \
  -n "dispatch-nomatch    + registry load + match() over 54 projects" \
      "/tmp/012/w-dispatch" \
  -n "run-print           + workflow read + YAML parse + every refusal" \
      "$DEVMAN --registry $REG --dagu-home $DAGU_H run format -p devman --print" \
  -n "dagu-help           Go binary start, nothing else" \
      "dagu --help"
