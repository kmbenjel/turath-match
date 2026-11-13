"""Held-out check: Wikidata's records of Arabic books against OpenITI, labelled by the Shamela id both carry.

The matching rules were developed on OpenITI release 2025.1.9 (benchmarks 1, 3 and 4 in docs/benchmarks.md all
draw on it). This benchmark puts on one side records the rules never saw: the Arabic label of a Wikidata book item
and the Arabic label of its author, as Wikidata's editors wrote them. The other side is the same OpenITI release.

Labelling, automatic and stated: a Wikidata item carries a Shamela book edition id (P12239); an OpenITI version
made from that Shamela book carries the same id in its URI (``…Shamela0001681-ara1``). The item and every version
of that OpenITI book are one work; the item and the versions of every other book are not. Items whose Shamela id
is in no OpenITI version URI, or in versions of two books, are left out: their answer is not known. The matcher
sees titles and author names only, never the ids or the URIs.

Many of these Wikidata labels were entered from the Shamela card, so the version made from that very Shamela book
often carries the same title. The result is also given without those pairs («other sources»): the item against
the versions of the same work that OpenITI took from another source or another Shamela book.

Usage: python bench/wikidata_heldout.py bench/data/openiti.tsv [--wikidata bench/data/wikidata_shamela_books.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

from turath_match.index import TokenIndex
from turath_match.models import MATCH, REVIEW, SAME, Record
from turath_match.sources.openiti import OpenITI
from turath_match.text import search_key
from turath_match.work import match_work

SPARQL = "https://query.wikidata.org/sparql"
QUERY = """SELECT ?item ?sid ?label ?authorLabel WHERE {
  ?item wdt:P12239 ?sid ; rdfs:label ?label . FILTER(LANG(?label) = "ar")
  OPTIONAL { ?item wdt:P50 ?a1 . ?a1 rdfs:label ?l1 . FILTER(LANG(?l1) = "ar") }
  OPTIONAL { ?item wdt:P629 ?work . ?work wdt:P50 ?a2 . ?a2 rdfs:label ?l2 . FILTER(LANG(?l2) = "ar") }
  BIND(COALESCE(?l1, ?l2) AS ?authorLabel)
}"""
UA = "turath-match-bench/0.1 (https://github.com/kmbenjel/turath-match)"

_BY_KEY: dict[str, Record] = {}


def _score(k: tuple[str, str]):
    return match_work(_BY_KEY[k[0]], _BY_KEY[k[1]])


def fetch_wikidata(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        url = SPARQL + "?" + urllib.parse.urlencode({"query": QUERY, "format": "json"})
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"}
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            rows = json.loads(r.read())["results"]["bindings"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "query": QUERY,
                    "fetched": time.strftime("%Y-%m-%d"),
                    "rows": [{k: v["value"] for k, v in row.items()} for row in rows],
                },
                ensure_ascii=False,
            ),
            "utf-8",
        )
    return list(json.loads(path.read_text("utf-8"))["rows"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("metadata")
    ap.add_argument("--wikidata", default="bench/data/wikidata_shamela_books.json")
    ap.add_argument("--out", default="bench/out/wikidata_heldout.json")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    oi = [r for r in OpenITI(a.metadata).records() if r.author and r.title]
    books_of_sid: dict[int, set[str]] = defaultdict(set)
    for r in oi:
        if r.extra.get("source_collection") == "Shamela" and r.extra.get("source_id", "").isdigit():
            books_of_sid[int(r.extra["source_id"])].add(r.work_uri)

    items: dict[str, dict] = {}
    for row in fetch_wikidata(Path(a.wikidata)):
        if not row.get("sid", "").isdigit():
            continue
        it = items.setdefault(row["item"], {"sid": int(row["sid"]), "label": row["label"], "authors": []})
        if row.get("authorLabel") and row["authorLabel"] not in it["authors"]:
            it["authors"].append(row["authorLabel"])
    skipped = Counter()
    queries: list[Record] = []
    truth: dict[str, str] = {}
    for qid, it in sorted(items.items()):
        books = books_of_sid.get(it["sid"], set())
        if not it["authors"]:
            skipped["no Arabic author label"] += 1
        elif not books:
            skipped["Shamela id in no OpenITI version"] += 1
        elif len(books) > 1:
            skipped["Shamela id in versions of two OpenITI books"] += 1
        else:
            q = Record("wikidata", qid.rsplit("/", 1)[-1], it["label"], " ؛ ".join(it["authors"]))
            q.extra["sid"] = it["sid"]
            queries.append(q)
            truth[q.key] = next(iter(books))
    for r in oi:
        truth[r.key] = r.work_uri
    blind = [replace(r, work_uri="") for r in oi]
    global _BY_KEY
    _BY_KEY = {r.key: r for r in blind + queries}
    keys_of_sid: dict[int, list[str]] = defaultdict(list)
    for r in oi:
        if r.extra.get("source_collection") == "Shamela" and r.extra.get("source_id", "").isdigit():
            keys_of_sid[int(r.extra["source_id"])].append(r.key)
    same_source = {(q.key, k) for q in queries for k in keys_of_sid[q.extra["sid"]]}

    t0 = time.perf_counter()
    idx = TokenIndex(blind)
    keys = sorted({(q.key, c.key) for q in queries for c in idx.candidates(q, limit=60)})
    with Pool(a.workers) as pool:
        pred = dict(zip(keys, pool.map(_score, keys, chunksize=200), strict=True))
    secs = time.perf_counter() - t0

    versions_of: Counter = Counter(r.work_uri for r in oi)

    def tally(include_same_source: bool) -> dict[str, float | int]:
        n_pos = sum(versions_of[truth[q.key]] for q in queries)
        if not include_same_source:
            n_pos -= sum(1 for q in queries for k in same_source if k[0] == q.key)
        tp = fp = rev_pos = rev_neg = 0
        for k, m in pred.items():
            if not include_same_source and k in same_source:
                continue
            same = truth[k[0]] == truth[k[1]]
            if m.verdict == SAME and m.status == MATCH:
                tp += same
                fp += not same
            elif m.status == REVIEW:
                rev_pos += same
                rev_neg += not same
        return {
            "positive_pairs": n_pos,
            "true_positive": tp,
            "false_positive": fp,
            "precision": round(tp / max(1, tp + fp), 4),
            "recall": round(tp / max(1, n_pos), 4),
            "review_same_work": rev_pos,
            "review_other_work": rev_neg,
        }

    oi_by_key = {r.key: r for r in oi}
    identical = sum(
        1
        for q in queries
        if any(
            search_key(q.title) == search_key(t)
            for k in same_source
            if k[0] == q.key
            for t in oi_by_key[k[1]].title.split(" = ")
        )
    )
    res = {
        "wikidata_items_with_a_shamela_id": len(items),
        "left_out": dict(skipped),
        "queries": len(queries),
        "openiti_versions": len(oi),
        "pairs_compared": len(pred),
        "seconds": round(secs, 1),
        "queries_whose_title_is_that_of_the_same_shamela_version": identical,
        "all_pairs": tally(True),
        "other_sources": tally(False),
        "evidence_share": round(sum(1 for m in pred.values() if m.evidence) / max(1, len(pred)), 4),
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
