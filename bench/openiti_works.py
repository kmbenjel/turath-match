"""Work-level precision and recall on OpenITI, a public labelled set.

Every OpenITI text version carries a *book URI*, curated by the KITAB team: versions with the same book URI are
the same work, versions with different book URIs are different works. The benchmark hides the URI, lets
turath-match compare every version with the candidates its index proposes, and scores the verdicts:

* a pair predicted «same work» (status match) is a true positive when both versions share the book URI;
* recall counts every same-book pair in the sample, including pairs the index never proposed;
* «related» verdicts (commentary, abridgement …) are checked against OpenITI's own book_relations file when given.

Usage:
  turath-match fetch openiti -o bench/data/openiti.tsv
  python bench/openiti_works.py bench/data/openiti.tsv [--sample 3000] [--seed 7] [--relations rel.json]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

from turath_match.index import TokenIndex
from turath_match.models import MATCH, RELATED, REVIEW, SAME
from turath_match.sources.openiti import OpenITI
from turath_match.work import match_work


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("metadata")
    ap.add_argument("--sample", type=int, default=0, help="number of books (all their versions are kept)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--relations", help="OpenITI book_relations.json (optional)")
    ap.add_argument("--out", default="bench/out/openiti_works.json")
    a = ap.parse_args()

    recs = [r for r in OpenITI(a.metadata).records() if r.author and r.title]
    books = sorted({r.work_uri for r in recs})
    if a.sample and a.sample < len(books):
        keep = set(random.Random(a.seed).sample(books, a.sample))
        recs = [r for r in recs if r.work_uri in keep]
    truth = {r.key: r.work_uri for r in recs}
    blind = [replace(r, work_uri="") for r in recs]  # the matcher never sees the answer
    by_key = {r.key: r for r in blind}

    t0 = time.perf_counter()
    idx = TokenIndex(blind)
    seen: set[tuple[str, str]] = set()
    pred: dict[tuple[str, str], object] = {}
    for r in blind:
        for c in idx.candidates(r, limit=60):
            if c.key == r.key:
                continue
            k = (r.key, c.key) if r.key < c.key else (c.key, r.key)
            if k in seen:
                continue
            seen.add(k)
            pred[k] = match_work(by_key[k[0]], by_key[k[1]])
    secs = time.perf_counter() - t0

    pos = Counter(truth.values())
    n_pos = sum(n * (n - 1) // 2 for n in pos.values())
    tp = fp = rev_pos = rev_neg = rel = 0
    fps, fns_proposed = [], []
    for k, m in pred.items():
        same_book = truth[k[0]] == truth[k[1]]
        if m.verdict == SAME and m.status == MATCH:
            if same_book:
                tp += 1
            else:
                fp += 1
                fps.append((m.left.title, m.left.author[:40], m.right.title, m.right.author[:40], truth[k[0]], truth[k[1]]))
        elif m.status == REVIEW:
            rev_pos += same_book
            rev_neg += not same_book
        elif m.verdict == RELATED:
            rel += 1
            if same_book:
                fns_proposed.append((m.left.title, m.right.title, m.relation))
    related_ok = None
    if a.relations:
        rels = json.loads(Path(a.relations).read_text("utf-8"))
        pairs = {frozenset((x["source"], x["dest"])) for v in rels.values() for x in v}
        hits = [k for k, m in pred.items() if m.verdict == RELATED and frozenset((truth[k[0]], truth[k[1]])) in pairs]
        related_ok = {"related_pairs_in_openiti_relations": len(hits), "related_predicted": rel}
    res = {
        "records": len(recs), "books": len(pos), "pairs_compared": len(pred), "seconds": round(secs, 1),
        "positive_pairs": n_pos, "true_positive": tp, "false_positive": fp,
        "precision": round(tp / max(1, tp + fp), 4), "recall": round(tp / max(1, n_pos), 4),
        "review_same_book": rev_pos, "review_other_book": rev_neg,
        "related_on_same_book": len(fns_proposed), "related": related_ok,
        "evidence_share": round(sum(1 for m in pred.values() if m.evidence) / max(1, len(pred)), 4),
        "false_positive_examples": fps[:40], "related_but_same_book_examples": fns_proposed[:20],
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps({k: v for k, v in res.items() if not k.endswith("examples")}, ensure_ascii=False, indent=1))
    by_coll: dict[str, int] = defaultdict(int)
    for r in recs:
        by_coll[r.extra.get("source_collection") or "other"] += 1
    print("versions by source collection:", dict(sorted(by_coll.items(), key=lambda x: -x[1])[:8]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
