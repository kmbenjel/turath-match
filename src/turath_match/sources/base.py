"""The adapter contract and the ``scheme:location`` registry the CLI uses."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..models import Record


@runtime_checkable
class Source(Protocol):
    """Anything that yields records. ``scheme`` prefixes every record id (``waqfeya:66a8…``)."""

    scheme: str

    def records(self) -> Iterator[Record]: ...


class ListSource:
    """Records already in memory (tests, the Python API)."""

    def __init__(self, scheme: str, records: Iterable[Record]):
        self.scheme = scheme
        self._records = list(records)

    def records(self) -> Iterator[Record]:
        return iter(self._records)


class JsonlSource:
    """Records saved by ``turath-match export`` or ``save_jsonl`` (one ``Record.to_dict`` per line)."""

    def __init__(self, path: str | Path, scheme: str | None = None):
        self.path = Path(path)
        self.scheme = scheme or "jsonl"

    def records(self) -> Iterator[Record]:
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = Record.from_dict(json.loads(line))
                    self.scheme = r.scheme
                    yield r


def save_jsonl(records: Iterable[Record], path: str | Path) -> int:
    n = 0
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
            n += 1
    return n


_REGISTRY: dict[str, Callable[[str], Source]] = {}


def register(scheme: str) -> Callable[[Callable[[str], Source]], Callable[[str], Source]]:
    def deco(fn: Callable[[str], Source]) -> Callable[[str], Source]:
        _REGISTRY[scheme] = fn
        return fn

    return deco


def schemes() -> list[str]:
    return sorted(_REGISTRY)


def open_source(spec: str) -> Source:
    """``csv:wishlist.csv``, ``folder:~/Books``, ``openiti:meta.tsv``, ``shamela:~/shamela``, ``waqfeya:dump.jsonl``,
    ``archive:items.jsonl``, ``jsonl:records.jsonl``. A bare path is guessed from its extension."""
    scheme, sep, loc = spec.partition(":")
    if not sep or scheme not in _REGISTRY or len(scheme) == 1:  # «C:\…» or a bare path
        p = Path(spec).expanduser()
        if p.is_dir():
            scheme, loc = "folder", spec
        elif p.suffix.lower() in (".csv", ".tsv"):
            scheme, loc = "csv", spec
        elif p.suffix.lower() == ".jsonl":
            scheme, loc = "jsonl", spec
        else:
            raise ValueError(
                f"cannot tell what kind of source «{spec}» is; write it as scheme:path, "
                f"with scheme one of {', '.join(schemes())}"
            )
    return _REGISTRY[scheme](str(Path(loc).expanduser()))


@register("jsonl")
def _jsonl(loc: str) -> Source:
    return JsonlSource(loc)
