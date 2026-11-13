"""Head-to-head on the OpenITI work set: OpenRefine's clustering against turath-match.

OpenRefine (https://openrefine.org) is the standard tool for reconciling and de-duplicating catalog records. Its
key-collision clusterers (fingerprint, n-gram fingerprint) and nearest-neighbour clusterer (Levenshtein) are run
here through its own HTTP API, on exactly the records ``openiti_works.py`` scores, and judged by the same rule:
two records predicted to be one work are right when OpenITI files them under the same book URI.

A running OpenRefine is needed (bench/compare.sh starts one):
  ./openrefine-3.10.1/refine -i 127.0.0.1 -p 3333 -d /tmp/or-work &
  python bench/openrefine_compare.py bench/data/openiti.tsv --url http://127.0.0.1:3333
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from turath_match.sources.openiti import OpenITI

CLUSTERERS = {
    "fingerprint": {"type": "binning", "function": "fingerprint", "params": {}},
    "ngram-fingerprint (2)": {
        "type": "binning",
        "function": "ngram-fingerprint",
        "params": {"ngram-size": 2},
    },
    "levenshtein (radius 2)": {
        "type": "knn",
        "function": "levenshtein",
        "params": {"radius": 2, "blocking-ngram-size": 6},
    },
}


class Refine:
    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def _req(self, path: str, data: bytes | None = None, ctype: str | None = None) -> bytes:
        req = urllib.request.Request(self.url + path, data=data)
        if ctype:
            req.add_header("Content-Type", ctype)
        with urllib.request.urlopen(req, timeout=3600) as r:
            return bytes(r.read())

    def token(self) -> str:
        return str(json.loads(self._req("/command/core/get-csrf-token"))["token"])

    def create(self, name: str, tsv: str) -> str:
        b = uuid.uuid4().hex
        opts = json.dumps(
            {"separator": "\t", "headerLines": 1, "guessCellValueTypes": False, "encoding": "UTF-8"}
        )
        parts = []
        for k, v in (("project-name", name), ("format", "text/line-based/*sv"), ("options", opts)):
            parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        parts.append(
            f'--{b}\r\nContent-Disposition: form-data; name="project-file"; filename="d.tsv"\r\n'
            f"Content-Type: text/tab-separated-values\r\n\r\n".encode()
            + tsv.encode("utf-8")
            + b"\r\n"
        )
        parts.append(f"--{b}--\r\n".encode())
        req = urllib.request.Request(
            f"{self.url}/command/core/create-project-from-upload?csrf_token={self.token()}",
            data=b"".join(parts),
        )
        req.add_header("Content-Type", f"multipart/form-data; boundary={b}")

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        try:
            r = opener.open(req, timeout=600)
            loc = r.headers.get("Location", "") or r.url
        except urllib.error.HTTPError as e:  # the 302 lands here
            loc = e.headers.get("Location", "")
        return urllib.parse.parse_qs(urllib.parse.urlsplit(loc).query)["project"][0]

    def clusters(self, project: str, column: str, clusterer: dict) -> list[list[str]]:
        body = urllib.parse.urlencode(
            {
                "engine": json.dumps({"facets": [], "mode": "row-based"}),
                "clusterer": json.dumps({**clusterer, "column": column}),
            }
        ).encode()
        out = json.loads(
            self._req(
                f"/command/core/compute-clusters?project={project}&csrf_token={self.token()}",
                body,
                "application/x-www-form-urlencoded",
            )
        )
        return [[c["v"] for c in cl] for cl in out]


def score(groups: list[list[int]], truth: list[str]) -> dict[str, float]:
    pos = Counter(truth)
    n_pos = sum(n * (n - 1) // 2 for n in pos.values())
    tp = fp = 0
    for g in groups:
        for i, j in combinations(g, 2):
            if truth[i] == truth[j]:
                tp += 1
            else:
                fp += 1
    return {
        "true_positive": tp,
        "false_positive": fp,
        "precision": round(tp / max(1, tp + fp), 4),
        "recall": round(tp / max(1, n_pos), 4),
        "positive_pairs": n_pos,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("metadata")
    ap.add_argument("--url", default="http://127.0.0.1:3333")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="bench/out/openrefine_compare.json")
    ap.add_argument(
        "--slow",
        action="store_true",
        help="also run Levenshtein on the title + author column (no result after 20 minutes on the full set)",
    )
    ap.add_argument(
        "--baseline-only",
        action="store_true",
        help="only the exact-equality baseline (identical title, identical title + author): no OpenRefine needed",
    )
    a = ap.parse_args()
    recs = [r for r in OpenITI(a.metadata).records() if r.author and r.title]
    if a.sample:
        books = sorted({r.work_uri for r in recs})
        keep = set(random.Random(a.seed).sample(books, min(a.sample, len(books))))
        recs = [r for r in recs if r.work_uri in keep]
    truth = [r.work_uri for r in recs]
    clean = lambda s: " ".join(s.replace("\t", " ").split())  # noqa: E731
    keys = {
        "title": [clean(r.title.split(" = ")[0]) for r in recs],
        "title + author": [clean(r.title.split(" = ")[0] + " | " + r.author.split(" ؛ ")[0]) for r in recs],
    }
    tsv = "title\ttitle_author\n" + "".join(
        f"{t}\t{ta}\n" for t, ta in zip(keys["title"], keys["title + author"], strict=True)
    )
    res: dict[str, dict] = {"records": len(recs), "books": len(set(truth))}
    for name, vals in keys.items():  # the baseline: records whose value is character for character the same
        by_val: dict[str, list[int]] = defaultdict(list)
        for i, v in enumerate(vals):
            by_val[v].append(i)
        res[f"{name} | identical values"] = score([ids for ids in by_val.values() if len(ids) > 1], truth)
    if a.baseline_only:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    rf = Refine(a.url)
    pid = rf.create(f"openiti-{int(time.time())}", tsv)
    res["openrefine"] = a.url  # type: ignore[assignment]
    for col, name in (("title", "title"), ("title_author", "title + author")):
        vals = keys[name]
        for cname, cl in CLUSTERERS.items():
            if cl["type"] == "knn" and name == "title + author" and not a.slow:
                res["note"] = (
                    f"{name} | {cname} not run: no result after 20 minutes on the full set (--slow runs it)"
                )
                continue
            t0 = time.perf_counter()
            clusters = rf.clusters(pid, col, cl)
            secs = time.perf_counter() - t0
            # a user merges each cluster into one value: every record of every value in it becomes one group
            merged: dict[str, int] = {}
            for k, cluster in enumerate(clusters):
                for v in cluster:
                    merged[v] = k
            groups: dict[object, list[int]] = defaultdict(list)
            for i, v in enumerate(vals):
                groups[merged.get(v, ("v", v))].append(i)
            res[f"{name} | {cname}"] = {
                **score([g for g in groups.values() if len(g) > 1], truth),
                "clusters": len(clusters),
                "seconds": round(secs, 1),
            }
            print(name, cname, res[f"{name} | {cname}"], flush=True)
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(
                json.dumps(res, ensure_ascii=False, indent=1), "utf-8"
            )  # partial results survive
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
