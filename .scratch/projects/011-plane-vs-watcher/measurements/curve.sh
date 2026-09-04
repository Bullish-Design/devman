#!/usr/bin/env bash
WE=/nix/store/4f67kvm4dlllmakjnm4dd42haaklddaw-watchexec-2.5.1/bin/watchexec
PY=/home/andrew/Documents/Projects/devman-spike/.devenv/state/venv/bin/python
REG=/home/andrew/.local/share/devman
R=/tmp/dm011/repos
S=/tmp/dm011/sample.sh
SETTLE=15; WINDOW=60
for N in 1 5 10 25; do
  # --- plane: ONE watchexec, N --watch paths, live flags ---
  args=(--emit-events-to=json-stdio --postpone --on-busy-update=queue --project-origin=$REG)
  for g in '**/.devman/.runs/**' '**/.git/**' '**/.devenv/**' '**/.direnv/**' '**/.venv/**' '**/__pycache__/**' '**/node_modules/**'; do args+=(--ignore "$g"); done
  for i in $(seq 1 $N); do args+=(--watch $R/repo$i); done
  $WE "${args[@]}" -- /bin/true >/dev/null 2>&1 &
  wpid=$!
  sleep $SETTLE
  $S "plane_watchexec N=$N" $WINDOW $wpid
  kill $wpid 2>/dev/null; wait $wpid 2>/dev/null

  # --- spike: N watchfiles daemons ---
  pids=""
  for i in $(seq 1 $N); do $PY /tmp/dm011/spikewatch.py $R/repo$i >/dev/null 2>&1 & pids="$pids $!"; done
  sleep $SETTLE
  $S "spike_watchfiles N=$N" $WINDOW $pids
  for p in $pids; do kill $p 2>/dev/null; done
  wait 2>/dev/null
done
