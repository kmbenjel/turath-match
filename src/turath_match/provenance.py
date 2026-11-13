"""File-level provenance: which source file is this local file, byte for byte?

Scanned PDFs are large and their exact byte sizes almost never collide, so a local file whose size equals one
source file (an archive.org file, a Shamela PDF) is that file. When several source files share the size, the
one whose record also matches the book's title wins, and the match is flagged as ambiguous. When the source
publishes a checksum (archive.org gives md5 and sha1), ``verify=True`` reads the local file and proves it.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from .edition import MIN_PROOF_SIZE
from .models import DIFFERENT, EXACT_SIZE, HASH, SAME, Evidence, FileRef, Match, Record
from .work import match_work


class SizeIndex:
    """size in bytes -> [(record, file)] over every file of every source record."""

    def __init__(self, records: Iterable[Record]):
        self.by_size: dict[int, list[tuple[Record, FileRef]]] = defaultdict(list)
        for r in records:
            for f in r.files:
                if f.size and f.size > 0:
                    self.by_size[f.size].append((r, f))

    def __len__(self) -> int:
        return sum(len(v) for v in self.by_size.values())

    def lookup(self, size: int | None) -> list[tuple[Record, FileRef]]:
        return list(self.by_size.get(size or -1, []))


def _hash_file(path: str, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def trace(library: Iterable[Record], index: SizeIndex, *, verify: bool = False) -> list[Match]:
    """One file-level match per library file that has a same-size source file."""
    out: list[Match] = []
    for lib in library:
        votes: dict[str, int] = defaultdict(int)  # source record -> how many of this book's files it holds
        for f in lib.files:
            c = index.lookup(f.size)
            if len(c) == 1:
                votes[c[0][0].key] += 1
        for f in lib.files:
            cands = index.lookup(f.size)
            if not cands:
                continue
            ev: list[Evidence] = []
            if len(cands) == 1:
                rec, sf = cands[0]
                kind = "unique"
            else:

                def rank(
                    c: tuple[Record, FileRef], lib: Record = lib, votes: dict = votes
                ) -> tuple[int, float]:
                    m = match_work(lib, c[0])
                    return votes.get(c[0].key, 0), m.score if m.verdict == SAME else 0.0

                rec, sf = max(cands, key=rank)
                kind = f"ambiguous-{len(cands)}"
                ev.append(
                    Evidence(
                        "size",
                        f"{len(cands)} source files share this size; chosen by title and siblings",
                        -0.2,
                    )
                )
            size = f.size or 0
            strong = size >= MIN_PROOF_SIZE
            ev.insert(
                0,
                Evidence(
                    "size", f"{f.name} and {sf.name} are both {size:,} bytes ({kind})", 0.9 if strong else 0.3
                ),
            )
            if votes.get(rec.key, 0) > 1:
                ev.append(
                    Evidence("size", f"{votes[rec.key]} files of this book are files of {rec.key}", 0.1)
                )
            score = (0.95 if strong else 0.5) - (0.15 if len(cands) > 1 else 0.0)
            method, verdict = EXACT_SIZE, SAME
            if verify and f.path and Path(f.path).is_file() and (sf.md5 or sf.sha1):
                algo, want = ("md5", sf.md5) if sf.md5 else ("sha1", sf.sha1)
                got = _hash_file(f.path, algo)
                if got == want:
                    ev.append(Evidence("hash", f"{algo} {got} equals the source's", 1.0))
                    method, score = HASH, 1.0
                else:
                    ev.append(
                        Evidence("hash", f"{algo} differs from the source's: same size, other bytes", -1.0)
                    )
                    verdict, score = DIFFERENT, 0.95
            single = Record(lib.scheme, lib.id, lib.title, lib.author, files=[f], url=lib.url)
            target = Record(rec.scheme, rec.id, rec.title, rec.author, files=[sf], url=sf.url or rec.url)
            out.append(Match(single, target, "file", verdict, score, method, ev))
    return out
