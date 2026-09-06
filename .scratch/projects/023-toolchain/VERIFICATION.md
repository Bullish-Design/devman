# Verification plan

## V1 — the interpreter probe becomes a check

The single highest-value addition. Both doctors ask their own interpreter and
report green while a step fails (M6). Add to `devman doctor`, or to the
`changelog` group's own gate:

```
devenv shell -- python3 -c 'import pyjutsu, templateer'
```

run as the **step** runs it. A check that cannot fail proved nothing; this one
fails today.

## V2 — the environment matrix, as a script

Re-run the probe used in this investigation across all five boundaries and
diff against the recorded table in `INVENTORY.md` §3:

```
zsh -lic 'bash probe.sh'
devenv shell -- bash probe.sh
<disposable Dagu DAG> -> raw step
<disposable Dagu DAG> -> devenv shell -- bash probe.sh
~/.local/share/repoman/venv/bin/python probe.py
```

Every row must name exactly one interpreter and one path per package.

## V3 — one name, one binary

```
for c in python3 repoman devenv gitman uv; do
  type -a $c
done
```
Each must print exactly one line, in both a login shell and a devenv.

## V4 — the plane's existing gates

```
devenv tasks run -v base:check
devenv tasks run -v base:test
devman doctor
repoman doctor
```
All must exit 0 before any change to `modules/`, `groups/`, `nix/` or
`src/devman/` is committed.

## V5 — end to end, in a disposable adopter

The 022 kickoff already specifies this and it stands: real `gitman start` /
`save` / `land`, the real post-hook enqueue, the chained workflow reaching
generation, and the resulting lane diff inspected by a person. Plus both
refusals: empty batch, and a second unreviewed lane.

## V6 — fresh-machine rebuild

The claim "reproducible" is only proven by rebuilding. The honest current answer
is that it cannot be done: the toolchain venv needs `UV_FIND_LINKS` pointing at
one Nix store path, and four of its entries are editable installs of local
working trees. Step 7 of the migration is what makes V6 possible.
