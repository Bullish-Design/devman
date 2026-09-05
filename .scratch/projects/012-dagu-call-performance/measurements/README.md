# 012 measurements — how to take these numbers again

Every figure in `../RESULT.md` came from one of these. They are here so that a
disagreement with a number is a re-run rather than an argument.

## Before anything

Run them from the repository's **devenv shell**. `hyperfine` and `watchexec` are
in `devenv.nix` for this project's sake; nothing here works without them.

```bash
devenv shell
```

Two of the scripts compare the shipped code against its predecessor, so they
need two builds on disk. Build the current tree, and build the parent commit's
tree the same way if you want the "before" column:

```bash
nix build .#devman --out-link /tmp/012/devman-new
mkdir -p /tmp/012/binnew && ln -sf /tmp/012/devman-new/bin/devman /tmp/012/binnew/devman
```

`micro.sh` also reads two fixture files — a watchexec batch that matches no glob,
and one that matches `**/*.py`:

```bash
mkdir -p /tmp/012
python3 -c 'import json;print(json.dumps({"tags":[{"kind":"path","absolute":"'"$PWD"'/README.md"}]}))'      > /tmp/012/batch-nomatch.json
python3 -c 'import json;print(json.dumps({"tags":[{"kind":"path","absolute":"'"$PWD"'/src/devman/watch.py"}]}))' > /tmp/012/batch-match.json
```

**The no-match batch is the safe one.** It resolves to the `devman` project and
matches no glob, so `match()` does its full work over the registry and enqueues
nothing. The match batch enqueues a real `format` run every time it is used.

## What each script answers

| script | question | touches the live plane? |
|---|---|---|
| `micro.sh` | where the dispatch's milliseconds go, one process at a time | reads the registry; **enqueues nothing** |
| `watchexec_lat.sh` | a `write()` to the dispatcher's first instruction | no — its own watchexec over a scratch tree |
| `enqueue_lat.py N GAP OUT` | enqueue to the step's first byte | **yes** — enqueues N real `devman.format` runs |
| `tick_fit.py OUT [OUT…]` | is the drain periodic, and what is the period | no — reads the JSON the above wrote |
| `scale_registry.py N DIR` | builds a synthetic registry of N projects under `/tmp` | no |
| `scale_queue.sh` | enqueue cost against queue depth | no — throwaway `DAGU_HOME` |
| `scale_history.sh` | enqueue cost against history size | reads `data/dag-runs`, writes to the throwaway home |
| `coordinator_cost.sh` | what `coordinator.enabled` costs when idle | no — throwaway home, ports 18080/50155 |
| `set_coordinator.py` | one config key, for the script above | no |

`ENQUEUE=http enqueue_lat.py …` measures Dagu's HTTP enqueue instead of
`devman run`. That is what answered candidate 3.

## The rule these follow

**A throwaway `DAGU_HOME` under `/tmp`, never the plane's own.** `devenv.nix`
already says why a second Dagu may not share the first one's ports, and the
KICKOFF forbids reconfiguring the live plane. `coordinator_cost.sh` starts a
Dagu; it starts it on 18080 and 50155, and it kills only processes whose command
line carries the throwaway home — the live `dagu start-all` does not.

## The raw data

`enqueue-idle.json`, `enqueue-idle-2.json` and `enqueue-http.json` hold one
object per run: the run id, how long the enqueue took, when Dagu recorded the
item, when the step's stdout file appeared, and the difference. `tick_fit.py`
reads them. They are committed because §2.1's claim is a fit, and a fit without
its data is an assertion.
