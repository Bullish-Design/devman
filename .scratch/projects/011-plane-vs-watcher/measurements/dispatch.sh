#!/usr/bin/env bash
# Decompose the plane's 502 ms dispatch (RESULT.md section 4.2). 10 runs each.
D=/nix/store/2mjbj2imilxj56l8l79z689hz40ram6a-dagu-2.15.0/bin/dagu
t() { for i in $(seq 1 10); do s=$(date +%s%N); "$@" >/dev/null 2>&1; e=$(date +%s%N); echo $(( (e-s)/1000000 )); done \
      | sort -n | awk '{a[NR]=$1} END{print "p50",a[int(NR/2)+1],"min",a[1],"max",a[NR]}'; }
echo -n "devman CLI cold start   : "; t devman --help
echo -n "dagu binary cold start  : "; t $D --help
echo -n "devman run --print      : "; t devman run format --print
echo "watchexec debounce default: 50 ms (watchexec --help; live argv does not override it)"
