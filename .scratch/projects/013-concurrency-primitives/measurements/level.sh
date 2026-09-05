#!/usr/bin/env bash
# one concurrency level: L fresh flake checks at once
L=$1
for i in $(seq 1 $L); do
  sed -i '/cap-marker/d' /tmp/013/cap/r$i/nix/nixos-module.nix
  echo "# cap-marker r$i-L$L $(date +%s%N)" >> /tmp/013/cap/r$i/nix/nixos-module.nix
done
echo "--- L=$L  load_before=$(cut -d' ' -f1 /proc/loadavg)"
t0=$SECONDS
for i in $(seq 1 $L); do
  ( s=$SECONDS; (cd /tmp/013/cap/r$i && nix flake check >/dev/null 2>&1); echo "$i $((SECONDS-s))" >> /tmp/013/out/level_$L.txt ) &
done
wait
echo "    wall=$((SECONDS-t0))s  load_after=$(cut -d' ' -f1 /proc/loadavg)"
sort -n /tmp/013/out/level_$L.txt | awk '{a[NR]=$2} END{printf "    per-run: min %ds  p50 %ds  max %ds  (n=%d)\n", a[1], a[int((NR+1)/2)], a[NR], NR}'
