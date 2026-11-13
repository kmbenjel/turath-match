"""Title analysis: what a heritage title says about the work it names.

A title such as «فتح الباري بشرح صحيح البخاري - ت محب الدين الخطيب - ط السلفية» carries the work («فتح الباري»),
a subtitle that relates it to another work («بشرح صحيح البخاري»), and edition tails (editor, publisher) that say
nothing about the work. «مختصر …», «شرح …», «ذيل …» name *another* work built on the first, and «رواية يحيى»,
«السفر الثاني» name a recension or a part. ``analyse`` takes a title apart; ``compare_titles`` says whether two
titles name the same work, a related one, or neither, and why.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from .text import author_tokens, search_key


def tok(w: str) -> str:
    """One normalised word in its comparison form: «ابن» = «بن», «الديوان» = «شعر», the article dropped."""
    if w == "ابن":
        return "بن"
    if w in ("ديوان", "الديوان"):
        return "شعر"
    if (w.startswith("بال") or w.startswith("وال")) and len(w) > 5:
        return w[3:]
    if w.startswith("ال") and len(w) > 3 and w != "الله":
        return w[2:]
    return w


def _words(s: str) -> list[str]:
    return [
        tok(w)
        for w in search_key(s).split()
        if w not in FUNC and not (w[:1] == "و" and w[1:] in FUNC) and len(w) > 1
    ]


FUNC = set(search_key("في على من عن إلى و ما أو مع التي الذي منه منها فيه فيها").split())
FILL = {
    tok(w)
    for w in search_key(
        "إمام الإمام قاضي شيخ الشيخ حافظ الحافظ علامة العلامة إسلام كتاب رسالة شريف الشريف نبوية كريم الكريم "
        "صلى الله عليه وسلم سلم رضي عنه عنهم تعالى بن أبي أبو أبا عبد"
    ).split()
}

# a word that makes a title name another work built on the first one
RELATIONS: dict[str, str] = {}
for _rel, _ws in {
    "abridgement": "مختصر اختصار تلخيص ملخص خلاصة تهذيب تقريب",
    "commentary": "شرح",
    "gloss": "حاشية حواشي تعليق تعليقات تقريرات",
    "continuation": "ذيل تكملة تتمة صلة مستدرك استدراك متمم",
    "selection": "منتقى منتخب انتخاب مختار المختار زوائد مقتطفات صفحات",
    "versification": "نظم منظومة أرجوزة",
    "refutation": "رد نقد",
    "takhrij": "تخريج",
    "index": "فهارس فهرس",
    "study": "دراسة",
    "rearrangement": "ترتيب",
    "part": "قطعة جزء مجلس مجالس سفر",
}.items():
    for _w in search_key(_ws).split():
        RELATIONS[tok(_w)] = _rel

LEAD = {
    tok(w) for w in search_key("كتاب مسألة مسالة جزء").split()
}  # «مسألة الاحتجاج بالشافعي» = «الاحتجاج بالشافعي»
PART_INTRO = {tok(w) for w in search_key("رواية برواية السفر الجزء القسم المجلد").split()}
SIZE = {tok(w) for w in search_key("الكبرى الكبير الصغرى الصغير الوسيط الأوسط الوجيز").split()}
JOINERS = re.compile(
    r"\s(?:ويليه|ويليها|ويليهما|ومعه|ومعها|ومعهما|وبهامشه|وبهامشها|وبذيله|وبذيلها|ويذيله|ويتلوه|وتليه|وعليه)\s"
)
TAIL = re.compile(
    r"^(?:(?:ط|ت)[\s.]|ط$|ضمن|تحقيق|بتحقيق|طبعة|الطبعة|المنسوب|منسوب|جامعة|رسالة\s+(?:ماجستير|دكتوراه|دكتوراة|علمية)"
    r"|مخطوط|نشرة|ق\s*\d|\d)"
)
_THESIS = re.compile(r"رسال[ةه]\s+(?:ماجستير|دكتوراه|دكتوراة|علمي[ةه])|أطروحة|اطروحة")
_MANUSCRIPT = re.compile(r"\bمخطوط")
_PARTNO = re.compile(r"(?:^|\s)(?:الجزء|ج|المجلد|مج)\s*\d+")


def base(w: str) -> str:
    """«بشرح» -> «شرح», «وشرح» -> «شرح», «لمختصر» -> «مختصر»."""
    if w in RELATIONS:
        return w
    for p in ("و", "ب", "ل", "ف"):
        if w.startswith(p) and len(w) > 3:
            r = tok(w[1:])
            if r in RELATIONS:
                return r
    return w


def has(t: str, words: set[str]) -> bool:
    """«بعلم» counts as «علم», «لألفية» as «ألفية»: a joined particle never makes two words differ."""
    if t in words:
        return True
    if any(c + t in words for c in ("و", "ب", "ل", "لل", "بال", "وال", "ف")):
        return True
    return len(t) > 4 and t[0] in "وبلف" and (t[1:] in words or tok(t[1:]) in words)


@dataclass
class TitleForm:
    words: list[str]  # the title's words in order (function words out)

    @property
    def core(self) -> list[str]:
        return [w for w in self.words if w not in FILL] or list(self.words)

    @property
    def mandatory(self) -> set[str]:
        """the two words after «رواية», «السفر», «الجزء» … name the recension or the part"""
        out: set[str] = set()
        c = self.core
        for i, x in enumerate(c):
            if x in PART_INTRO:
                out |= set(c[i + 1 : i + 3])
        return out


@dataclass
class TitleInfo:
    raw: str
    forms: list[TitleForm] = field(default_factory=list)
    joined: list[str] = field(default_factory=list)  # «ويليه …»: other works printed in the same volume
    flags: set[str] = field(default_factory=set)
    editor_hint: str = ""
    publisher_hint: str = ""
    attribution: set[str] = field(
        default_factory=set
    )  # author name tokens the title itself carries («… للبيهقي»)


def _strip_attribution(words: list[str], names: dict[str, str]) -> tuple[list[str], set[str]]:
    """«شعب الإيمان للبيهقي» -> («شعب الإيمان», {البيهقي}) when «البيهقي» is the author's name."""
    if len(words) < 2 or not names:
        return words, set()
    for i in range(len(words) - 1, 0, -1):
        w = words[i]
        first = w[2:] if w.startswith("لل") else w[1:] if w.startswith("ل") else None
        if first is None:
            continue
        tail = [tok(first), *words[i + 1 :]]
        if any(x in names for x in tail) and all(x in names or x in FILL or x == "بن" for x in tail):
            return words[:i], {names[x] for x in tail if x in names}
        break
    return words, set()


def analyse(title: str, author: str = "") -> TitleInfo:
    info = TitleInfo(raw=title or "")
    t = title or ""
    if _THESIS.search(t):
        info.flags.add("thesis")
    if _MANUSCRIPT.search(t):
        info.flags.add("manuscript")
    if _PARTNO.search(t):
        info.flags.add("part")
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t)
    names = {tok(a): a for a in author_tokens(author)}
    parts = [p.strip() for p in re.split(r"\s+[-–]\s+", t) if p.strip()]
    head = parts[0] if parts else ""
    for p in parts[1:]:
        m = re.match(r"^ت[\s.]+(.+)$", p)
        if m:
            info.editor_hint = info.editor_hint or m.group(1).strip()
            continue
        m = re.match(r"^ط[\s.]+(.+)$", p)
        if m:
            info.publisher_hint = info.publisher_hint or m.group(1).strip()
            continue
        if TAIL.match(p):
            continue
        ws = [w for w in _words(p) if w not in FILL and not w.isdigit()]
        if not ws or all(w in names for w in ws):  # «- الضياء المقدسي»: the author, not the title
            continue
        head += " " + p  # «- رواية أبي مصعب», «- السفر الثاني»: part of what the title names
    for alt in re.split(r"=|\s(?:المسمى|المسماة|المسمي|المسماه|المعروف ب|المشهور ب)\s", head):
        pieces = JOINERS.split(" " + alt + " ")
        main = pieces[0]
        info.joined.extend(x.strip() for x in pieces[1:] if x.strip())
        ws = _words(main)
        while len(ws) > 2 and ws[0] in LEAD:  # «جزء فيه حديث لوين» = «حديث لوين», «مسألة الاحتجاج …»
            ws = ws[1:]
        if len(ws) > 1 and ws[0] == "كتاب":
            ws = ws[1:]
        ws, attr = _strip_attribution(ws, names)
        info.attribution |= attr
        if ws:
            info.forms.append(TitleForm(ws))
    return info


@dataclass
class TitleComparison:
    kind: str  # exact | head | fuzzy | related | conflict | none
    score: float
    detail: str
    relation: str | None = None
    derived_side: str | None = None  # "left" | "right"


def _is_head(short: list[str], long: list[str]) -> bool:
    return len(short) <= len(long) and all(
        has(s, {lw}) or has(lw, {s}) for s, lw in zip(short, long, strict=False)
    )


def _compare_forms(
    a: TitleForm, b: TitleForm, names: frozenset[str] = frozenset(), shown: str = ""
) -> TitleComparison:
    ca, cb = a.core, b.core
    # «مقدمة ابن خلدون» = «المقدمة» by Ibn Khaldun: words that only name the author do not tell works apart
    if names:
        ra, rb = [x for x in ca if x not in names], [x for x in cb if x not in names]
        if ra and rb and (len(ra) < len(ca) or len(rb) < len(cb)):
            ca, cb = ra, rb
    if (
        "".join(ca) == "".join(cb) and ca != cb
    ):  # «ومايتبعها» / «وما يتبعها»: the same letters, spaced otherwise
        ca = cb
    sa, sb = set(ca), set(cb)
    miss_b = [x for x in ca if not has(x, sb)]  # in a, not in b
    miss_a = [x for x in cb if not has(x, sa)]
    joined = shown or f"«{' '.join(ca)}» / «{' '.join(cb)}»"
    ma, mb = a.mandatory, b.mandatory
    rest_a = [x for x in ca if x not in ma and x not in PART_INTRO]
    rest_b = [x for x in cb if x not in mb and x not in PART_INTRO]
    short_rest = min(rest_a, rest_b, key=len)
    long_rest = set(rest_b if short_rest is rest_a else rest_a)
    agree_rest = bool(short_rest) and sum(1 for x in short_rest if has(x, long_rest)) >= max(
        1, len(short_rest) - 1
    )
    if (ma or mb) and (ma - sb or mb - sa) and agree_rest:  # the same title, another recension or part
        side = "left" if ma - sb and not (mb - sa) else "right" if mb - sa and not (ma - sb) else None
        rel = "recension" if any(base(x) in ("روايه", "بروايه") for x in ca + cb) else "part"
        if side is None:
            return TitleComparison("conflict", 0.0, f"different {rel}: {joined}", rel)
        return TitleComparison("related", 0.6, f"one names a {rel} the other does not: {joined}", rel, side)
    za, zb = sa & SIZE, sb & SIZE
    if za and zb and za != zb:
        return TitleComparison(
            "conflict", 0.0, f"different size words ({'/'.join(za)} vs {'/'.join(zb)}): {joined}"
        )
    if not miss_a and not miss_b:
        if len(ca) == 1:
            return TitleComparison("exact", 0.9, f"same one-word title {joined}")
        return TitleComparison("exact", 1.0, f"same title words {joined}")
    short, long_, side = (ca, cb, "right") if len(ca) <= len(cb) else (cb, ca, "left")
    extra = miss_a if side == "right" else miss_b  # words only the longer title has
    rels = [RELATIONS[base(x)] for x in extra if base(x) in RELATIONS]
    if _is_head(short, long_) and short:
        # the shorter title is the start of the longer: a subtitle, unless the longer one *starts* differently
        if len(short) == 1:
            return TitleComparison("head", 0.55, f"one-word title is the start of the other {joined}")
        cap = 0.7 if (za ^ zb) else 0.85
        return TitleComparison("head", cap, f"one title is the start of the other (a subtitle) {joined}")
    if not rels and len(short) >= 3 and short[0] == long_[0] and all(has(x, set(long_)) for x in short):
        # every word of the shorter title is in the longer one, in a title that starts alike: a fuller title
        return TitleComparison("head", 0.85, f"the longer title holds every word of the shorter {joined}")
    if rels:
        covered = [x for x in short if has(x, set(long_)) or any(has(y, {x}) for y in long_)]
        if len(covered) >= max(1, len(short) - (1 if len(short) >= 4 else 0)):
            words = "/".join(e for e in extra if base(e) in RELATIONS)
            return TitleComparison(
                "related",
                0.7,
                f"«{words}» makes it {'an' if rels[0][0] in 'aeiou' else 'a'} {rels[0]} {joined}",
                rels[0],
                side,
            )
    slack = max(
        1, min(len(ca), len(cb)) // 4
    )  # long titles: one word in four may be spelt or cut differently
    if (
        len(ca) >= 3
        and len(cb) >= 3
        and len(miss_a) <= slack
        and len(miss_b) <= slack
        and ca[0] == cb[0]
        and (slack == 1 or ca[1] == cb[1])
    ):
        if any(base(x) in RELATIONS for x in miss_a + miss_b):
            return TitleComparison("none", 0.3, f"titles differ by a relation word {joined}")
        return TitleComparison("fuzzy", 0.7, f"titles differ by one word {joined}")
    shared = len(sa & sb)
    return TitleComparison("none", shared / max(len(sa), len(sb)), f"different titles {joined}")


ORDER = {"exact": 5, "head": 4, "fuzzy": 3, "related": 2, "conflict": 1, "none": 0}


def compare_titles(a: TitleInfo, b: TitleInfo, names: Iterable[str] = ()) -> TitleComparison:
    """The best reading over every alternative title («=») of both sides. ``names``: the author's name words
    (comparison form), which a title may carry («تفسير الطبري») without naming another work."""
    best = TitleComparison("none", 0.0, "no title words")
    nm = frozenset(names)
    shown = f"«{a.raw.strip()}» / «{b.raw.strip()}»"
    veto = None
    for fa in a.forms:
        for fb in b.forms:
            c = _compare_forms(fa, fb, nm, shown)
            if c.kind == "conflict":
                veto = veto or c
            if (ORDER[c.kind], c.score) > (ORDER[best.kind], best.score):
                best = c
    if veto is not None and best.kind in ("exact", "head", "fuzzy"):
        # «مسائل أحمد رواية عبد الله = مسائل أحمد» / «مسائل أحمد رواية ابن هانئ = …»: a generic alternative title
        # never overrides the recension, part or size one of the titles names
        return veto
    za = {w for f in a.forms for w in f.core} & SIZE
    zb = {w for f in b.forms for w in f.core} & SIZE
    if best.kind in ("exact", "head") and bool(za) != bool(zb):
        # «كتاب السنن الكبرى = كتاب السنن» / «سنن»: one record says which of the author's Sunan it is
        best = TitleComparison(
            best.kind, min(best.score, 0.7), best.detail + f"; only one says «{'/'.join(za | zb)}»"
        )
    return best


def core_tokens(title: str) -> list[str]:
    """The words an index should use to find candidates for this title."""
    info = analyse(title)
    out: list[str] = []
    for f in info.forms:
        out.extend(f.core)
    return out
