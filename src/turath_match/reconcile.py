"""Reconciliation: the library against the catalogs, and the missing works against the copy sources.

For every *target* (a record of a catalog or a wish list) the result says one of:

``have``           the work is in the library and the edition is proven (exact file size, or editor+publisher)
``partial``        the same edition, with some of its volumes
``have_work``      the work is in the library; nothing says which edition it is
``other_edition``  the work is in the library in another edition
``related_only``   the library holds only a commentary, abridgement, selection … of it
``review``         a possible match that the evidence cannot settle: a person decides
``missing``        not in the library

and, for what is missing or held in another edition, where trustworthy copies are (with exact sizes).
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .edition import MIN_PROOF_SIZE, match_edition
from .index import TokenIndex
from .models import (
    DIFFERENT,
    EXACT_SIZE,
    MANUAL,
    MATCH,
    RELATED,
    REVIEW,
    SAME,
    UNCERTAIN,
    Evidence,
    Match,
    Record,
)
from .provenance import SizeIndex, trace
from .text import work_id
from .work import match_work

STATUSES = ("have", "partial", "have_work", "other_edition", "related_only", "review", "missing")
SOURCE_TRUST = {"archive": 3, "waqfeya": 2, "shamela": 2, "openiti": 1, "csv": 1}


@dataclass
class Copy:
    record: Record
    match: Match
    edition: Match | None
    rank: float

    def to_dict(self) -> dict[str, Any]:
        r = self.record
        return {
            "scheme": r.scheme,
            "id": r.id,
            "title": r.title,
            "author": r.author,
            "url": r.url,
            "files": [f.to_dict() for f in r.files],
            "work_score": round(self.match.score, 3),
            "same_edition": bool(self.edition and self.edition.verdict == SAME),
            "rank": round(self.rank, 3),
        }


def wants_edition(t: Record) -> bool:
    """A target that names an editor, a publisher, a year or files asks for an edition, not only the work."""
    return bool(t.editor or t.publisher or t.year or t.files)


NEEDS_COPY = ("missing", "other_edition", "related_only", "review", "have_work")


@dataclass
class TargetStatus:
    target: Record
    status: str
    work: Match | None = None  # the best work-level match in the library
    edition: Match | None = None
    files: list[Match] = field(default_factory=list)
    related: list[Match] = field(default_factory=list)
    copies: list[Copy] = field(default_factory=list)
    provenance: list[Match] = field(default_factory=list)  # the library book's files traced to source files

    @property
    def library(self) -> Record | None:
        if self.work and self.work.verdict in (SAME, UNCERTAIN):
            return self.work.right
        return self.files[0].right if self.files else None


@dataclass
class Reconciliation:
    targets: list[TargetStatus]
    library: list[Record]
    matches: list[Match]
    unidentified: list[Record]
    clusters: list[dict[str, Any]] = field(default_factory=list)
    identified_by_bytes: list[Match] = field(default_factory=list)  # library files known only by exact size

    def counts(self) -> dict[str, int]:
        c = dict.fromkeys(STATUSES, 0)
        for t in self.targets:
            c[t.status] += 1
        return c

    def review(self) -> list[Match]:
        return [m for m in self.matches if m.status == REVIEW]

    # ---- output -------------------------------------------------------------------------------------------
    def write(self, out: str | Path) -> dict[str, Path]:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        paths = {
            k: out / v
            for k, v in (
                ("matches", "matches.jsonl"),
                ("status", "status.tsv"),
                ("review", "review.tsv"),
                ("copies", "copies.tsv"),
                ("crosswalk", "crosswalk.jsonl"),
            )
        }
        with paths["matches"].open("w", encoding="utf-8") as fh:
            for m in self.matches:
                fh.write(json.dumps(m.to_dict(), ensure_ascii=False) + "\n")
        with paths["status"].open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(
                [
                    "target",
                    "title",
                    "author",
                    "status",
                    "confidence",
                    "library_id",
                    "library_title",
                    "method",
                    "evidence",
                ]
            )
            for t in self.targets:
                best: Match | None = t.edition or t.work or (t.files[0] if t.files else None)
                lib = t.library
                w.writerow(
                    [
                        t.target.key,
                        t.target.title,
                        t.target.author,
                        t.status,
                        best.confidence if best else "",
                        lib.id if lib else "",
                        lib.title if lib else "",
                        best.method if best else "",
                        " | ".join(e.detail for e in (best.evidence if best else [])),
                    ]
                )
        with paths["review"].open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(
                [
                    "left",
                    "right",
                    "level",
                    "score",
                    "left_title",
                    "left_author",
                    "right_title",
                    "right_author",
                    "why",
                    "decision",
                ]
            )
            for m in self.review():
                w.writerow(
                    [
                        m.left.key,
                        m.right.key,
                        m.level,
                        f"{m.score:.2f}",
                        m.left.title,
                        m.left.author,
                        m.right.title,
                        m.right.author,
                        " | ".join(e.detail for e in m.evidence),
                        "",
                    ]
                )
        with paths["copies"].open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(
                ["target", "title", "status", "copy", "copy_title", "same_edition", "files", "bytes", "url"]
            )
            for t in self.targets:
                for c in t.copies:
                    sizes = [f.size for f in c.record.files if f.size]
                    w.writerow(
                        [
                            t.target.key,
                            t.target.title,
                            t.status,
                            c.record.key,
                            c.record.title,
                            "yes" if c.edition and c.edition.verdict == SAME else "",
                            len(c.record.files),
                            sum(sizes) if sizes else "",
                            c.record.url,
                        ]
                    )
        with paths["crosswalk"].open("w", encoding="utf-8") as fh:
            for cl in self.clusters:
                fh.write(json.dumps(cl, ensure_ascii=False) + "\n")
        return paths


def load_decisions(path: str | Path) -> dict[tuple[str, str], str]:
    """A filled-in review.tsv (or any TSV with left, right, decision): same | different | related."""
    out: dict[tuple[str, str], str] = {}
    with Path(path).open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            d = (row.get("decision") or "").strip().lower()
            if d in ("same", "different", "related", "yes", "no"):
                d = {"yes": "same", "no": "different"}.get(d, d)
                out[(row["left"], row["right"])] = d
                out[(row["right"], row["left"])] = d
    return out


def _decided(a: Record, b: Record, verdict: str) -> Match:
    v = {"same": SAME, "different": DIFFERENT, "related": RELATED}[verdict]
    return Match(a, b, "work", v, 1.0, MANUAL, [Evidence("manual", f"decided by a person: {verdict}", 1.0)])


class _Matcher:
    def __init__(self, decisions: dict[tuple[str, str], str] | None):
        self.decisions = decisions or {}
        self.cache: dict[tuple[str, str], Match] = {}

    def work(self, a: Record, b: Record) -> Match:
        k = (a.key, b.key)
        if k not in self.cache:
            d = self.decisions.get(k)
            m = _decided(a, b, d) if d else match_work(a, b)
            for r in (a, b):
                if r.extra.get("author_from"):
                    m.evidence.append(
                        Evidence(
                            "author",
                            f"the author of {r.key} is read from {r.extra['author_from']}, "
                            "the source of its file (exact size)",
                            0.0,
                        )
                    )
            self.cache[k] = m
        return self.cache[k]


def _best(ms: list[Match]) -> Match | None:
    order = {SAME: 3, UNCERTAIN: 2, RELATED: 1, DIFFERENT: 0}
    return max(ms, key=lambda m: (order[m.verdict], m.score)) if ms else None


def _cluster_id(title: str, author: str) -> str:
    return work_id(title, author)


def build_clusters(records: dict[str, Record], pairs: Iterable[Match]) -> list[dict[str, Any]]:
    parent: dict[str, str] = {k: k for k in records}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for m in pairs:
        if m.level == "work" and m.status == MATCH and m.left.key in parent and m.right.key in parent:
            parent[find(m.left.key)] = find(m.right.key)
    groups: dict[str, list[Record]] = defaultdict(list)
    for k, r in records.items():
        groups[find(k)].append(r)
    out = []
    for members in groups.values():
        if len(members) < 2:
            continue
        best = max(members, key=lambda r: (bool(r.author), r.death is not None, len(r.title)))
        uri = next((r.work_uri for r in members if r.work_uri), "")
        ext = sorted({f"{r.scheme}:{r.id}" for r in members if r.scheme != "library"})
        out.append(
            {
                "cluster_id": _cluster_id(best.title, best.author),
                "title_ar": best.title,
                "author_ar": best.author,
                "death_ah": next((r.death for r in members if r.death), None),
                "openiti_uri": uri,
                "ext_ids": ";".join(ext),
                "members": [
                    {
                        "scheme": r.scheme,
                        "id": r.id,
                        "url": r.url,
                        "editors": r.editor,
                        "publisher": r.publisher,
                        "place": r.place,
                        "year": r.year,
                        "volumes": r.volumes,
                        "size_bytes": r.total_size,
                        "files": [f.to_dict() for f in r.files if f.size],
                    }
                    for r in members
                ],
            }
        )
    return out


def reconcile(
    library: Iterable[Record],
    targets: Iterable[Record],
    copies: Iterable[Record] = (),
    *,
    decisions: dict[tuple[str, str], str] | None = None,
    online: Any = None,
    max_copies: int = 5,
) -> Reconciliation:
    """Reconcile ``library`` with ``targets``; look for copies of what is missing in ``copies`` (and ``online``,
    an :class:`~turath_match.sources.ArchiveOrg`, when given)."""
    raw_lib = list(library)
    tgts = list(targets)
    copy_recs = list(copies)
    mt = _Matcher(decisions)
    # file-level provenance first: a library file of exactly the size of a source file *is* that file
    prov: dict[str, list[Match]] = defaultdict(list)
    for m in trace(raw_lib, SizeIndex([*copy_recs, *tgts])):
        if m.verdict == SAME and m.score >= 0.8:
            prov[m.left.key].append(m)
    src = {r.key: r for r in [*copy_recs, *tgts]}
    lib = []
    for r in raw_lib:
        ms = prov.get(r.key, [])
        if not r.author and ms and src[ms[0].right.key].author:  # the source's record names the author
            r = Record(
                **{
                    **r.__dict__,
                    "author": src[ms[0].right.key].author,
                    "extra": {**r.extra, "author_from": ms[0].right.key},
                }
            )
        lib.append(r)
    lib_index = TokenIndex(lib)
    # copies come from the copy sources, and from targets that carry files of their own
    copy_index = TokenIndex([*copy_recs, *(t for t in tgts if t.files)])
    lib_sizes: dict[int, list[tuple[Record, Any]]] = defaultdict(list)
    for r in lib:
        for f in r.files:
            if f.size and f.size >= MIN_PROOF_SIZE:
                lib_sizes[f.size].append((r, f))

    all_matches: list[Match] = []
    statuses: list[TargetStatus] = []
    matched_lib: set[str] = set()
    touched: set[str] = set()  # library books with any work-level link (same, uncertain, related)
    for t in tgts:
        # byte-level presence: a library file of exactly this record's size, whatever it is called
        fmatches = []
        for f in t.files:
            for lr, lf in lib_sizes.get(f.size or -1, []):
                ev = [Evidence("size", f"{lf.name} and {f.name} are both {f.size:,} bytes", 0.9)]
                fmatches.append(
                    Match(
                        t,
                        Record(lr.scheme, lr.id, lr.title, lr.author, files=[lf], url=lr.url),
                        "file",
                        SAME,
                        0.95,
                        EXACT_SIZE,
                        ev,
                    )
                )
        works = [mt.work(t, c) for c in lib_index.candidates(t)]
        same = sorted((m for m in works if m.verdict == SAME), key=lambda m: -m.score)
        related = [m for m in works if m.verdict == RELATED]
        best = _best([m for m in works if m.verdict != DIFFERENT])
        st = TargetStatus(t, "missing", best, files=fmatches, related=related)
        if fmatches:
            lr = fmatches[0].right
            st.status = "have"
            n = len({fm.left.files[0].name for fm in fmatches if fm.left.files})
            if len(t.files) > 1 and n < len(t.files):
                st.status = "partial"
            full = next((r for r in lib if r.key == lr.key), lr)
            st.edition = match_edition(full, t)
            matched_lib.add(lr.key)
        elif same and same[0].status == MATCH:
            eds = []
            for m in same:
                if m.status != MATCH:
                    continue
                eds.append(match_edition(m.right, t))
                for pm in prov.get(m.right.key, []):  # the edition of the file's source record
                    e2 = match_edition(src[pm.right.key], t)
                    e2.left = m.right
                    e2.evidence.insert(
                        0, Evidence("size", f"the library file is {pm.right.key} (exact size)", 0.0)
                    )
                    eds.append(e2)
            ed = max(eds, key=lambda e: ({SAME: 2, UNCERTAIN: 1, DIFFERENT: 0}[e.verdict], e.score))
            st.work = next(m for m in same if m.right.key == ed.left.key)
            st.edition = ed if wants_edition(t) or ed.verdict == SAME else None
            if not wants_edition(t) and ed.verdict != DIFFERENT:
                st.status = "have"  # the work was asked for, not an edition
            elif ed.verdict == SAME and ed.status == MATCH:
                st.status = "partial" if ed.relation == "part" else "have"
            elif ed.verdict == DIFFERENT:
                st.status = "other_edition"
            else:
                st.status = "have_work"
            matched_lib.add(st.work.right.key)
        elif best is not None and best.status == REVIEW:
            st.status = "review"
        elif related:
            st.status = "related_only"
        all_matches.extend(m for m in works if m.verdict != DIFFERENT or m.method == MANUAL)
        all_matches.extend(fmatches)
        if st.edition is not None:
            all_matches.append(st.edition)
        lib_rec = st.library
        if lib_rec is not None:
            st.provenance = prov.get(lib_rec.key, [])
            all_matches.extend(st.provenance)
        for m in works:
            if m.verdict in (SAME, UNCERTAIN, RELATED):
                touched.add(m.right.key)
        # every target is linked to its copies (the crosswalk needs them); the report shows them where needed
        st.copies = find_copies(
            t, copy_index, mt, online=online if st.status == "missing" else None, limit=max_copies
        )
        all_matches.extend(c.match for c in st.copies)
        statuses.append(st)
    by_bytes: list[Match] = []
    for r in lib:  # a book that is on no list can still be told by its bytes
        if r.key not in matched_lib and r.key not in touched and prov.get(r.key):
            by_bytes.extend(prov[r.key])
    all_matches.extend(by_bytes)
    unidentified = [
        r for r in lib if r.key not in matched_lib and r.key not in touched and not prov.get(r.key)
    ]
    recs = {r.key: r for r in [*lib, *tgts, *copy_recs]}
    for st in statuses:
        for c in st.copies:
            recs.setdefault(c.record.key, c.record)
    clusters = build_clusters(recs, all_matches)
    return Reconciliation(statuses, lib, all_matches, unidentified, clusters, by_bytes)


def find_copies(
    t: Record, index: TokenIndex, mt: _Matcher, *, online: Any = None, limit: int = 5
) -> list[Copy]:
    """Records of the same work that carry files (or a text), best first: the same edition, a known exact
    size, a source that publishes checksums."""
    cands = [c for c in index.candidates(t) if c.key != t.key]
    if online is not None:
        try:
            cands += online.search(
                t.title.split(" - ")[0], t.author.split("؛")[0].split()[-1] if t.author else ""
            )
        except Exception as e:  # network trouble never breaks a report
            t.extra.setdefault("warnings", []).append(f"online search failed: {e}")
    out: list[Copy] = []
    seen: set[str] = set()
    for c in cands:
        if c.key in seen or not (c.files or c.url):
            continue
        seen.add(c.key)
        m = mt.work(t, c)
        if m.verdict != SAME or m.status != MATCH:
            continue
        ed = match_edition(c, t) if (t.editor or t.publisher or t.files) else None
        sized = sum(1 for f in c.files if f.size)
        rank = (
            m.score
            + 0.3 * bool(ed and ed.verdict == SAME)
            - 0.3 * bool(ed and ed.verdict == DIFFERENT)
            + 0.1 * SOURCE_TRUST.get(c.scheme, 0)
            + 0.1 * bool(sized)
            + 0.05 * any(f.md5 or f.sha1 for f in c.files)
        )
        out.append(Copy(c, m, ed, rank))
    out.sort(key=lambda c: -c.rank)
    return out[:limit]
