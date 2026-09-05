#!/usr/bin/env bash
# 012 Part C — does `dagu enqueue` slow down as run history grows?
#
# Same throwaway home. The queue is emptied first so depth does not confound the
# answer, then the live plane's `data/dag-runs` is COPIED in (read-only from the
# live side) at 1x and 5x, which stands in for the year the plane has not had.
set -euo pipefail
H=/tmp/012/dagu-home
REAL=$HOME/.local/share/dagu/data/dag-runs
echo "load: $(cut -d' ' -f1-3 /proc/loadavg)"
runs() { find "$H/data/dag-runs" -name status.jsonl 2>/dev/null | wc -l; }
measure() {
  printf -- "--- %s: %s runs, %s on disk\n" "$1" "$(runs)" \
    "$(du -sh "$H/data/dag-runs" 2>/dev/null | cut -f1 || echo 0)"
  hyperfine --warmup 2 --runs 20 -N -n "enqueue" /tmp/012/w-benchq 2>&1 | grep -E 'Time \(|Range'
  rm -rf "$H/data/queue"
}
rm -rf "$H/data/queue" "$H/data/dag-runs"
measure "no history"
cp -r "$REAL" "$H/data/dag-runs"
measure "1x the live plane"
# Multiply by copying the YEAR directory, which is the level Dagu buckets runs
# at (`<dag>/dag-runs/YYYY/MM/DD/`). Copying anything below that leaves the
# extra runs outside the tree Dagu walks, which is what a first attempt did —
# it reported "5x" at 1.17x and the figure meant nothing.
for year in 2019 2020 2021 2022 2023 2024 2025; do
  for d in "$H/data/dag-runs"/*/dag-runs/; do
    [ -d "$d/2026" ] && cp -r "$d/2026" "$d/$year" || true
  done
done
measure "8x the live plane — about a year at the current rate"
