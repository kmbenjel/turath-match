"""Edition-level matching: given two records of one work, are they the same edition?

Title and author never prove an edition. A file of the record's exact size (or the same hash) does; otherwise
the editor, the publisher and the number of volumes must agree, and any of them disagreeing makes it another
edition. A thesis, a manuscript or a typed transcription is not the printed edition it is about.
"""

from __future__ import annotations

import re

from .models import DIFFERENT, EXACT_SIZE, FUZZY_TITLE_AUTHOR, HASH, SAME, UNCERTAIN, Evidence, Match, Record
from .text import same_person, same_publisher, to_ascii_digits
from .titles import analyse

MIN_PROOF_SIZE = 100_000  # bytes: below this an equal size is a coincidence too often to prove anything


def _years(s: str) -> set[int]:
    return {int(y) for y in re.findall(r"\b(\d{3,4})\b", to_ascii_digits(s or ""))}


def _hint(r: Record) -> tuple[str, str]:
    info = analyse(r.title, r.author)
    return (r.editor or info.editor_hint, r.publisher or info.publisher_hint)


def _flags(r: Record) -> set[str]:
    return set(r.flags) | analyse(r.title).flags


def file_evidence(a: Record, b: Record) -> tuple[str | None, list[Evidence], int, int]:
    """(method, evidence, matched files, files on b) for byte-level agreement between the two file lists."""
    ev: list[Evidence] = []
    hb = {f.md5: f for f in b.files if f.md5} | {f.sha1: f for f in b.files if f.sha1}
    hashed = [f for f in a.files if (f.md5 and f.md5 in hb) or (f.sha1 and f.sha1 in hb)]
    sizes_b = {f.size: f for f in b.files if f.size and f.size >= MIN_PROOF_SIZE}
    sized = [f for f in a.files if f.size and f.size in sizes_b]
    nb = len([f for f in b.files if f.size]) or len(b.files)
    if hashed:
        ev.append(Evidence("hash", f"{len(hashed)} file(s) with the same checksum", 1.0))
        return HASH, ev, len(hashed), nb
    if sized:
        f = sized[0]
        ev.append(
            Evidence(
                "size",
                f"{len(sized)} of {nb} file(s) of exactly the same size "
                f"(e.g. {f.size:,} bytes: {f.name} = {sizes_b[f.size].name})",
                0.9,
            )
        )
        return EXACT_SIZE, ev, len(sized), nb
    return None, ev, 0, nb


def match_edition(a: Record, b: Record) -> Match:
    """Compare two records of the same work at the edition level."""
    method, ev, n_same, nb = file_evidence(a, b)
    if method:
        partial = 0 < n_same < nb and nb > 1
        if partial:
            ev.append(Evidence("volumes", f"{n_same} of {nb} volumes present", 0.0))
        m = Match(a, b, "edition", SAME, 0.99 if method == HASH else 0.95, method, ev)
        if partial:
            m.relation, m.direction = "part", "left"
        return m

    pos, neg = 0.0, 0.0
    ea, pa = _hint(a)
    eb, pb = _hint(b)
    s = same_person(ea, eb)
    if s is True:
        ev.append(Evidence("editor", f"same editor: «{ea}» / «{eb}»", 0.4))
        pos += 0.4
    elif s is False:
        ev.append(Evidence("editor", f"different editors: «{ea}» / «{eb}»", -1.0))
        neg += 1.0
    p = same_publisher(pa, pb)
    if p is True:
        ev.append(Evidence("publisher", f"same publisher: «{pa}» / «{pb}»", 0.3))
        pos += 0.3
    elif p is False:
        ev.append(Evidence("publisher", f"different publishers: «{pa}» / «{pb}»", -0.6))
        neg += 0.6
    if a.volumes and b.volumes:
        if a.volumes == b.volumes:
            ev.append(Evidence("volumes", f"same number of volumes: {a.volumes}", 0.2))
            pos += 0.2
        else:
            ev.append(Evidence("volumes", f"volumes differ: {a.volumes} / {b.volumes}", -0.5))
            neg += 0.5
    ya, yb = _years(a.year), _years(b.year)
    if ya and yb:
        if ya & yb:
            ev.append(Evidence("year", f"same year: {sorted(ya & yb)[0]}", 0.1))
            pos += 0.1
        else:
            ev.append(Evidence("year", f"years differ: {a.year} / {b.year} (another printing)", -0.2))
            neg += 0.2
    fa, fb = _flags(a), _flags(b)
    for flag in ("thesis", "manuscript", "typed"):
        if (flag in fa) != (flag in fb):
            ev.append(Evidence("flag", f"only one side is a {flag}", -0.6))
            neg += 0.6

    if neg >= 0.5:
        return Match(a, b, "edition", DIFFERENT, min(0.95, 0.5 + neg / 2), FUZZY_TITLE_AUTHOR, ev)
    if s is True and (p is True or (a.volumes and a.volumes == b.volumes)):
        return Match(a, b, "edition", SAME, 0.88 if neg == 0 else 0.75, FUZZY_TITLE_AUTHOR, ev)
    asked = [x for x in (eb, pb, b.volumes, b.year) if x]
    if neg == 0 and s is True and len(asked) == 1:
        # the right-hand record (a wish list, a catalog entry) names only its editor, and that editor agrees
        ev.append(Evidence("edition", "the editor is all the other record says about its edition", 0.0))
        return Match(a, b, "edition", SAME, 0.85, FUZZY_TITLE_AUTHOR, ev)
    if pos >= 0.4:
        return Match(a, b, "edition", SAME, 0.7, FUZZY_TITLE_AUTHOR, ev)
    if not ev:
        ev.append(Evidence("edition", "neither side says which edition it is", 0.0))
    return Match(a, b, "edition", UNCERTAIN, 0.3 + pos / 2, FUZZY_TITLE_AUTHOR, ev)
