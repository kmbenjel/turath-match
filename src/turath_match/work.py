"""Work-level matching: do two records name the same work?

A work is the same when the titles agree *and* the authors agree. A common name never carries a match on its
own (arabic-bib's ``match_authors`` refuses «محمد», «الدمشقي», «شمس الدين» alone). An abridgement, a
commentary, a selection, a continuation or another recension is a *related* work, never the work itself. When
the title agrees but nothing says who wrote one side, the pair is *uncertain* and goes to the review list.
"""

from __future__ import annotations

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
from .text import author_tokens, match_authors
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


def _author_line(r: Record) -> str:
    return r.author + (f" ت {r.death}" if r.death and str(r.death) not in r.author else "")


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
    if a.death and b.death and abs(a.death - b.death) > 2:
        am_verdict, am_score, reasons = "different", 0.0, (f"death-conflict:{a.death}!={b.death}",)
    else:
        am = match_authors(_author_line(a), _author_line(b))
        am_verdict, am_score, reasons = am.verdict, am.score, am.reasons
        if am_verdict == "unknown":
            for own, other, side in ((ta, b, "left"), (tb, a, "right")):
                if own.attribution and other.author:
                    m2 = match_authors(" ".join(own.attribution), other.author)
                    if m2.verdict == "same":
                        am_verdict, am_score = "same", 0.75
                        reasons = (f"{side} title names the author: {' '.join(sorted(own.attribution))}",)
    if (
        am_verdict == "unknown"
        and a.death
        and b.death
        and abs(a.death - b.death) <= 1
        and author_tokens(a.author) & author_tokens(b.author)
    ):
        # «الشافعي» alone is a madhhab nisba shared by thousands; with the same death year it is one man
        am_verdict, am_score = "same", 0.75
        reasons = (*reasons, f"same death year {a.death} and a shared name")
    if a.death and b.death and am_verdict == "same" and abs(a.death - b.death) <= 2:
        ev.append(Evidence("death", f"death years agree: {a.death} / {b.death} AH", 0.2))
    aw = {"same": am_score, "different": -1.0, "unknown": 0.0}[am_verdict]
    ev.append(
        Evidence(
            "author", f"{am_verdict}: «{a.author or '?'}» / «{b.author or '?'}» ({', '.join(reasons)})", aw
        )
    )

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
        return Match(a, b, "work", SAME, score, method, ev)
    if am_verdict == "different":
        ev.append(Evidence("author", "same title by another author: another work", -1.0))
        return Match(a, b, "work", DIFFERENT, 0.9 if tc.kind == "exact" else 0.85, method, ev)
    n = min(len(f.core) for f in (ta.forms[:1] + tb.forms[:1])) if ta.forms and tb.forms else 0
    score = _UNKNOWN_SCORE.get(key, 0.4) - (0.1 if tc.kind == "exact" and n == 2 else 0.0)
    why = (
        "an author is missing"
        if not (a.author and b.author)
        else "the authors are not shown to be one person nor two"
    )
    ev.append(Evidence("author", f"{why}: the title alone cannot prove the work", 0.0))
    return Match(a, b, "work", UNCERTAIN, score, method, ev)
