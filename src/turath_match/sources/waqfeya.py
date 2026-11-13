"""Waqfeya (waqfeya.net): the catalog's public JSON list API, plus each book page's detail record.

``fetch_catalog`` pages through ``/books/books-api`` (100 records a page, one request a second, every page
cached); ``fetch_details`` reads a book page's embedded record (editor, publisher, volumes, size, links). The
dump is yours: turath-match ships no Waqfeya data. A record's files are its archive.org links; their exact sizes
come from the archive.org adapter. Labels on Waqfeya can be wrong, and one linked archive.org item can hold
several books: a link is evidence for a match, never the match itself.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..models import FileRef, Record
from ..net import Http
from ..text import parse_death, to_ascii_digits
from .base import register

API = "https://waqfeya.net/books/books-api?page={page}&pageSize={size}&sortBy=latest"
BOOK = "https://waqfeya.net/books/{permalink}"
_ARCHIVE = re.compile(r"archive\.org/(?:details|download)/([^/\"?#\s]+)(?:/([^\"?#\s]+))?")


def _name(v: Any) -> str:
    return str((v or {}).get("name", "")) if isinstance(v, dict) else str(v or "")


def _int(s: Any) -> int | None:
    m = re.search(r"\d+", to_ascii_digits(str(s or "")))
    return int(m.group()) if m else None


def to_record(d: dict[str, Any]) -> Record:
    """One Waqfeya list or detail object -> a Record (unknown fields are kept in ``extra``)."""
    pub = str(d.get("publisher") or "").strip()
    place = ""
    if " - " in pub:
        pub, place = (x.strip() for x in pub.rsplit(" - ", 1))
    files, items = [], []
    blob = json.dumps([d.get("links"), d.get("archiveLink"), d.get("thumbnail")], ensure_ascii=False)
    for ident, fname in _ARCHIVE.findall(blob):
        if ident not in items:
            items.append(ident)
        if fname and fname.lower().endswith(".pdf"):
            files.append(
                FileRef(name=urllib.parse.unquote(fname), url=f"https://archive.org/download/{ident}/{fname}")
            )
    author = _name(d.get("author"))
    century = _name(d.get("century"))
    return Record(
        "waqfeya",
        str(d["_id"]),
        str(d.get("name", "")).strip(),
        author,
        death=parse_death(author),
        editor=str(d.get("researcher") or d.get("investigator") or "").strip(),
        publisher=pub,
        place=place,
        year=str(d.get("yearOfPublish") or ""),
        volumes=_int(d.get("numberOfVolumes")),
        files=files,
        url=BOOK.format(permalink=urllib.parse.quote(str(d.get("permalink", "")))),
        extra={
            "archive_items": items,
            "century": century,
            "category": _name(d.get("category")),
            "size_mb": d.get("sizeInMB"),
            "pages": d.get("pages"),
        },
    )


def _rsc_text(html: str) -> str:
    """The Next.js flight payload of a page, where the full book record lives."""
    pat = r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)'
    return "".join(json.loads('"' + m.group(1) + '"') for m in re.finditer(pat, html, flags=re.S))


def parse_detail(html: str, book_id: str) -> dict[str, Any] | None:
    t = _rsc_text(html)
    needle = '{"_id":"' + book_id + '","name"'
    k = t.find(needle)
    while k >= 0:
        obj, _ = json.JSONDecoder().raw_decode(t, k)
        if "links" in obj or "century" in obj:
            return dict(obj)
        k = t.find(needle, k + 1)
    return None


class Waqfeya:
    """Online adapter (polite: one request a second by default, every response cached)."""

    scheme = "waqfeya"

    def __init__(self, http: Http | None = None, page_size: int = 100):
        self.http = http or Http(min_interval=1.0)
        self.page_size = page_size

    def pages(self, max_pages: int | None = None) -> Iterator[list[dict[str, Any]]]:
        page, total = 1, None
        while total is None or page <= total:
            d = self.http.get_json(API.format(page=page, size=self.page_size))
            total = int(d.get("pagination", {}).get("totalPages", 1))
            yield list(d.get("data", []))
            page += 1
            if max_pages and page > max_pages:
                return

    def fetch_catalog(self, max_pages: int | None = None) -> Iterator[dict[str, Any]]:
        for batch in self.pages(max_pages):
            yield from batch

    def fetch_detail(self, raw: dict[str, Any]) -> dict[str, Any]:
        html = self.http.get(BOOK.format(permalink=urllib.parse.quote(raw["permalink"]))).decode(
            "utf-8", "replace"
        )
        return {**raw, **(parse_detail(html, raw["_id"]) or {"nodetail": True})}


class WaqfeyaDump:
    """A JSONL dump of raw Waqfeya objects (list records, detail records, or both: later lines enrich earlier)."""

    scheme = "waqfeya"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def records(self) -> Iterator[Record]:
        merged: dict[str, dict[str, Any]] = {}
        paths = sorted(self.path.glob("*.jsonl")) if self.path.is_dir() else [self.path]
        for p in paths:
            with p.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        d = json.loads(line)
                        if "_id" in d and not d.get("error"):
                            merged[d["_id"]] = {**merged.get(d["_id"], {}), **d}
        for d in merged.values():
            if d.get("name"):
                yield to_record(d)


@register("waqfeya")
def _open(loc: str) -> WaqfeyaDump:
    return WaqfeyaDump(loc)
