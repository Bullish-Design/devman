# Guide 03 — repair `~/Notes`, then wire the notes plane

**Two jobs, in order.** First undo a move that split your notes' history while a
live service was writing to them. Then wire the shape you actually want.

**Size:** repair ~30 min · wiring ~half a day, gated on two rebuilds.
**Do the repair before anything else.** SilverBullet is writing through a symlink
into the config repository right now.

**Concept:** [`CONCEPT.md`](CONCEPT.md) §8, rewritten for this.

---

## 1. What happened, measured 2026-09-10

Guide 02's session moved `~/Notes` into `~/.config/devman/notes/` and left a
symlink behind. SilverBullet (**PID 1032**, `--port 3000 … /home/andrew/Notes`)
never noticed and kept writing through it.

| Fact | Evidence |
|---|---|
| **No note content was lost** | `diff -rq ~/Notes.pre-link ~/.config/devman/notes --exclude=.git` → **0 differences**, both 20 `.md` files |
| **History was lost** | moved copy has **1 commit** (`3a718f3`, today 13:40). Original has full history (`8ec045c` → 2026-08-27 and earlier) |
| **The config repo is mid-conflict** | `main` tracks 22 files under `notes/argentic/`; the worktree has `notes/` as an **untracked nested git repo**. A `promote` lane shows **+0 −2063** |
| **`~/Notes` is a live service's data dir** | `silverbullet-server/modules/silverbullet-server.nix:39` hard-codes `default = "/home/andrew/Notes"`; `:133` auto-commits every 15 min; the Runtime API writes `.chrome-data/` |

**The design was wrong, not just the execution.** `CONCEPT.md` §8 treated `~/Notes`
as content the config repository could own. It is a running service's directory
with its own VCS. §8.1 now records the reversal.

---

## 2. The repair (~30 min)

Do this first, in one sitting, with the service stopped.

### 2.1 Stop the writer

```bash
systemctl status silverbullet          # find the unit owning PID 1032
sudo systemctl stop silverbullet
pgrep -af silverbullet                 # must be empty before continuing
```

### 2.2 Save today's edits

The moved copy is the one SilverBullet has been writing to since 09:29. Its single
commit is `3a718f3`, dated today 13:40.

```bash
git -C ~/.config/devman/notes log --stat -1     # what changed today
git -C ~/.config/devman/notes diff HEAD         # anything uncommitted
```

Keep that patch. You will replay it in 2.4.

### 2.3 Put the real tree back

```bash
rm ~/Notes                                      # the SYMLINK only — verify with `ls -ld ~/Notes`
mv ~/Notes.pre-link ~/Notes                     # full history restored
```

⚠ **`rm ~/Notes` must remove a symlink, not a directory.** Confirm with
`ls -ld ~/Notes` first — it should print `lrwxrwxrwx`.

### 2.4 Replay today's edits

Apply the patch from 2.2 onto the restored tree, then let SilverBullet's timer
commit it, or commit by hand.

### 2.5 Restart and confirm

```bash
sudo systemctl start silverbullet
git -C ~/Notes log --oneline | head -3          # full history present
ls ~/Notes/1_Projects/                          # andrew argentic flora … present
```

### 2.6 Clean the config repository

```bash
cd ~/.config/devman
gitman abandon promote                          # the lane carrying −2063
git rm -r --cached notes                        # stop tracking the 22 argentic files
rm -rf notes
printf 'notes/\n' >> .gitignore
```

Then land `promote/pydantree-envrc` on its own — it was blocked only because its
parent lane carried the notes deletion.

**Also finish two loose ends from guide 02:** `common/envrc` is modified and
uncommitted, and `.agents/skills/gitman/SKILL.md` is tracked while `.gitignore`
lists `.agents/` — decide whether that early Guide 01 content stays.

---

## 3. Two rebuilds gate the wiring

Neither is optional, and both are quick.

**3.1 loci-core 0.4.2.** Upward vault discovery is written and unreleased:

```
source pyproject version   0.4.2      find_vault_root at src/loci_core/vault/init.py:58
installed store build      0.3.0      grep -c find_vault_root → 0
```

Measured consequence today — even a plain subdirectory of a vault fails:

```
$ cd ~/Notes/1_Projects/flora && loci documents/list
error: VaultNotInitialized: no vault manifest at …/1_Projects/flora
$ cd flora && loci --vault ~/Notes documents/list        ✓ works
```

Release 0.4.2 and rebuild. Then decision **D-041** applies and `cd <repo>/.loci`
resolves upward to `~/Notes` on its own.

**3.2 devman.** `devman link` exists only inside devman's own devenv shell;
`/run/current-system/sw/bin/devman` is the stale profile build:

```
$ devman link status
devman: error: argument command: invalid choice: 'link'
```

A NixOS rebuild is required before any repository can reconcile links.

---

## 4. The wiring (~half a day, after §3)

### 4.1 The target

```
~/Notes/                              its own git repo · SilverBullet's space · THE vault
  .loci/vault.toml                    one manifest for every project
  1_Projects/flora/                   REAL directory — the notes live here
  Inbox/ Journal/ Library/ Scratch/   personal, untouched

flora/.loci -> ~/Notes/1_Projects/flora          excluded from flora's git
~/.config/devman/projects/flora/notes -> same    absolute → gitignored
```

**`1_Projects/` already holds repo names** — `andrew`, `argentic`, `flora`,
`image-gen-pipeline`, `nix-nvim`, `nvcheck`, `shellij`. The convention exists; this
wires it up.

### 4.2 The one new case in `link.py`

`devman.link` knows `canonical = "central"` (under `overlayDir`) and
`canonical = "repo"`. Notes need a third: **canonical is an absolute path outside
both roots.**

```nix
devman.link.".loci" = {
  canonical = "external";
  path      = "~/Notes/1_Projects/${project}";
};
```

Roughly 30 lines in `src/devman/link.py`:

- `Declaration.read` accepts `external` and expands `~`.
- `resolve` sets `canonical_path` from the absolute path instead of `overlayDir`.
- The five states of §5.1 are **unchanged** — that is the point of the state
  machine.
- `_create_canonical` for `external` is `mkdir -p`, never a template.

**Guard it:** refuse an `external` path that is not absolute after expansion, and
refuse one that resolves inside a project repository — that would put notes back
into project history, which is the whole thing this avoids.

### 4.3 Adopt

Per repository you want notes for:

```bash
mkdir -p ~/Notes/1_Projects/<repo>
# add the devman.link entry to devenv.nix
devenv shell        # reconciles: creates .loci, writes the exclude line
```

Start with **one** repository. Confirm all three access paths before doing more.

---

## 5. Verify

```bash
# 1. the notes' history is intact and the service owns them
git -C ~/Notes log --oneline | wc -l          # many, not 1
pgrep -af silverbullet                         # running against /home/andrew/Notes

# 2. no note content is in a project repo's history
git -C <repo> ls-files | grep '^\.loci/'      # empty
git -C <repo> check-ignore -v .loci           # matched by .git/info/exclude

# 3. all three write paths reach the same inode
echo "probe" > <repo>/.loci/_probe.md
test -f ~/Notes/1_Projects/<repo>/_probe.md && echo "repo → Notes OK"
git -C ~/Notes status --porcelain | grep _probe && echo "Notes git sees it"
rm <repo>/.loci/_probe.md

# 4. loci resolves without --vault  (only after §3.1)
cd <repo>/.loci && loci documents/list

# 5. the config repo is clean
cd ~/.config/devman && git status --porcelain      # no `?? notes/`
```

---

## 6. Do not do these

1. **Do not move `~/Notes` again.** It is a live service's data directory with a
   hard-coded path and an auto-commit timer. That is what broke.
2. **Do not put notes in the config repository.** §8.1. SilverBullet already
   versions them, better, and git cannot version content behind a symlink anyway.
3. **Do not make one vault per repository.** Fifty-two caches and no cross-project
   links, which is loci's main feature.
4. **Do not put `vault.toml` under `1_Projects/<repo>/`.** The vault root is
   `~/Notes` and only `~/Notes`.
5. **Do not wire any repository before both rebuilds land** (§3). Without them the
   link is inert and loci needs `--vault` every time.
6. **Do not `rm -rf ~/Notes` at any point.** In step 2.3 you are removing a
   symlink; check `ls -ld` first.

---

## 7. What this changes in the other guides

- **`CONCEPT.md` §8** — rewritten. `~/Notes` is a third root with its own owner;
  the config repository holds a derived, gitignored link only.
- **`GUIDE-02` §3** — its "`notes/` is ONE loci vault" step is **withdrawn**. The
  config repository creates no `notes/` directory.
- **`GUIDE-01`** — unaffected. The agent surface still lives in the config
  repository; only notes moved out.
