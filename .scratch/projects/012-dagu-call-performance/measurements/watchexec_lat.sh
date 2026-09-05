#!/usr/bin/env bash
# 012 Part A — a write, to the dispatcher's first instruction.
#
# The plane's own watchexec cannot be timed from outside: its command is
# `devman watch --dispatch`, and the first timestamp devman writes is the
# `fired.jsonl` line, which is AFTER the registry load, `match()`, and a whole
# `devman run`. So this starts a second watchexec with the same argv shape the
# supervisor builds (`watch.py:watchexec_command`) over a scratch directory,
# and gives it a command that does nothing but record the time.
#
# The measured segment is therefore: inotify delivery + watchexec's default
# 50 ms debounce + fork/exec of the command. It is not devman's, and no part of
# it is devman's to remove.
set -euo pipefail
N=${1:-30}
D=$(mktemp -d /tmp/012-wx.XXXXXX)
OUT=$D/fired
: > "$OUT"
cat > "$D/rec" <<'R'
#!/bin/sh
cat > /dev/null      # drain the json-stdio batch, as the dispatcher does
date +%s%N >> "$FIRED"
R
chmod +x "$D/rec"
export FIRED=$OUT
watchexec --emit-events-to=json-stdio --postpone --on-busy-update=queue \
  --project-origin="$D" \
  --ignore '**/.devman/.runs/**' --ignore '**/.git/**' --ignore '**/.devenv/**' \
  --ignore '**/.direnv/**' --ignore '**/.venv/**' --ignore '**/__pycache__/**' \
  --ignore '**/node_modules/**' \
  --watch "$D/tree" -- "$D/rec" &
WX=$!
mkdir -p "$D/tree"
sleep 2                              # let watchexec establish its watches
: > "$D/wrote"
for i in $(seq 1 "$N"); do
  date +%s%N >> "$D/wrote"
  echo "x = $i" > "$D/tree/f.py"
  sleep 1.2                          # well clear of the 50 ms debounce
done
sleep 2
kill $WX 2>/dev/null || true; wait $WX 2>/dev/null || true
paste "$D/wrote" "$OUT" | awk '
  {d=($2-$1)/1e6; print "  " NR ": " d " ms"; a[NR]=d; n++}
  END{
    asort(a);
    printf "\nwrite -> dispatcher started, n=%d\n", n;
    printf "  p0   %8.1f ms\n", a[1];
    printf "  p50  %8.1f ms\n", a[int(0.5*n)+0];
    printf "  p90  %8.1f ms\n", a[int(0.9*n)+0];
    printf "  p100 %8.1f ms\n", a[n];
  }' 2>/dev/null || paste "$D/wrote" "$OUT" | awk '{print ($2-$1)/1e6}'
echo "(wrote $(wc -l < "$D/wrote") events, saw $(wc -l < "$OUT") dispatches)"
rm -rf "$D"
