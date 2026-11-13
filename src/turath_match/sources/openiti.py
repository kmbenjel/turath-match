"""OpenITI: the open machine-readable corpus of Islamicate texts (KITAB project), through its metadata file.

Every OpenITI text has a *version URI* (``0256Bukhari.Sahih.Shamela0001681-ara1``) under a *book URI*
(``0256Bukhari.Sahih``): the book URI is a work identifier shared by every version, with the author's death year
(AH) in its first four digits. That makes OpenITI the open backbone for work-level matching: a record matched to
one version is linked to the work and to every other version and source of it.

The metadata TSV of each release is on Zenodo (CC BY-NC-SA 4.0; cite the release). ``fetch_metadata`` downloads
it once into the cache; nothing from OpenITI is shipped with turath-match.
"""

from __future__ import annotations

import csv
import re
import sys
from collections.abc import Iterator
from pathlib import Path

from ..models import Record
from ..net import Http
from .base import register

RELEASE = "2025.1.9"
METADATA_URL = "https://zenodo.org/records/17767721/files/OpenITI_metadata_2025-1-9.tsv?download=1"
CITATION = (
    "Nigst, Romanov, Savant, Seydi, Verkinderen et al., OpenITI: a Machine-Readable Corpus of Islamicate "
    "Texts, release 2025.1.9, Zenodo, doi:10.5281/zenodo.17767721"
)


def repo_of(date: str) -> str:
    """The GitHub repository of a 25-year period: death 256 -> «0275AH»."""
    y = int(date)
    return f"{((y + 24) // 25) * 25:04d}AH"


def text_url(version_uri: str, book: str, date: str) -> str:
    author = book.split(".")[0]
    if not date.isdigit():
        return ""
    return f"https://github.com/OpenITI/{repo_of(date)}/blob/master/data/{author}/{book}/{version_uri}"


def _alts(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split("::") if x.strip()]


_PUB = re.compile(
    r"دار|مكتب[ةه]|مطبع[ةه]|المطبع|مؤسس[ةه]|المؤسس|الناشر|شرك[ةه]|منشورات|المجمع|جامع[ةه]|Press|Verlag|Brill"
)
_YEAR = re.compile(r"\b\d{3,4}\s*(?:هـ|ه|م)\b|\b1[2-4]\d\d\b|\b(?:19|20)\d\d\b")
_EDN = re.compile(
    r"^(?:الطبعة|ط)?\s*(?:الأولى|الاولى|الثانية|الثالثة|الرابعة|الخامسة|السادسة|السابعة|الثامنة|التاسعة|العاشرة)$"
)
_PLACE = re.compile(
    r"^(?:بيروت|القاهرة|دمشق|الرياض|مصر|بغداد|تونس|الرباط|فاس|الكويت|عمان|حلب|ليدن|بولاق|المنصورة|"
    r"المدينة|مكة|جدة|الدوحة|لبنان|بيروت\s*/\s*لبنان|لا يوجد)\b"
)


def parse_ed_info(s: str) -> dict[str, str]:
    """OpenITI «ed_info» pieces («editor :: place :: year :: publisher», in any order) -> fields."""
    out: dict[str, str] = {}
    for p in _alts(s):
        p = re.sub(r"\s+", " ", p.replace("¶", " ")).strip()
        if p.startswith("http") or p == "لا يوجد":
            continue
        if _EDN.match(p):
            out.setdefault("edition", p)
        elif _PUB.search(p):
            out.setdefault("publisher", p)
        elif _YEAR.search(p) and len(p) < 30:
            out.setdefault("year", p)
        elif _PLACE.match(p):
            out.setdefault("place", p)
        elif "editor" not in out and re.search(r"[\u0621-\u064a]", p):
            out["editor"] = re.sub(r"^(?:تحقيق(?: وشرح)?\s*:?\s*|د\s*\.\s*|الدكتور\s+|المحامي\s+)", "", p)
    return out


_SOURCE = re.compile(
    r"\.(Shamela|ShamAY|JK|Sham19Y|ShamIbadiyya|Zaydiyya|Shia|Masaha|Hindawi|PV|GRAR|LAL)(\w+?)(?:Vols)?-"
)


def to_record(row: dict[str, str]) -> Record | None:
    titles, authors = _alts(row.get("title_ar", "")), _alts(row.get("author_ar", ""))
    if not titles or not row.get("book"):
        return None
    date = (row.get("date") or "").strip()
    death = int(date) if date.isdigit() and 0 < int(date) < 1500 else None
    ed = parse_ed_info(row.get("ed_info", ""))
    m = _SOURCE.search(row["version_uri"])
    flags = {"manuscript"} if row.get("shelfmark") else set()
    return Record(
        "openiti",
        row["version_uri"],
        " = ".join(dict.fromkeys(titles)),
        " ؛ ".join(dict.fromkeys(authors)),
        death=death,
        editor=ed.get("editor", ""),
        publisher=ed.get("publisher", ""),
        place=ed.get("place", ""),
        year=ed.get("year", ""),
        url=text_url(row["version_uri"], row["book"], date),
        work_uri=row["book"],
        flags=flags,
        extra={
            "status": row.get("status", ""),
            "language": row.get("language", ""),
            "tokens": row.get("tok_length", ""),
            "source_collection": m.group(1) if m else "",
            "source_id": m.group(2) if m else "",
            "ed_info": row.get("ed_info", ""),
        },
    )


class OpenITI:
    """Read a metadata TSV (a release file or the KITAB «metadata_light» export)."""

    scheme = "openiti"

    def __init__(
        self, path: str | Path, *, languages: tuple[str, ...] = ("ara",), primary_only: bool = False
    ):
        self.path = Path(path)
        self.languages, self.primary_only = languages, primary_only

    def records(self) -> Iterator[Record]:
        csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
        with self.path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                if self.languages and row.get("language") not in self.languages:
                    continue
                if self.primary_only and row.get("status") != "pri":
                    continue
                r = to_record(row)
                if r:
                    yield r


def fetch_metadata(http: Http | None = None, url: str = METADATA_URL, dest: str | Path | None = None) -> Path:
    """Download the release metadata once (cached) and return its local path."""
    http = http or Http(min_interval=1.0, timeout=300)
    data = http.get(url)
    path = Path(dest) if dest else http._path(url).with_suffix(".tsv")
    if not path.exists() or path.stat().st_size != len(data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return path


@register("openiti")
def _open(loc: str) -> OpenITI:
    return OpenITI(loc)
