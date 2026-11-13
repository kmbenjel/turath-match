"""A user CSV/TSV: a library inventory, a wish list, or any catalog exported from a spreadsheet.

Only ``title`` is required. Column names may be English or Arabic (``العنوان``, ``المؤلف``, ``المحقق``,
``الناشر``, ``الأجزاء``, ``الحجم``…). ``size`` holds exact file sizes in bytes, several separated by ``;``;
``file`` the matching file names; ``url`` a link to the record.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from pathlib import Path

from ..models import FileRef, Record
from ..text import parse_death, to_ascii_digits
from .base import register

ALIASES = {
    "id": ("id", "book_id", "record_id", "الرقم", "رقم"),
    "title": ("title", "name", "book", "العنوان", "الكتاب", "اسم الكتاب"),
    "author": ("author", "creator", "المؤلف", "المصنف"),
    "death": ("death", "death_ah", "died", "الوفاة", "سنة الوفاة"),
    "editor": ("editor", "editors", "researcher", "investigator", "المحقق", "تحقيق"),
    "publisher": ("publisher", "الناشر", "دار النشر"),
    "place": ("place", "city", "المدينة", "مكان النشر"),
    "year": ("year", "date", "سنة النشر", "عام النشر", "التاريخ"),
    "volumes": ("volumes", "vols", "عدد الأجزاء", "الأجزاء", "المجلدات"),
    "size": ("size", "sizes", "bytes", "size_bytes", "الحجم"),
    "file": ("file", "files", "filename", "path", "الملف"),
    "url": ("url", "link", "الرابط"),
    "work_uri": ("work_uri", "openiti", "openiti_uri"),
    "flags": ("flags",),
}


def _col(header: list[str]) -> dict[str, str]:
    low = {h.strip().lower(): h for h in header}
    out = {}
    for field, names in ALIASES.items():
        for n in names:
            if n.lower() in low:
                out[field] = low[n.lower()]
                break
    return out


def _int(s: str) -> int | None:
    m = re.search(r"\d+", to_ascii_digits(s or ""))
    return int(m.group()) if m else None


class CsvSource:
    def __init__(self, path: str | Path, scheme: str = "csv"):
        self.path = Path(path)
        self.scheme = scheme

    def records(self) -> Iterator[Record]:
        text = self.path.read_text(encoding="utf-8-sig")
        first = text.splitlines()[0] if text else ""
        delim = "\t" if first.count("\t") >= first.count(",") and "\t" in first else ","
        rows = csv.DictReader(text.splitlines(), delimiter=delim)
        cols = _col(list(rows.fieldnames or []))
        if "title" not in cols:
            raise ValueError(f"{self.path}: no title column (looked for {', '.join(ALIASES['title'])})")
        for n, row in enumerate(rows, 1):
            g = lambda f, row=row: (row.get(cols[f]) or "").strip() if f in cols else ""  # noqa: E731
            if not g("title"):
                continue
            sizes = [_int(x) for x in re.split(r"[;|]", g("size")) if x.strip()]
            names = [x.strip() for x in re.split(r"[;|]", g("file")) if x.strip()]
            k = max(len(sizes), len(names))
            files = [
                FileRef(
                    name=(names[i] if i < len(names) else f"file{i + 1}"),
                    size=(sizes[i] if i < len(sizes) else None),
                    path=(names[i] if i < len(names) else ""),
                )
                for i in range(k)
            ]
            death = _int(g("death")) if g("death") else parse_death(g("author"))
            yield Record(
                scheme=self.scheme,
                id=g("id") or str(n),
                title=g("title"),
                author=g("author"),
                death=death,
                editor=g("editor"),
                publisher=g("publisher"),
                place=g("place"),
                year=g("year"),
                volumes=_int(g("volumes")),
                files=files,
                url=g("url"),
                work_uri=g("work_uri"),
                flags={x.strip() for x in g("flags").split(";") if x.strip()},
            )


@register("csv")
def _open(loc: str) -> CsvSource:
    return CsvSource(loc)
