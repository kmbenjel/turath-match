"""Shamela (al-Maktaba al-Shamila): a reader of the catalog of *your own* local install.

turath-match ships no Shamela data and downloads nothing from Shamela. This adapter opens the ``master.db`` of
a Shamela desktop installation you already have, read-only, and turns its book list into records: title,
author, death year, category and the size of the scanned PDF Shamela links to (exact-size provenance for your
files). The richer book cards («بطاقة الكتاب»: editor, publisher, edition, volumes) live in Shamela's Lucene
store; ``tools/shamela-dump`` exports them with Shamela's own Java and jars, and ``cards=`` reads that export.
See docs/shamela.md for the legal note.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..models import FileRef, Record
from ..text import to_ascii_digits
from .base import register

DEFAULT_LOCATIONS = (
    "~/.local/share/shamela",
    "~/shamela",
    "~/Shamela",
    "C:/shamela4",
    "~/Library/Application Support/shamela",
)

CARD_FIELDS = [
    ("title", r"الكتاب|اسم الكتاب"),
    ("author", r"المؤلف|تأليف|المؤلفون"),
    (
        "editor",
        r"المحقق|المحققون|تحقيق|دراسة وتحقيق|تحقيق ودراسة|تحقيق وتعليق|حققه وعلق عليه|حققه|اعتنى به|ضبطه",
    ),
    ("publisher", r"الناشر|دار النشر"),
    ("edition", r"الطبعة"),
    ("year", r"عام النشر|سنة النشر"),
    ("volumes", r"عدد الأجزاء"),
    ("pages", r"عدد الصفحات"),
]


def find_master_db(location: str | Path | None = None) -> Path:
    cands = [location] if location else [os.environ.get("SHAMELA_HOME", ""), *DEFAULT_LOCATIONS]
    for c in cands:
        if not c:
            continue
        p = Path(c).expanduser()
        for q in (p, p / "master.db", p / "database" / "master.db"):
            if q.is_file() and q.name.endswith(".db"):
                return q
    raise FileNotFoundError(
        "no Shamela master.db found; pass the folder of your Shamela install (shamela:/path/to/shamela) "
        "or set SHAMELA_HOME"
    )


def parse_card(card: str) -> dict[str, Any]:
    """«الحقل: القيمة» lines of a Shamela book card -> fields (editor, publisher, edition, year, volumes …)."""
    d: dict[str, Any] = {}
    for line in re.split(r"[\r\n]+", card or ""):
        line = line.strip()
        if line.startswith(("ويليه", "ومعه", "وبهامشه", "وبذيله")):
            d.setdefault("joined", []).append(line)
            continue
        m = re.match(r"^([^:]{2,30}):\s*(.+)$", line)
        if not m:
            continue
        k, v = m.group(1).strip(), m.group(2).strip()
        for f, rx in CARD_FIELDS:
            if re.fullmatch(rx, k):
                if f == "editor" and f in d:
                    d[f] += " ؛ " + v
                else:
                    d.setdefault(f, v)
                break
    if "volumes" in d:
        m = re.search(r"\d+", to_ascii_digits(d["volumes"]))
        d["volumes_n"] = int(m.group()) if m else None
    return d


def load_cards(path: str | Path) -> dict[str, dict[str, Any]]:
    """Cards exported by tools/shamela-dump (JSONL: ``id`` + ``body_store`` or already parsed fields)."""
    out: dict[str, dict[str, Any]] = {}
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            c = json.loads(line)
            body = c.get("body_store") or c.get("card") or ""
            out[str(c["id"])] = {
                **parse_card(body),
                **{k: v for k, v in c.items() if k not in ("body_store", "card")},
            }
    return out


class ShamelaLocal:
    scheme = "shamela"

    def __init__(
        self,
        location: str | Path | None = None,
        cards: str | Path | None = None,
        include_hidden: bool = False,
    ):
        self.db = find_master_db(location)
        self.cards = load_cards(cards) if cards else {}
        self.include_hidden = include_hidden

    def records(self) -> Iterator[Record]:
        con = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            cats = dict(con.execute("select category_id, category_name from category"))
            auth = {
                a: (n or "", d)
                for a, n, d in con.execute("select author_id, author_name, death_number from author")
            }
            q = "select book_id, book_name, book_category, main_author, printed, pdf_links, hidden from book order by book_id"
            for bid, name, cat, main, printed, pdf, hidden in con.execute(q):
                if hidden and not self.include_hidden:
                    continue
                aname, death = auth.get(main, ("", None))
                files: list[FileRef] = []
                if pdf:
                    try:
                        pl = json.loads(pdf)
                    except ValueError:
                        pl = {}
                    for i, f in enumerate(pl.get("files") or []):
                        size = pl.get("size") if i == 0 and len(pl.get("files") or []) == 1 else None
                        files.append(FileRef(name=str(f).rsplit("/", 1)[-1], size=size))
                card = self.cards.get(str(bid), {})
                flags = {"manuscript"} if re.search(r"مخطوط", name or "") else set()
                yield Record(
                    "shamela",
                    str(bid),
                    name or "",
                    aname,
                    death=death if death and death < 2000 else None,
                    editor=card.get("editor", ""),
                    publisher=card.get("publisher", ""),
                    year=card.get("year", ""),
                    volumes=card.get("volumes_n"),
                    files=files,
                    url=f"https://shamela.ws/book/{bid}",
                    flags=flags,
                    extra={
                        "category": cats.get(cat, ""),
                        "printed": printed,
                        "edition": card.get("edition", ""),
                    },
                )
        finally:
            con.close()


@register("shamela")
def _open(loc: str) -> ShamelaLocal:
    cards = None
    if "::" in loc:  # shamela:/path::cards.jsonl
        loc, cards = loc.split("::", 1)
    return ShamelaLocal(loc or None, cards)
