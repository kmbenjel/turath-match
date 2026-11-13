"""A 500-book library against a 9,000-work catalog: how long it takes and how much a person still has to check.

The library is made of 500 OpenITI books, each described the way a collector's file name would describe it: the
title and the author's name of a *secondary* version (another source, other spellings), not the version the
catalog holds. The catalog is every OpenITI book (its primary version). turath-match answers «which of these
9,000 works do I have?»; the answer is checked against OpenITI's book URIs, which the matcher never sees.

Usage: python bench/library500.py bench/data/openiti.tsv [--n 500]
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

from turath_match import reconcile
from turath_match.models import Record
from turath_match.sources.openiti import OpenITI

HAVE = {"have", "have_work", "partial", "other_edition"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("metadata")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--manual-minutes", type=float, default=3.0,
                    help="assumed minutes for one person to check one catalog lookup by hand")
    ap.add_argument("--out", default="bench/out/library500.json")
    a = ap.parse_args()

    by_book: dict[str, list[Record]] = defaultdict(list)
    for r in OpenITI(a.metadata).records():
        if r.author and r.title:
            by_book[r.work_uri].append(r)
    prim = {b: next((r for r in rs if r.extra.get("status") == "pri"), rs[0]) for b, rs in by_book.items()}
    multi = sorted(b for b, rs in by_book.items() if len(rs) > 1)
    chosen = random.Random(a.seed).sample(multi, a.n)
    lib = []
    for i, b in enumerate(chosen):
        sec = next(r for r in by_book[b] if r is not prim[b])
        lib.append(Record("library", f"L{i:04d}", sec.title.split(" = ")[0], sec.author.split(" ؛ ")[0]))
    targets = [replace(r, scheme="catalog", work_uri="", extra={"book": b}) for b, r in prim.items()]

    t0 = time.perf_counter()
    rec = reconcile(lib, targets)
    secs = time.perf_counter() - t0

    have_truth = set(chosen)
    c = Counter(t.status for t in rec.targets)
    tp = sum(1 for t in rec.targets if t.status in HAVE and t.target.extra["book"] in have_truth)
    fp = sum(1 for t in rec.targets if t.status in HAVE and t.target.extra["book"] not in have_truth)
    review_true = sum(1 for t in rec.targets if t.status == "review" and t.target.extra["book"] in have_truth)
    review = c["review"]
    decided = len(have_truth) - review_true
    res = {
        "library_books": len(lib), "catalog_works": len(targets), "seconds": round(secs, 1),
        "statuses": dict(c), "found": tp, "wrongly_found": fp,
        "precision": round(tp / max(1, tp + fp), 4), "recall": round(tp / len(have_truth), 4),
        "on_review_list": review, "review_items_that_are_in_the_library": review_true,
        "matches_with_evidence": round(sum(1 for m in rec.matches if m.evidence) / max(1, len(rec.matches)), 4),
        "manual_minutes_per_book_assumed": a.manual_minutes,
        "manual_hours_for_the_library": round(len(lib) * a.manual_minutes / 60, 1),
        "person_hours_left_with_turath_match": round(review * a.manual_minutes / 60, 1),
        "decided_without_a_person": decided,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
