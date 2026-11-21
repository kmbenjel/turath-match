"""Duplicate proof by size plus sampled bytes.

Two files are candidates only when their sizes are equal. A candidate pair is a duplicate when five 64 KB
windows agree: the start, 25 %, 50 %, 75 % and the end. That reads 320 KB per file instead of the whole file,
so it works over slow links (FTP, SFTP, a phone) where checksums are not available; ``deep=True`` adds a full
SHA-256 for the final proof. A file that cannot be read gets its own fingerprint and is never called a duplicate.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .sources.folder import parse_name

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
    if not root.is_dir():
        raise ValueError(f"{root} is not a folder")
    return [
        (str(p), p.stat().st_size)
        for p in sorted(root.rglob("*"))
        if p.is_file() and (not suffixes or p.suffix.lower() in suffixes)
    ]


# a camera, scanner or download name: «scan_0007», «IMG_1234», «DSC01234», «document (3)», «12345», a hex id
_RAW_NAME = re.compile(
    r"^(?:(?:scan|scanned|img|image|dsc|dscn|pxl|photo|doc|document|file|page|untitled|copy|new|book|download)s?"
    r"[\s_.\-]*)?[\d\s_.\-()]*$|^[0-9a-f]{12,}$",
    re.I,
)
_VOLUME_PREFIX = re.compile(r"^\s*(?:\d{1,3}|ج\s*\d{1,3})(?:\s+-\s+|\s*$)")


def _book_name(path: str, root: str | Path | None) -> str:
    """The name that describes the book: the file's stem, or its folder's name when the file is only a volume
    number («01.pdf», «03 - .pdf»), as in a folder of numbered volumes."""
    p = Path(path)
    stem = _VOLUME_PREFIX.sub("", p.stem).strip()
    if not stem and p.parent.name and (root is None or p.parent != Path(root)):
        return p.parent.name
    return stem or p.stem


def is_raw_name(name: str) -> bool:
    """True for a scanner, camera or download name that says nothing about the book."""
    return bool(_RAW_NAME.match(name.strip())) or not re.search(r"[^\W\d_]", name)


# what a file manager or a browser adds to the name of a second copy: «X - Copy», «X (1)», «Copy of X», «X - نسخة»
_COPY_MARK = re.compile(
    r"\s*(?:[-–_]\s*)?(?:\(\s*\d{1,3}\s*\)|\(?\b(?:copy|copie|kopie|duplicate)\b(?:\s*\(?\d{1,3}\)?)?\)?"
    r"|(?:نسخة|نسخه)(?:\s+(?:ثانية|ثالثة|أخرى|اخرى|مكررة|\d{1,3}))?)\s*$|^\s*copy\s+of\s+",
    re.I,
)


def strip_copy_marks(name: str) -> tuple[str, int]:
    """(the name without the marks of a second copy, how many there were): «X(2) - Copy» -> («X», 2)."""
    n = 0
    while True:
        m = _COPY_MARK.search(name)
        if not m or not (name[: m.start()] + name[m.end() :]).strip():
            return name.strip(), n
        name, n = name[: m.start()] + name[m.end() :], n + 1


def keep_rank(
    path: str, profile: str = "smart", root: str | Path | None = None
) -> tuple[int, int, int, int, str]:
    """Sort key for the copy to keep, best first: a name that the naming ``profile`` reads into a title and at
    least one more part beats a raw scan name; then the name that is not marked as a second copy («- Copy»,
    «(1)», «نسخة»); then the name with more metadata parts; then the shorter path."""
    name, marks = strip_copy_marks(_book_name(path, root))
    raw = is_raw_name(name)
    fields = {k: v for k, v in parse_name(name, profile).items() if v}
    passes = not raw and (len(fields) >= 2 or profile == "title")
    return (0 if passes else 1 if not raw else 2, marks, -len(fields), len(path), path)


def choose_keep(paths: Iterable[str], profile: str = "smart", root: str | Path | None = None) -> list[str]:
    """``paths`` ordered best copy first (see :func:`keep_rank`): the first is kept, the rest are duplicates."""
    return sorted(paths, key=lambda p: keep_rank(p, profile, root))
