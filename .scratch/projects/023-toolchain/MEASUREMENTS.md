# Measurements

All on `server`, 2026-09-06, warm Nix eval cache unless stated.
Timing method: wall clock around the process, `date +%s%N`, sorted samples.

## M1 — startup and resolution cost

| Command | n | samples (ms, sorted) | median | interpretation |
|---|---|---|---|---|
| `zsh -lic true` | 5 | 675 675 757 808 810 | **757** | login shell is already slow; do not add work to it |
| `~/.local/share/repoman/venv/bin/python -c 'import pyjutsu'` | 5 | 311 506 568 602 713 | **568** | loading the 20 MB `.so` dominates; first sample is the page-cache-warm floor |
| `~/.local/share/repoman/venv/bin/gitman --help` | 5 | 848 1056 1065 1092 1190 | **1065** | Typer + pydantic + pyjutsu import |
| `devenv shell -- true` | 3 | 731 755 899 | **755** | warm devenv entry |
| `devenv shell -- gitman --help` | 3 | 1674 2016 2445 | **2016** | = devenv entry + gitman. The wrapper roughly doubles the cost. |
| `devenv shell -- python3 -c 'import templateer'` | 3 | 1408 1513 1586 | **1513** | |
| `devenv shell -- env PYTHONPATH=... uv run --project templateer_v2 templateer --help` | 3 | 1413 510 492 | **510** warm | first call resolves the project; later calls are cached |

## M2 — cold `devenv shell` inside a Dagu step

From the disposable probe DAG's stderr:

```
✓ Evaluating shell in 6.05s
✓ Configuring shell in 6.06s
✓ Running tasks in 49.4ms
• warning: Git tree '/home/andrew/Documents/Projects/repoman' is dirty
```

6.05 s to evaluate, against 0.755 s warm. The `git+file:` input on a dirty
`repoman` tree is what invalidates the evaluation cache: any edit anywhere in
the repoman checkout re-evaluates every devenv that imports it.

**Cost projection for `changelog.yaml` as written:** the workflow calls
`devenv shell --` four times in three steps. At the warm 0.755 s entry cost
that is ~3 s of pure wrapper overhead per run; after any repoman edit the first
of those four pays ~6 s.

## M3 — the defect, reproduced directly

```
$ cd ~/Documents/Projects/devman
$ devenv shell -- python3 -c 'import pyjutsu; print(pyjutsu.__file__)'
ModuleNotFoundError: No module named 'pyjutsu'

$ devenv shell -- gitman --help
(works)
```

`groups/changelog/workflows/changelog.yaml` steps `gate` and `write` both run
`devenv shell -- python3 - <<PYEOF ... import pyjutsu`. Both fail today in
devman's own checkout.

Confirmed identically from inside a real Dagu step (probe DAG
`zz-toolchain-probe`, run `034KOdSeVgQC8oUGKUyGGD`, result Succeeded, step log
retained under `.devman/.runs/logs/`).

## M4 — why `gitman` works and `import pyjutsu` does not

```
$ head -1 ~/.local/share/repoman/venv/bin/gitman
#!/home/andrew/.local/share/repoman/venv/bin/python
```

The console script names its interpreter absolutely. `python3` on `PATH`
resolves to the project venv first, because devenv prepends
`.devenv/state/venv/bin` ahead of `$REPOMAN_TOOLCHAIN_VENV/bin`. Two
interpreters, both 3.13, different patch levels (3.13.13 vs 3.13.14) and
disjoint `site-packages`.

## M5 — duplicate disk

Eight `_pyjutsu.abi3.so` copies, three distinct builds, 218 MB total.
`~/.cache/uv` 43 GB. `pyjutsu/target` 6.9 GB. See `INVENTORY.md` §5.

## M6 — `repoman doctor`, inside devman's devenv

```
OK   toolchain:venv, toolchain:lock, lock:git
OK   version:managers.git — gitman 0.6.0
OK   version:managers.git-pyjutsu — pyjutsu 0.20.0
OK   version:repoman — repoman 0.7.1
OK   deps:toolchain — 33 package(s) mutually compatible
WARN skill:entrypoint — missing — run `repoman install-skills`
gitman doctor: ok pyjutsu 0.20.0 (jj-lib 0.44.0), ok uv, !! config [version] table
```

Both doctors report green on `pyjutsu` while `devenv shell -- python3 -c
'import pyjutsu'` fails. Each doctor asks its **own** interpreter. Neither asks
the interpreter a workflow step actually uses. This is the diagnosis gap.
