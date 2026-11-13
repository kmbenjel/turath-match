"""Work-level matching: do two records name the same work?

A work is the same when the titles agree *and* the authors agree. A common name never carries a match on its
own (arabic-bib's ``match_authors`` refuses «محمد», «الدمشقي», «شمس الدين» alone). An abridgement, a
commentary, a selection, a continuation or another recension is a *related* work, never the work itself. When
the title agrees but nothing says who wrote one side, the pair is *uncertain* and goes to the review list.
"""

from __future__ import annotations

import re

from .models import (
    DIFFERENT,
    EXACT_TITLE_AUTHOR,
    FUZZY_TITLE_AUTHOR,
    RELATED,
    SAME,
    UNCERTAIN,
    Evidence,
    Match,
    Record,
)
from .text import author_tokens, match_authors, parse_death, search_key
from .titles import analyse, compare_titles, tok

# score of «same work» by how the titles agree, when the authors agree
_SAME_SCORE = {
    ("exact", 1.0): 0.97,
    ("exact", 0.9): 0.92,
    ("head", 0.85): 0.9,
    ("head", 0.7): 0.8,
    ("head", 0.55): 0.7,
    ("fuzzy", 0.7): 0.78,
}
# score of «uncertain» when one author is unknown
_UNKNOWN_SCORE = {
    ("exact", 1.0): 0.7,
    ("exact", 0.9): 0.45,
    ("head", 0.85): 0.55,
    ("head", 0.7): 0.5,
    ("head", 0.55): 0.35,
    ("fuzzy", 0.7): 0.5,
}


DEATH_SLACK = 12  # years: beyond this, two death dates are two people
_DEATH_NOTE = re.compile(
    r"[(\[]?\s*(?:ت|المتوفى|المتوفي|توفي)\s*[:.]?\s*[\d٠-٩]{1,4}\s*(?:هـ|ه)?\s*[)\]]?|[(\[][^)\]]*\d[^)\]]*[)\]]"
)


def strip_death(name: str) -> str:
    """The name without its death note: «… (المتوفى: 1345هـ)», «… ت 728 هـ», «… (28 - 110 ه)»."""
    return " ".join(_DEATH_NOTE.sub(" ", name or "").split())


_PARTICLES = set(search_key("بن ابن بنت أبو أبي أبا أم عبد ال").split())


def _name_words(name: str) -> set[str]:
    """Every word of a name but the particles: «محمد» counts here (it is evidence of nothing, but not of two people)."""
    return {tok(w) for w in search_key(strip_death(name)).split() if w not in _PARTICLES and len(w) > 1}


_ORDER = {"same": 2, "unknown": 1, "different": 0}


def _forms(author: str) -> list[str]:
    """«الجاحظ ؛ أبو عثمان عمرو بن بحر» -> the name forms a catalog gives for one person (at most three)."""
    out = [x.strip() for x in re.split(r"[؛;]", author or "") if x.strip()]
    return out[:3] or [""]


def agree_authors(a: str, b: str) -> tuple[str, float, tuple[str, ...]]:
    """The best agreement over every pair of name forms: one form that proves the person is enough."""
    best: tuple[str, float, tuple[str, ...]] | None = None
    for fa in _forms(a):
        for fb in _forms(b):
            m = match_authors(fa, fb)
            cand = (m.verdict, m.score, tuple(m.reasons))
            if best is None or (_ORDER[cand[0]], cand[1]) > (_ORDER[best[0]], best[1]):
                best = cand
    assert best is not None
    if best[0] == "unknown" and (len(_forms(a)) > 1 or len(_forms(b)) > 1):
        whole = match_authors(" ".join(_forms(a)), " ".join(_forms(b)))
        if whole.verdict == "same":
            best = (whole.verdict, whole.score, tuple(whole.reasons))
    return best


GENERIC_ADJ = {
    tok(w)
    for w in search_key(
        "الأدبية الكاملة المختارة الفلسفية الكلامية الفقهية السياسية الصغرى الكبرى المجموعة"
    ).split()
}
COLLECTION = {
    tok(w) for w in search_key("رسائل الرسائل مجموع مجموعة مؤلفات الأعمال أعمال آثار موسوعة ديوان").split()
}


def match_work(a: Record, b: Record) -> Match:
    """Compare two records at the work level and return the verdict with its evidence."""
    ev: list[Evidence] = []
    if a.work_uri and b.work_uri:
        if a.work_uri == b.work_uri:
            ev.append(Evidence("uri", f"same work identifier {a.work_uri}", 1.0))
            return Match(a, b, "work", SAME, 0.99, EXACT_TITLE_AUTHOR, ev)
        ev.append(Evidence("uri", f"different work identifiers {a.work_uri} / {b.work_uri}", -0.3))

    both = f"{a.author} {b.author}"
    ta, tb = analyse(a.title, both), analyse(b.title, both)
    names = (
        {tok(x) for x in author_tokens(a.author) & author_tokens(b.author)}
        if a.author and b.author
        else set()
    )
    names |= {tok(x) for x in ta.attribution | tb.attribution}
    tc = compare_titles(ta, tb, names)
    tw = tc.score if tc.kind in ("exact", "head", "fuzzy") else -1.0 if tc.kind == "conflict" else 0.0
    ev.append(Evidence("title", f"{tc.kind}: {tc.detail}", tw))

    # who wrote it: the author fields, the death years, and an author the title itself names («… للبيهقي»)
    da, db = a.death or parse_death(a.author), b.death or parse_death(b.author)
    death_doubt = False
    am_verdict, am_score, reasons = agree_authors(strip_death(a.author), strip_death(b.author))
    if am_verdict == "unknown":
        for own, other, side in ((ta, b, "left"), (tb, a, "right")):
            if own.attribution and other.author:
                m2 = match_authors(" ".join(own.attribution), strip_death(other.author))
                if m2.verdict == "same":
                    am_verdict, am_score = "same", 0.75
                    reasons = (f"{side} title names the author: {' '.join(sorted(own.attribution))}",)
    if da and db:
        gap = abs(da - db)
        if gap <= 2:
            if am_verdict == "unknown" and author_tokens(a.author) & author_tokens(b.author) and gap <= 1:
                # «الشافعي» alone is a madhhab nisba shared by thousands; with the same death year it is one man
                am_verdict, am_score = "same", 0.75
                reasons = (*reasons, f"same death year {da} and a shared name")
            if am_verdict == "same":
                ev.append(Evidence("death", f"death years agree: {da} / {db} AH", 0.2))
        elif gap <= DEATH_SLACK and am_verdict == "same" and am_score >= 0.9:
            # catalogs disagree on uncertain death dates (أبو الفرج الأصبهاني: 356 or 362); the names decide
            ev.append(
                Evidence("death", f"death years differ by {gap} ({da} / {db} AH); the full names agree", -0.3)
            )
            am_score, death_doubt = 0.7, True
        else:
            am_verdict, am_score = "different", 0.0
            reasons = (*reasons, f"death-conflict:{da}!={db}")
    aw = {"same": am_score, "different": -1.0, "unknown": 0.0}[am_verdict]
    ev.append(
        Evidence(
            "author", f"{am_verdict}: «{a.author or '?'}» / «{b.author or '?'}» ({', '.join(reasons)})", aw
        )
    )

    if tc.kind == "related" and tc.relation not in ("part", "recension") and am_verdict != "same":
        # «المنتخب من كتاب الزهد والرقائق» is not built on every «الزهد»: a one-word base needs its author named
        base_rec, der = (b, ta) if tc.derived_side == "left" else (a, tb)
        base_words = min((len(f.core) for f in (tb if tc.derived_side == "left" else ta).forms), default=0)
        own = {tok(x) for x in author_tokens(base_rec.author)}
        if base_words <= 1 and not own & {w for f in der.forms for w in f.words}:
            ev.append(
                Evidence(
                    "derivation", "a one-word title, and the derived title does not name its author", -0.5
                )
            )
            return Match(a, b, "work", DIFFERENT, 0.6, FUZZY_TITLE_AUTHOR, ev)
    if tc.kind == "related":
        ev.append(
            Evidence("derivation", f"{tc.relation}: the {tc.derived_side} record is built on the other", -1.0)
        )
        return Match(a, b, "work", RELATED, tc.score, FUZZY_TITLE_AUTHOR, ev, tc.relation, tc.derived_side)
    if tc.kind == "conflict":
        rel = tc.relation
        return Match(a, b, "work", RELATED if rel else DIFFERENT, 0.8, FUZZY_TITLE_AUTHOR, ev, rel)
    if tc.kind == "none":
        return Match(a, b, "work", DIFFERENT, max(0.5, 1 - tc.score), FUZZY_TITLE_AUTHOR, ev)

    method = EXACT_TITLE_AUTHOR if tc.kind == "exact" else FUZZY_TITLE_AUTHOR
    key = (tc.kind, tc.score)
    if am_verdict == "same":
        score = _SAME_SCORE.get(key, 0.6) - (0.05 if am_score < 0.8 else 0.0)
        if death_doubt:
            score = min(score, 0.8)  # two death years: a person confirms
        core = [w for f in ta.forms[:1] for w in f.core if w not in names]
        if (
            core
            and core[0] in COLLECTION
            and core[0] != "شعر"
            and all(w in COLLECTION | GENERIC_ADJ for w in core[1:])
        ):
            # «رسائل الجاحظ», «مجموع الفتاوى»: a collection's name, which many single works also carry
            ev.append(Evidence("title", "a collection title by this author: it does not name one work", -0.3))
            return Match(a, b, "work", UNCERTAIN, min(score, 0.6), method, ev)
        return Match(a, b, "work", SAME, score, method, ev)
    if am_verdict == "different":
        ev.append(Evidence("author", "same title by another author: another work", -1.0))
        return Match(a, b, "work", DIFFERENT, 0.9 if tc.kind == "exact" else 0.85, method, ev)
    n = min(len(f.core) for f in (ta.forms[:1] + tb.forms[:1])) if ta.forms and tb.forms else 0
    score = _UNKNOWN_SCORE.get(key, 0.4) - (0.1 if tc.kind == "exact" and n == 2 else 0.0)
    if a.author and b.author and not _name_words(a.author) & _name_words(b.author):
        score -= 0.15  # two named authors who share no name at all: probably two people
    why = (
        "an author is missing"
        if not (a.author and b.author)
        else "the authors are not shown to be one person nor two"
    )
    ev.append(Evidence("author", f"{why}: the title alone cannot prove the work", 0.0))
    return Match(a, b, "work", UNCERTAIN, score, method, ev)
