#!/usr/bin/env bash
# 012 Part B candidate 4 — what does the coordinator cost when nothing uses it?
#
# `coordinator.enabled` defaults true and the live config.yaml names a host and
# a port for it. Project 011 recorded it as configured and unused. This measures
# it, on a THROWAWAY DAGU_HOME on other ports (18080/50155), so the live plane
# keeps 8080 and 50055 and is never stopped or reconfigured.
#
# Two 60 s idle windows, one per setting, reading utime+stime from
# /proc/<pid>/stat and RSS from /proc/<pid>/status. Nothing is enqueued.
set -euo pipefail
H=/tmp/012/dagu-home
DAGU=${DAGU:-/nix/store/80z64fdn6gkgagz7xh2v4mh362hahvqa-dagu-2.15.0/bin/dagu}
WINDOW=${WINDOW:-60}

# A throwaway instance from an earlier, failed run still holds 50155, and the
# next one then dies on "address already in use" without saying which run left
# it. Match on the throwaway home so the live plane's `dagu start-all` — which
# does NOT carry that path — can never be selected here.
pkill -f "dagu --dagu-home $H" 2>/dev/null || true
sleep 1

ticks() { awk '{print $14+$15}' "/proc/$1/stat"; }
rss()   { awk '/VmRSS/{print $2}' "/proc/$1/status"; }
kids()  { pgrep -P "$1" 2>/dev/null | tr '\n' ' '; }

window() {
  local label=$1 pid=$2
  local t0 t1 r1
  t0=$(ticks "$pid")
  sleep "$WINDOW"
  t1=$(ticks "$pid"); r1=$(rss "$pid")
  awk -v l="$label" -v d="$((t1 - t0))" -v w="$WINDOW" -v r="$r1" \
    'BEGIN{printf "  %-22s %4d ticks / %d s   RSS %6.1f MB\n", l, d, w, r/1024}' 
}

for enabled in true false; do
  python3 "$(dirname "$0")/set_coordinator.py" "$H/config.yaml" "$enabled"
  "$DAGU" --dagu-home "$H" start-all >/tmp/012/dagu-$enabled.log 2>&1 &
  PID=$!
  sleep 8                                   # let it bind and settle
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "  coordinator=$enabled: did not start"; tail -3 /tmp/012/dagu-$enabled.log; continue
  fi
  echo "coordinator.enabled = $enabled   (pid $PID, children: $(kids "$PID"))"
  window "idle" "$PID"
  kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true
  sleep 2
done
echo "--- ports the live plane keeps: 8080, 50055. this used 18080, 50155."
