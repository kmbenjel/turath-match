"""Duplicate proof by size plus sampled bytes.

Two files are candidates only when their sizes are equal. A candidate pair is a duplicate when five 64 KB
windows agree: the start, 25 %, 50 %, 75 % and the end. That reads 320 KB per file instead of the whole file,
so it works over slow links (FTP, SFTP, a phone) where checksums are not available; ``deep=True`` adds a full
SHA-256 for the final proof. A file that cannot be read gets its own fingerprint and is never called a duplicate.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

WINDOW = 64 * 1024
FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)

Reader = Callable[[str, int, int], bytes]


def local_reader(path: str, offset: int, length: int) -> bytes:
    with open(path, "rb") as fh:
        fh.seek(offset)
        return fh.read(length)


def windows(size: int, window: int = WINDOW) -> list[int]:
    """Offsets of the sampled windows (deduplicated for small files)."""
    if size <= window:
        return [0]
    offs = []
    for fr in FRACTIONS:
        o = size - window if fr == 1.0 else int((size - window) * fr)
        if o not in offs:
            offs.append(o)
    return offs


def fingerprint(path: str, size: int, reader: Reader = local_reader, window: int = WINDOW) -> str:
    """sha1 over the sampled windows; «error:<…>» (unique to the path) when a read fails or comes back short."""
    h = hashlib.sha1(str(size).encode())
    try:
        for off in windows(size, window):
            want = min(window, size - off)
            b = reader(path, off, want)
            if len(b) != want:
                raise OSError(f"short read at {off}")
            h.update(b"|" + b)
    except OSError as e:
        return "error:" + hashlib.sha1(f"{path}|{e}".encode()).hexdigest()
    return h.hexdigest()


def full_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class DuplicateGroup:
    size: int
    fingerprint: str
    paths: list[str] = field(default_factory=list)
    method: str = "sampled_bytes"  # or "hash" after deep=True

    def to_dict(self) -> dict[str, object]:
        return {
            "size": self.size,
            "fingerprint": self.fingerprint,
            "method": self.method,
            "paths": self.paths,
        }


def find_duplicates(
    entries: Iterable[tuple[str, int]],
    reader: Reader = local_reader,
    *,
    deep: bool = False,
    workers: int = 4,
) -> list[DuplicateGroup]:
    """Groups of files proven identical. ``entries`` are (path, size); only same-size files are read."""
    by_size: dict[int, list[str]] = defaultdict(list)
    for p, s in entries:
        if s and s > 0:
            by_size[int(s)].append(p)
    cands = [(p, s) for s, ps in by_size.items() if len(ps) > 1 for p in ps]
    with ThreadPoolExecutor(max(1, workers)) as ex:
        fps = list(ex.map(lambda c: fingerprint(c[0], c[1], reader), cands))
    groups: dict[tuple[int, str], list[str]] = defaultdict(list)
    for (p, s), fp in zip(cands, fps, strict=True):
        if not fp.startswith("error:"):
            groups[(s, fp)].append(p)
    out = [DuplicateGroup(s, fp, sorted(ps)) for (s, fp), ps in groups.items() if len(ps) > 1]
    if deep:
        proven: list[DuplicateGroup] = []
        for g in out:
            by_hash: dict[str, list[str]] = defaultdict(list)
            for p in g.paths:
                by_hash[full_hash(p)].append(p)
            proven += [DuplicateGroup(g.size, h, ps, "hash") for h, ps in by_hash.items() if len(ps) > 1]
        out = proven
    return sorted(out, key=lambda g: (-g.size, g.paths))


def scan_sizes(
    root: str | Path, suffixes: tuple[str, ...] = (".pdf", ".epub", ".djvu")
) -> list[tuple[str, int]]:
    root = Path(root)
    return [
        (str(p), p.stat().st_size)
        for p in sorted(root.rglob("*"))
        if p.is_file() and (not suffixes or p.suffix.lower() in suffixes)
    ]
