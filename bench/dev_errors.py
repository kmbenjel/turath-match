"""Where the matcher loses pairs on the development set (OpenITI), by cause, with the pairs themselves.

A rule is written by reading these lists; it is then measured once on the held-out set
(``bench/wikidata_heldout.py``), which is never read this way: its wrong pairs stay unseen, so the held-out
numbers say how the rules do on records they were not written for.

Every same-book pair the matcher did not call «same work» is filed under what stopped it:

* ``not-proposed``: the index never put the two records side by side;
* ``<verdict>/<status>|title:<kind>|author:<verdict>``: what ``match_work`` said, and how the titles and the
  authors compared (``different/no_match|title:exact|author:different`` is an author the name rules split in two).

Usage:
  python bench/dev_errors.py bench/data/openiti.tsv --out bench/out/dev_errors.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

from turath_match.index import TokenIndex
from turath_match.models import MATCH, SAME, Record
from turath_match.sources.openiti import OpenITI
from turath_match.work import match_work

_BY_KEY: dict[str, Record] = {}


def _score(k: tuple[str, str]) -> tuple[str, str, float, list[tuple[str, str, float]]]:
    m = match_work(_BY_KEY[k[0]], _BY_KEY[k[1]])
    return m.verdict, m.status, round(m.score, 3), [(e.kind, e.detail, e.weight) for e in m.evidence]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("metadata")
    ap.add_argument("--out", default="bench/out/dev_errors.json")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    recs = [r for r in OpenITI(a.metadata).records() if r.author and r.title]
    truth = {r.key: r.work_uri for r in recs}
    blind = [replace(r, work_uri="") for r in recs]  # the matcher never sees the answer
    global _BY_KEY
    _BY_KEY = {r.key: r for r in blind}
    idx = TokenIndex(blind)
    keys: set[tuple[str, str]] = set()
    for r in blind:
        for c in idx.candidates(r, limit=60):
            if c.key != r.key:
                keys.add((r.key, c.key) if r.key < c.key else (c.key, r.key))
    ordered = sorted(keys)
    with Pool(a.workers) as pool:
        pred = dict(zip(ordered, pool.map(_score, ordered, chunksize=500), strict=True))

    by_book: dict[str, list[str]] = defaultdict(list)
    for r in recs:
        by_book[r.work_uri].append(r.key)
    causes: Counter[str] = Counter()
    missed = []
    for ks in by_book.values():
        for i, x in enumerate(ks):
            for y in ks[i + 1 :]:
                k = (x, y) if x < y else (y, x)
                p = pred.get(k)
                if p and p[0] == SAME and p[1] == MATCH:
                    continue
                if p is None:
                    cause, evidence, score = "not-proposed", [], None
                else:
                    verdict, status, score, evidence = p
                    how = {kind: detail.split(":")[0] for kind, detail, _ in reversed(evidence)}
                    cause = f"{verdict}/{status}|title:{how.get('title', '')}|author:{how.get('author', '')}"
                causes[cause] += 1
                left, right = _BY_KEY[k[0]], _BY_KEY[k[1]]
                missed.append(
                    {
                        "cause": cause,
                        "left": [left.title, left.author, left.death],
                        "right": [right.title, right.author, right.death],
                        "score": score,
                        "evidence": evidence,
                    }
                )
    wrong = []
    for k, (verdict, status, score, evidence) in pred.items():
        if verdict == SAME and status == MATCH and truth[k[0]] != truth[k[1]]:
            left, right = _BY_KEY[k[0]], _BY_KEY[k[1]]
            wrong.append(
                {
                    "left": [left.title, left.author, left.death, truth[k[0]]],
                    "right": [right.title, right.author, right.death, truth[k[1]]],
                    "score": score,
                    "evidence": evidence,
                }
            )
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(
        json.dumps({"causes": causes.most_common(), "missed": missed, "wrong": wrong}, ensure_ascii=False),
        "utf-8",
    )
    for cause, n in causes.most_common():
        print(f"{n:6}  {cause}")
    print(f"{len(wrong):6}  pairs called «same work» that OpenITI files under two books", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
