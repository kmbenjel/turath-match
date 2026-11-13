"""archive.org: search items by title and author, and list each item's files with exact sizes and checksums.

Two public endpoints, both cached on disk by :class:`~turath_match.net.Http`:

* ``advancedsearch.php`` (title, creator, downloads) to find candidate items;
* ``/download/<id>/<id>_files.xml`` for every file's exact byte size, md5 and sha1 — the key to exact-size
  provenance. One archive.org item often holds several books, so files are kept per file, never per item.
"""

from __future__ import annotations

import json
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from ..models import FileRef, Record
from ..net import Http, HttpError
from ..text import search_key
from .base import register

SEARCH = "https://archive.org/advancedsearch.php?"
FIELDS = ("identifier", "title", "creator", "date", "downloads", "item_size", "mediatype")


def _s(v: Any) -> str:
    return " ؛ ".join(map(str, v)) if isinstance(v, list) else str(v or "")


def is_book_file(f: FileRef) -> bool:
    n = f.name.lower()
    return (
        n.endswith((".pdf", ".djvu", ".epub"))
        and not n.endswith("_text.pdf")
        and "text pdf" not in f.format.lower()
        and bool(f.size)
    )


def parse_files_xml(data: bytes, identifier: str) -> list[FileRef]:
    root = ET.fromstring(data)
    out = []
    for f in root.findall("file"):
        name = f.get("name") or ""
        size = f.findtext("size")
        ref = FileRef(
            name=name,
            size=int(size) if size and size.isdigit() else None,
            url=f"https://archive.org/download/{urllib.parse.quote(identifier)}/{urllib.parse.quote(name)}",
            md5=f.findtext("md5") or "",
            sha1=f.findtext("sha1") or "",
            format=f.findtext("format") or "",
        )
        if is_book_file(ref):
            out.append(ref)
    return out


class ArchiveOrg:
    """Online adapter. ``search`` finds items, ``item`` lists one item's book files."""

    scheme = "archive"

    def __init__(self, http: Http | None = None, rows: int = 25):
        self.http = http or Http()
        self.rows = rows

    def search_raw(self, query: str, rows: int | None = None) -> list[dict[str, Any]]:
        params = [("q", query), ("rows", str(rows or self.rows)), ("page", "1"), ("output", "json")]
        params += [("fl[]", f) for f in FIELDS]
        d = self.http.get_json(SEARCH + urllib.parse.urlencode(params))
        return list(d.get("response", {}).get("docs", []))

    def search(self, title: str, author: str = "", *, with_files: bool = True) -> list[Record]:
        """Items whose title holds every word of ``title`` (archive.org's own search, then checked here)."""
        q = f"title:({title}) AND mediatype:texts"
        if author:
            q += f" AND (creator:({author}) OR title:({author}))"
        docs = self.search_raw(q)
        if not docs and author:
            docs = self.search_raw(f"title:({title}) AND mediatype:texts")
        want = set(search_key(title).split())
        out = []
        for d in docs:
            if not want <= set(search_key(_s(d.get("title"))).split()):
                continue
            out.append(self.item(d["identifier"], d) if with_files else self._record(d, []))
        return out

    def _record(self, d: dict[str, Any], files: list[FileRef]) -> Record:
        ident = d["identifier"]
        return Record(
            "archive",
            ident,
            _s(d.get("title")) or ident,
            _s(d.get("creator")),
            year=_s(d.get("date"))[:10],
            files=files,
            url=f"https://archive.org/details/{ident}",
            extra={"downloads": d.get("downloads", 0)},
        )

    def files(self, identifier: str) -> list[FileRef]:
        q = urllib.parse.quote(identifier)
        try:
            return parse_files_xml(
                self.http.get(f"https://archive.org/download/{q}/{q}_files.xml"), identifier
            )
        except HttpError as e:
            if e.code in (403, 404):  # a dark or removed item
                return []
            raise

    def item(self, identifier: str, doc: dict[str, Any] | None = None) -> Record:
        return self._record(doc or {"identifier": identifier}, self.files(identifier))

    def items(self, identifiers: Iterable[str]) -> Iterator[Record]:
        for i in identifiers:
            yield self.item(i)


class ArchiveDump:
    """Records saved earlier: JSONL lines ``{"identifier", "title", "creator", "files": [{name, size, md5, …}]}``
    (or ``id`` for ``identifier``) — the format ``turath-match fetch archive`` writes."""

    scheme = "archive"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def records(self) -> Iterator[Record]:
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                d = json.loads(line)
                ident = d.get("identifier") or d.get("id")
                if not ident or d.get("error"):
                    continue
                files = []
                for f in d.get("files", []):
                    url = (
                        f.get("url")
                        or f"https://archive.org/download/{ident}/{urllib.parse.quote(f['name'])}"
                    )
                    ref = FileRef(
                        name=f["name"],
                        size=f.get("size"),
                        url=url,
                        md5=f.get("md5", ""),
                        sha1=f.get("sha1", ""),
                        format=f.get("format", ""),
                    )
                    if is_book_file(ref):
                        files.append(ref)
                yield Record(
                    "archive",
                    ident,
                    _s(d.get("title")) or ident,
                    _s(d.get("creator")),
                    year=_s(d.get("date"))[:10],
                    files=files,
                    url=f"https://archive.org/details/{ident}",
                )


@register("archive")
def _open(loc: str) -> ArchiveDump:
    return ArchiveDump(loc)
