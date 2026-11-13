"""A folder of books: each single file is a book, each folder of numbered volumes is one multi-volume book.

File names are read with a *profile*:

``smart`` (default)
    ``<title> - <author> - ت <editor> - ط <publisher> <city>``; every part after the title is optional, a part that
    starts with «ت » is the editor and one that starts with «ط » (or comes last) is the publisher. Latin titles
    («Title - Author») work the same way.
``warraq``
    The naming rule of the Warraq library: as ``smart``, and the part after the editor is always the publisher,
    with or without «ط»; volumes are ``NN - <shared name>.pdf`` with ``00`` for front matter.
``title``
    The whole name is the title (no author): matches will mostly land on the review list.
``pattern:{title} - {author}``
    Your own pattern, with ``{title} {author} {editor} {publisher} {year} {skip}`` fields.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from pathlib import Path

from ..models import FileRef, Record
from ..text import parse_death
from .base import register

BOOK_SUFFIXES = (".pdf", ".epub", ".djvu", ".mobi", ".azw3", ".doc", ".docx", ".chm")
_VOL = re.compile(r"^\s*(?:\d{1,3}|ج\s*\d{1,3}|vol(?:ume)?\.?\s*\d{1,3}|الجزء\s+\S+)\s*[-_.)\s]", re.I)
_NUMBERED = re.compile(r"(?:(?:^|\s)(?:ج|vol\.?|v)\s*)?\d+", re.I)


def _norm_sep(s: str) -> str:
    return re.sub(r"\s+[-–—]\s+", " - ", s.replace("_", " ")).strip()


def parse_name(stem: str, profile: str = "smart") -> dict[str, str]:
    """Fields of a book named by its file or folder name."""
    s = _norm_sep(stem)
    if profile == "title":
        return {"title": s}
    if profile.startswith("pattern:"):
        pat = profile[len("pattern:") :]
        rx = (
            "^"
            + re.sub(
                r"\\\{(\w+)\\\}",
                lambda m: f"(?P<{m.group(1)}>.+?)" if m.group(1) != "skip" else ".+?",
                re.escape(pat),
            )
            + "$"
        )
        m = re.match(rx, s)
        return {k: v.strip() for k, v in (m.groupdict() if m else {"title": s}).items()}
    parts = [p.strip() for p in s.split(" - ") if p.strip()]
    out: dict[str, str] = {"title": parts[0] if parts else s}
    rest = parts[1:]
    for i, p in enumerate(rest):
        if re.match(r"^ت[\s.]", p):
            out["editor"] = re.sub(r"^ت[\s.]+", "", p)
        elif re.match(r"^ط[\s.]", p):
            out["publisher"] = re.sub(r"^ط[\s.]+", "", p)
        elif re.fullmatch(r"\(?\d{3,4}\)?\s*(?:هـ|ه|م)?", p):
            out["year"] = p.strip("()")
        elif "author" not in out and "editor" not in out and i == 0:
            out["author"] = p
        elif profile == "warraq" or i == len(rest) - 1:
            out.setdefault("publisher", p)
    return out


def _is_volume_set(files: list[Path]) -> bool:
    if len(files) < 2:
        return False
    if sum(1 for f in files if _VOL.match(f.stem)) >= max(2, len(files) // 2):
        return True
    stems = {_NUMBERED.sub(" ", f.stem).strip(" -_.") for f in files}
    return len(stems) == 1


def _rid(rel: str) -> str:
    return hashlib.sha1(rel.encode()).hexdigest()[:12]


class FolderSource:
    """Scan a folder into library records (sizes are read from the file system; nothing is opened)."""

    def __init__(
        self,
        root: str | Path,
        profile: str = "smart",
        scheme: str = "library",
        suffixes: tuple[str, ...] = BOOK_SUFFIXES,
    ):
        self.root = Path(root)
        self.profile, self.scheme, self.suffixes = profile, scheme, suffixes
        if not self.root.is_dir():
            raise ValueError(f"{self.root} is not a folder")

    def _record(self, name: str, files: list[Path], rel: str) -> Record:
        f = parse_name(name, self.profile)
        refs = [FileRef(name=p.name, size=p.stat().st_size, path=str(p)) for p in sorted(files)]
        return Record(
            self.scheme,
            _rid(rel),
            f.get("title", name),
            f.get("author", ""),
            death=parse_death(f.get("author", "")),
            editor=f.get("editor", ""),
            publisher=f.get("publisher", ""),
            year=f.get("year", ""),
            volumes=len(refs) if len(refs) > 1 else 1,
            files=refs,
            url=rel,
            extra={"path": rel},
        )

    def records(self) -> Iterator[Record]:
        dirs = [self.root, *sorted(p for p in self.root.rglob("*") if p.is_dir())]
        for d in dirs:
            books = sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in self.suffixes)
            if not books:
                continue
            rel = str(d.relative_to(self.root)) if d != self.root else ""
            if d != self.root and _is_volume_set(books):
                yield self._record(d.name, books, rel)
                continue
            for b in books:
                yield self._record(b.stem, [b], str(b.relative_to(self.root)))


@register("folder")
def _open(loc: str) -> FolderSource:
    prof = "smart"
    if "::" in loc:  # folder:~/Books::warraq
        loc, prof = loc.split("::", 1)
    return FolderSource(loc, prof)
