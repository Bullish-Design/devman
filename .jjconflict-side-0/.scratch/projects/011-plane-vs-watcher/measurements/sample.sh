#!/usr/bin/env bash
# sample.sh <label> <secs> <pid...>  -> ticks over window, RSS sum, fds, inotify watches
label=$1; secs=$2; shift 2; pids="$@"
t0=0; for p in $pids; do v=$(awk '{print $14+$15}' /proc/$p/stat 2>/dev/null); t0=$((t0+v)); done
sleep $secs
t1=0; rss=0; fds=0; ino=0; thr=0
for p in $pids; do
  v=$(awk '{print $14+$15}' /proc/$p/stat 2>/dev/null); t1=$((t1+v))
  r=$(awk '/VmRSS/{print $2}' /proc/$p/status 2>/dev/null); rss=$((rss+r))
  f=$(ls /proc/$p/fd 2>/dev/null | wc -l); fds=$((fds+f))
  n=$(ls /proc/$p/task 2>/dev/null | wc -l); thr=$((thr+n))
  for ff in /proc/$p/fdinfo/*; do c=$(grep -c '^inotify' $ff 2>/dev/null); ino=$((ino+c)); done
done
echo "$label ticks=$((t1-t0)) rss_kb=$rss fds=$fds threads=$thr inotify=$ino nproc=$(echo $pids|wc -w)"
