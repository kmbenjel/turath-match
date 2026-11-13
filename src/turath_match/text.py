"""Arabic text helpers, delegated to `arabic-bib <https://github.com/kmbenjel/arabic-bib>`_.

turath-match never normalises Arabic on its own: search keys, title keys, author tokens, author agreement
and death years come from arabic-bib, so a catalog built by turath-catalog and a match made here use the same
keys. When arabic-bib cannot be imported (a source checkout without it), a small built-in fallback with the
same names keeps the tool usable; ``BACKEND`` says which one is active.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

try:  # pragma: no cover - exercised when arabic-bib is installed
    import arabic_bib as _ab

    _HAS_AB = all(hasattr(_ab, n) for n in ("search_key", "title_key", "author_tokens", "match_authors"))
except Exception:  # pragma: no cover
    _ab = None
    _HAS_AB = False

BACKEND = "arabic-bib" if _HAS_AB else "builtin"

_TASHKIL = re.compile("[ً-ْٰـ]")
_FOLD = str.maketrans(
    {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي", "ء": None}
)
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def _fallback_key(s: str) -> str:
    s = _TASHKIL.sub("", (s or "").translate(_DIGITS)).translate(_FOLD)
    s = re.sub(r"[^ء-ي0-9a-zA-Z ]", " ", s).lower()
    return " ".join(s.split())


def search_key(s: str) -> str:
    """Accent- and spelling-folded form for comparison: «إحياء علوم الدّين» -> «احياء علوم الدين»."""
    if _HAS_AB:
        return str(_ab.search_key(s or ""))
    return _fallback_key(s)


def to_ascii_digits(s: str) -> str:
    return (s or "").translate(_DIGITS)


def title_key(t: str) -> str:
    """The title without (…)/[…], edition tails («- ط …», «ت …») and a leading «كتاب»."""
    if _HAS_AB:
        return str(_ab.title_key(t or ""))
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t or "")
    t = re.split(r"\s+-\s+|\s+ط\s|\s+ت\s", " " + t + " ")[0]
    w = search_key(t).split()
    if len(w) > 1 and w[0] == "كتاب":
        w = w[1:]
    return " ".join(w)


def author_key(a: str) -> str:
    if _HAS_AB and hasattr(_ab, "author_key"):
        return str(_ab.author_key(a or ""))
    return " ".join(sorted(author_tokens(a)))


_STOP_AUTH = set(
    [
        "بن",
        "ابن",
        "ابي",
        "ابو",
        "ابا",
        "عبد",
        "الله",
        "الامام",
        "الحافظ",
        "الشيخ",
        "العلامه",
        "القاضي",
        "شيخ",
        "الاسلام",
        "ت",
        "ط",
        "المتوفي",
    ]
)


def author_tokens(a: str) -> frozenset[str]:
    """Distinctive name words of an author string (particles and honorifics left out)."""
    if _HAS_AB:
        return frozenset(_ab.author_tokens(a or ""))
    return frozenset(
        w for w in search_key(a).split() if w not in _STOP_AUTH and len(w) > 2 and not w.isdigit()
    )


@dataclass(frozen=True)
class AuthorMatch:
    verdict: str  # same | different | unknown
    score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)


# The fallback's common-name list: a name carried by many people never proves two authors are one.
_COMMON = set(
    _fallback_key(
        "محمد أحمد علي عمر عثمان إبراهيم يحيى إسماعيل يوسف سليمان موسى عيسى داود خالد سعيد سعد جعفر حفص بكر زيد "
        "يزيد منصور القاسم الحسن الحسين حسن حسين الرحمن العزيز الملك الوهاب الفضل العباس طاهر صالح مصطفى عمرو "
        "عامر أيوب حمد ناصر الدين نصر بنت تقي شمس جمال بدر زين عز العز علاء سراج محيي شهاب فخر نجم صلاح برهان "
        "عماد مجد موفق ضياء رضي كمال صدر قطب نور السلام الرحيم الكريم الحميد المجيد اللطيف الغني القادر الواحد "
        "المالكي الحنفي الشافعي الحنبلي الدمشقي البغدادي المصري القرشي الانصاري الاندلسي"
    ).split()
)
_ANON = {"مجهول", "مولف مجهول", "غير معروف", "anonymous", "unknown"}


def parse_death(s: str) -> int | None:
    """The Hijri death year in «ت 728 هـ», «(ت ٧٢٨هـ)», «661-728», «المتوفى: 728»."""
    if not s:
        return None
    if _HAS_AB and hasattr(_ab, "parse_death"):
        d = _ab.parse_death(s)
        return getattr(d, "hijri", None) if d is not None else None
    t = to_ascii_digits(s)
    m = re.search(r"(?:ت|المتوفى|المتوفي|توفي)[\s.:]*(\d{1,4})", t) or re.search(
        r"\d{1,4}\s*-\s*(\d{1,4})", t
    )
    if not m:
        m = re.fullmatch(r"\s*(\d{1,4})\s*(?:هـ|ه)?\s*", t)
    return int(m.group(1)) if m else None


_INVERTED = re.compile(r"^\s*([^،,؛;]+?)\s*[،,]\s*([^،,؛;]+?)\s*(?:[،,]\s*(.*))?$")


def uninvert(name: str) -> str:
    """Library-catalog order «ابن المقفع، عبد الله» -> «عبد الله ابن المقفع» (quotes and «إبن» cleaned)."""
    n = re.sub(r"[\"“”«»]", " ", name or "").replace("إبن", "ابن").strip()
    m = _INVERTED.match(n)
    if m and not re.search(r"\d", m.group(2)) and len(m.group(2).split()) <= 4:
        rest = f" {m.group(3)}" if m.group(3) else ""
        n = f"{m.group(2)} {m.group(1)}{rest}"
    return " ".join(n.split())


def match_authors(a: str, b: str, *, common: Any = None) -> AuthorMatch:
    """Tri-state author agreement. Never «same» on a common given name, laqab or nisba alone."""
    a, b = uninvert(a), uninvert(b)
    if _HAS_AB:
        r = _ab.match_authors(a or "", b or "", common=common)
        return AuthorMatch(str(r.verdict), float(r.score), tuple(r.reasons))
    ka, kb = search_key(a), search_key(b)
    if not ka or not kb or ka in _ANON or kb in _ANON:
        return AuthorMatch("unknown", 0.0, ("missing-author",))
    da, db = parse_death(a), parse_death(b)
    if da and db and abs(da - db) > 2:
        return AuthorMatch("different", 0.0, (f"death-conflict:{da}!={db}",))
    extra = {search_key(c) for c in common} if common else set()
    ta, tb = author_tokens(a), author_tokens(b)
    ca, cb = ta - _COMMON - extra, tb - _COMMON - extra
    shared = ca & cb
    if shared:
        return AuthorMatch(
            "same", min(1.0, 0.6 + 0.2 * len(shared)), tuple(f"shared:{x}" for x in sorted(shared))
        )
    if ka == kb:
        return AuthorMatch("same", 0.8, ("identical-name",))
    if ca and cb:
        return AuthorMatch("different", 0.1, ("no-shared-distinctive-token",))
    return AuthorMatch("unknown", 0.3 if ta & tb else 0.0, ("only-common-tokens",))


def same_person(a: str, b: str) -> bool | None:
    """Editors: True/False when both are named, None when one is missing."""
    if not search_key(a) or not search_key(b):
        return None
    if _HAS_AB and hasattr(_ab, "same_person"):
        return bool(_ab.same_person(a, b))
    return match_authors(a, b).verdict == "same"


_PUB_GENERIC = set(
    _fallback_key("دار مكتبة مطبعة المطبعة مؤسسة شركة الناشر للنشر والتوزيع للطباعة والنشر النشر").split()
)


def same_publisher(a: str, b: str) -> bool | None:
    if not search_key(a) or not search_key(b):
        return None
    if _HAS_AB and hasattr(_ab, "same_publisher"):
        return bool(_ab.same_publisher(a, b))
    art = lambda w: w[2:] if w.startswith("ال") and len(w) > 3 else w  # noqa: E731
    gen = {art(w) for w in _PUB_GENERIC}
    wa = {art(w) for w in search_key(a).split()} - gen
    wb = {art(w) for w in search_key(b).split()} - gen
    if not wa or not wb:
        return search_key(a) == search_key(b)
    return wa == wb  # «دار الفكر» and «دار الفكر العربي» are two publishers


# ---- the shared work id (turath-catalog's recipe, byte for byte; independent of the text backend) ----------
_HONORIFIC = re.compile(
    r"^(?:الإمام|الامام|الحافظ|الشيخ|العلامة|العلامه|شيخ الإسلام|شيخ الاسلام|القاضي|الأستاذ|الدكتور|د)\.?\s+"
)


def _id_norm(s: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFC", s or "")
    s = _TASHKIL.sub("", s).translate(_FOLD).translate(_DIGITS)
    s = re.sub(r"[^\u0621-\u064a0-9 ]", " ", s)
    return " ".join(s.split())


def work_id(title: str, author: str) -> str:
    """«w_» + 10 hex of sha1(title_key|author_key), as turath-catalog computes its ``work_id``."""
    import hashlib
    import unicodedata

    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", title or "")
    t = re.split(r" - | ط | ت ", t)[0]
    w = _id_norm(t).split()
    if len(w) > 1 and w[0] == "كتاب":
        w = w[1:]
    a = re.split(r"[؛;]", author or "")[0].strip()
    while True:
        b = _HONORIFIC.sub("", a)
        if b == a:
            break
        a = b
    key = unicodedata.normalize("NFC", f"{' '.join(w)}|{_id_norm(a)}")
    return "w_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
