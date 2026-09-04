#!/usr/bin/env bash
# Plane equivalent of spike gate A14, scaled 10x down: 2,000 files at once.
# Creates .py files inside the watched devman repo, outside .scratch (which the
# repo's own triggers.toml ignores), then measures dispatch and convergence.
set -u
REPO=/home/andrew/Documents/Projects/devman
D=$REPO/zz_flood
FIRED=/home/andrew/.local/share/devman/watch/fired.jsonl
META=$REPO/.devman/.runs/metadata.jsonl
before_f=$(wc -l < $FIRED); before_m=$(wc -l < $META)
mkdir -p $D
t0=$(date +%s.%N)
for i in $(seq 1 2000); do printf 'x  =  %d\n' $i > $D/f$i.py; done
t1=$(date +%s.%N)
echo "created 2000 files in $(echo "$t1-$t0"|bc)s at $(date -Iseconds)"
# watch for quiet: no new fired line and no new metadata line for 20s
last=""; quiet=0; start=$(date +%s)
while [ $(( $(date +%s) - start )) -lt 240 ]; do
  now="$(wc -l < $FIRED) $(wc -l < $META)"
  if [ "$now" = "$last" ]; then quiet=$((quiet+2)); else quiet=0; last="$now"; fi
  [ $quiet -ge 20 ] && break
  sleep 2
done
after_f=$(wc -l < $FIRED); after_m=$(wc -l < $META)
echo "elapsed_to_quiet=$(( $(date +%s) - start ))s (minus 20s quiet window)"
echo "dispatches_fired=$((after_f-before_f))  runs_recorded=$((after_m-before_m))"
echo "--- fired lines ---"; tail -n $((after_f-before_f)) $FIRED
echo "--- run statuses ---"; tail -n $((after_m-before_m)) $META | grep -o '"status":"[a-z]*"' | sort | uniq -c
rm -rf $D
echo "cleaned up; files remaining: $(ls $D 2>/dev/null | wc -l)"
