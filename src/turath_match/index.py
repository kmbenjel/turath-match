"""Candidate generation: which records are worth comparing at all.

Comparing every record with every other is quadratic; a heritage catalog has tens of thousands of records.
The index maps each title word (in its comparison form) to the records whose titles hold it. A record's
candidates share its first title word, or at least two title words; words that occur in a large share of the
catalog («كتاب», «شرح», «رسالة») only count together with a rarer one, or together with the author: a title made
of common words («تاريخ الإسلام», «الأمالي», «السنة») finds the records that share one of its words and a
distinctive word of its author's name.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .models import Record
from .text import author_tokens
from .titles import FILL, analyse, base, tok


def _keys(words: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for w in words:
        out.add(w)
        b = base(w)
        if b != w:
            out.add(b)
        if len(w) > 4 and w[0] in "وبلف":
            out.add(tok(w[1:]))
    return out


def title_words(r: Record) -> tuple[list[str], set[str]]:
    """(first core word of each alternative title, every index key of the title)"""
    info = analyse(r.title, r.author)
    firsts, keys = [], set()
    for f in info.forms:
        core = [w for w in f.words if w not in FILL] or f.words
        if core:
            firsts.append(core[0])
        keys |= _keys(core)
    return firsts, keys


class TokenIndex:
    def __init__(self, records: Iterable[Record], common_share: float = 0.05):
        self.records: list[Record] = list(records)
        self.post: dict[str, set[int]] = defaultdict(set)
        self.first: dict[str, set[int]] = defaultdict(set)
        self.by_author: dict[str, set[int]] = defaultdict(set)
        for i, r in enumerate(self.records):
            firsts, keys = title_words(r)
            for k in keys:
                self.post[k].add(i)
            for f in firsts:
                self.first[f].add(i)
            for a in author_tokens(r.author):
                self.by_author[a].add(i)
        self.common = max(50, int(len(self.records) * common_share))

    def candidates(self, r: Record, limit: int = 200) -> list[Record]:
        firsts, keys = title_words(r)
        hits: dict[int, int] = defaultdict(int)
        rare = [k for k in keys if 0 < len(self.post.get(k, ())) <= self.common]
        for k in rare:
            for i in self.post[k]:
                hits[i] += 1
        need = 2 if len(keys) >= 2 else 1
        chosen = {i for i, n in hits.items() if n >= need}
        for f in firsts:
            ids = self.first.get(f, set())
            chosen |= ids & set(hits) if len(ids) > self.common else ids
        # the same author (a distinctive word of the name) and one title word in common, however common the word
        same_author: set[int] = set()
        for a in author_tokens(r.author):
            ids = self.by_author.get(a) or set()
            if 0 < len(ids) <= self.common:
                same_author |= ids
        by_name: set[int] = set()
        if same_author:
            for k in keys:
                by_name |= self.post.get(k, set()) & same_author
            chosen |= by_name
        if (
            not chosen and len(keys) == 1
        ):  # a one-word title made of a common word: compare with its namesakes
            chosen = set(list(self.first.get(next(iter(keys)), set()))[:limit])
        ranked = sorted(chosen, key=lambda i: (-hits.get(i, 0) - (2 if i in by_name else 0), i))[:limit]
        return [self.records[i] for i in ranked]
