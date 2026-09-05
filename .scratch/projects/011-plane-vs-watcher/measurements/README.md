# Raw measurements for 011

Taken 2026-09-04 on this machine. 8 cores, load average 3.86 at the start of
the scaling run, the live plane running throughout.

| File | What it is |
|---|---|
| `curve.sh` | the scaling driver — one watchexec with N `--watch` paths against N watchfiles daemons, N = 1, 5, 10, 25 |
| `sample.sh` | samples ticks / RSS / fds / threads / inotify watches over a window, summed across processes |
| `spikewatch.py` | one bare `watchfiles` daemon with `dspike.watcher.watch`'s exact parameters |
| `curve.out` | the scaling result — RESULT.md section 2 |
| `flood.sh` | the plane's answer to spike gate A14, scaled 10x down to 2,000 files |
| `flood.out` | the flood result — RESULT.md section 4.1 |
| `dispatch.sh` | decomposes the plane's 502 ms dispatch into its four stages, 10 runs each |
| `dispatch.out` | the dispatch decomposition — RESULT.md section 4.2 |

Reproducing `curve.sh` needs the 25 synthetic trees it reads from
`/tmp/dm011/repos` (316 directories each); the script does not create them:

    for i in $(seq 1 25); do for a in $(seq 1 15); do for b in $(seq 1 20); do
      mkdir -p /tmp/dm011/repos/repo$i/pkg$a/sub$b; done; done; done

`flood.sh` writes into the live `devman` repository and removes what it wrote.
