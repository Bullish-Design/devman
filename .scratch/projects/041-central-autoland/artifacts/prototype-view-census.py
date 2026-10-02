import os, sys
from pathlib import Path
from collections import Counter
CENTRAL=(Path.home()/".config/devman").resolve(); FLEET=Path.home()/"Documents/Projects"
SKIP={".git",".jj",".devenv",".direnv",".venv","node_modules","__pycache__",".worktrees",".archive",".runs"}
c=Counter(); repos=set()
for repo in sorted(p for p in FLEET.iterdir() if p.is_dir() and p.name not in SKIP):
    for cur,dirs,files in os.walk(repo,followlinks=False):
        d=len(Path(cur).relative_to(repo).parts)
        dirs[:]=[] if d>=2 else [x for x in dirs if x not in SKIP]
        for n in list(dirs)+files:
            p=Path(cur)/n
            if not p.is_symlink(): continue
            raw=os.readlink(p); t=Path(os.path.normpath(raw if os.path.isabs(raw) else Path(cur)/raw))
            if str(t).startswith(str(CENTRAL)+"/") or str(t)==str(CENTRAL):
                c[str(p.relative_to(repo))]+=1; repos.add(repo.name)
    g=repo/".git"; ex=g/"info"/"exclude" if g.is_dir() else None
    if ex and ex.is_symlink():
        t=Path(os.path.normpath(os.readlink(ex)))
        if str(t).startswith(str(CENTRAL)+"/"): c[".git/info/exclude"]+=1; repos.add(repo.name)
print("repos:",len(repos)); print("total:",sum(c.values()))
for k,v in c.most_common(15): print(f"  {k:35s} {v}")
