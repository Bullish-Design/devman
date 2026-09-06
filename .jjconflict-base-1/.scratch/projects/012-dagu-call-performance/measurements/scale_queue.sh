#!/usr/bin/env bash
# 012 Part C — does `dagu enqueue` slow down as the queue gets deeper?
#
# On a THROWAWAY DAGU_HOME with no scheduler running, so the queue only grows.
# The live plane is not touched: its home, its config and its data are read once
# to build this one, and never written.
set -euo pipefail
H=/tmp/012/dagu-home
DAGU=${DAGU:-/nix/store/80z64fdn6gkgagz7xh2v4mh362hahvqa-dagu-2.15.0/bin/dagu}
D=/home/andrew/Documents/Projects/devman
cat > /tmp/012/w-benchq <<W
#!/bin/sh
DEVMAN_PROJECT_DIR=$D
export DEVMAN_PROJECT_DIR
exec $DAGU --dagu-home $H enqueue bench -- DEVMAN_PROJECT_DIR=$D
W
chmod +x /tmp/012/w-benchq
depth() { find "$H/data/queue" -name 'item_*.json' | wc -l; }
fill() { while [ "$(depth)" -lt "$1" ]; do /tmp/012/w-benchq >/dev/null 2>&1; done; }
echo "load: $(cut -d' ' -f1-3 /proc/loadavg)"
for target in 1 100 1000; do
  fill "$target"
  echo "--- queue depth $(depth), $(du -sh "$H/data/queue" | cut -f1) on disk"
  hyperfine --warmup 2 --runs 20 -N -n "enqueue at depth ~$target" /tmp/012/w-benchq 2>&1 \
    | grep -E 'Time \(|Range'
done
echo "final depth $(depth)"
