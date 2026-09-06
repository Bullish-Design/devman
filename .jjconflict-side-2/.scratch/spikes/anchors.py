#!/usr/bin/env python
"""Spike E — does the mirror anchor survive ordinary work?

004-unified-charter §6.2 keys authored prose to `<relpath>::<dotted.symbol>`.
§15 step 1 says measure the orphan rate before anything depends on it, and
§16 criterion 10 sets the bar: >= 90% of prose re-attaches per commit, 0 lost.

Method
------
Replay a repo's first-parent history. At each commit, extract every anchor
with pydantree-sitter. For each consecutive pair (parent -> child):

    survived   parent anchor still present in child
    orphaned   parent anchor absent from child

Then split the orphans by whether the code actually went away, using the
body hash:

    vanished     body hash appears nowhere in the child   -> legitimate
    moved        body hash appears under a NEW anchor      -> RECOVERABLE FAILURE

`moved` is the number that matters. It is prose that would be quarantined by
§6.3 even though its subject is still in the tree, and it sizes the "rename
bridge" question in §17.

Usage
-----
    PYTHONPATH=<pydantree>/src <pydantree>/.venv/bin/python anchors.py <repo> [max_commits]
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field

import tree_sitter_python
from pydantree_sitter import Language, M, OutputModel, Span, capture, source_meta


# --------------------------------------------------------------------------
# the models ARE the queries
# --------------------------------------------------------------------------

class PyFunc(OutputModel):
    __match__ = M("module", ..., "function_definition")
    name: str = capture("name")
    span: Span = source_meta()

    model_config = {"arbitrary_types_allowed": True}


class PyClass(OutputModel):
    __match__ = M("module", ..., "class_definition")
    name: str = capture("name")
    span: Span = source_meta()

    model_config = {"arbitrary_types_allowed": True}


LANG = Language.from_module(tree_sitter_python)
FUNCS = LANG.extractor(PyFunc)
CLASSES = LANG.extractor(PyClass)


# --------------------------------------------------------------------------
# anchors
# --------------------------------------------------------------------------

def dotted_anchors(source: str) -> dict[str, str]:
    """{dotted.symbol.path: body-hash} for one file.

    The dotted path is built by span containment: a symbol's parents are
    every other symbol whose span strictly encloses it, innermost last.
    """
    try:
        rows = [(r.name, r.span, "def") for r in FUNCS.extract(source)]
        rows += [(r.name, r.span, "class") for r in CLASSES.extract(source)]
    except Exception:
        return {}

    # sort by start, then by widest first, so containers precede contents
    rows.sort(key=lambda r: (r[1].start_byte, -r[1].end_byte))

    out: dict[str, str] = {}
    stack: list[tuple[str, int]] = []          # (name, end_byte)
    for name, span, _kind in rows:
        while stack and span.start_byte >= stack[-1][1]:
            stack.pop()
        dotted = ".".join(n for n, _ in stack + [(name, 0)])
        body = span.text if isinstance(span.text, str) else str(span.text)
        out[dotted] = hashlib.blake2b(body.encode(), digest_size=8).hexdigest()
        stack.append((name, span.end_byte))
    return out


# --------------------------------------------------------------------------
# git, read-only, never touches a worktree
# --------------------------------------------------------------------------

def git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True, text=True, check=True, errors="replace",
    ).stdout


def commits(repo: str, limit: int | None) -> list[tuple[str, bool]]:
    """[(sha, is_merge)] oldest-first along the first-parent chain.

    Merges are kept in the chain (so the tree stays continuous) but their
    pairs are excluded from the rate statistics: a first-parent diff across
    a merge shows an entire branch's work as one step, which is not the unit
    prose is written against.
    """
    out: list[tuple[str, bool]] = []
    for line in git(repo, "log", "--first-parent", "--reverse",
                    "--format=%H %P").splitlines():
        parts = line.split()
        if parts:
            out.append((parts[0], len(parts) > 2))
    return out[-limit:] if limit else out


def renames(repo: str, parent: str, child: str) -> dict[str, str]:
    """{old_path: new_path} for .py files git detects as renamed."""
    out: dict[str, str] = {}
    try:
        diff = git(repo, "diff", "--name-status", "-M", "--diff-filter=R",
                   parent, child)
    except subprocess.CalledProcessError:
        return out
    for line in diff.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].startswith("R"):
            _, old, new = parts
            if old.endswith(".py") and new.endswith(".py"):
                out[old] = new
    return out


def tree(repo: str, rev: str, prefix: str = "") -> dict[str, str]:
    """{path: blob_sha} for .py files at rev, optionally under a prefix."""
    out: dict[str, str] = {}
    for line in git(repo, "ls-tree", "-r", rev).splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob" and path.endswith(".py"):
            if prefix and not path.startswith(prefix):
                continue
            out[path] = parts[2]
    return out


class BlobCache:
    """blob sha -> anchors. Unchanged files cost nothing across the replay."""

    def __init__(self, repo: str) -> None:
        self.repo = repo
        self.cache: dict[str, dict[str, str]] = {}
        self.reads = 0

    def get(self, sha: str) -> dict[str, str]:
        hit = self.cache.get(sha)
        if hit is not None:
            return hit
        self.reads += 1
        raw = subprocess.run(
            ["git", "-C", self.repo, "cat-file", "blob", sha],
            capture_output=True, check=True,
        ).stdout
        try:
            src = raw.decode("utf-8")
        except UnicodeDecodeError:
            src = ""
        val = dotted_anchors(src) if src else {}
        self.cache[sha] = val
        return val


PUBLIC_ONLY = False


def _public(path: str, dotted: str) -> bool:
    """Would a human plausibly write prose here?

    Prose targets stable, public API — not private helpers, not test
    functions. Annotating everything (the default) measures an upper bound
    on churn, because private helpers churn hardest.
    """
    base = path.rsplit("/", 1)[-1]
    if base.startswith("test_") or "/tests/" in path or path.startswith("tests/"):
        return False
    return not any(part.startswith("_") and part != "__init__"
                   for part in dotted.split("."))


def anchors_at(repo: str, rev: str, cache: BlobCache,
               prefix: str = "") -> dict[str, str]:
    """{'path::dotted': body-hash} for the tree at rev."""
    out: dict[str, str] = {}
    for path, sha in tree(repo, rev, prefix).items():
        for dotted, bhash in cache.get(sha).items():
            if PUBLIC_ONLY and not _public(path, dotted):
                continue
            out[f"{path}::{dotted}"] = bhash
    return out


# --------------------------------------------------------------------------
# the measurement
# --------------------------------------------------------------------------

@dataclass
class Totals:
    pairs: int = 0
    merges_skipped: int = 0
    pairs_with_churn: int = 0
    parent_anchors: int = 0
    survived: int = 0
    orphaned: int = 0
    vanished: int = 0
    moved: int = 0
    bridged: int = 0
    blobs: int = 0
    raw_rates: list[float] = field(default_factory=list)
    bridged_rates: list[float] = field(default_factory=list)
    worst: list[tuple[float, float, str, int, int]] = field(default_factory=list)
    moved_examples: list[tuple[str, str]] = field(default_factory=list)
    reasons: Counter = field(default_factory=Counter)


def replay(repo: str, limit: int | None, prefix: str = "") -> Totals:
    revs = commits(repo, limit)
    cache = BlobCache(repo)
    t = Totals()

    prev_rev, _ = revs[0]
    prev = anchors_at(repo, prev_rev, cache, prefix)

    for rev, is_merge in revs[1:]:
        cur = anchors_at(repo, rev, cache, prefix)
        t.pairs += 1

        if is_merge:
            # a first-parent diff across a merge is a whole branch of work,
            # not one step; excluded from the rates, kept in the chain
            t.merges_skipped += 1
            prev, prev_rev = cur, rev
            continue
        if not prev:
            prev, prev_rev = cur, rev
            continue

        orphans = {a: h for a, h in prev.items() if a not in cur}
        survived = len(prev) - len(orphans)
        t.parent_anchors += len(prev)
        t.survived += survived
        t.orphaned += len(orphans)

        if orphans:
            t.pairs_with_churn += 1

            # the rename bridge: git's own -M detection, nothing more
            rmap = renames(repo, prev_rev, rev)
            bridged_here = 0

            # body hashes NEW in the child — where a moved orphan must land
            new_by_hash: dict[str, list[str]] = {}
            for a, h in cur.items():
                if a not in prev:
                    new_by_hash.setdefault(h, []).append(a)

            for a, h in orphans.items():
                o_file, _, o_sym = a.partition("::")
                new_file = rmap.get(o_file)
                if new_file and f"{new_file}::{o_sym}" in cur:
                    bridged_here += 1
                    t.bridged += 1

                targets = new_by_hash.get(h)
                if not targets:
                    t.vanished += 1
                    continue
                t.moved += 1
                dst = targets[0]
                n_file, _, n_sym = dst.partition("::")
                if o_sym == n_sym and o_file != n_file:
                    t.reasons["file moved or renamed"] += 1
                elif o_file == n_file:
                    t.reasons["symbol renamed in place"] += 1
                else:
                    t.reasons["file and symbol both changed"] += 1
                if len(t.moved_examples) < 12:
                    t.moved_examples.append((a, dst))

            raw = survived / len(prev)
            brd = (survived + bridged_here) / len(prev)
            t.raw_rates.append(raw)
            t.bridged_rates.append(brd)
            t.worst.append((brd, raw, rev[:9], survived + bridged_here, len(prev)))

        prev, prev_rev = cur, rev

    t.blobs = cache.reads
    t.worst.sort()
    return t


def _stats(rates: list[float]) -> tuple[float, float, float, int]:
    s = sorted(rates)
    mean = sum(s) / len(s)
    median = s[len(s) // 2]
    p10 = s[max(0, int(len(s) * 0.10))]
    return mean, median, p10, sum(1 for r in s if r < 0.90)


def report(name: str, t: Totals, prefix: str) -> None:
    scope = f"  [{prefix}]" if prefix else ""
    print(f"\n{'=' * 68}\n{name}{scope}\n{'=' * 68}")
    print(f"  commit pairs            {t.pairs}"
          f"   ({t.merges_skipped} merges excluded)")
    print(f"  pairs with churn        {t.pairs_with_churn}")
    print(f"  unique blobs parsed     {t.blobs}")
    if not t.parent_anchors:
        print("  no anchors found")
        return

    print(f"\n  parent anchors          {t.parent_anchors}")
    print(f"  survived verbatim       {t.survived}"
          f"  ({t.survived / t.parent_anchors:.2%})")
    print(f"  orphaned                {t.orphaned}"
          f"  ({t.orphaned / t.parent_anchors:.2%})")
    print(f"    vanished (deleted)    {t.vanished}   legitimate")
    print(f"    moved (still there)   {t.moved}   failure")
    print(f"  recovered by git -M     {t.bridged}"
          f"   ({t.bridged / t.orphaned:.1%} of orphans)" if t.orphaned else "")

    for label, rates in (("raw    ", t.raw_rates),
                         ("bridged", t.bridged_rates)):
        if rates:
            mean, median, p10, under = _stats(rates)
            print(f"\n  per-pair re-attach, {label}"
                  f"  mean {mean:6.2%}  median {median:6.2%}  p10 {p10:6.2%}")
            print(f"    under the 90% bar     {under}/{len(rates)}"
                  f"  ({under / len(rates):.1%})")

    if t.reasons:
        print("\n  why anchors moved:")
        for reason, n in t.reasons.most_common():
            print(f"    {reason:<30} {n}")

    if t.worst:
        print("\n  worst commits (bridged rate):")
        for brd, raw, sha, kept, total in t.worst[:5]:
            print(f"    {sha}  raw {raw:6.1%} -> bridged {brd:6.1%}"
                  f"   {kept}/{total}")


def replay_persistent(repo: str, limit: int | None, prefix: str = "") -> dict:
    """Simulate the design in §6.3, not a pairwise diff.

    Prose is written once per anchor and NEVER deleted. When its anchor
    disappears the prose goes to quarantine; if the anchor comes back — a
    revert, a re-landed branch, a restored file — it re-attaches by itself.
    The pairwise measure cannot see that, and so understates the design.

    Also measures a name-only bridge: match a quarantined anchor by its
    dotted symbol alone, ignoring the path. `ambiguous` counts the cases
    where that name is not unique, which is where the bridge would guess.
    """
    revs = commits(repo, limit)
    cache = BlobCache(repo)

    written: set[str] = set()
    quarantined: set[str] = set()
    detached = recovered = 0
    name_recoverable = ambiguous = 0
    worst_quarantine = 0

    for rev, _is_merge in revs:
        cur = set(anchors_at(repo, rev, cache, prefix))

        back = quarantined & cur
        recovered += len(back)
        quarantined -= back

        live = (written - quarantined) - cur
        detached += len(live)
        quarantined |= live

        written |= cur
        worst_quarantine = max(worst_quarantine, len(quarantined))

    # could a name-only bridge clear the residue at HEAD?
    head_rev = revs[-1][0]
    head = anchors_at(repo, head_rev, cache, prefix)
    by_symbol: dict[str, list[str]] = {}
    for a in head:
        by_symbol.setdefault(a.partition("::")[2], []).append(a)
    for a in quarantined:
        hits = by_symbol.get(a.partition("::")[2], [])
        if len(hits) == 1:
            name_recoverable += 1
        elif len(hits) > 1:
            ambiguous += 1

    return {
        "written": len(written),
        "detached": detached,
        "recovered": recovered,
        "stranded": len(quarantined),
        "peak_quarantine": worst_quarantine,
        "live_at_head": len(head),
        "name_recoverable": name_recoverable,
        "ambiguous": ambiguous,
    }


def report_persistent(name: str, p: dict, prefix: str) -> None:
    scope = f"  [{prefix}]" if prefix else ""
    print(f"\n  -- persistent store, whole history --{scope}")
    print(f"  anchors ever written    {p['written']}")
    print(f"  detach events           {p['detached']}")
    print(f"  re-attached later       {p['recovered']}"
          f"   ({p['recovered'] / p['detached']:.1%} of detaches)"
          if p["detached"] else "  re-attached later       0")
    print(f"  still quarantined       {p['stranded']}"
          f"   (peak {p['peak_quarantine']})")
    print(f"  live anchors at HEAD    {p['live_at_head']}")
    if p["stranded"]:
        print(f"  name-only bridge could clear {p['name_recoverable']}"
              f"  ({p['name_recoverable'] / p['stranded']:.1%}),"
              f" ambiguous on {p['ambiguous']}")


if __name__ == "__main__":
    repo = sys.argv[1].rstrip("/")
    prefix = ""
    limit = None
    for arg in sys.argv[2:]:
        if arg.startswith("--prefix="):
            prefix = arg.split("=", 1)[1]
        elif arg == "--public":
            PUBLIC_ONLY = True
        else:
            limit = int(arg)
    name = repo.rsplit("/", 1)[-1]
    report(name, replay(repo, limit, prefix), prefix)
    report_persistent(name, replay_persistent(repo, limit, prefix), prefix)
