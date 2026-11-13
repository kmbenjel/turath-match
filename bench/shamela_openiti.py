"""Work- and edition-level precision and recall: OpenITI against YOUR local Shamela.

Labels come from OpenITI, not from turath-match: a version such as ``0256Bukhari.Sahih.Shamela0001681-ara1`` was
made from Shamela book 1681, and OpenITI files it under the book URI ``0256Bukhari.Sahih``. For a version *v* and
a Shamela book *s* that is itself the source of some OpenITI version:

* same work      <=> book URI of v == book URI of the version made from s
* same edition   <=> s is the very Shamela book v was made from

turath-match sees titles, authors, death years and the edition fields (OpenITI's ``ed_info``; the Shamela book
cards exported from your install) and never the URIs. Nothing from Shamela is shipped or printed: the script
writes counts only.

Usage:
  turath-match shamela-cards --path ~/.local/share/shamela -o bench/data/shamela-cards.jsonl
  python bench/shamela_openiti.py bench/data/openiti.tsv ~/.local/share/shamela bench/data/shamela-cards.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

from turath_match.edition import match_edition
from turath_match.index import TokenIndex
from turath_match.models import MATCH, REVIEW, SAME
from turath_match.sources.openiti import OpenITI
from turath_match.sources.shamela import ShamelaLocal
from turath_match.work import match_work

_CTX: dict = {}


def _one(v):
    c = _CTX
    cw: Counter = Counter()
    ce: Counter = Counter()
    vb = replace(v, work_uri="")
    cw["pos"] += len(c["by_book"][v.work_uri] & c["have"])
    cands = c["idx"].candidates(vb, limit=60)
    for s in cands:
        same_work = c["bos"][s.id] == v.work_uri
        m = match_work(vb, s)
        if m.verdict == SAME and m.status == MATCH:
            cw["tp" if same_work else "fp"] += 1
            if not same_work:
                continue
            ed = match_edition(vb, s)
            same_ed = s.id == c["src"][v.id]
            if ed.verdict == SAME and ed.status == MATCH:
                ce["tp" if same_ed else "fp"] += 1
            elif ed.verdict == "different":
                ce["fn" if same_ed else "tn"] += 1
            else:
                ce["uncertain_pos" if same_ed else "uncertain_neg"] += 1
        elif m.status == REVIEW:
            cw["review_pos" if same_work else "review_neg"] += 1
    return len(cands), cw, ce


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("openiti")
    ap.add_argument("shamela")
    ap.add_argument("cards", nargs="?")
    ap.add_argument("--sample", type=int, default=0, help="OpenITI versions to test (0 = all)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="bench/out/shamela_openiti.json")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    versions = [
        r for r in OpenITI(a.openiti).records() if r.extra.get("source_collection") == "Shamela" and r.author
    ]
    src = {r.id: str(int(r.extra["source_id"])) for r in versions if r.extra.get("source_id", "").isdigit()}
    book_of_shamela = {}
    for r in versions:
        if r.id in src:
            book_of_shamela.setdefault(src[r.id], r.work_uri)
    shamela = [s for s in ShamelaLocal(a.shamela, a.cards).records() if s.id in book_of_shamela]
    if a.sample:
        versions = random.Random(a.seed).sample(versions, min(a.sample, len(versions)))
    versions = [v for v in versions if v.id in src and src[v.id] in book_of_shamela]
    by_book: dict[str, set[str]] = defaultdict(set)
    for sid, b in book_of_shamela.items():
        by_book[b].add(sid)
    have = {s.id for s in shamela}

    t0 = time.perf_counter()
    global _CTX
    _CTX = {"idx": TokenIndex(shamela), "by_book": by_book, "have": have, "bos": book_of_shamela, "src": src}
    w = {"tp": 0, "fp": 0, "review_pos": 0, "review_neg": 0, "pos": 0}
    e = {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "uncertain_pos": 0, "uncertain_neg": 0}
    pairs = 0
    with Pool(a.workers) as pool:
        for n, cw, ce in pool.imap_unordered(_one, versions, chunksize=20):
            pairs += n
            for k, v in cw.items():
                w[k] += v
            for k, v in ce.items():
                e[k] += v
    secs = time.perf_counter() - t0
    res = {
        "openiti_versions": len(versions),
        "shamela_books_labelled": len(shamela),
        "pairs_compared": pairs,
        "seconds": round(secs, 1),
        "work": {
            **w,
            "precision": round(w["tp"] / max(1, w["tp"] + w["fp"]), 4),
            "recall": round(w["tp"] / max(1, w["pos"]), 4),
        },
        "edition": {
            **e,
            "precision": round(e["tp"] / max(1, e["tp"] + e["fp"]), 4),
            "recall": round(e["tp"] / max(1, e["tp"] + e["fn"] + e["uncertain_pos"]), 4),
            "different_rejected": round(e["tn"] / max(1, e["tn"] + e["fp"] + e["uncertain_neg"]), 4),
        },
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1), "utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
